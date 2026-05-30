"""盯盘融合引擎。复用阈值告警(WatchlistManager.monitor_alerts)，仅对触发的股票
调 AdviceEngine 富化 AI 建议，组装 monitor_alerts 入库。
依赖注入便于测试；无触发不调 LLM（成本闸门）；advise 失败降级不丢告警。
"""
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# 阈值告警 type → monitor_alerts type 映射
_TYPE_MAP = {
    "price_alert": "price",
    "limit_up_alert": "price",
    "limit_down_alert": "price",
    "volume_alert": "volume",
    "flow_alert": "flow",
}


def _default_config_loader(user_id: str) -> Dict[str, Any]:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    doc = db["monitor_configs"].find_one({"user_id": user_id}) or {}
    return doc


def _default_alert_saver(doc: Dict[str, Any]) -> None:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    db["monitor_alerts"].insert_one(doc)


class MonitorEngine:
    def __init__(self, watchlist_manager=None, advice_engine=None,
                 config_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
                 alert_saver: Optional[Callable[[Dict[str, Any]], None]] = None):
        if watchlist_manager is None:
            from modules.watchlist.watchlist import WatchlistManager
            watchlist_manager = WatchlistManager()
        if advice_engine is None:
            from modules.ai.engines.advice import AdviceEngine
            advice_engine = AdviceEngine()
        self.watchlist_manager = watchlist_manager
        self.advice_engine = advice_engine
        self.config_loader = config_loader or _default_config_loader
        self.alert_saver = alert_saver or _default_alert_saver

    def scan(self, user_id: str = "default") -> List[Dict[str, Any]]:
        config = self.config_loader(user_id) or {}
        rise = config.get("price_rise_threshold", 5.0)
        fall = config.get("price_fall_threshold", 3.0)
        price_threshold = min(rise, fall)  # 取较小值，涨跌都能触发
        volume_multiplier = config.get("volume_ratio_threshold", 2.0)

        threshold_alerts = self.watchlist_manager.monitor_alerts(
            user_id,
            price_change_threshold=price_threshold,
            volume_multiplier=volume_multiplier,
        ) or []

        created: List[Dict[str, Any]] = []
        for ta in threshold_alerts:
            code = ta.get("code")
            raw_type = ta.get("type", "")
            ai_advice = None
            try:
                advice_result = self.advice_engine.advise(code)
                adv = advice_result.get("advice", {})
                ai_advice = {
                    "action": adv.get("action", ""),
                    "reason": adv.get("reason", ""),
                    "composite": advice_result.get("composite"),
                }
            except Exception:
                ai_advice = None  # 降级：告警不丢

            level = "danger" if raw_type == "limit_down_alert" else "warning"
            if ai_advice and ai_advice.get("action") in ("减仓", "回避", "卖出"):
                level = "danger"

            doc = {
                "user_id": user_id,
                "id": f"alert_{uuid.uuid4().hex[:12]}",
                "code": code,
                "name": ta.get("name", ""),
                "type": _TYPE_MAP.get(raw_type, "other"),
                "level": level,
                "message": ta.get("message", ""),
                "detail": (ai_advice or {}).get("reason", "") if ai_advice else "",
                "ai_advice": ai_advice,
                "read": False,
                "created_at": datetime.now().isoformat(),
            }
            self.alert_saver(doc)
            created.append(doc)

        return created
