"""
AI 实时监控 API 路由 — 主力资金流量 + 研报分析，长短线投资建议
"""
import threading
from typing import Dict
from flask import Blueprint, jsonify, request, g

from modules.monitor.storage import MonitorStorage
from utils.logger import get_logger
from api.auth_utils import login_required

logger = get_logger(__name__)

monitor_bp = Blueprint("monitor", __name__, url_prefix="/api/v1/monitor")

_engine = None
_engine_lock = threading.Lock()
_refresh_lock = threading.Lock()


def _get_user_stock_codes(user_id: str) -> set:
    """获取用户关心的股票代码（持仓 + 自选 + 策略选股/量化选股）"""
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    codes = set()
    # 兼容 pre-auth 遗留数据（user_id="default"）和当前用户
    uid_filter = {"$in": [user_id, "default"]}
    try:
        for p in db["positions"].find({"user_id": uid_filter}):
            c = p.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    try:
        for p in db["positions"].find({"user_id": {"$exists": False}}):
            c = p.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    try:
        for p in db["trade_records"].aggregate([
            {"$match": {"user_id": uid_filter, "action": "buy"}},
            {"$group": {"_id": None, "codes": {"$addToSet": "$code"}}},
        ]):
            for c in p.get("codes", []):
                codes.add(c)
    except Exception:
        pass
    try:
        for w in db["watchlist"].find({"user_id": uid_filter, "enabled": True}):
            c = w.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    try:
        for r in db["ai_pick_results"].find({}):
            for pick in (r.get("picks") or []):
                c = pick.get("code", "")
                if c: codes.add(c)
    except Exception:
        pass
    try:
        for f in db["factor_cache"].find({}):
            c = f.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    return codes


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from modules.monitor.engine import MonitorEngine
                _engine = MonitorEngine()
    return _engine


@monitor_bp.route("/signals", methods=["GET"])
@login_required
def get_signals():
    try:
        storage = MonitorStorage()
        all_signals = storage.get_all_signals()
        user_codes = _get_user_stock_codes(g.current_user["user_id"])
        if user_codes:
            signals = [s for s in all_signals if s.get("code") in user_codes]
        else:
            signals = all_signals
        return jsonify({"success": True, "count": len(signals), "data": signals})
    except Exception as e:
        logger.error(f"Get signals failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/signals/<code>", methods=["GET"])
def get_signal(code: str):
    try:
        storage = MonitorStorage()
        signal = storage.get_signal(code)
        if not signal:
            return jsonify({"success": False, "error": "未找到该股票信号"}), 404
        return jsonify({"success": True, "data": signal})
    except Exception as e:
        logger.error(f"Get signal {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/signals/<code>/history", methods=["GET"])
def get_signal_history(code: str):
    try:
        days = int(request.args.get("days", 30))
        storage = MonitorStorage()
        history = storage.get_history(code, days)
        return jsonify({"success": True, "count": len(history), "data": history})
    except Exception as e:
        logger.error(f"Get history for {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/refresh", methods=["POST"])
