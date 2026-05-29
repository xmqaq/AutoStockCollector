"""
自选股管理模块
支持自选股管理、异动监控
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from core.storage.mongo_storage import WatchlistStorage, KlineStorage, StockInfoStorage
from utils.logger import get_logger
from utils.helpers import normalize_stock_code


logger = get_logger(__name__)


class WatchlistManager:
    def __init__(self):
        self.storage = WatchlistStorage()
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.default_user_id = "default"

    def add_stock(
        self,
        user_id: str,
        code: str,
        priority: int = 0
    ) -> bool:
        code = normalize_stock_code(code)

        if not self._validate_stock(code):
            logger.warning(f"Invalid stock code: {code}")
            return False

        return self.storage.add_stock(user_id, code, "default", priority)

    def remove_stock(self, user_id: str, code: str) -> bool:
        code = normalize_stock_code(code)
        return self.storage.remove_stock(user_id, code)

    def get_watchlist(self, user_id: str = "default") -> List[Dict[str, Any]]:
        stocks = self.storage.get_user_watchlist(user_id)

        name_cache: Dict[str, str] = {}

        enriched_stocks = []
        for stock in stocks:
            code = stock.get("code")

            if code not in name_cache:
                info = self.stock_info_storage.get_by_code(code)
                name = ""
                if info:
                    name = info.get("name") or info.get("A股简称") or info.get("公司名称") or ""
                name_cache[code] = name
            stock["name"] = name_cache[code]

            latest_kline = self.kline_storage.find_one(
                {"code": code},
                sort=[("date", -1)]
            )
            if latest_kline and latest_kline.get("volume") is None:
                klines = self.kline_storage.find_many(
                    {"code": code},
                    sort=[("date", -1)],
                    limit=2
                )
                if klines:
                    for k in klines:
                        if k.get("volume") is not None:
                            latest_kline = k
                            break

            stock["latest_price"] = latest_kline.get("close") if latest_kline else None

            change_rate = (
                latest_kline.get("change_rate")
                or latest_kline.get("涨跌幅")
                or latest_kline.get("change")
            )
            if change_rate is None and latest_kline:
                prev_kline = self.kline_storage.find_one(
                    {"code": code, "date": {"$lt": latest_kline.get("date")}},
                    sort=[("date", -1)]
                )
                if prev_kline and prev_kline.get("close"):
                    prev_close = float(prev_kline["close"])
                    curr_close = float(latest_kline["close"])
                    if prev_close > 0:
                        change_rate = round((curr_close - prev_close) / prev_close * 100, 2)
            stock["change_rate"] = change_rate

            stock["latest_date"] = latest_kline.get("date") if latest_kline else None

            stock["volume"] = latest_kline.get("volume") if latest_kline else None
            stock["turnover"] = latest_kline.get("amount") or latest_kline.get("成交额")
            stock["turnover_rate"] = latest_kline.get("turnover_rate") or latest_kline.get("换手率")

            stock.pop("_id", None)
            stock.pop("_updated_at", None)
            stock.pop("enabled", None)
            stock.pop("user_id", None)
            stock.pop("group_id", None)
            stock.pop("priority", None)

            enriched_stocks.append(stock)

        return enriched_stocks

    def update_priority(
        self,
        user_id: str,
        code: str,
        priority: int
    ) -> bool:
        code = normalize_stock_code(code)
        return self.storage.update_stock_priority(user_id, code, priority)

    def create_group(
        self,
        user_id: str,
        group_id: str,
        name: str = "",
        description: str = ""
    ) -> bool:
        from config.database import get_collection

        groups_collection = get_collection("watchlist_groups")

        group_doc = {
            "user_id": user_id,
            "group_id": group_id,
            "name": name,
            "description": description,
            "create_time": datetime.now()
        }

        try:
            groups_collection.update_one(
                {"user_id": user_id, "group_id": group_id},
                {"$set": group_doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create group: {e}")
            return False

    def delete_group(self, user_id: str, group_id: str) -> bool:
        from config.database import get_collection

        groups_collection = get_collection("watchlist_groups")
        watchlist_collection = get_collection("watchlist")

        try:
            groups_collection.delete_one({"user_id": user_id, "group_id": group_id})
            watchlist_collection.update_many(
                {"user_id": user_id, "group_id": group_id},
                {"$set": {"enabled": False}}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete group: {e}")
            return False

    def get_groups(self, user_id: str = "default") -> List[Dict[str, Any]]:
        from config.database import get_collection

        groups_collection = get_collection("watchlist_groups")

        groups = list(groups_collection.find({"user_id": user_id}))

        for group in groups:
            count = self.storage.count_documents({
                "user_id": user_id,
                "group_id": group.get("group_id"),
                "enabled": True
            })
            group["stock_count"] = count

        return groups

    def move_stock_to_group(
        self,
        user_id: str,
        code: str,
        new_group_id: str
    ) -> bool:
        code = normalize_stock_code(code)

        return self.storage.update_one(
            {"user_id": user_id, "code": code},
            {"group_id": new_group_id}
        ) > 0

    def get_stock_snapshots(
        self,
        user_id: str,
        code: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        snapshots = self.kline_storage.find_many(
            {"code": code, "date": {"$gte": start_date, "$lte": end_date}},
            sort=[("date", 1)]
        )

        return snapshots

    def monitor_alerts(
        self,
        user_id: str,
        price_change_threshold: float = 5.0,
        volume_multiplier: float = 3.0
    ) -> List[Dict[str, Any]]:
        stocks = self.get_watchlist(user_id)
        alerts = []

        for stock in stocks:
            code = stock.get("code")
            latest_kline = self.kline_storage.find_one(
                {"code": code},
                sort=[("date", -1)]
            )

            if not latest_kline:
                continue

            yesterday_kline = self.kline_storage.find_one(
                {"code": code, "date": {"$lt": latest_kline.get("date")}},
                sort=[("date", -1)]
            )

            change_pct = latest_kline.get("涨跌幅", 0)
            if abs(change_pct) >= price_change_threshold:
                alerts.append({
                    "code": code,
                    "type": "price_alert",
                    "message": f"价格异动: {change_pct:.2f}%",
                    "price": latest_kline.get("close"),
                    "change_pct": change_pct,
                    "date": latest_kline.get("date")
                })

            if yesterday_kline:
                volume_today = latest_kline.get("volume", 0)
                volume_yesterday = yesterday_kline.get("volume", 0)

                if volume_yesterday > 0 and volume_today >= volume_yesterday * volume_multiplier:
                    alerts.append({
                        "code": code,
                        "type": "volume_alert",
                        "message": f"成交量异常放大: {volume_today/volume_yesterday:.2f}倍",
                        "volume": volume_today,
                        "volume_ratio": volume_today/volume_yesterday,
                        "date": latest_kline.get("date")
                    })

            limit_up = self._check_limit_up(latest_kline)
            if limit_up:
                alerts.append({
                    "code": code,
                    "type": "limit_up_alert",
                    "message": "涨停",
                    "price": latest_kline.get("close"),
                    "date": latest_kline.get("date")
                })

            limit_down = self._check_limit_down(latest_kline)
            if limit_down:
                alerts.append({
                    "code": code,
                    "type": "limit_down_alert",
                    "message": "跌停",
                    "price": latest_kline.get("close"),
                    "date": latest_kline.get("date")
                })

        return alerts

    def _check_limit_up(self, kline: Dict[str, Any]) -> bool:
        if "pct_chg" in kline and kline["pct_chg"] >= 9.9:
            return True
        return False

    def _check_limit_down(self, kline: Dict[str, Any]) -> bool:
        if "pct_chg" in kline and kline["pct_chg"] <= -9.9:
            return True
        return False

    def _validate_stock(self, code: str) -> bool:
        if not code:
            return False

        code = normalize_stock_code(code)

        code_upper = code.upper()
        if not (code_upper.startswith("SH") or code_upper.startswith("SZ")):
            return False

        digits_only = "".join(c for c in code if c.isdigit())
        if len(digits_only) != 6:
            return False

        return True

    def batch_add_stocks(
        self,
        user_id: str,
        codes: List[str],
        group_id: str = "default"
    ) -> Dict[str, int]:
        success_count = 0
        failed_count = 0

        for code in codes:
            if self.add_stock(user_id, code, group_id):
                success_count += 1
            else:
                failed_count += 1

        return {
            "success": success_count,
            "failed": failed_count
        }

    def get_priority_stocks(self, user_id: str = "default") -> List[Dict[str, Any]]:
        stocks = self.storage.find_many(
            {"user_id": user_id, "enabled": True},
            sort=[("priority", -1), ("add_time", -1)]
        )

        return [s for s in stocks if s.get("priority", 0) > 0]


class WatchlistLinkageController:
    def __init__(self):
        self.watchlist_storage = WatchlistStorage()
        self.kline_storage = KlineStorage()
        self.validator = None
        self.risk_controller = None
        self._scheduler = None

    def link_with_validator(self):
        from core.validator.validator import DataValidator
        self.validator = DataValidator()
        logger.info("自选股已联动数据校验模块")

    def link_with_risk_controller(self):
        from core.risk_control.risk_control import RiskController
        self.risk_controller = RiskController()
        logger.info("自选股已联动风控模块")

    def link_with_scheduler(self, scheduler):
        self._scheduler = scheduler
        logger.info("自选股已联动任务调度模块")

    def validate_watchlist_data(self, user_id: str = "default") -> Dict[str, Any]:
        if self.validator is None:
            self.link_with_validator()

        stocks = self.watchlist_storage.get_user_watchlist(user_id)
        codes = [s.get("code") for s in stocks]

        results = self.validator.validate_batch(codes, data_type="kline")

        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count
        avg_completeness = sum(r.completeness_score for r in results) / len(results) if results else 0

        return {
            "total": len(codes),
            "valid": valid_count,
            "invalid": invalid_count,
            "avg_completeness": avg_completeness
        }

    def get_watchlist_risk_status(self, user_id: str = "default") -> List[Dict[str, Any]]:
        if self.risk_controller is None:
            self.link_with_risk_controller()

        stocks = self.watchlist_storage.get_user_watchlist(user_id)
        risk_status = []

        for stock in stocks:
            code = stock.get("code")
            latest = self.kline_storage.find_one(
                {"code": code},
                sort=[("date", -1)]
            )

            if not latest:
                risk_status.append({
                    "code": code,
                    "risk_level": "unknown",
                    "message": "无数据"
                })
                continue

            change_pct = abs(latest.get("涨跌幅", 0))
            volume = latest.get("volume", 0)

            risk_level = "low"
            risk_factors = []

            if change_pct >= 9.5:
                risk_level = "high"
                risk_factors.append("涨停/跌停风险")
            elif change_pct >= 5:
                risk_level = "medium"
                risk_factors.append("价格波动较大")

            if volume < 1000000:
                risk_factors.append("流动性较低")

            risk_status.append({
                "code": code,
                "name": stock.get("name", ""),
                "risk_level": risk_level,
                "factors": risk_factors,
                "change_pct": change_pct,
                "volume": volume,
                "date": latest.get("date")
            })

        return risk_status

    def auto_fill_missing_data(self, user_id: str = "default") -> Dict[str, int]:
        validation = self.validate_watchlist_data(user_id)
        missing_count = validation["invalid"]

        if missing_count > 0 and self._scheduler is not None:
            stocks = self.watchlist_storage.get_user_watchlist(user_id)
            codes = [s.get("code") for s in stocks]
            self._scheduler.create_task("backfill", {"codes": codes})
            logger.info(f"触发自选股数据补采任务，标的数量: {len(codes)}")

        return {
            "triggered": missing_count > 0 and self._scheduler is not None,
            "missing_count": missing_count
        }

    def get_watchlist_report(self, user_id: str = "default") -> Dict[str, Any]:
        stocks = self.watchlist_storage.get_user_watchlist(user_id)

        valid_data_count = 0
        risk_summary = {"low": 0, "medium": 0, "high": 0}

        for stock in stocks:
            latest = self.kline_storage.find_one(
                {"code": stock.get("code")},
                sort=[("date", -1)]
            )
            if latest:
                valid_data_count += 1
                change = abs(latest.get("涨跌幅", 0))
                if change >= 9.5:
                    risk_summary["high"] += 1
                elif change >= 5:
                    risk_summary["medium"] += 1
                else:
                    risk_summary["low"] += 1

        return {
            "user_id": user_id,
            "total_stocks": len(stocks),
            "valid_data_count": valid_data_count,
            "data_completeness": valid_data_count / len(stocks) if stocks else 0,
            "risk_summary": risk_summary
        }


watchlist_manager = WatchlistManager()
watchlist_linkage = WatchlistLinkageController()
