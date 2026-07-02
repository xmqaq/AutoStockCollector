"""AI 实时监控引擎 — 协调各分析器，并行分析股票池，生成短/长期信号。

重构后只做编排：股票池四来源（持仓+自选+智选+投研）→ 6 路分析器 → composite →
规则决策器(decider) → 落库 monitor_signals。异动检测/组合概览在 anomaly.py，
买卖决策在 decider.py，实时数据在 realtime.py，LLM 预测在 ai_advisor.py。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from core.storage.mongo_storage import StockInfoStorage, WatchlistStorage
from utils.helpers import normalize_stock_code_flexible
from utils.logger import get_logger

from .storage import MonitorStorage
from .analyzers import (
    FundFlowAnalyzer,
    PricePredictionAnalyzer,
    ResearchReportAnalyzer,
    TechnicalAnalyzer,
    FundamentalAnalyzer,
    CompositeAnalyzer,
    StockNewsSentimentAnalyzer,
)
from . import anomaly
from .decider import AdviceContext, SellDecider, BuyDecider, HoldDecider, _calc_rr, merge_advice, build_advice

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
        self._news_sentiment = StockNewsSentimentAnalyzer()
        self._watchlist = WatchlistStorage()
        self._db = DatabaseConfig.get_database()
        self._sell_decider = SellDecider()
        self._buy_decider = BuyDecider()
        self._hold_decider = HoldDecider()

    def refresh_all(self, user_id: str = "default", sync_fusion: bool = True) -> Dict[str, Any]:
        """对「持仓 + 自选股 + AI智选 + 投研分析」统一做买卖点分析，并维护监控生命周期。
        sync_fusion=False 时跳过智选/投研追踪与过期清理（盘中刷新用，只更新买卖点）。"""
        from modules.monitor.lifecycle import MonitorLifecycle
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine

        lifecycle = MonitorLifecycle()
        positions_synced = lifecycle.sync_positions(user_id)
        if sync_fusion:
            fusion_synced = lifecycle.sync_fusion_pick_tracking(user_id)
            research_synced = lifecycle.sync_research_tracking(user_id)
            expired_cleaned = lifecycle.cleanup_expired_fusion_picks()
        else:
            fusion_synced = {"skipped": True}
            research_synced = {"skipped": True}
            expired_cleaned = {"skipped": True}

        stocks = self._collect_stocks(user_id)

        analyzed = 0
        advice: List[Dict[str, Any]] = []
        if stocks:
            with ThreadPoolExecutor(max_workers=8) as pool:
                fut_map = {pool.submit(self._analyze_one, self._to_analyze_input(s)): s
                           for s in stocks}
                for fut in as_completed(fut_map):
                    s = fut_map[fut]
                    try:
                        result = fut.result()
                    except Exception as e:
                        logger.error(f"Analyze {s.get('code')} failed: {e}")
                        continue
                    if not result:
                        continue
                    self._attach_lifecycle_fields(result, s)
                    self._storage.upsert_signal(result["code"], result)
                    # 写历史快照供 auto_trading._merge_ai_monitor 读取（修 history 断写）。
                    # 盘中 3min 刷新会写多条，_expire_at TTL 90 天自动过期防膨胀。
                    try:
                        self._storage.save_history(result["code"], result)
                    except Exception as e:
                        logger.warning(f"save_history {result['code']} failed: {e}")
                    advice.append(self._advice_item(result))
                    analyzed += 1

        account = PaperAccount().get(user_id) or {"cash_balance": 0}
        try:
            positions, _ = TradeEngine().get_positions(user_id)
        except Exception as e:
            logger.error(f"Get positions failed for {user_id}: {e}")
            positions = []

        anomaly_alerts = anomaly.get_anomaly_alerts(self._db, account, positions, stocks)
        psummary = anomaly.portfolio_summary(account, positions, stocks)

        timestamp = datetime.now().isoformat()
        lifecycle_summary = {
            "positions_synced": positions_synced,
            "fusion_tracking_synced": fusion_synced,
            "research_tracking_synced": research_synced,
            "expired_cleaned": expired_cleaned,
        }
        # 合成"组合建议"文档，供 /portfolio 路由回读最近一次结果
        self._storage.upsert_signal(f"__monitor_portfolio_{user_id}__", {
            "code": f"__monitor_portfolio_{user_id}__",
            "type": "portfolio_advice",
            "user_id": user_id,
            "advice": advice,
            "portfolio_summary": psummary,
            "anomaly_alerts": anomaly_alerts,
            "lifecycle_summary": lifecycle_summary,
            "analyzed": analyzed,
            "timestamp": timestamp,
        })

        logger.info(f"Monitor refresh done user={user_id}: analyzed={analyzed}, "
                    f"advice={len(advice)}, alerts={len(anomaly_alerts)}")
        return {
            "success": True,
            "advice": advice,
            "portfolio_summary": psummary,
            "anomaly_alerts": anomaly_alerts,
            "lifecycle_summary": lifecycle_summary,
            "analyzed": analyzed,
            "timestamp": timestamp,
        }

    @staticmethod
    def _to_analyze_input(s: Dict[str, Any]) -> Dict[str, Any]:
        """把 _collect_stocks 条目转成 _analyze_one 入参；持仓标 type=持仓。"""
        is_pos = "position" in (s.get("sources") or [])
        return {
            "code": s["code"],
            "name": s.get("name", ""),
            "type": "持仓" if is_pos else "自选",
            "shares": s.get("shares", 0),
            "avg_cost": s.get("avg_cost", 0),
            "market_value": s.get("market_value", 0),
            "pnl": s.get("pnl", 0),  # 已是小数口径（见 _collect_stocks）
        }

    @staticmethod
    def _attach_lifecycle_fields(result: Dict[str, Any], meta: Dict[str, Any]) -> None:
        """把来源/连续入选/强化信号写入分析结果；连续≥3天插入强化信号文案。"""
        sources = meta.get("sources", []) or []
        consecutive = int(meta.get("consecutive_days", 0) or 0)
        is_fusion = "fusion_pick" in sources
        strong = is_fusion and consecutive >= 3
        result["sources"] = sources
        result["consecutive_days"] = consecutive if is_fusion else 0
        result["strong_signal"] = strong
        result["first_selected_at"] = meta.get("first_selected_at", "") or ""
        if strong:
            ta = result.get("trading_advice") or {}
            reasons = list(ta.get("reasons") or [])
            tip = f"已连续{consecutive}天入选AI智选，关注度持续走高"
            if tip not in reasons:
                ta["reasons"] = [tip] + reasons
            result["trading_advice"] = ta

    @staticmethod
    def _advice_item(result: Dict[str, Any]) -> Dict[str, Any]:
        """组合建议列表的单项：身份 + 生命周期字段 + trading_advice 全部字段。"""
        ta = result.get("trading_advice", {}) or {}
        return {
            "code": result.get("code"),
            "name": result.get("name", ""),
            "price": result.get("price", 0),
            "sources": result.get("sources", []),
            "consecutive_days": result.get("consecutive_days", 0),
            "strong_signal": result.get("strong_signal", False),
            "first_selected_at": result.get("first_selected_at", ""),
            **ta,
        }

    def refresh_stock(self, code: str) -> Optional[Dict[str, Any]]:
        """单股刷新（同步），写历史轨迹。"""
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

    def _collect_stocks(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """汇总四个来源（持仓 + 自选股 + AI智选 + 投研分析），按 code 去重并合并 sources。"""
        merged: Dict[str, Dict[str, Any]] = {}

        def _entry(code: str, name: str = "") -> Dict[str, Any]:
            e = merged.get(code)
            if e is None:
                e = {"code": code, "name": name, "sources": [],
                     "shares": 0, "avg_cost": 0, "market_value": 0, "pnl": 0,
                     "fusion_score": 0, "research_score": 0, "research_reason": "",
                     "consecutive_days": 0, "first_selected_at": ""}
                merged[code] = e
            if name and not e.get("name"):
                e["name"] = name
            return e

        def _add_source(e: Dict[str, Any], src: str) -> None:
            if src not in e["sources"]:
                e["sources"].append(src)

        # a) 持仓：模拟盘 TradeEngine + 兼容实盘 positions 集合
        try:
            from modules.paper_trading.trade_engine import TradeEngine
            positions, _ = TradeEngine().get_positions(user_id)
            for p in positions:
                code = p.get("code")
                if not code or (p.get("shares", 0) or 0) <= 0:
                    continue
                e = _entry(code, p.get("name", ""))
                _add_source(e, "position")
                e["shares"] = p.get("shares", 0)
                e["avg_cost"] = p.get("avg_cost", 0)
                e["market_value"] = p.get("market_value", 0)
                e["pnl"] = (p.get("pnl_percent", 0) or 0) / 100
        except Exception as e:
            logger.error(f"_collect_stocks paper positions failed: {e}")
        try:
            for p in self._db["positions"].find():
                code = p.get("code")
                if not code or (p.get("shares", 0) or 0) <= 0:
                    continue
                e = _entry(code, p.get("name", ""))
                _add_source(e, "position")
                if not e["shares"]:
                    e["shares"] = p.get("shares", 0)
                    e["avg_cost"] = p.get("avg_cost", 0)
                    e["market_value"] = p.get("market_value", 0)
                    e["pnl"] = p.get("pnl", 0)
        except Exception as e:
            logger.error(f"_collect_stocks legacy positions failed: {e}")

        # b) 自选股
        try:
            for w in self._watchlist.get_user_watchlist(user_id):
                code = w.get("code")
                if not code:
                    continue
                _add_source(_entry(code, w.get("name", w.get("A股简称", ""))), "watchlist")
        except Exception as e:
            logger.error(f"_collect_stocks watchlist failed: {e}")

        # c) AI 智选最新一轮 picks（code 已带前缀）
        try:
            latest = self._db["fusion_pick_results"].find_one(
                {}, sort=[("created_at", -1)])
            for pick in ((latest or {}).get("picks") or []):
                code = pick.get("code")
                if not code:
                    continue
                e = _entry(code, pick.get("name", ""))
                _add_source(e, "fusion_pick")
                e["fusion_score"] = pick.get("fusion_score", 0)
                if pick.get("track"):
                    e["track"] = pick["track"]
        except Exception as e:
            logger.error(f"_collect_stocks fusion picks failed: {e}")

        # d) 投研分析最新一轮 candidates（code 是纯数字，需归一化为带前缀）
        try:
            latest_research = self._db["research_analysis_results"].find_one(
                {"source": "cron_daily"}, sort=[("created_at", -1)])
            for cand in (((latest_research or {}).get("result") or {}).get("candidates") or []):
                raw_code = cand.get("code", "")
                code = normalize_stock_code_flexible(raw_code) if raw_code else ""
                if not code:
                    continue
                e = _entry(code, cand.get("name", ""))
                _add_source(e, "research")
                e["research_score"] = cand.get("score", 0) or 0
                e["research_reason"] = cand.get("reason_text") or cand.get("reason", "") or ""
        except Exception as e:
            logger.error(f"_collect_stocks research candidates failed: {e}")

        # 补充追踪字段（consecutive_days / first_selected_at 由 lifecycle 写入 monitor_signals）
        try:
            codes = list(merged.keys())
            if codes:
                for d in self._db["monitor_signals"].find(
                        {"code": {"$in": codes}},
                        {"code": 1, "consecutive_days": 1, "first_selected_at": 1}):
                    e = merged.get(d.get("code"))
                    if e:
                        e["consecutive_days"] = d.get("consecutive_days", 0) or 0
                        e["first_selected_at"] = d.get("first_selected_at", "") or ""
        except Exception as e:
            logger.error(f"_collect_stocks tracking enrich failed: {e}")

        stocks = list(merged.values())
        logger.info(f"Collected {len(stocks)} stocks to monitor (user={user_id})")
        return stocks

    def _analyze_one(self, stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        code = stock["code"]
        name = stock.get("name", "")
        stock_type = stock.get("type", "自选")
        info = self._stock_info.get_by_code(code) or {}
        industry = info.get("industry", info.get("所属行业", ""))

        try:
            fund_flow = self._fund_flow.analyze(code)
            research = self._research.analyze(code, name)
            technical = self._technical.analyze(code)
            fundamental = self._fundamental.analyze(code)
            price_prediction = self._price_prediction.analyze(code)
            news_sentiment = self._news_sentiment.analyze(code, name, industry)
            # 估值维度复用 fundamental.score（valuation.py 已并入 fundamental）
            composite = self._composite.composite(
                fund_flow, research, technical, fundamental, fundamental, news_sentiment,
            )
        except Exception as e:
            logger.error(f"Analyze {code} failed: {e}")
            return None

        current_price = technical.get("current_price", 0)

        pp = price_prediction
        ctx = AdviceContext(
            current_price=current_price,
            target_price=pp.get("target_price", 0),
            stop_loss=pp.get("stop_loss", 0),
            buy_low=pp.get("buy_zone_low", 0),
            buy_high=pp.get("buy_zone_high", 0),
            expected_return=pp.get("expected_return", 0),
            max_loss=pp.get("max_loss", 0),
            stock_type=stock_type,
            shares=stock.get("shares", 0),
            avg_cost=stock.get("avg_cost", 0),
            market_value=stock.get("market_value", 0),
            pnl=stock.get("pnl", 0),
            ff_s=fund_flow.get("short_term", {}).get("score", 50),
            ff_l=fund_flow.get("long_term", {}).get("score", 50),
            rs_s=research.get("short_term", {}).get("score", 50),
            rs_l=research.get("long_term", {}).get("score", 50),
            rs_c=research.get("composite_score", 50),
            tc_s=technical.get("short_term", {}).get("score", 50),
            tc_l=technical.get("long_term", {}).get("score", 50),
            vl_s=fundamental.get("score", 50),
            cp_s=composite.get("composite_score", 50),
            cp_sig=composite.get("composite_signal", "hold"),
            sc_s=composite.get("short_term", {}).get("score", 50),
            sc_l=composite.get("long_term", {}).get("score", 50),
            divergence=composite.get("divergence", ""),
            ns_bullish=(news_sentiment or {}).get("overall", {}).get("bullish", False),
            ns_score=(news_sentiment or {}).get("overall", {}).get("score", 50),
            ns_pos_count=(news_sentiment or {}).get("positive_count", 0),
            change_rate=self._get_change_rate(code),
        )
        ctx.rr = _calc_rr(ctx.expected_return, ctx.max_loss)

        sell = self._sell_decider.decide(ctx)
        buy = self._buy_decider.decide(ctx)
        hold = self._hold_decider.decide(ctx)

        action, sig, reasons, source = merge_advice(sell, buy, hold)
        trading_advice = build_advice(ctx, action, sig, reasons, source)

        # 采集三路外部信号（PA/竞价/agent 快照）+ 算综合融合分
        from .analyzers.external_signals import collect_external_signals
        from utils.helpers import beijing_now
        ext = collect_external_signals(
            code, composite.get("composite_score", 50),
            beijing_now().strftime("%Y-%m-%d"),
        )

        result = {
            "code": code,
            "name": name or info.get("A股简称", info.get("name", "")),
            "type": stock_type,
            "price": current_price,
            "change_rate": ctx.change_rate,
            "industry": industry,
            "short_term": composite["short_term"],
            "long_term": composite["long_term"],
            "composite": {
                "score": composite["composite_score"],
                "signal": composite["composite_signal"],
                "label": composite["composite_label"],
                "divergence": composite["divergence"],
            },
            "external_signals": ext,  # {pa, auction, agent, fusion_score, fusion_breakdown, fusion_weights}
            "price_prediction": price_prediction,
            "analysis": {
                "fund_flow": fund_flow,
                "research": research,
                "technical": technical,
                "fundamental": fundamental,
                "news_sentiment": news_sentiment,
            },
            "trading_advice": trading_advice,
            "updated_at": datetime.now().isoformat(),
        }
        return result

    def _get_change_rate(self, code: str) -> float:
        """取实时涨跌幅（优先 monitor_realtime，回退 stock_valuation.change_pct）。"""
        try:
            rt = self._db["monitor_realtime"].find_one(
                {"code": code}, {"change_rate": 1, "_id": 0})
            if rt and rt.get("change_rate") is not None:
                return float(rt["change_rate"])
        except Exception:
            pass
        try:
            val = self._fundamental._val.get_by_code(code)
            if val and val.get("change_pct") is not None:
                return float(val["change_pct"])
        except Exception:
            pass
        return 0.0