@login_required
def refresh_all():
    if _refresh_lock.locked():
        return jsonify({"success": False, "error": "刷新任务正在运行中，请稍候再试"}), 429

    def _run():
        with _refresh_lock:
            try:
                _get_engine().refresh_all()
            except Exception as e:
                logger.error(f"Refresh all failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "刷新任务已启动，请稍后查询结果"})


@monitor_bp.route("/refresh/<code>", methods=["POST"])
@login_required
def refresh_stock(code: str):
    try:
        result = _get_engine().refresh_stock(code)
        if not result:
            return jsonify({"success": False, "error": "分析失败"}), 500
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Refresh {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/scan", methods=["GET"])
@login_required
def scan_once():
    try:
        result = _get_engine().refresh_all()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/backtest/<code>", methods=["GET"])
def get_backtest(code: str):
    """获取单只股票信号回测结果"""
    try:
        from modules.monitor.backtest import SignalBacktest
        days = int(request.args.get("days", 60))
        result = SignalBacktest().evaluate(code, days)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Backtest {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/backtest", methods=["GET"])
def get_backtest_all():
    """获取所有信号回测结果"""
    try:
        from modules.monitor.backtest import SignalBacktest
        results = SignalBacktest().evaluate_all()
        return jsonify({"success": True, "count": len(results), "data": results})
    except Exception as e:
        logger.error(f"Backtest all failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/sector-sentiment", methods=["GET"])
def get_sector_sentiment():
    """板块舆情热度排行 — 按行业聚合新闻情感评分"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        signals = list(db["monitor_signals"].find(
            {"analysis.news_sentiment": {"$exists": True}},
            {"industry": 1, "analysis.news_sentiment": 1, "name": 1, "code": 1, "_id": 0},
        ))

        sector_map: Dict[str, Dict] = {}
        for s in signals:
            industry = s.get("industry", "") or "未知"
            ns = s.get("analysis", {}).get("news_sentiment", {})
            overall = ns.get("overall", {})
            score = overall.get("score", 50)
            pos = ns.get("positive_count", 0)
            neg = ns.get("negative_count", 0)
            total = ns.get("news_count", 0)
            bullish = overall.get("bullish", False)

            if industry not in sector_map:
                sector_map[industry] = {
                    "industry": industry,
                    "stock_count": 0,
                    "total_score": 0.0,
                    "total_news": 0,
                    "positive_news": 0,
                    "negative_news": 0,
                    "bullish_stocks": 0,
                    "top_stocks": [],
                }
            sec = sector_map[industry]
            sec["stock_count"] += 1
            sec["total_score"] += score
            sec["total_news"] += total
            sec["positive_news"] += pos
            sec["negative_news"] += neg
            if bullish:
                sec["bullish_stocks"] += 1
            if total > 0:
                sec["top_stocks"].append({
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "news_count": total,
                    "sentiment_score": round(score, 1),
                    "bullish": bullish,
                })

        result = []
        for industry, sec in sector_map.items():
            avg_score = sec["total_score"] / sec["stock_count"] if sec["stock_count"] > 0 else 50
            sec["top_stocks"].sort(key=lambda x: x["news_count"], reverse=True)
            result.append({
                "industry": industry,
                "stock_count": sec["stock_count"],
                "avg_sentiment_score": round(avg_score, 1),
                "total_news": sec["total_news"],
                "positive_news": sec["positive_news"],
                "negative_news": sec["negative_news"],
                "bullish_stock_ratio": round(sec["bullish_stocks"] / sec["stock_count"] * 100, 1) if sec["stock_count"] > 0 else 0,
                "top_stocks": sec["top_stocks"][:5],
                "signal": "bullish" if avg_score >= 60 else "bearish" if avg_score <= 40 else "neutral",
            })

        result.sort(key=lambda x: x["avg_sentiment_score"], reverse=True)
        return jsonify({"success": True, "count": len(result), "data": result})
    except Exception as e:
        logger.error(f"Sector sentiment failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/fund-flow-anomalies", methods=["GET"])
@login_required
def get_fund_flow_anomalies():
    """主力资金异动监测: 最近5日异常净流入/流出、连续异动、趋势反转"""
    try:
        from config.database import DatabaseConfig
        import numpy as np
        db = DatabaseConfig.get_database()
        days = int(request.args.get("days", 5))
        limit = int(request.args.get("limit", 100))

        from datetime import datetime, timedelta
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
                "latest_price": {"$first": "$price"},
                "latest_change": {"$first": "$change_pct"},
                "latest_turnover": {"$first": "$turnover_rate"},
                "latest_amount": {"$first": "$total_amount"},
                "nets": {"$push": "$main_net_inflow"},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gte": days - 1}}},
        ]

        results = []
        for doc in db["fund_flow"].aggregate(pipe, allowDiskUse=True):
            code = doc["_id"]
            nets = [float(x or 0) for x in doc["nets"]]
            latest_net = float(doc["latest_net"] or 0)
            if len(nets) < 2:
                continue

            avg_net = float(np.mean(nets))
            std_net = float(np.std(nets)) if len(nets) > 1 else 1
            z_score = (latest_net - avg_net) / std_net if std_net > 0 else 0

            # 连续正/负天数
            consec = 0
            for v in nets:
                if v > 0: consec += 1
                elif v < 0: consec -= 1
                else: break

            # 趋势反转判断: 前3天 vs 最近2天
            first_half = float(np.mean(nets[:-2])) if len(nets) > 2 else avg_net
            second_half = float(np.mean(nets[:2])) if len(nets) >= 2 else latest_net
            reversal = second_half > 0 > first_half or second_half < 0 < first_half

            # 净流入占比
            latest_amount = float(doc["latest_amount"] or 1)
            net_ratio = latest_net / latest_amount if latest_amount > 0 else 0

            anomaly_score = abs(z_score) * 40 + abs(consec) * 8 + (20 if reversal else 0) + abs(net_ratio) * 10

            anomaly_type = "大幅流入" if latest_net > 0 and z_score > 1.5 else \
                           "大幅流出" if latest_net < 0 and z_score < -1.5 else \
                           "连续流入" if consec >= 3 else \
                           "连续流出" if consec <= -3 else \
                           "趋势反转" if reversal else "关注"

            results.append({
                "code": code,
                "name": doc.get("name", code),
                "latest_date": doc["latest_date"],
                "latest_net": round(latest_net, 2),
                "latest_amount": round(latest_amount, 2) if latest_amount else 0,
                "latest_price": round(float(doc["latest_price"] or 0), 2),
                "latest_change": round(float((doc.get("latest_change", "") or "0").replace("%", "")), 2),
                "latest_turnover": round(float((doc.get("latest_turnover", "") or "0").replace("%", "")), 2),
                "avg_net": round(avg_net, 2),
                "std_net": round(std_net, 2),
                "z_score": round(z_score, 2),
                "consecutive_days": consec,
                "net_ratio": round(net_ratio, 4),
                "reversal": reversal,
                "anomaly_score": round(anomaly_score, 1),
                "anomaly_type": anomaly_type,
                "data_days": len(nets),
            })

        results.sort(key=lambda r: r["anomaly_score"], reverse=True)

        # 统计摘要
        total = len(results)
        big_inflow = sum(1 for r in results if r["anomaly_type"] == "大幅流入")
        big_outflow = sum(1 for r in results if r["anomaly_type"] == "大幅流出")
        consec_inflow = sum(1 for r in results if r["anomaly_type"] == "连续流入")
        consec_outflow = sum(1 for r in results if r["anomaly_type"] == "连续流出")
        reversals = sum(1 for r in results if r["reversal"])

        return jsonify({
            "success": True,
            "count": len(results[:limit]),
            "data": results[:limit],
            "summary": {
                "total": total,
                "big_inflow": big_inflow,
                "big_outflow": big_outflow,
                "consec_inflow": consec_inflow,
                "consec_outflow": consec_outflow,
                "reversals": reversals,
            },
        })
    except Exception as e:
        logger.error(f"Fund flow anomalies failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/config", methods=["GET"])
@login_required
def get_monitor_config():
    """读当前用户的双轨道监控配置（不存在返回默认值）。"""
    try:
        from modules.monitor.config import MonitorConfig
        config = MonitorConfig().get(g.current_user["user_id"])
        return jsonify({"success": True, "data": config})
    except Exception as e:
        logger.error(f"Get monitor config failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/config", methods=["PUT"])
@login_required
def put_monitor_config():
    """保存（部分或完整）监控配置，merge_with_default 后落库，返回合并后的完整配置。"""
    try:
        from modules.monitor.config import MonitorConfig
        body = request.get_json(silent=True) or {}
        mc = MonitorConfig()
        merged = mc.merge_with_default(body)
        mc.save(g.current_user["user_id"], merged)
        return jsonify({"success": True, "data": merged})
    except Exception as e:
        logger.error(f"Save monitor config failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/portfolio", methods=["GET"])
@login_required
def get_monitor_portfolio():
    """读最近一次 refresh_all 的双轨道调仓建议 + 组合概览 + 异动预警。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        uid = g.current_user["user_id"]
        doc = (db["monitor_signals"].find_one({"type": "portfolio_advice", "user_id": uid})
               or db["monitor_signals"].find_one({"type": "portfolio_advice", "user_id": "default"}))
        if not doc:
            return jsonify({"success": True, "data": None})
        doc.pop("_id", None)
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.error(f"Get monitor portfolio failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
