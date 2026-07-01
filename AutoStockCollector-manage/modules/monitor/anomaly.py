"""异动检测 + 组合概览（从 engine.py 迁出）。

主力资金异动：近 N 日 Z-score 聚合，anomaly_score 超阈值才返回。
持仓股优先，其次监控对象，再其余。组合概览含四来源（持仓/自选/智选/投研）数量分布。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


def _bare(c: str) -> str:
    """带前缀码 → 纯数字（fund_flow 集合存纯数字）。"""
    return c[2:] if c[:2] in ("SH", "SZ") else c


def get_anomaly_alerts(db, account_info: Dict, current_positions: List[Dict],
                       monitor_stocks: Optional[List[Dict]] = None) -> List[Dict]:
    """主力资金异动：近 N 日 Z-score 聚合，anomaly_score 超阈值才返回。"""
    try:
        import numpy as np
        from config.settings import settings

        threshold = getattr(settings, "MONITOR_ANOMALY_THRESHOLD", 60)
        window_days = getattr(settings, "MONITOR_ANOMALY_WINDOW_DAYS", 5)

        hold = {_bare(p.get("code", "")) for p in current_positions}
        sources_by_bare = {_bare(s.get("code", "")): (s.get("sources") or [])
                           for s in (monitor_stocks or [])}
        days = window_days
        cutoff = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        pipe = [
            {"$match": {"date": {"$gte": cutoff}}},
            {"$sort": {"date": -1}},
            {"$group": {
                "_id": "$code",
                "name": {"$first": "$name"},
                "latest_date": {"$first": "$date"},
                "latest_net": {"$first": "$main_net_inflow"},
                "latest_amount": {"$first": "$total_amount"},
                "nets": {"$push": "$main_net_inflow"},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gte": days - 1}}},
        ]

        results: List[Dict] = []
        for doc in db["fund_flow"].aggregate(pipe, allowDiskUse=True):
            code = doc["_id"]
            nets = [float(x or 0) for x in doc["nets"]]
            if len(nets) < 2:
                continue
            latest_net = float(doc["latest_net"] or 0)
            avg_net = float(np.mean(nets))
            std_net = float(np.std(nets)) if len(nets) > 1 else 1
            z_score = (latest_net - avg_net) / std_net if std_net > 0 else 0

            consec = 0
            for v in nets:
                if v > 0: consec += 1
                elif v < 0: consec -= 1
                else: break

            first_half = float(np.mean(nets[:-2])) if len(nets) > 2 else avg_net
            second_half = float(np.mean(nets[:2])) if len(nets) >= 2 else latest_net
            reversal = second_half > 0 > first_half or second_half < 0 < first_half

            latest_amount = float(doc["latest_amount"] or 1)
            net_ratio = latest_net / latest_amount if latest_amount > 0 else 0
            anomaly_score = abs(z_score) * 40 + abs(consec) * 8 + (20 if reversal else 0) + abs(net_ratio) * 10
            if anomaly_score <= threshold:
                continue

            anomaly_type = "大幅流入" if latest_net > 0 and z_score > 1.5 else \
                           "大幅流出" if latest_net < 0 and z_score < -1.5 else \
                           "连续流入" if consec >= 3 else \
                           "连续流出" if consec <= -3 else \
                           "趋势反转" if reversal else "关注"
            bare = _bare(code)
            item = {
                "code": code,
                "name": doc.get("name", code),
                "latest_date": doc["latest_date"],
                "latest_net": round(latest_net, 2),
                "z_score": round(z_score, 2),
                "consecutive_days": consec,
                "reversal": reversal,
                "anomaly_score": round(anomaly_score, 1),
                "anomaly_type": anomaly_type,
                "is_holding": bare in hold,
            }
            if bare in sources_by_bare:
                item["in_monitor"] = True
                item["monitor_sources"] = sources_by_bare[bare]
            results.append(item)
        # 排序优先级：持仓 > 监控对象 > 其余异动股
        results.sort(key=lambda r: (not r["is_holding"],
                                    not r.get("in_monitor", False),
                                    -r["anomaly_score"]))
        return results
    except Exception as e:
        logger.error(f"Anomaly alerts failed: {e}")
        return []


def portfolio_summary(account: Dict, positions: List[Dict],
                      stocks: List[Dict]) -> Dict:
    """组合概览：总市值 + 四来源数量分布 + 重叠数。"""
    cash = (account or {}).get("cash_balance", 0) or 0
    position_value = sum(p.get("market_value", 0) or 0 for p in positions)
    total_value = cash + position_value

    def codes_with(src):
        return {s["code"] for s in stocks if src in (s.get("sources") or [])}

    pos_codes = codes_with("position")
    watch_codes = codes_with("watchlist")
    fusion_codes = codes_with("fusion_pick")
    research_codes = codes_with("research")
    overlap = ((pos_codes & watch_codes) | (pos_codes & fusion_codes)
               | (pos_codes & research_codes) | (watch_codes & fusion_codes)
               | (watch_codes & research_codes) | (fusion_codes & research_codes))
    return {
        "total_value": round(total_value, 2),
        "cash": round(cash, 2),
        "position_value": round(position_value, 2),
        "monitor_count": len(stocks),
        "position_count": len(pos_codes),
        "watchlist_count": len(watch_codes),
        "fusion_pick_count": len(fusion_codes),
        "research_count": len(research_codes),
        "overlap_count": len(overlap),
    }
