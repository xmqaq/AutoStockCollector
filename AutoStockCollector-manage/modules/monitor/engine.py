"""
AI 监控引擎 — 协调各分析器，并行分析股票池，生成短/长期信号
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from core.storage.mongo_storage import StockInfoStorage, WatchlistStorage
from utils.logger import get_logger

from .storage import MonitorStorage
from .backtest import SignalBacktest
from .analyzers import (
    FundFlowAnalyzer,
    PricePredictionAnalyzer,
    ResearchReportAnalyzer,
    TechnicalAnalyzer,
    FundamentalAnalyzer,
    CompositeAnalyzer,
)

logger = get_logger(__name__)


class MonitorEngine:
    """AI 实时监控主引擎"""

    def __init__(self):
        self._storage = MonitorStorage()
        self._stock_info = StockInfoStorage()
        self._fund_flow = FundFlowAnalyzer()
        self._research = ResearchReportAnalyzer()
        self._technical = TechnicalAnalyzer()
        self._fundamental = FundamentalAnalyzer()
        self._composite = CompositeAnalyzer()
        self._price_prediction = PricePredictionAnalyzer()
        self._backtest = SignalBacktest()
        self._watchlist = WatchlistStorage()
        self._db = DatabaseConfig.get_database()

    def refresh_all(self) -> Dict[str, Any]:
        stocks = self._collect_stocks()
        if not stocks:
            logger.warning("No stocks to analyze")
            return {"success": True, "analyzed": 0, "total": 0}

        results = []
        errors = 0

        with ThreadPoolExecutor(max_workers=8) as pool:
            fut_map = {
                pool.submit(self._analyze_one, s): s for s in stocks
            }
            for fut in as_completed(fut_map):
                s = fut_map[fut]
                try:
                    result = fut.result()
                    if result:
                        results.append(result)
                        self._storage.upsert_signal(s["code"], result)
                        self._storage.save_history(s["code"], result)
                except Exception as e:
                    errors += 1
                    logger.error(f"Analyze {s.get('code')} failed: {e}")

        # 后台回测
        try:
            self._backtest.store_accuracy_all()
        except Exception as e:
            logger.error(f"Backtest failed: {e}")

        logger.info(f"Refreshed {len(results)} stocks ({errors} errors)")
        return {
            "success": True,
            "analyzed": len(results),
            "total": len(stocks),
            "errors": errors,
        }

    def refresh_stock(self, code: str) -> Optional[Dict[str, Any]]:
        info = self._stock_info.get_by_code(code) or {"code": code, "A股简称": ""}
        s = {
            "code": code,
            "name": info.get("A股简称", info.get("name", "")),
            "type": "manual",
        }
        result = self._analyze_one(s)
        if result:
            self._storage.upsert_signal(code, result)
            self._storage.save_history(code, result)
        return result

    def _collect_stocks(self) -> List[Dict[str, Any]]:
        """收集需要分析的股票: 持仓(paper_account) + 自选(watchlist)"""
        seen = set()
        stocks = []

        # 持仓: paper_account 集合
        try:
            accounts = list(self._db["paper_account"].find())
            for acct in accounts:
                holdings = acct.get("holdings", acct.get("positions", []))
                for h in holdings:
                    code = h.get("code", "")
                    if code and code not in seen:
                        seen.add(code)
                        stocks.append({
                            "code": code,
                            "name": h.get("name", ""),
                            "type": "持仓",
                        })
        except Exception as e:
            logger.error(f"Get positions failed: {e}")

        # 自选: watchlist 集合 (不分用户)
        try:
            items = self._watchlist.find_many({"enabled": True})
            for item in items:
                code = item.get("code", "")
                if code and code not in seen:
                    seen.add(code)
                    stocks.append({
                        "code": code,
                        "name": item.get("name", item.get("A股简称", "")),
                        "type": "自选",
                    })
        except Exception as e:
            logger.error(f"Get watchlist failed: {e}")

        logger.info(f"Collected {len(stocks)} stocks to analyze ({len(seen)} unique)")
        return stocks

    def _analyze_one(self, stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        code = stock["code"]
        name = stock.get("name", "")
        stock_type = stock.get("type", "自选")

        try:
            fund_flow = self._fund_flow.analyze(code)
            research = self._research.analyze(code, name)
            technical = self._technical.analyze(code)
            fundamental = self._fundamental.analyze(code)
            price_prediction = self._price_prediction.analyze(code)
            composite = self._composite.composite(fund_flow, research, technical, fundamental)
        except Exception as e:
            logger.error(f"Analyze {code} failed: {e}")
            return None

        info = self._stock_info.get_by_code(code) or {}

        current_price = technical.get("current_price", 0)

        result = {
            "code": code,
            "name": name or info.get("A股简称", info.get("name", "")),
            "type": stock_type,
            "price": current_price,
            "change_rate": 0.0,
            "industry": info.get("industry", info.get("所属行业", "")),
            "short_term": composite["short_term"],
            "long_term": composite["long_term"],
            "composite": {
                "score": composite["composite_score"],
                "signal": composite["composite_signal"],
                "label": composite["composite_label"],
                "divergence": composite["divergence"],
            },
            "confidence": self._calc_confidence(composite),
            "price_prediction": price_prediction,
            "analysis": {
                "fund_flow": fund_flow,
                "research": research,
                "technical": technical,
                "fundamental": fundamental,
            },
            "updated_at": datetime.now().isoformat(),
        }

        self._update_price_change(result, code)
        return result

    def _update_price_change(self, result: Dict, code: str):
        try:
            val = self._fundamental._val.get_by_code(code)
            if val and "change_pct" in val:
                result["change_rate"] = float(val["change_pct"])
        except Exception:
            pass

    def _calc_confidence(self, composite: Dict) -> float:
        s = composite["short_term"]["score"]
        l = composite["long_term"]["score"]
        avg = (s + l) / 2
        consistency = 1 - abs(s - l) / 100
        return round(avg * consistency / 100, 2)
