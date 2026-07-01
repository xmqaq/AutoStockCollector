"""RiskDashboard — 风控仪表盘（持仓/盈亏/敞口/板块分布）。

从 intraday_tracker 拆出，修复 bug 4：原 get_risk_summary 直接
`from api.routes.paper_trading import _lazy_init, _account, _engine`，
业务模块反向依赖 API 层（循环依赖隐患）。现改为依赖注入 engine/account。
"""
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .radar_utils import now_shanghai, today_str, strip_prefix_from_code

logger = get_logger(__name__)


class RiskDashboard:
    def __init__(self, engine=None, account=None):
        """依赖注入 engine/account。未注入时延迟从 paper_trading 取（仅查询用，不形成循环依赖）。"""
        self._engine = engine
        self._account = account

    def _ensure_deps(self):
        if self._engine is None or self._account is None:
            from modules.paper_trading.account import PaperAccount
            from modules.paper_trading.trade_engine import TradeEngine
            self._engine = self._engine or TradeEngine()
            self._account = self._account or PaperAccount()

    def get_summary(self, date: Optional[str] = None, user_id: str = "default") -> Dict[str, Any]:
        """返回风控仪表盘数据：持仓、盈亏、敞口、板块分布、距止损距离。"""
        date = date or today_str()
        try:
            self._ensure_deps()
            positions, _ = self._engine.get_positions(user_id)
            acc_doc = self._account.get(user_id)
            cash = acc_doc.get("cash_balance", 0) if acc_doc else 0
            total_market_value = sum(p.get("market_value", 0) for p in positions)
            total_cost = sum(p.get("avg_cost", 0) * p.get("shares", 0) for p in positions)
            total_pnl = total_market_value - total_cost

            # 仅展示当日竞价建仓的持仓
            auto_trade_positions = []
            for p in positions:
                trade = self._find_auto_trade_record(p.get("code", ""), date)
                if trade:
                    p = {**p, "auto_trade_info": trade}
                    auto_trade_positions.append(p)

            sector_exposure = self._sector_exposure(positions, date)

            return {
                "cash_balance": round(cash, 2),
                "total_market_value": round(total_market_value, 2),
                "total_cost": round(total_cost, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
                "position_count": len(positions),
                "auto_trade_count": len(auto_trade_positions),
                "max_positions": AuctionConfig.MAX_POSITIONS_PER_DAY,
                "total_exposure_pct": round(total_market_value / (cash + total_market_value) * 100, 2) if (cash + total_market_value) > 0 else 0,
                "max_exposure_pct": AuctionConfig.MAX_TOTAL_EXPOSURE_PCT * 100,
                "sector_exposure": {k: round(v, 2) for k, v in sorted(sector_exposure.items(), key=lambda x: -x[1])},
                "positions": [self._format_pos(p) for p in auto_trade_positions],
            }
        except Exception as e:
            logger.warning(f"[RiskDashboard] summary error: {e}")
            return {"error": str(e), "positions": []}

    def _sector_exposure(self, positions: List[Dict], date: str) -> Dict[str, float]:
        """按行业聚合持仓市值。industry 来自 intraday_track / auction_results。"""
        code_to_industry = self._build_code_industry_map(date)
        sector: Dict[str, float] = {}
        for p in positions:
            raw_code = strip_prefix_from_code(p.get("code", ""))
            ind = code_to_industry.get(raw_code, p.get("code", "其他")[:2])
            sector[ind] = sector.get(ind, 0) + p.get("market_value", 0)
        return sector

    def _format_pos(self, p: Dict) -> Dict:
        sl = p.get("stop_loss")
        return {
            "code": p.get("code", ""),
            "name": p.get("name", ""),
            "shares": p.get("shares", 0),
            "avg_cost": p.get("avg_cost", 0),
            "current_price": p.get("current_price", 0),
            "market_value": p.get("market_value", 0),
            "pnl": p.get("pnl", 0),
            "pnl_percent": p.get("pnl_percent", 0),
            "today_pnl_percent": p.get("today_pnl_percent", 0),
            "stop_loss": sl,
            "take_profit": p.get("take_profit"),
            "distance_to_sl": round((p.get("current_price", 0) - sl) / sl * 100, 2) if sl else None,
        }

    def _find_auto_trade_record(self, code: str, date: str) -> Optional[Dict]:
        """查当日竞价雷达建仓记录。"""
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            today_start = f"{date}T00:00:00"
            today_end = f"{date}T23:59:59"
            return db["trade_records"].find_one({
                "code": code, "action": "buy",
                "traded_at": {"$gte": today_start, "$lte": today_end},
                "ai_signal.source": {"$in": ["auction_radar_auto", "auction_radar"]},
            })
        except Exception:
            return None

    def _build_code_industry_map(self, date: str) -> Dict[str, str]:
        """从 intraday_track + auction_results 拼行业映射。"""
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            result = {}
            for doc in db["auction_intraday_track"].find({"date": date}, {"code": 1, "industry": 1}):
                result[doc.get("code", "")] = doc.get("industry", "")
            for doc in db[AuctionConfig.RESULT_COLLECTION].find({"date": date}, {"top_stocks.industry": 1, "top_stocks.symbol": 1}):
                for s in doc.get("top_stocks") or []:
                    result[s.get("symbol", "")] = s.get("industry", "")
            return result
        except Exception:
            return {}


# 向后兼容模块级函数
def get_risk_summary(date: Optional[str] = None) -> Dict[str, Any]:
    return RiskDashboard().get_summary(date)
