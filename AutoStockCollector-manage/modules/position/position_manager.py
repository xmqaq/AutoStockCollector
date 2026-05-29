"""
持仓管理模块
支持持仓记录、盈亏计算、止损预警、风控管理
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class Position:
    code: str
    name: str
    shares: int
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    position_ratio: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def calculate(self) -> "Position":
        cost_basis = self.shares * self.avg_cost
        self.market_value = self.shares * self.current_price
        self.pnl = self.market_value - cost_basis
        self.pnl_percent = (self.pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        self.updated_at = datetime.now().isoformat()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "shares": self.shares,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": round(self.market_value, 2),
            "pnl": round(self.pnl, 2),
            "pnl_percent": round(self.pnl_percent, 2),
            "position_ratio": round(self.position_ratio, 2),
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class PositionManager:
    def __init__(self):
        from core.storage.mongo_storage import MongoStorage
        self._storage = MongoStorage("position")

    def add_position(
        self,
        code: str,
        shares: int,
        avg_cost: float,
        stop_loss: float = 0.0,
        target_price: float = 0.0
    ) -> Dict[str, Any]:
        from core.storage.mongo_storage import StockInfoStorage, KlineStorage

        info_storage = StockInfoStorage()
        kline_storage = KlineStorage()

        stock_info = info_storage.get_by_code(code)
        name = stock_info.get("name", code) if stock_info else code

        latest_kline = kline_storage.find_one(
            {"code": code},
            sort=[("date", -1]
        )
        current_price = latest_kline.get("close", avg_cost) if latest_kline else avg_cost

        existing = self._storage.find_one({"code": code})
        if existing:
            return {"error": f"Position {code} already exists"}

        position = Position(
            code=code,
            name=name,
            shares=shares,
            avg_cost=avg_cost,
            current_price=current_price,
            stop_loss=stop_loss,
            target_price=target_price,
            created_at=datetime.now().isoformat()
        )
        position.calculate()

        self._storage.insert_one(position.to_dict())
        logger.info(f"Added position: {code} - {shares} shares at {avg_cost}")

        return position.to_dict()

    def update_position(
        self,
        code: str,
        shares: Optional[int] = None,
        avg_cost: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target_price: Optional[float] = None
    ) -> Dict[str, Any]:
        from core.storage.mongo_storage import KlineStorage

        position = self._storage.find_one({"code": code})
        if not position:
            return {"error": f"Position {code} not found"}

        if shares is not None:
            position["shares"] = shares
        if avg_cost is not None:
            position["avg_cost"] = avg_cost
        if stop_loss is not None:
            position["stop_loss"] = stop_loss
        if target_price is not None:
            position["target_price"] = target_price

        kline_storage = KlineStorage()
        latest_kline = kline_storage.find_one(
            {"code": code},
            sort=[("date", -1]
        )
        if latest_kline:
            position["current_price"] = latest_kline.get("close", position.get("avg_cost", 0)

        pos = Position(**position)
        pos.calculate()
        self._storage.update_one({"code": code}, pos.to_dict())
        logger.info(f"Updated position: {code}")

        return pos.to_dict()

    def remove_position(self, code: str) -> bool:
        result = self._storage.delete_one({"code": code})
        logger.info(f"Removed position: {code}")
        return result

    def get_position(self, code: str) -> Optional[Dict[str, Any]]:
        return self._storage.find_one({"code": code})

    def list_positions(self) -> List[Dict[str, Any]]:
        from core.storage.mongo_storage import KlineStorage

        positions = self._storage.find_many({})
        if not positions:
            return []

        kline_storage = KlineStorage()
        for p in positions:
            kline = kline_storage.find_one(
                {"code": p["code"]},
                sort=[("date", -1]
            )
            if kline:
                p["current_price"] = kline.get("close", p.get("avg_cost", 0)

        return positions

    def calculate_portfolio(self) -> Dict[str, Any]:
        positions = self.list_positions()

        if not positions:
            return {
                "total_market_value": 0,
                "total_cost": 0,
                "total_pnl": 0,
                "total_pnl_percent": 0,
                "positions": [],
                "alerts": []
            }

        total_market = 0.0
        total_cost = 0.0
        alerts = []

        for p in positions:
            shares = p.get("shares", 0)
            cost = p.get("avg_cost", 0)
            price = p.get("current_price", cost)
            
            market_value = shares * price
            pnl = market_value - shares * cost
            pnl_percent = (pnl / (shares * cost) * 100) if cost > 0 else 0

            p["market_value"] = market_value
            p["pnl"] = pnl
            p["pnl_percent"] = pnl_percent

            total_market += market_value
            total_cost += shares * cost

            if pnl_percent <= -10:
                alerts.append({
                    "code": p["code"],
                    "label": "止损预警",
                    "type": "danger",
                    "message": f"{p.get('name', p['code']} 亏损已达 {abs(pnl_percent):.2f}%，建议关注"
                })
            elif pnl_percent <= -5:
                alerts.append({
                    "code": p["code"],
                    "label": "亏损预警",
                    "type": "warning",
                    "message": f"{p.get('name', p['code']} 亏损 {abs(pnl_percent):.2f}%"
                })

            stop_loss = p.get("stop_loss", 0)
            if stop_loss > 0 and price <= stop_loss:
                alerts.append({
                    "code": p["code"],
                    "label": "触发止损",
                    "type": "danger",
                    "message": f"{p.get('name', p['code']} 当前价已跌破止损位 {stop_loss}"
                })

        total_pnl = total_market - total_cost
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        for p in positions:
            p["position_ratio"] = (p.get("market_value", 0) / total_market * 100 if total_market > 0 else 0

        return {
            "total_market_value": round(total_market, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": round(total_pnl_percent, 2),
            "positions": positions,
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }

    def get_distribution(self) -> List[Dict[str, Any]]:
        portfolio = self.calculate_portfolio()
        positions = portfolio.get("positions", [])

        if not positions:
            return []

        total = portfolio.get("total_market_value", 0)
        if total <= 0:
            return []

        distribution = []
        for p in sorted(positions, key=lambda x: x.get("market_value", 0), reverse=True):
            distribution.append({
                "code": p["code"],
                "name": p.get("name", ""),
                "market_value": p.get("market_value", 0),
                "percent": round(p.get("market_value", 0) / total * 100, 2)
            })

        return distribution


class PositionAlertSystem:
    def __init__(self):
        self.position_manager = PositionManager()

    def check_alerts(self) -> List[Dict[str, Any]]:
        portfolio = self.position_manager.calculate_portfolio()
        return portfolio.get("alerts", [])

    def get_stop_loss_alerts(self) -> List[Dict[str, Any]]:
        positions = self.position_manager.list_positions()
        alerts = []

        for p in positions:
            stop_loss = p.get("stop_loss", 0)
            current_price = p.get("current_price", 0)

            if stop_loss > 0 and current_price > 0 and current_price <= stop_loss:
                alerts.append({
                    "code": p["code"],
                    "name": p.get("name", ""),
                    "type": "stop_loss",
                    "message": f"触发止损: {p.get('name', p['code']} 当前价 {current_price:.2f} <= 止损位 {stop_loss}"
                })

        return alerts

    def get_concentration_alerts(self, max_ratio: float = 30.0) -> List[Dict[str, Any]]:
        portfolio = self.position_manager.calculate_portfolio()
        positions = portfolio.get("positions", [])
        alerts = []

        for p in positions:
            ratio = p.get("position_ratio", 0)
            if ratio > max_ratio:
                alerts.append({
                    "code": p["code"],
                    "name": p.get("name", ""),
                    "type": "concentration",
                    "message": f"仓位过重: {p.get('name', p['code']} 占比 {ratio:.1f}%，建议分散风险"
                })

        return alerts


position_manager = PositionManager()
alert_system = PositionAlertSystem()
