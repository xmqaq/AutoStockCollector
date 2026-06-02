"""
API路由定义
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import time
import threading
from utils.logger import get_logger
from modules.ai.engines.analysis import AnalysisEngine
from modules.ai.engines.advice import AdviceEngine
from modules.ai.engines.picker import PickerEngine

logger = get_logger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# 8 类数据按时间语义分组（采集规划唯一事实来源）
RANGE_TYPES = ["kline", "financial", "dragon_tiger", "margin"]   # 按日期区间
SNAPSHOT_TYPES = ["news", "fund_flow", "sector"]                 # 仅当前快照
CATALOG_TYPES = ["stock_info"]                                   # 全量名录


def _normalize_code(code: str) -> str:
    """统一股票代码格式，支持多种输入格式"""
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


# ============================================================================
# 实时数据补全：百度估值 + Sina K线
# 数据库里的 stock_info 来自 cninfo（无 PE/PB/总市值），kline 来自腾讯（无 volume）
# 在路由层用 AKShare 接口补齐
# ============================================================================
_realtime_cache: Dict[str, tuple] = {}  # key -> (timestamp, value)
_cache_lock = threading.Lock()
_CACHE_TTL = 60.0  # 秒


def _cache_get(key: str):
    with _cache_lock:
        item = _realtime_cache.get(key)
        if item and (time.time() - item[0]) < _CACHE_TTL:
            return item[1]
    return None


def _cache_set(key: str, value):
    with _cache_lock:
        _realtime_cache[key] = (time.time(), value)


def _fetch_valuation(bare_code: str) -> Dict[str, Optional[float]]:
    """通过百度估值接口拉取 PE/PB/总市值（单位：亿元 → 元）"""
    cache_key = f"valuation_{bare_code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    import akshare as ak
    result = {"pe": None, "pe_static": None, "pb": None, "total_mv": None}
    indicators = [
        ("pe", "市盈率(TTM)"),
        ("pe_static", "市盈率(静)"),
        ("pb", "市净率"),
        ("total_mv_yi", "总市值"),  # 单位亿元
    ]
    for field, ind in indicators:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=bare_code, indicator=ind, period="近一年")
            if df is not None and not df.empty:
                val = df.iloc[-1].get("value")
                if val is not None:
                    if field == "total_mv_yi":
                        result["total_mv"] = float(val) * 1e8  # 亿 → 元
                    else:
                        result[field] = float(val)
        except Exception:
            continue
    _cache_set(cache_key, result)
    return result


def _fetch_kline_with_volume(full_code: str) -> Dict[str, Dict]:
    """新浪 stock_zh_a_daily 全量历史 → {date_str: {volume/amount/change_rate/turnover_rate}}
    full_code: 'sh600000' / 'sz000001'，按整支股票缓存（外部接口的最小调用单位也是整支）
    """
    sym = full_code.lower()
    cache_key = f"kline_daily_{sym}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    import akshare as ak
    out: Dict[str, Dict] = {}
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust="qfq")
        if df is not None and not df.empty:
            prev_close = None
            for _, row in df.iterrows():
                date_val = row.get("date")
                date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
                close = float(row.get("close") or 0)
                volume_shares = float(row.get("volume") or 0)
                amount_yuan = float(row.get("amount") or 0)
                turnover_decimal = float(row.get("turnover") or 0)
                # 涨跌幅由相邻收盘价计算
                change_rate = ((close - prev_close) / prev_close * 100) if prev_close and prev_close > 0 else 0.0
                out[date_str] = {
                    "volume": volume_shares,  # 单位：股
                    "amount": amount_yuan,    # 单位：元
                    "change_rate": round(change_rate, 4),
                    "turnover_rate": round(turnover_decimal * 100, 4),  # 百分比
                }
                prev_close = close
    except Exception:
        pass
    _cache_set(cache_key, out)
    return out


def register_routes(app):
    from api.routes.ai_advanced import ai_advanced_bp
    from api.routes.monitor import monitor_bp
    from api.routes.sentiment import sentiment_bp
    from api.routes.paper_trading import paper_bp
    from api.routes.market import market_bp
    from api.routes.ai_agent import ai_agent_bp
    from api.routes.workflow import workflow_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(ai_advanced_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(sentiment_bp)
    app.register_blueprint(paper_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(ai_agent_bp)
    app.register_blueprint(workflow_bp)

    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat()
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "Not Found",
            "message": "The requested resource was not found"
        }), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e)
        }), 500


@api_bp.route("/task/create", methods=["POST"])
def create_task():
    from core.scheduler.scheduler import scheduler

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    task_type = data.get("task_type")
    params = data.get("params", {})

    if not task_type:
        return jsonify({"error": "task_type is required"}), 400

    try:
        task_id = scheduler.create_task(task_type, params)
        return jsonify({
            "success": True,
            "task_id": task_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/task/<task_id>", methods=["GET"])
def get_task(task_id):
    from core.scheduler.scheduler import scheduler

    if not task_id:
        return jsonify({"error": "task_id is required"}), 400

    task = scheduler.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task)


@api_bp.route("/task/<task_id>/start", methods=["POST"])
def start_task(task_id):
    from core.scheduler.scheduler import scheduler

    if not task_id:
        return jsonify({"error": "task_id is required"}), 400

    success = scheduler.start_task(task_id)
    if not success:
        return jsonify({"error": "Failed to start task"}), 400

    return jsonify({"success": True, "message": "Task started"})


@api_bp.route("/task/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    from core.scheduler.scheduler import scheduler

    if not task_id:
        return jsonify({"error": "task_id is required"}), 400

    success = scheduler.cancel_task(task_id)
    if not success:
        return jsonify({"error": "Failed to cancel task"}), 400

    return jsonify({"success": True, "message": "Task cancelled"})


@api_bp.route("/task/<task_id>/retry", methods=["POST"])
def retry_task(task_id):
    from core.scheduler.scheduler import scheduler

    if not task_id:
        return jsonify({"error": "task_id is required"}), 400

    success = scheduler.retry_failed_task(task_id)
    if not success:
        return jsonify({"error": "Failed to retry task"}), 400

    return jsonify({"success": True, "message": "Task retry initiated"})


@api_bp.route("/task/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    """删除单个历史任务。运行中/等待中的任务需先取消。"""
    from core.scheduler.scheduler import scheduler

    if not task_id:
        return jsonify({"error": "task_id is required"}), 400

    task = scheduler.get_task(task_id)
    if task and task.get("status") in ("running", "pending"):
        return jsonify({"error": "任务运行中，请先取消再删除"}), 400

    ok = scheduler.delete_task(task_id)
    return jsonify({"success": ok})


@api_bp.route("/tasks/clear", methods=["POST"])
def clear_finished_tasks():
    """清空所有终态任务（completed/failed/cancelled），保留运行中/等待中。"""
    from core.scheduler.scheduler import scheduler

    deleted = scheduler.clear_finished_tasks()
    return jsonify({"success": True, "deleted": deleted})


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    from core.scheduler.scheduler import scheduler

    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))

    tasks = scheduler.list_tasks(status=status, limit=limit)
    return jsonify({
        "success": True,
        "tasks": tasks
    })


@api_bp.route("/tasks", methods=["POST"])
def create_task_v2():
    """别名路由：兼容前端 POST /tasks（与 /task/create 等价）"""
    from core.scheduler.scheduler import scheduler

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    task_type = data.get("task_type")
    params = data.get("params", {})

    if not task_type:
        return jsonify({"error": "task_type is required"}), 400

    try:
        task_id = scheduler.create_task(task_type, params)
        return jsonify({"success": True, "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/kline/<code>", methods=["GET"])
def get_kline(code):
    from core.storage.mongo_storage import KlineStorage

    code = _normalize_code(code)
    if not code:
        return jsonify({"error": "code is required"}), 400

    storage = KlineStorage()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if start_date and end_date:
        records = storage.query_by_date_range(code, "date", start_date, end_date)
    else:
        records = storage.find_many({"code": code}, sort=[("date", -1)])

    for record in records:
        record.pop("_id", None)
        record.pop("_updated_at", None)
        # 将 datetime 对象统一转为 YYYY-MM-DD 字符串
        if "date" in record and hasattr(record["date"], "strftime"):
            record["date"] = record["date"].strftime("%Y-%m-%d")

    # 检查首条是否缺 volume —— 数据库里 kline 来自腾讯接口，没有成交量/涨跌幅/换手率
    need_augment = bool(records) and (
        "volume" not in records[0] or records[0].get("volume") in (None, 0)
    )
    if need_augment:
        vol_map = _fetch_kline_with_volume(code.lower())
        # 新浪权威字段，直接覆盖（DB 里 amount 是腾讯接口的"千元"单位，与 volume/turnover 不一致）
        AUTHORITATIVE = {"volume", "amount", "change_rate", "turnover_rate"}
        for r in records:
            ext = vol_map.get(r.get("date"))
            if not ext:
                continue
            for k, v in ext.items():
                if k in AUTHORITATIVE:
                    r[k] = v  # 强制以新浪元单位为准
                elif r.get(k) in (None, 0) or k not in r:
                    r[k] = v

    return jsonify({
        "success": True,
        "code": code,
        "count": len(records),
        "data": records
    })


@api_bp.route("/kline/<code>/latest", methods=["GET"])
def get_latest_kline(code):
    from core.storage.mongo_storage import KlineStorage

    code = _normalize_code(code)
    storage = KlineStorage()
    record = storage.find_one({"code": code}, sort=[("date", -1)])

    if not record:
        return jsonify({"error": "No data found"}), 404
    
    record.pop("_id", None)
    record.pop("_updated_at", None)

    return jsonify({
        "success": True,
        "data": record
    })


@api_bp.route("/stock/<code>/info", methods=["GET"])
def get_stock_info(code):
    from core.storage.mongo_storage import StockInfoStorage

    code = _normalize_code(code)
    storage = StockInfoStorage()
    info = storage.get_by_code(code) or {"code": code}

    # 用百度估值接口补齐 PE/PB/总市值（DB 里只有 cninfo 公司简介，没这几个字段）
    bare = code[2:] if code[:2] in ("SH", "SZ") else code
    try:
        valuation = _fetch_valuation(bare)
        # 不覆盖已有的非空值（极少数情况采集器可能补过），但 注册资金 ≠ 总市值，必须覆盖
        for k, v in valuation.items():
            if v is not None:
                info[k] = v
    except Exception:
        pass

    # 统一暴露常用字段，前端不用再处理中文字段名
    info["name"] = info.get("name") or info.get("A股简称") or info.get("公司名称") or ""
    info["industry"] = info.get("industry") or info.get("所属行业") or ""
    info["list_date"] = info.get("list_date") or info.get("上市日期") or ""
    info["area"] = info.get("area") or info.get("注册地址") or info.get("办公地址") or ""
    # pe 字段已通过百度 TTM 接口写入；pe_static 为静态PE供对比
    # 前端可区分展示 pe（TTM）和 pe_static（静态）

    if not info or len(info) <= 1:
        return jsonify({"error": "Stock info not found"}), 404

    return jsonify({
        "success": True,
        "data": info
    })


def _map_financial_record(r: dict) -> dict:
    """将财务记录中文字段名统一映射为英文，兼容 AKShare 直接存储的 DataFrame 列名"""
    r.pop("_id", None)
    r.pop("_updated_at", None)
    # 报告期字段
    report_date = (
        r.get("report_date") or r.get("报告期") or r.get("日期") or ""
    )
    if hasattr(report_date, "strftime"):
        report_date = report_date.strftime("%Y-%m-%d")
    elif isinstance(report_date, str) and len(report_date) == 8 and report_date.isdigit():
        report_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    return {
        "code": r.get("code", ""),
        "report_date": str(report_date)[:10],
        "net_profit": r.get("net_profit") or r.get("净利润") or r.get("净利润(元)") or 0,
        "revenue":    r.get("revenue")    or r.get("营业收入") or r.get("营业总收入(元)") or 0,
        "roe":        r.get("roe")        or r.get("ROE") or r.get("净资产收益率") or 0,
        "roa":        r.get("roa")        or r.get("ROA") or r.get("总资产收益率") or 0,
        "eps":        r.get("eps")        or r.get("EPS") or r.get("每股收益") or 0,
        "bps":        r.get("bps")        or r.get("BPS") or r.get("每股净资产") or 0,
        **{k: v for k, v in r.items() if k not in (
            "code", "report_date", "net_profit", "revenue", "roe", "roa", "eps", "bps",
            "报告期", "日期", "净利润", "净利润(元)", "营业收入", "营业总收入(元)",
            "ROE", "净资产收益率", "ROA", "总资产收益率", "EPS", "每股收益", "BPS", "每股净资产"
        )},
    }


@api_bp.route("/financial/<code>", methods=["GET"])
def get_financial(code):
    from core.storage.mongo_storage import FinancialStorage

    code = _normalize_code(code)
    storage = FinancialStorage()
    report_date = request.args.get("report_date")

    if report_date:
        record = storage.get_by_code_and_period(code, report_date)
        records = [_map_financial_record(record)] if record else []
    else:
        raw = storage.find_many({"code": code}, sort=[("report_date", -1)])
        if not raw:
            # 兼容中文报告期字段名排序
            raw = storage.find_many({"code": code}, sort=[("报告期", -1)])
        records = [_map_financial_record(r) for r in raw]

    return jsonify({
        "success": True,
        "count": len(records),
        "data": records
    })


@api_bp.route("/news", methods=["GET"])
def get_news():
    from modules.news import NewsManager
    from core.storage.mongo_storage import NewsStorage

    news_type = request.args.get("type")
    channel_name = request.args.get("channel")
    is_breaking = request.args.get("breaking")
    limit = int(request.args.get("limit", 100))
    code = request.args.get("code", "").strip()

    breaking_filter = None
    if is_breaking is not None:
        breaking_filter = is_breaking.lower() in ("true", "1", "yes")

    # 按股票代码/关键词搜索（全文匹配标题和内容）
    if code:
        storage = NewsStorage()
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        query = {"$or": [
            {"title": {"$regex": bare, "$options": "i"}},
            {"content": {"$regex": bare, "$options": "i"}},
        ]}
        if news_type:
            query["news_type"] = news_type
        records = storage.find_many(query, sort=[("publish_date", -1), ("_updated_at", -1)], limit=limit)
        for r in records:
            r.pop("_id", None)
            r.pop("_updated_at", None)
            r.pop("_collect_at", None)
        return jsonify({"success": True, "count": len(records), "data": records})

    manager = NewsManager()
    records = manager.get_news(
        news_type=news_type,
        channel_name=channel_name,
        is_breaking=breaking_filter,
        limit=limit
    )
    manager.close()

    return jsonify({
        "success": True,
        "count": len(records),
        "data": records
    })


@api_bp.route("/news/stats", methods=["GET"])
def get_news_stats():
    from modules.news import NewsManager

    manager = NewsManager()
    stats = manager.get_stats()
    manager.close()

    return jsonify({
        "success": True,
        "data": stats
    })


@api_bp.route("/news/categories", methods=["GET"])
def get_news_categories():
    from modules.news import NewsManager

    manager = NewsManager()
    categories = manager.get_categories()
    manager.close()

    return jsonify({
        "success": True,
        "data": categories
    })


@api_bp.route("/news/breaking", methods=["GET"])
def get_breaking_news():
    from modules.news import NewsManager

    manager = NewsManager()
    limit = int(request.args.get("limit", 20))
    records = manager.get_breaking(limit=limit)
    manager.close()

    return jsonify({
        "success": True,
        "count": len(records),
        "data": records
    })


@api_bp.route("/fund-flow/rank", methods=["GET"])
def get_fund_flow_rank():
    """全市场资金流向排行，按主力净流入降序。
    ?limit=50&date=2026-06-01
    """
    from core.storage.mongo_storage import FundFlowStorage

    limit = int(request.args.get("limit", 50))
    date_filter = request.args.get("date")
    storage = FundFlowStorage()

    query = {}
    if date_filter:
        query["date"] = date_filter
    else:
        # 取最新一天的数据
        latest = storage.find_one({"date": {"$exists": True}}, sort=[("date", -1)])
        if latest:
            query["date"] = latest.get("date")

    records = storage.find_many(
        {**query, "main_net_inflow": {"$exists": True}},
        sort=[("main_net_inflow", -1)],
        limit=limit
    )
    for r in records:
        r.pop("_id", None)
        r.pop("_updated_at", None)

    return jsonify({
        "success": True,
        "count": len(records),
        "date": query.get("date"),
        "data": records
    })


@api_bp.route("/fund-flow/<code>", methods=["GET"])
def get_fund_flow(code):
    from core.storage.mongo_storage import FundFlowStorage

    code = _normalize_code(code)
    storage = FundFlowStorage()
    bare_code = code[2:] if code[:2] in ("SH", "SZ") else code
    record = storage.get_latest_flow(bare_code)

    if not record:
        return jsonify({"error": "No fund flow data found"}), 404

    return jsonify({
        "success": True,
        "data": record
    })


@api_bp.route("/validation/<data_type>", methods=["POST"])
def validate_data(data_type):
    from core.validator.validator import DataValidator

    data = request.get_json() or {}
    codes = data.get("codes", [])
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    validator = DataValidator()
    results = validator.validate_batch(
        codes,
        data_type=data_type,
        start_date=start_date,
        end_date=end_date
    )

    return jsonify({
        "success": True,
        "results": [r.to_dict() for r in results]
    })


@api_bp.route("/validation/report", methods=["GET"])
def validation_report():
    from core.validator.validator import DataValidator

    data_type = request.args.get("data_type", "kline")

    validator = DataValidator()
    report = validator.generate_validation_report(data_type=data_type)

    return jsonify({
        "success": True,
        "report": report
    })


@api_bp.route("/validation/gaps", methods=["GET"])
def check_gaps():
    from core.validator.validator import DataValidator

    code = request.args.get("code")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    data_type = request.args.get("data_type", "kline")

    if not all([code, start_date, end_date]):
        return jsonify({"error": "code, start_date, end_date are required"}), 400

    validator = DataValidator()
    gaps = validator.check_data_gaps(
        code=code,
        start_date=start_date,
        end_date=end_date,
        data_type=data_type
    )

    return jsonify({
        "success": True,
        "code": code,
        "missing_dates": gaps,
        "missing_count": len(gaps)
    })


@api_bp.route("/watchlist", methods=["GET"])
def get_watchlist():
    from modules.watchlist.watchlist import WatchlistManager

    user_id = request.args.get("user_id", "default")

    manager = WatchlistManager()
    stocks = manager.get_watchlist(user_id)

    for stock in stocks:
        if "add_time" in stock and hasattr(stock["add_time"], "isoformat"):
            stock["add_time"] = stock["add_time"].isoformat()

    return jsonify({
        "success": True,
        "count": len(stocks),
        "data": stocks
    })


@api_bp.route("/watchlist", methods=["POST"])
def add_to_watchlist():
    from modules.watchlist.watchlist import WatchlistManager

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = data.get("user_id", "default")
    code = data.get("code")
    priority = data.get("priority", 0)

    if not code:
        return jsonify({"error": "code is required"}), 400

    manager = WatchlistManager()
    success = manager.add_stock(user_id, code, priority)

    return jsonify({
        "success": success,
        "message": "Added to watchlist" if success else "Failed to add"
    })


@api_bp.route("/watchlist/<code>", methods=["DELETE"])
def remove_from_watchlist(code):
    from modules.watchlist.watchlist import WatchlistManager

    code = _normalize_code(code)
    user_id = request.args.get("user_id", "default")

    manager = WatchlistManager()
    success = manager.remove_stock(user_id, code)

    return jsonify({
        "success": success,
        "message": "Removed from watchlist" if success else "Failed to remove"
    })


@api_bp.route("/ai/analyze", methods=["POST"])
def analyze_stock():
    from modules.ai.ai_analyzer import AIAnalyzer

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    code = data.get("code")
    analysis_type = data.get("type", "comprehensive")

    if not code:
        return jsonify({"error": "code is required"}), 400

    analyzer = AIAnalyzer()
    try:
        result = analyzer.analyze(code, analysis_type)
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/ai/stock/<code>/analysis", methods=["GET"])
def ai_stock_analysis(code):
    """个股深度分析（底座层引擎）。"""
    normalized = _normalize_code(code)
    if not normalized:
        return jsonify({"success": False, "error": "invalid code"}), 400
    try:
        result = AnalysisEngine().analyze(normalized)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"AI stock analysis failed for {code}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _latest_pick_result():
    """读 ai_pick_results 集合最近一条选股结果。"""
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    return db["ai_pick_results"].find_one({}, {"_id": 0}, sort=[("timestamp", -1)])


@api_bp.route("/ai/stock/<code>/advice", methods=["POST"])
def ai_stock_advice(code):
    """买卖参考建议。"""
    normalized = _normalize_code(code)
    if not normalized:
        return jsonify({"success": False, "error": "invalid code"}), 400
    data = request.get_json() or {}
    try:
        result = AdviceEngine().advise(
            normalized, cost=data.get("cost"), position=data.get("position")
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"AI advice failed for {code}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


_pick_running = False  # 简单互斥，防止重复触发

@api_bp.route("/ai/pick/run", methods=["POST"])
def ai_pick_run():
    """触发 AI 智能选股（两阶段漏斗）。后台线程执行，立即返回。"""
    global _pick_running
    if _pick_running:
        return jsonify({"success": False, "error": "已有选股任务正在运行，请稍后刷新结果"}), 409

    data = request.get_json() or {}
    strategy = data.get("strategy", "default")
    top_n = data.get("top_n", 10)
    candidate_pool = data.get("candidate_pool", 50)

    def _run_async():
        global _pick_running
        _pick_running = True
        try:
            PickerEngine().run(strategy=strategy, top_n=top_n, candidate_pool=candidate_pool)
        except Exception as e:
            logger.error(f"AI pick run failed: {e}")
        finally:
            _pick_running = False

    import threading
    t = threading.Thread(target=_run_async, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "选股任务已启动，请 1-3 分钟后刷新结果"})


@api_bp.route("/ai/chat", methods=["POST"])
def ai_chat():
    """通用AI对话接口，支持多轮对话历史"""
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    message = data.get("message", "")
    provider = data.get("provider")
    history = data.get("history", [])  # [{role: 'user'|'assistant', content: '...'}]

    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    try:
        router = LLMRouter()
        if provider:
            router.providers = [provider]

        # 构建多轮对话 messages（最多保留最近10条历史）
        messages = None
        if history:
            valid_history = [
                {"role": m["role"], "content": m["content"]}
                for m in history[-10:]
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
            if valid_history:
                messages = valid_history + [{"role": "user", "content": message}]

        result = router.chat(message, use_cache=not messages, messages=messages)
        if result.success:
            return jsonify({
                "success": True,
                "data": {
                    "content": result.raw,
                    "provider": result.provider,
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error or "AI服务暂不可用"
            }), 500
    except Exception as e:
        logger.error(f"AI chat failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai/chat/stream", methods=["POST"])
def ai_chat_stream():
    """流式AI对话接口，支持多轮对话历史，SSE格式返回"""
    import json as _json
    from flask import Response
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    message = data.get("message", "")
    provider = data.get("provider")
    history = data.get("history", [])

    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    # 构建多轮对话 messages（最多保留最近10条历史）
    valid_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-10:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages = valid_history + [{"role": "user", "content": message}]

    def generate():
        try:
            router = LLMRouter()
            if provider:
                router.providers = [provider]

            full_content = ""
            for chunk in router.chat_stream("", messages=messages):
                if chunk:
                    full_content += chunk
                    yield f"data: {_json.dumps({'type': 'content', 'data': chunk})}\n\n"

            yield f"data: {_json.dumps({'type': 'done', 'data': {'content': full_content}})}\n\n"
        except Exception as e:
            logger.error(f"AI chat stream failed: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_bp.route("/ai/analyze-news", methods=["POST"])
def ai_analyze_news():
    """用 LLM 对单条新闻进行情绪/信号分析。
    Body: { "news": { "title": str, "content": str, ... } }
    Returns: { success, data: { signal, summary, provider } }
    """
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    news = data.get("news") or {}
    title = news.get("title", "")
    content = news.get("content", "")

    if not title and not content:
        return jsonify({"success": False, "error": "news title or content is required"}), 400

    prompt = (
        f"请对以下财经新闻进行简短分析，判断对A股市场的影响，"
        f"给出信号（利好/利空/中性/观望）和一句话摘要。\n\n"
        f"标题：{title}\n"
        f"内容：{content[:500] if content else '（无正文）'}\n\n"
        f"请用JSON格式回复，字段：signal（利好/利空/中性/观望）、summary（不超过50字）。"
    )

    try:
        router = LLMRouter()
        result = router.chat(prompt, use_cache=False)
        if not result.success:
            return jsonify({"success": False, "error": result.error or "AI服务暂不可用"}), 500

        raw = result.raw or ""
        import re, json as _json
        signal = "观望"
        summary = raw[:100]
        m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if m:
            try:
                parsed = _json.loads(m.group())
                signal = parsed.get("signal", signal)
                summary = parsed.get("summary", summary)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "data": {
                "signal": signal,
                "summary": summary,
                "provider": result.provider,
            }
        })
    except Exception as e:
        logger.error(f"AI analyze-news failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/ai/pick/results", methods=["GET"])
def ai_pick_results():
    """读最近一次选股结果（缓存）。"""
    try:
        doc = _latest_pick_result()
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.error(f"AI pick results failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scheduler/stats", methods=["GET"])
def get_scheduler_stats():
    from core.scheduler.scheduler import scheduler

    stats = scheduler.get_task_statistics()
    return jsonify({
        "success": True,
        "stats": stats
    })


@api_bp.route("/collect/cron_status", methods=["GET"])
def get_cron_status():
    """返回所有定时任务的下次执行时间、最近执行结果和告警状态。"""
    try:
        from core.scheduler.cron import get_cron_status
        jobs = get_cron_status()
        has_alert = any(j.get("alert") for j in jobs)
        return jsonify({
            "success": True,
            "jobs": jobs,
            "has_alert": has_alert,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "jobs": []}), 200


@api_bp.route("/collect/kline", methods=["POST"])
def collect_kline():
    from core.collector.kline_collector import KlineCollector
    from core.storage.mongo_storage import KlineStorage

    data = request.get_json() or {}
    codes = data.get("codes", [])
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    adjust = data.get("adjust", "qfq")

    collector = KlineCollector()
    storage = KlineStorage()

    if not codes:
        codes = collector.get_all_stock_codes()

    records = collector.collect(
        codes=codes[:10],
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )

    if records:
        storage.save_kline_batch(records)

    return jsonify({
        "success": True,
        "collected_count": len(records),
        "code_count": len(codes)
    })


@api_bp.route("/collect/incremental", methods=["POST"])
def collect_incremental():
    from core.collector.kline_collector import KlineCollector
    from core.storage.mongo_storage import KlineStorage

    data = request.get_json() or {}
    codes = data.get("codes", [])

    collector = KlineCollector()
    storage = KlineStorage()

    if not codes:
        codes = collector.get_all_stock_codes()

    results = collector.collect_batch_incremental(codes=codes[:10])

    return jsonify({
        "success": True,
        "results": results
    })


@api_bp.route("/collect/index", methods=["POST"])
def collect_index():
    from core.collector.index_collector import IndexCollector

    data = request.get_json() or {}
    index_codes = data.get("index_codes")

    collector = IndexCollector()
    results = collector.collect(index_codes=index_codes)

    return jsonify({
        "success": True,
        "results": results
    })


@api_bp.route("/index/<index_code>/components", methods=["GET"])
def get_index_components(index_code):
    from core.collector.index_collector import IndexCollector

    collector = IndexCollector()
    components = collector.get_index_components(index_code)

    for comp in components:
        comp.pop("_id", None)

    return jsonify({
        "success": True,
        "index_code": index_code,
        "count": len(components),
        "components": components
    })


@api_bp.route("/stock/<stock_code>/indices", methods=["GET"])
def get_stock_indices(stock_code):
    from core.collector.index_collector import IndexCollector

    collector = IndexCollector()
    indices = collector.get_stock_indices(stock_code)

    return jsonify({
        "success": True,
        "stock_code": stock_code,
        "indices": indices
    })


@api_bp.route("/collect/news", methods=["POST"])
def collect_news():
    from modules.news import NewsManager

    data = request.get_json() or {}
    channels = data.get("channels")
    max_pages = data.get("max_pages", 5)
    with_content = data.get("with_content", False)

    manager = NewsManager()
    start_time = datetime.now()

    results = manager.collect(
        channels=channels,
        max_pages=max_pages,
        with_content=with_content
    )

    total_collected = sum(results.values())
    elapsed = (datetime.now() - start_time).total_seconds()
    manager.close()
    
    return jsonify({
        "success": True,
        "collected_count": total_collected,
        "channel_results": results,
        "elapsed_seconds": round(elapsed, 2),
        "collector": "sina_news"
    })


@api_bp.route("/collect/stock_info", methods=["POST"])
def collect_stock_info():
    from core.collector.stock_info_collector import StockInfoCollector
    from core.storage.mongo_storage import StockInfoStorage

    data = request.get_json() or {}
    codes = data.get("codes")

    collector = StockInfoCollector()
    storage = StockInfoStorage()

    start_time = datetime.now()
    if codes:
        records = collector.collect(codes=codes[:20])
    else:
        records = collector.collect(codes=None)

    elapsed = (datetime.now() - start_time).total_seconds()
    return jsonify({
        "success": True,
        "collected_count": len(records) if records else 0,
        "elapsed_seconds": round(elapsed, 2)
    })


@api_bp.route("/collect/financial", methods=["POST"])
def collect_financial():
    from core.collector.financial_collector import FinancialCollector
    from core.storage.mongo_storage import FinancialStorage

    data = request.get_json() or {}
    codes = data.get("codes", [])
    report_type = data.get("report_type", "annual")

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    collector = FinancialCollector()

    start_time = datetime.now()
    records = collector.collect(codes=codes[:5], report_type=report_type)
    elapsed = (datetime.now() - start_time).total_seconds()

    return jsonify({
        "success": True,
        "collected_count": len(records),
        "elapsed_seconds": round(elapsed, 2)
    })


@api_bp.route("/collect/fund_flow", methods=["POST"])
def collect_fund_flow():
    from core.collector.fund_flow_collector import FundFlowCollector
    from core.storage.mongo_storage import FundFlowStorage

    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    collector = FundFlowCollector()

    start_time = datetime.now()
    records = collector.collect(codes=codes[:5])
    elapsed = (datetime.now() - start_time).total_seconds()

    return jsonify({
        "success": True,
        "collected_count": len(records),
        "elapsed_seconds": round(elapsed, 2)
    })


@api_bp.route("/collect/dragon_tiger", methods=["POST"])
def collect_dragon_tiger():
    from core.collector.fund_flow_collector import DragonTigerCollector

    data = request.get_json() or {}
    date = data.get("date")

    collector = DragonTigerCollector()

    start_time = datetime.now()
    records = collector.collect(date=date)
    elapsed = (datetime.now() - start_time).total_seconds()

    return jsonify({
        "success": True,
        "collected_count": len(records),
        "elapsed_seconds": round(elapsed, 2)
    })


@api_bp.route("/collect/sector", methods=["POST"])
def collect_sector():
    from core.collector.fund_flow_collector import FundFlowCollector

    collector = FundFlowCollector()

    start_time = datetime.now()
    df = collector.collect_sector_flow()
    elapsed = (datetime.now() - start_time).total_seconds()

    records = df.to_dict("records") if df is not None and not df.empty else []
    return jsonify({
        "success": True,
        "collected_count": len(records),
        "elapsed_seconds": round(elapsed, 2),
        "sample": records[:3] if records else []
    })


@api_bp.route("/collect/dividend", methods=["POST"])
def collect_dividend():
    from core.collector.financial_collector import DividendCollector

    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    collector = DividendCollector()

    start_time = datetime.now()
    records = collector.collect(codes=codes[:5])
    elapsed = (datetime.now() - start_time).total_seconds()

    return jsonify({
        "success": True,
        "collected_count": len(records),
        "elapsed_seconds": round(elapsed, 2)
    })


_DATA_TYPE_COLLECTION_MAP = {
    "kline":        "kline",
    "stock_info":   "stock_info",
    "financial":    "financial",
    "news":         "news",
    "fund_flow":    "fund_flow",
    "dragon_tiger": "dragon_tiger",
    "sector":       "block",
    "margin":       "margin_data",
}

_ALL_COLLECTIONS = list(_DATA_TYPE_COLLECTION_MAP.values())


@api_bp.route("/db/clear", methods=["POST"])
def clear_collections():
    """清空指定的数据集合，默认清空所有8类数据"""
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    collections = data.get("collections", _ALL_COLLECTIONS)

    db = DatabaseConfig.get_database()
    results = {}
    for coll in collections:
        try:
            result = db[coll].delete_many({})
            results[coll] = result.deleted_count
        except Exception as e:
            results[coll] = f"error: {e}"

    _invalidate_stats_cache()
    return jsonify({
        "success": True,
        "deleted": results,
        "timestamp": datetime.now().isoformat()
    })


@api_bp.route("/collect/clear_single", methods=["POST"])
def clear_single_collection():
    """按数据类型清空单个集合。
    Body: {"data_type": "kline"}
    data_type 可选值：kline / stock_info / financial / news / fund_flow / dragon_tiger / sector / margin
    """
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    data_type = data.get("data_type")

    if not data_type:
        return jsonify({"error": "data_type is required"}), 400

    coll_name = _DATA_TYPE_COLLECTION_MAP.get(data_type)
    if not coll_name:
        return jsonify({"error": f"Unknown data_type: {data_type}. Valid: {list(_DATA_TYPE_COLLECTION_MAP)}"}), 400

    db = DatabaseConfig.get_database()
    try:
        result = db[coll_name].delete_many({})
        _invalidate_stats_cache()
        return jsonify({
            "success": True,
            "data_type": data_type,
            "collection": coll_name,
            "deleted_count": result.deleted_count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _build_history_tasks(start_date: str, end_date: str, task_types=None) -> list:
    """构建历史采集任务，支持全部8类数据类型。

    range 类（kline/financial/dragon_tiger/margin/fund_flow/news）按日期区间采集；
    snapshot 类（sector）只采最新快照（忽略日期参数）；
    catalog 类（stock_info）触发全量刷新（忽略日期参数）。
    """
    all_tasks_cfg = {
        # 区间历史类
        "kline":        {"start_date": start_date, "end_date": end_date, "adjust": "qfq"},
        "financial":    {"report_type": "annual", "start_date": start_date, "end_date": end_date},
        "dragon_tiger": {"start_date": start_date, "end_date": end_date},
        "margin":       {"start_date": start_date, "end_date": end_date},
        "fund_flow":    {},   # 快照接口，无历史数据，忽略日期参数
        "news":         {"max_pages": 5, "with_content": False},  # 只抓标题列表，避免长时间卡死
        # 快照类（日期无效，只采最新）
        "sector":       {},
        # 名录类（全量刷新）
        "stock_info":   {"mode": "full"},
    }
    selected = task_types if task_types else (RANGE_TYPES + SNAPSHOT_TYPES + CATALOG_TYPES)
    return [
        {"task_type": t, "params": all_tasks_cfg[t]}
        for t in (RANGE_TYPES + SNAPSHOT_TYPES + CATALOG_TYPES)
        if t in selected and t in all_tasks_cfg
    ]


@api_bp.route("/collect/history", methods=["POST"])
def start_history_collection():
    """启动历史数据全量采集，通过 start_date/end_date 指定时间范围

    Body 参数:
      start_date  (必填) 开始日期，格式 YYYY-MM-DD，如 2025-01-01
      end_date    (必填) 结束日期，格式 YYYY-MM-DD，如 2025-12-31
      task_types  (可选) 指定只跑哪几类，如 ["kline","financial"]，默认全部8类
    """
    from core.scheduler.scheduler import scheduler

    data = request.get_json() or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    task_types = data.get("task_types")

    if not start_date or not end_date:
        return jsonify({"error": "start_date 和 end_date 均为必填项，格式 YYYY-MM-DD"}), 400

    tasks = _build_history_tasks(start_date, end_date, task_types)

    started = {}
    failed = {}
    for task_cfg in tasks:
        ttype = task_cfg["task_type"]
        try:
            task_id = scheduler.create_task(ttype, task_cfg["params"])
            scheduler.start_task(task_id)
            started[ttype] = task_id
        except Exception as e:
            failed[ttype] = str(e)

    return jsonify({
        "success": True,
        "start_date": start_date,
        "end_date": end_date,
        "started": started,
        "failed": failed,
        "total_started": len(started),
        "timestamp": datetime.now().isoformat()
    })


def _get_effective_end_date(today: str) -> str:
    """返回最近的 A 股交易日（跳过周末；公众假日由调用者自行处理）。
    17:00 前用昨日，之后用今日；再向前滚直到落在周一~周五。
    """
    from datetime import datetime, timedelta, timezone
    beijing_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    d = datetime.strptime(today, "%Y-%m-%d")
    if beijing_now.hour < 17:
        d -= timedelta(days=1)
    # 向前滚到最近的工作日（周六=5，周日=6）
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _compute_update_latest_tasks(stats: dict, task_types=None, today: str = None,
                                  already_collected: set = None, force: bool = False):
    """根据各类数据当前覆盖情况，计算"更新到最新"应提交的任务。

    stats: _get_collection_stats(db) 的返回，形如
           {type: {"record_count": int, "date_from": str|None, "date_to": str|None}}
    already_collected: 今日已采集的快照类型集合，直接跳过（force=True 时忽略此参数）
    force: True=跳过"已是最新"判断，总是强制创建任务（用于"立即更新"按钮）
    返回: (tasks, skipped)
          tasks  = [{"task_type": str, "params": dict}, ...]
          skipped = [type, ...]
    """
    from datetime import datetime, timedelta

    already_collected = already_collected or set()
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    effective_end = _get_effective_end_date(today)

    all_types = RANGE_TYPES + SNAPSHOT_TYPES + CATALOG_TYPES
    selected = task_types if task_types else all_types

    tasks, skipped = [], []
    for t in selected:
        if t in RANGE_TYPES:
            date_to = (stats.get(t) or {}).get("date_to")
            if not force and date_to and date_to >= effective_end:
                skipped.append(t)
                continue
            if date_to:
                start = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                start = (datetime.strptime(effective_end, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            # force 时至少采最近1个交易日，避免 start > end
            if force and start > effective_end:
                start = effective_end
            params = {"start_date": start, "end_date": effective_end}
            if t == "kline":
                params["adjust"] = "qfq"
            elif t == "financial":
                params["report_type"] = "annual"
            tasks.append({"task_type": t, "params": params})
        elif t in SNAPSHOT_TYPES:
            if not force and t in already_collected:
                skipped.append(t)
                continue
            params = {"max_pages": 5, "with_content": False} if t == "news" else {}
            tasks.append({"task_type": t, "params": params})
        elif t in CATALOG_TYPES:
            tasks.append({"task_type": t, "params": {"mode": "incremental"}})
    return tasks, skipped


@api_bp.route("/collect/update_latest", methods=["POST"])
def start_update_latest():
    """一键更新到最新：区间类从 DB 最新日期补到今天，快照类抓最新，名录类增量补新。

    Body 参数:
      task_types (可选) 指定只更新哪几类，默认全部 8 类
      force      (可选) true=跳过"已是最新"判断，强制创建任务（用于"立即更新"按钮）
    """
    from core.scheduler.scheduler import scheduler
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    task_types = data.get("task_types")
    force = bool(data.get("force", False))

    db = DatabaseConfig.get_database()
    stats = _get_collection_stats(db)
    _invalidate_stats_cache()

    # force=True 时跳过快照去重逻辑，总是重新采集
    already_collected: set = set()
    if not force:
        from datetime import date as _date
        today_start = datetime.combine(_date.today(), datetime.min.time())
        _snap_collections = {"news": "news", "fund_flow": "fund_flow", "sector": "block"}
        for snap_type, coll_name in _snap_collections.items():
            if task_types and snap_type not in task_types:
                continue
            if db[coll_name].find_one({"_updated_at": {"$gte": today_start}}):
                already_collected.add(snap_type)

    tasks, skipped = _compute_update_latest_tasks(
        stats, task_types, already_collected=already_collected,
        force=force
    )

    started, failed = {}, {}
    for task_cfg in tasks:
        ttype = task_cfg["task_type"]
        try:
            task_id = scheduler.create_task(ttype, task_cfg["params"])
            scheduler.start_task(task_id)
            started[ttype] = task_id
        except Exception as e:
            failed[ttype] = str(e)

    return jsonify({
        "success": True,
        "started": started,
        "skipped": skipped,
        "failed": failed,
        "total_started": len(started),
        "timestamp": datetime.now().isoformat()
    })


def _parse_task_ts(task_id: str) -> int:
    """从 task_id（如 kline_1779931587433）提取毫秒时间戳，用于排序"""
    try:
        return int(task_id.rsplit("_", 1)[-1])
    except Exception:
        return 0


# ---------- 集合统计缓存（与前端刷新间隔对齐，避免每次 progress_all 打 16 次 MongoDB 查询） ----------
_stats_cache: dict = {}
_stats_cache_at: float = 0.0
_stats_cache_lock = threading.Lock()
_STATS_TTL = 30.0


def _fmt_dt(v) -> str:
    """把 datetime / 8位字符串 统一格式化为 YYYY-MM-DD"""
    if v is None:
        return None
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    s = str(v)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10] if s else None


def _get_collection_stats(db) -> dict:
    """查询各集合的记录数和数据时间区间；结果缓存 30s 避免重复打 MongoDB。"""
    global _stats_cache, _stats_cache_at

    with _stats_cache_lock:
        if _stats_cache and (time.time() - _stats_cache_at) < _STATS_TTL:
            return _stats_cache

    meta = {
        "kline":        ("kline",        "date"),
        "stock_info":   ("stock_info",   "_updated_at"),
        "financial":    ("financial",    "report_date"),
        "news":         ("news",         "publish_date"),   # publish_date 已修复为有效时间
        "fund_flow":    ("fund_flow",    "date"),           # 新格式个股数据有 date 字段
        "dragon_tiger": ("dragon_tiger", "上榜日"),
        "sector":       ("block",        "_updated_at"),    # block 无 date，用 _updated_at
        "margin":       ("margin_data",  "date"),           # 新格式个股数据有 date 字段
    }
    result = {}
    for task_type, (coll_name, date_field) in meta.items():
        coll = db[coll_name]
        count = coll.estimated_document_count()   # 用元数据计数，比 count_documents 快得多
        date_from, date_to = None, None
        if date_field and count > 0:
            try:
                # 一次聚合同时取 min/max，比两次 find_one 快
                agg = list(coll.aggregate([
                    {"$match": {date_field: {"$exists": True, "$ne": None}}},
                    {"$group": {"_id": None,
                                "mn": {"$min": f"${date_field}"},
                                "mx": {"$max": f"${date_field}"}}}
                ], allowDiskUse=False))
                if agg:
                    date_from = _fmt_dt(agg[0].get("mn"))
                    date_to   = _fmt_dt(agg[0].get("mx"))
            except Exception:
                pass
        result[task_type] = {"record_count": count, "date_from": date_from, "date_to": date_to}

    with _stats_cache_lock:
        _stats_cache = result
        _stats_cache_at = time.time()
    return result


def _invalidate_stats_cache():
    """任务完成后主动失效缓存，让下次 progress_all 拿到最新数据"""
    global _stats_cache_at
    with _stats_cache_lock:
        _stats_cache_at = 0.0


def _get_expected_latest_td(now: datetime) -> str:
    """返回"此时应有数据的最近交易日"，考虑16:00收盘时间。
    16:00前：上一个交易日（今日数据还未生成）
    16:00后：今日（若今日是交易日，否则往前找）
    """
    from utils.helpers import is_trading_day

    _CLOSE_HOUR = 16
    if now.hour < _CLOSE_HOUR:
        candidate = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    else:
        candidate = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for _ in range(10):
        if is_trading_day(candidate):
            return candidate.strftime("%Y-%m-%d")
        candidate -= timedelta(days=1)
    return (now - timedelta(days=1)).strftime("%Y-%m-%d")


def _count_trading_days_behind(date_to_str: str, expected_str: str) -> int:
    """计算 date_to 落后 expected 多少个交易日（用于 days_behind 展示）。"""
    from utils.helpers import get_trading_days
    try:
        dt_to = datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)
        return len(get_trading_days(dt_to.strftime("%Y-%m-%d"), expected_str))
    except Exception:
        try:
            return (datetime.strptime(expected_str, "%Y-%m-%d")
                    - datetime.strptime(date_to_str, "%Y-%m-%d")).days
        except Exception:
            return 0


def _compute_health(ttype: str, stats: dict, now: datetime) -> dict:
    """计算单类数据的时效性健康状态。
    返回 {'health': 'ok'|'stale'|'error', 'days_behind': int, 'latest_date': str|None}
    """
    record_count = stats.get("record_count", 0)
    date_to = stats.get("date_to")  # YYYY-MM-DD 字符串或 None

    if record_count == 0:
        return {"health": "error", "days_behind": None, "latest_date": None}

    # ── 每日更新类（K线/龙虎榜/资金流向/融资融券/板块）──────────────────────
    if ttype in ("kline", "dragon_tiger", "fund_flow", "margin", "sector"):
        if not date_to:
            return {"health": "error", "days_behind": None, "latest_date": None}
        try:
            expected = _get_expected_latest_td(now)
            date_to_str = str(date_to)[:10]
            if date_to_str >= expected:
                return {"health": "ok", "days_behind": 0, "latest_date": date_to_str}

            gap = _count_trading_days_behind(date_to_str, expected)
            # 板块快照：1个交易日内都算 ok
            if ttype == "sector" and gap <= 1:
                return {"health": "ok", "days_behind": gap, "latest_date": date_to_str}
            return {"health": "stale", "days_behind": gap, "latest_date": date_to_str}
        except Exception:
            return {"health": "error", "days_behind": None, "latest_date": date_to}

    # ── 财务数据：按真实披露截止日判断 ──────────────────────────────────────
    if ttype == "financial":
        if not date_to:
            return {"health": "error", "days_behind": None, "latest_date": None}
        try:
            year = now.year
            # (报告期, 披露截止日)；年报截止日为次年4月30
            events = [
                (f"{year - 1}-12-31", datetime(year, 4, 30)),
                (f"{year}-03-31",     datetime(year, 4, 30)),
                (f"{year}-06-30",     datetime(year, 8, 31)),
                (f"{year}-09-30",     datetime(year, 10, 31)),
                (f"{year}-12-31",     datetime(year + 1, 4, 30)),
            ]
            # 截止日已过的最新报告期
            due = [p for p, d in events if d <= now]
            expected_str = max(due) if due else f"{year - 1}-12-31"
            date_to_str = str(date_to)[:10]
            if date_to_str >= expected_str:
                return {"health": "ok", "days_behind": 0, "latest_date": date_to_str}
            date_to_dt = datetime.strptime(date_to_str, "%Y-%m-%d")
            delta = (now - date_to_dt).days
            return {"health": "stale", "days_behind": delta, "latest_date": date_to_str}
        except Exception:
            return {"health": "error", "days_behind": None, "latest_date": date_to}

    # ── 新闻：今天或昨天有新闻即为最新 ─────────────────────────────────────
    if ttype == "news":
        if not date_to:
            return {"health": "error", "days_behind": None, "latest_date": None}
        try:
            delta = (now.date() - datetime.strptime(str(date_to)[:10], "%Y-%m-%d").date()).days
            if delta <= 1:
                return {"health": "ok", "days_behind": delta, "latest_date": str(date_to)[:10]}
            return {"health": "stale", "days_behind": delta, "latest_date": str(date_to)[:10]}
        except Exception:
            return {"health": "stale", "days_behind": None, "latest_date": date_to}

    # ── 股票信息：最近7天内更新过 ────────────────────────────────────────────
    if ttype == "stock_info":
        if not date_to:
            # 没有 _updated_at 记录时退化为条数判断
            return {"health": "ok" if record_count >= 5000 else "stale",
                    "days_behind": None, "latest_date": None}
        try:
            delta = (now.date() - datetime.strptime(str(date_to)[:10], "%Y-%m-%d").date()).days
            if delta <= 7:
                return {"health": "ok", "days_behind": delta, "latest_date": str(date_to)[:10]}
            return {"health": "stale", "days_behind": delta, "latest_date": str(date_to)[:10]}
        except Exception:
            return {"health": "ok" if record_count >= 5000 else "stale",
                    "days_behind": None, "latest_date": date_to}

    return {"health": "ok", "days_behind": 0, "latest_date": date_to}


@api_bp.route("/collect/progress_all", methods=["GET"])
def progress_all():
    """聚合查询所有8类数据任务的最新进度和数据时效性健康状态"""
    from core.scheduler.scheduler import scheduler
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    coll_stats = _get_collection_stats(db)

    all_tasks = scheduler.list_tasks(limit=500)
    now = datetime.now()

    target_types = ["kline", "stock_info", "financial", "news",
                    "fund_flow", "dragon_tiger", "sector", "margin"]

    # 每种类型只取最新的非取消任务
    latest_by_type: dict = {}
    for task in all_tasks:
        ttype = task.get("task_type")
        if ttype not in target_types:
            continue
        if task.get("status") == "cancelled":
            continue
        tid = task.get("task_id", "")
        existing = latest_by_type.get(ttype)
        if not existing or _parse_task_ts(tid) > _parse_task_ts(existing.get("task_id", "")):
            latest_by_type[ttype] = task

    summary = {}
    healthy_count = 0  # 健康状态=ok 的类型数

    for ttype in target_types:
        task = latest_by_type.get(ttype)
        stats = coll_stats.get(ttype, {})
        record_count = stats.get("record_count", 0)
        health_info = _compute_health(ttype, stats, now)

        if task:
            progress = task.get("progress", 0)
            total = task.get("total", 0)
            status = task.get("status", "unknown")
            percent = round(progress / total * 100, 1) if total > 0 else (100.0 if status == "completed" else 0.0)
            failed_cnt = task.get("failed", 0)
            success = record_count if ttype in ("news", "fund_flow", "sector") else task.get("success", 0)
        else:
            progress = total = 0
            status = "not_started"
            percent = 0.0
            failed_cnt = 0
            success = record_count

        summary[ttype] = {
            "task_type": ttype,
            "status": status,
            "progress": progress,
            "total": total,
            "percent": percent,
            "success": success,
            "failed": failed_cnt,
            "task_id": task.get("task_id") if task else None,
            "elapsed_time": round(task.get("elapsed_time", 0), 1) if task else 0,
            "record_count": record_count,
            "date_from": stats.get("date_from"),
            "date_to": stats.get("date_to"),
            # 新增：时效性健康状态
            "health": health_info["health"],        # ok|stale|error
            "days_behind": health_info["days_behind"],
            "latest_date": health_info["latest_date"] or stats.get("date_to"),
        }

        # ok 和 stale 都算"有数据"，只有 error 才算无数据
        if health_info["health"] in ("ok", "stale"):
            healthy_count += 1

    # 整体进度 = 有数据的类型数 / 8（含义：数据覆盖完整度，不是实时性）
    overall_percent = round(healthy_count / len(target_types) * 100, 1)

    return jsonify({
        "success": True,
        "overall_percent": overall_percent,
        "completed_types": healthy_count,
        "total_types": len(target_types),
        "all_done": healthy_count == len(target_types),
        "tasks": summary,
        "timestamp": now.isoformat()
    })


# ---------- 数据缺口检测缓存（5分钟 TTL，K线百万级数据避免频繁触发大查询）----------
_gaps_cache: dict = {}
_gaps_cache_at: float = 0.0
_gaps_cache_lock = threading.Lock()
_GAPS_TTL = 300.0


def _invalidate_gaps_cache():
    global _gaps_cache_at
    with _gaps_cache_lock:
        _gaps_cache_at = 0.0


@api_bp.route("/collect/data_gaps", methods=["GET"])
def get_data_gaps():
    """检测各类数据的区间覆盖情况和缺口。
    对 kline/dragon_tiger/fund_flow/margin（每日数据）：与交易日历对比找缺口。
    对 financial（季度数据）：检测哪些标准季度缺失。
    结果缓存5分钟。
    """
    global _gaps_cache, _gaps_cache_at
    with _gaps_cache_lock:
        if _gaps_cache and (time.time() - _gaps_cache_at) < _GAPS_TTL:
            return jsonify({"success": True, "data": _gaps_cache, "cached": True,
                            "timestamp": datetime.now().isoformat()})

    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()

    result = {}

    # ── 每日数据类型 ─────────────────────────────────────────────────────────
    daily_types = {
        "kline":        "kline",
        "dragon_tiger": "dragon_tiger",
        "fund_flow":    "fund_flow",
        "margin":       "margin_data",
    }
    daily_date_fields = {
        "kline":        "date",
        "dragon_tiger": "上榜日",
        "fund_flow":    "date",
        "margin":       "date",
    }

    # 获取交易日历（一次性，供所有类型复用）
    trading_days_set: set = set()
    trading_days_sorted: list = []
    try:
        import akshare as ak
        td_df = ak.tool_trade_date_hist_sina()
        td_col = td_df.columns[0]
        for v in td_df[td_col]:
            s = str(v)[:10]
            if len(s) == 10:
                trading_days_set.add(s)
        trading_days_sorted = sorted(trading_days_set)
    except Exception:
        pass

    for ttype, coll_name in daily_types.items():
        coll = db[coll_name]
        date_field = daily_date_fields[ttype]
        try:
            # 只查 distinct date 字段（轻量）
            raw_dates = coll.distinct(date_field)
        except Exception:
            result[ttype] = {"error": "query failed"}
            continue

        db_dates: set = set()
        for v in raw_dates:
            if hasattr(v, "strftime"):
                db_dates.add(v.strftime("%Y-%m-%d"))
            else:
                s = str(v)[:10]
                if len(s) == 10:
                    db_dates.add(s)

        if not db_dates:
            result[ttype] = {
                "covered_ranges": [],
                "gap_ranges": [],
                "completeness_pct": 0.0,
                "has_data": False,
            }
            continue

        db_min = min(db_dates)
        db_max = max(db_dates)

        # 连续覆盖区间 vs 缺口
        covered_ranges = []
        gap_ranges = []

        if trading_days_set:
            # 在 [db_min, db_max] 范围内对比交易日历
            relevant_tds = [d for d in trading_days_sorted if db_min <= d <= db_max]
            total_relevant = len(relevant_tds)
            covered_count = sum(1 for d in relevant_tds if d in db_dates)
            completeness_pct = round(covered_count / total_relevant * 100, 1) if total_relevant > 0 else 0.0

            # 构建连续段
            def _build_ranges(dates_in_set, all_days):
                ranges = []
                seg_start = seg_end = None
                for d in all_days:
                    if d in dates_in_set:
                        if seg_start is None:
                            seg_start = d
                        seg_end = d
                    else:
                        if seg_start is not None:
                            ranges.append({"start": seg_start, "end": seg_end,
                                           "days": sum(1 for x in all_days if seg_start <= x <= seg_end and x in dates_in_set)})
                            seg_start = seg_end = None
                if seg_start is not None:
                    ranges.append({"start": seg_start, "end": seg_end,
                                   "days": sum(1 for x in all_days if seg_start <= x <= seg_end and x in dates_in_set)})
                return ranges

            covered_ranges = _build_ranges(db_dates, relevant_tds)
            gap_dates = {d for d in relevant_tds if d not in db_dates}
            gap_ranges = _build_ranges(gap_dates, relevant_tds)
        else:
            # 无交易日历时退化为纯区间
            covered_ranges = [{"start": db_min, "end": db_max, "days": len(db_dates)}]
            completeness_pct = 100.0

        result[ttype] = {
            "covered_ranges": covered_ranges,
            "gap_ranges": gap_ranges,
            "completeness_pct": completeness_pct,
            "has_data": True,
            "db_min": db_min,
            "db_max": db_max,
        }

    # ── 财务数据（季度） ────────────────────────────────────────────────────
    try:
        fin_coll = db["financial"]
        raw_periods = fin_coll.distinct("report_date")
        db_quarters: set = set()
        for v in raw_periods:
            if hasattr(v, "strftime"):
                db_quarters.add(v.strftime("%Y-%m-%d"))
            else:
                s = str(v)[:10]
                if len(s) == 10:
                    db_quarters.add(s)

        if db_quarters:
            db_min_q = min(db_quarters)[:4]
            db_max_q = max(db_quarters)[:4]
            today_str = datetime.now().strftime("%Y-%m-%d")
            # 只生成已经过去的季度（严格小于今天），未来季度财报尚不存在
            std_quarters = []
            for yr in range(int(db_min_q), int(db_max_q) + 1):
                for q in ("03-31", "06-30", "09-30", "12-31"):
                    qdate = f"{yr}-{q}"
                    if qdate < today_str:
                        std_quarters.append(qdate)
            covered_q = [q for q in std_quarters if q in db_quarters]
            missing_q = [q for q in std_quarters if q not in db_quarters]
            completeness_q = round(len(covered_q) / len(std_quarters) * 100, 1) if std_quarters else 0.0
            result["financial"] = {
                "covered_quarters": covered_q,
                "missing_quarters": missing_q,
                "completeness_pct": completeness_q,
                "has_data": True,
            }
        else:
            result["financial"] = {"covered_quarters": [], "missing_quarters": [], "completeness_pct": 0.0, "has_data": False}
    except Exception:
        result["financial"] = {"error": "query failed"}

    with _gaps_cache_lock:
        _gaps_cache = result
        _gaps_cache_at = time.time()

    return jsonify({"success": True, "data": result, "cached": False,
                    "timestamp": datetime.now().isoformat()})


def success_response(data: Any, message: str = "Success") -> Dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }


def error_response(message: str, code: int = 400) -> tuple:
    return jsonify({
        "success": False,
        "error": message,
        "timestamp": datetime.now().isoformat()
    }), code


@api_bp.route("/dragon_tiger", methods=["GET"])
def get_dragon_tiger_list():
    from core.storage.mongo_storage import DragonTigerStorage
    from datetime import datetime as _dt

    storage = DragonTigerStorage()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    code = request.args.get("code")
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(200, max(1, int(request.args.get("page_size", 50))))

    filter_doc = {}
    if code:
        filter_doc["code"] = _normalize_code(code)
    if start_date and end_date:
        try:
            sd = _dt.strptime(start_date[:10], "%Y-%m-%d")
            ed = _dt.strptime(end_date[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            filter_doc["上榜日"] = {"$gte": sd, "$lte": ed}
        except Exception:
            pass

    total = storage.collection.count_documents(filter_doc)
    skip = (page - 1) * page_size
    records = storage.find_many(filter_doc, sort=[("上榜日", -1)], skip=skip, limit=page_size)

    result = []
    for r in records:
        r.pop("_id", None)
        r.pop("_updated_at", None)
        raw_date = r.get("上榜日") or r.get("date") or r.get("日期", "")
        if hasattr(raw_date, "strftime"):
            raw_date = raw_date.strftime("%Y-%m-%d")
        result.append({
            "code": r.get("code", r.get("代码", "")),
            "name": r.get("name", r.get("名称", r.get("股票名称", ""))),
            "date": raw_date,
            "reason": r.get("reason", r.get("上榜原因", r.get("解读", ""))),
            "total_amount": r.get("total_amount", r.get("龙虎榜成交额", r.get("市场总成交额", 0))),
            "net_buy": r.get("net_buy", r.get("龙虎榜净买额", r.get("净买额", 0))),
            "close": r.get("收盘价", 0),
            "change_rate": r.get("涨跌幅", 0),
        })

    return jsonify({
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": result
    })


@api_bp.route("/margin", methods=["GET"])
def get_margin_data():
    from core.storage.mongo_storage import MarginStorage
    
    storage = MarginStorage()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    code = request.args.get("code")
    limit = int(request.args.get("limit", 100))
    
    filter_doc = {}
    # margin 集合存储的是市场级汇总数据；信用交易日期 存储为 8 位字符串 "20260527"
    if start_date and end_date:
        sd_8 = start_date.replace("-", "")[:8]
        ed_8 = end_date.replace("-", "")[:8]
        filter_doc["信用交易日期"] = {"$gte": sd_8, "$lte": ed_8}

    records = storage.find_many(filter_doc, sort=[("信用交易日期", -1)], limit=limit)
    
    for record in records:
        record.pop("_id", None)
        record.pop("_updated_at", None)
    
    seen = set()
    result = []
    for r in records:
        raw_date = r.get("信用交易日期", "")
        # 日期格式统一为 YYYY-MM-DD
        if isinstance(raw_date, str) and len(raw_date) == 8 and raw_date.isdigit():
            raw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        dedup_key = str(raw_date)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        result.append({
            "date": raw_date,
            "rz_balance": r.get("rz_balance", r.get("融资余额", 0)),
            "rz_buy": r.get("rz_buy", r.get("融资买入额", 0)),
            "rq_volume": r.get("rq_volume", r.get("融券余量", 0)),
            "rq_sell": r.get("rq_sell", r.get("融券卖出量", 0)),
        })
    
    return jsonify({
        "success": True,
        "count": len(result),
        "data": result
    })


MARKET_INDEX_CODES = [
    {"code": "sh000001", "name": "上证指数", "name_en": "SSE"},
    {"code": "sz399001", "name": "深证成指", "name_en": "SZSE"},
    {"code": "sz399006", "name": "创业板指", "name_en": "GEM"},
    {"code": "sh000688", "name": "科创50", "name_en": "STAR50"},
]


@api_bp.route("/market/indices", methods=["GET"])
def get_market_indices():
    import re
    import requests
    from datetime import datetime

    NO_PROXY = {"http": "", "https": ""}
    SINA_HEADERS = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}

    def _fetch_sina():
        codes = ",".join(
            ("s_" + idx["code"]) for idx in MARKET_INDEX_CODES
        )
        r = requests.get(
            f"http://hq.sinajs.cn/list={codes}",
            headers=SINA_HEADERS,
            proxies=NO_PROXY,
            timeout=8,
        )
        r.raise_for_status()
        result = []
        for idx in MARKET_INDEX_CODES:
            m = re.search(rf'hq_str_s_{idx["code"]}="([^"]+)"', r.text)
            if not m:
                continue
            parts = m.group(1).split(",")
            if len(parts) < 6:
                continue
            result.append({
                "code": idx["code"].upper(),
                "name": idx["name"],
                "price": float(parts[1]),
                "change": float(parts[3]),
                "change_amount": float(parts[2]),
                "volume": float(parts[4]),
                "amount": float(parts[5]) * 10000,  # 万元 → 元
                "amplitude": 0,
                "high": None,
                "low": None,
                "open": None,
                "prev_close": None,
            })
        return result

    def _fetch_tencent():
        codes = ",".join(idx["code"] for idx in MARKET_INDEX_CODES)
        r = requests.get(
            f"https://qt.gtimg.cn/q={codes}",
            proxies=NO_PROXY,
            timeout=8,
        )
        r.raise_for_status()
        result = []
        for idx in MARKET_INDEX_CODES:
            m = re.search(rf'v_{idx["code"]}="([^"]+)"', r.text)
            if not m:
                continue
            p = m.group(1).split("~")
            if len(p) < 36:
                continue
            def _f(v):
                try:
                    return float(v) if v else None
                except (ValueError, TypeError):
                    return None
            result.append({
                "code": idx["code"].upper(),
                "name": idx["name"],
                "price": _f(p[3]) or None,
                "change": _f(p[33]),
                "change_amount": _f(p[32]),
                "volume": _f(p[6]) or 0,
                "amount": 0,
                "amplitude": 0,
                "high": _f(p[34]),
                "low": _f(p[35]),
                "open": _f(p[5]),
                "prev_close": _f(p[4]),
            })
        return result

    errors = []
    for source, fetch_fn in [("sina_hq", _fetch_sina), ("tencent", _fetch_tencent)]:
        try:
            indices = fetch_fn()
            if indices:
                return jsonify({
                    "success": True,
                    "count": len(indices),
                    "data": indices,
                    "timestamp": datetime.now().isoformat(),
                    "source": source,
                })
        except Exception as e:
            errors.append(f"{source}: {e}")
            logger.warning(f"Index source {source} failed: {e}")

    logger.error(f"All index sources failed: {errors}")
    return jsonify({"error": "; ".join(errors)}), 500


@api_bp.route("/market/realtime-quotes", methods=["POST"])
def get_realtime_quotes():
    import re
    import requests as _requests
    from datetime import datetime

    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    normalized_codes = [_normalize_code(c) for c in codes]
    unique_codes = list(dict.fromkeys(normalized_codes))  # dedupe, preserve order

    NO_PROXY = {"http": "", "https": ""}

    def _fetch_tencent(code_list):
        # Tencent expects lowercase sh/sz prefix
        tencent_codes = ",".join(c.lower() for c in code_list)
        r = _requests.get(
            f"https://qt.gtimg.cn/q={tencent_codes}",
            proxies=NO_PROXY,
            timeout=10,
        )
        r.raise_for_status()
        results = []
        for code in code_list:
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if not m:
                continue
            p = m.group(1).split("~")
            if len(p) < 36:
                continue
            def _f(v):
                try:
                    return float(v) if v else None
                except (ValueError, TypeError):
                    return None
            # amount: p[35] = "price/volume/amount_yuan"
            amount = None
            try:
                amount = float(p[35].split("/")[2])
            except (IndexError, ValueError):
                pass
            results.append({
                "code": code.upper(),
                "name": p[1],
                "price": _f(p[3]),
                "change": _f(p[32]),
                "change_amount": _f(p[31]),
                "volume": _f(p[6]),   # 手
                "amount": amount,      # 元
                "open": _f(p[5]),
                "high": _f(p[33]),
                "low": _f(p[34]),
                "prev_close": _f(p[4]),
                "turnover": _f(p[38]),  # 换手率%
            })
        return results

    def _fetch_sina(code_list):
        sina_codes = ",".join(c.lower() for c in code_list)
        r = _requests.get(
            f"http://hq.sinajs.cn/list={sina_codes}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            proxies=NO_PROXY,
            timeout=10,
        )
        r.raise_for_status()
        results = []
        for code in code_list:
            m = re.search(rf'hq_str_{code.lower()}="([^"]+)"', r.text)
            if not m:
                continue
            p = m.group(1).split(",")
            if len(p) < 10:
                continue
            def _f(v):
                try:
                    return float(v) if v else None
                except (ValueError, TypeError):
                    return None
            prev_close = _f(p[2])
            price = _f(p[3])
            change = round((price - prev_close) / prev_close * 100, 2) if price and prev_close else None
            results.append({
                "code": code.upper(),
                "name": p[0],
                "price": price,
                "change": change,
                "change_amount": round(price - prev_close, 2) if price and prev_close else None,
                "volume": _f(p[8]),
                "amount": _f(p[9]),
                "open": _f(p[1]),
                "high": _f(p[4]),
                "low": _f(p[5]),
                "prev_close": prev_close,
                "turnover": None,
            })
        return results

    errors = []
    for source, fetch_fn in [("tencent", _fetch_tencent), ("sina", _fetch_sina)]:
        try:
            results = fetch_fn(unique_codes)
            if results:
                return jsonify({
                    "success": True,
                    "count": len(results),
                    "data": results,
                    "timestamp": datetime.now().isoformat(),
                    "source": source,
                })
        except Exception as e:
            errors.append(f"{source}: {e}")
            logger.warning(f"Realtime quotes source {source} failed: {e}")

    logger.error(f"All realtime-quotes sources failed: {errors}")
    return jsonify({"error": "; ".join(errors)}), 500


@api_bp.route("/market/minute-kline/<code>", methods=["GET"])
def get_minute_kline(code):
    import akshare as ak
    from datetime import datetime

    code = _normalize_code(code)
    if not code:
        return jsonify({"error": "invalid code"}), 400

    try:
        symbol = code.lower()
        df = ak.stock_zh_a_minute(symbol=symbol, period="1", adjust="qfq")

        records = []
        for _, row in df.tail(240).iterrows():
            dt_val = row.get("时间") or row.get("Datetime") or row.get("date")
            if hasattr(dt_val, "strftime"):
                time_str = dt_val.strftime("%Y-%m-%d %H:%M")
            else:
                time_str = str(dt_val)[:16] if dt_val else ""
            records.append({
                "time": time_str,
                "price": float(row["最新价"]) if pd.notna(row.get("最新价")) else 0,
                "volume": float(row["成交量"]) if pd.notna(row.get("成交量")) else 0,
            })

        return jsonify({
            "success": True,
            "code": code,
            "count": len(records),
            "data": records,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get minute kline for {code}: {e}")
        return jsonify({"error": str(e)}), 500


import pandas as pd


@api_bp.route("/ai-keys", methods=["GET"])
def list_ai_keys():
    from modules.ai.ai_key_manager import ai_key_manager
    keys = ai_key_manager.list_keys()
    return jsonify({"success": True, "data": keys})


@api_bp.route("/ai-keys", methods=["POST"])
def update_ai_key():
    from modules.ai.ai_key_manager import ai_key_manager
    data = request.get_json() or {}
    provider = data.get("provider")
    name = data.get("name", provider)
    enabled = data.get("enabled", False)
    priority = data.get("priority", 99)
    api_key = data.get("api_key")
    base_url = data.get("base_url")
    model = data.get("model")
    if not provider:
        return jsonify({"error": "provider is required"}), 400
    ai_key_manager.update_key(provider, name, enabled, priority, api_key, base_url, model)
    return jsonify({"success": True, "message": "Key updated"})


@api_bp.route("/ai-keys/<provider>", methods=["DELETE"])
def delete_ai_key(provider):
    from modules.ai.ai_key_manager import ai_key_manager
    ai_key_manager.delete_key(provider)
    return jsonify({"success": True, "message": "Key deleted"})


@api_bp.route("/ai-keys/reorder", methods=["PUT"])
def reorder_ai_keys():
    from config.database import DatabaseConfig
    data = request.get_json() or {}
    priorities = data.get("priorities", [])
    if not priorities:
        return jsonify({"error": "priorities is required"}), 400
    db = DatabaseConfig.get_database()
    for item in priorities:
        provider = item.get("provider")
        priority = item.get("priority")
        if provider and priority is not None:
            db["ai_keys"].update_one(
                {"provider": provider},
                {"$set": {"priority": priority, "updated_at": datetime.now().isoformat()}}
            )
    return jsonify({"success": True, "updated": len(priorities)})


@api_bp.route("/ai-keys/<provider>/models", methods=["GET"])
def get_ai_key_models(provider):
    from modules.ai.ai_key_manager import ai_key_manager
    from config.database import DatabaseConfig

    db = DatabaseConfig.get_database()
    doc = db["ai_keys"].find_one({"provider": provider})
    if not doc:
        return jsonify({"error": "Provider not found"}), 404

    api_key = doc.get("api_key", "")
    base_url = doc.get("base_url", "")

    result = ai_key_manager.fetch_models(provider, api_key, base_url)
    return jsonify({"success": True, "models": result["models"], "source": result["source"]})


@api_bp.route("/ai-keys/<provider>/test", methods=["POST"])
def test_ai_key(provider):
    from modules.ai.ai_key_manager import ai_key_manager
    from config.database import DatabaseConfig
    data = request.get_json() or {}
    api_key = data.get("api_key")
    base_url = data.get("base_url", "")

    db = DatabaseConfig.get_database()
    doc = db["ai_keys"].find_one({"provider": provider})
    if not api_key and doc:
        api_key = doc.get("api_key")
    if not base_url and doc:
        base_url = doc.get("base_url", "")

    if not api_key:
        return jsonify({"success": False, "valid": False, "message": "未找到 API Key，请先配置"}), 400
    result = ai_key_manager.test_key(provider, api_key, base_url or "")
    return jsonify({"success": True, "valid": result["valid"], "message": result["message"]})


@api_bp.route("/pick/smart-advanced", methods=["POST"])
def smart_pick_advanced():
    from modules.ai.smart_picker import SmartPicker

    data = request.get_json() or {}
    top_n = data.get("top_n", 20)
    min_score = data.get("min_score", 60)
    factors = data.get("factors", ["trend", "volume", "value", "fund_flow"])

    picker = SmartPicker()
    results = picker.pick(top_n=top_n * 2, factors=factors)

    for r in results:
        r["score"] = r.pop("total", 60)
        r["technical_score"] = r.get("scores", {}).get("trend", 60)
        r["fundamental_score"] = r.get("scores", {}).get("value", 60)
        r["sentiment_score"] = 65
        r["fund_flow_score"] = r.get("scores", {}).get("fund_flow", 60)
        r["recommendation"] = "买入" if r["score"] >= 70 else "观望" if r["score"] >= 50 else "回避"
        r["risk_level"] = "低" if r["score"] >= 70 else "中" if r["score"] >= 50 else "高"
        r["stop_loss"] = 0
        r["target_price"] = 0

    results = [r for r in results if r.get("score", 0) >= min_score][:top_n]

    return jsonify({"success": True, "count": len(results), "results": results})


@api_bp.route("/pick/smart", methods=["POST"])
def smart_pick():
    from modules.ai.smart_picker import smart_picker
    data = request.get_json() or {}
    top_n = data.get("top_n", 10)
    factors = data.get("factors", ["trend", "volume", "value", "fund_flow"])
    results = smart_picker.pick(top_n=top_n, factors=factors)
    return jsonify({"success": True, "count": len(results), "data": results})


@api_bp.route("/sector", methods=["GET"])
def get_sector_list():
    from core.storage.mongo_storage import BlockStorage

    storage = BlockStorage()
    # 取全部记录，按名字去重：优先保留 block_type=="industry" 的记录，
    # 相同名字出现多次时取 change_rate 绝对值最大的（数据更新鲜）
    records = storage.find_many({})

    seen_names: dict = {}
    for r in records:
        r.pop("_id", None)
        r.pop("_updated_at", None)
        name = r.get("name") or r.get("行业") or r.get("block_name", "")
        net_flow = r.get("net_flow") or r.get("净额") or r.get("成交额") or 0
        # 兼容采集时直接存储的中文列名 "涨跌幅"
        change_rate = r.get("change_rate") or r.get("行业-涨跌幅") or r.get("涨跌幅") or 0
        block_type = r.get("block_type", "")
        if not name:
            continue
        entry = {
            "name": name,
            "net_flow": float(net_flow) if net_flow else 0,
            "change_rate": float(change_rate) if change_rate else 0,
            "_block_type": block_type,
        }
        existing = seen_names.get(name)
        if existing is None:
            seen_names[name] = entry
        elif block_type == "industry" and existing["_block_type"] != "industry":
            # 行业板块优先于概念板块
            seen_names[name] = entry
        elif block_type == existing["_block_type"] and abs(entry["change_rate"]) > abs(existing["change_rate"]):
            seen_names[name] = entry

    result = [{"name": v["name"], "net_flow": v["net_flow"], "change_rate": v["change_rate"]}
              for v in seen_names.values()]

    return jsonify({
        "success": True,
        "count": len(result),
        "data": result
    })


@api_bp.route("/sector/<sector_name>/stocks", methods=["GET"])
def get_sector_stocks(sector_name):
    from core.storage.mongo_storage import BlockStorage, KlineStorage
    
    block_storage = BlockStorage()
    kline_storage = KlineStorage()
    
    blocks = block_storage.find_many({"name": sector_name})
    
    if not blocks:
        return jsonify({
            "success": True,
            "count": 0,
            "data": []
        })
    
    result = []
    for block in blocks:
        code = block.get("code")
        if code:
            latest = kline_storage.find_one({"code": code}, sort=[("date", -1)])
            result.append({
                "code": code,
                "name": block.get("name", ""),
                "change_rate": latest.get("change_rate", 0) if latest else 0,
                "net_flow": block.get("net_flow", 0),
            })

    return jsonify({
        "success": True,
        "count": len(result),
        "data": result
    })


@api_bp.route("/ai/agent-chat", methods=["POST"])
def ai_agent_chat():
    """统一 Agent Chat：通用聊天 + 角色 agent + 股票数据预注入，SSE 流式返回。
    Body: {message, agent_id?, stock_code?, history?, provider?}
    """
    import json as _json
    from flask import Response
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    agent_id = (data.get("agent_id") or "").strip()
    stock_code = (data.get("stock_code") or "").strip()
    history = data.get("history") or []
    provider = (data.get("provider") or "").strip()

    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    # 1. 加载 agent 配置
    system_prompt = "你是一个专业的A股投资助手，能够提供市场分析和投资建议。"
    temperature = 0.7
    max_tokens = 2000
    if agent_id:
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            agent_doc = db["ai_agents"].find_one({"id": agent_id, "enabled": True})
            if agent_doc:
                system_prompt = agent_doc.get("system_prompt", system_prompt)
                temperature = float(agent_doc.get("temperature", temperature))
                max_tokens = int(agent_doc.get("max_tokens", max_tokens))
        except Exception as e:
            logger.warning(f"Failed to load agent config for {agent_id}: {e}")

    # 2. 构建股票上下文
    context_block = ""
    stock_name = ""
    if stock_code:
        try:
            from modules.ai.foundation.dal import StockDAL
            from modules.ai.foundation.factors import (
                trend_score, volume_score, valuation_score,
                fund_flow_score, composite_score,
            )
            bundle = StockDAL().get_stock_bundle(stock_code)
            stock_name = bundle.name or stock_code

            scores: dict = {}
            if bundle.closes:
                scores["trend"] = round(trend_score(bundle.closes), 1)
                if bundle.volumes:
                    scores["volume"] = round(volume_score(bundle.volumes), 1)
            scores["valuation"] = round(valuation_score(
                bundle.pe, bundle.pb, getattr(bundle, "ps", None),
                bundle.roe, bundle.gross_margin, bundle.debt_ratio,
                bundle.revenue_growth, bundle.profit_growth,
            ), 1)
            scores["fund_flow"] = round(fund_flow_score(bundle.main_net_inflow), 1)
            defined = {k: v for k, v in scores.items() if v is not None}
            total_w = {"trend": 0.25, "volume": 0.10, "valuation": 0.35, "fund_flow": 0.30}
            scores["composite"] = round(composite_score(defined, total_w), 1)

            context_block = _build_agent_context(agent_id, bundle, scores)
        except Exception as e:
            logger.warning(f"Failed to build stock context for {stock_code}: {e}")
            context_block = f"（获取 {stock_code} 数据时出错，请基于通用知识分析）"

    def generate():
        yield f"data: {_json.dumps({'type': 'context', 'data': {'stock_name': stock_name, 'has_data': bool(context_block)}})}\n\n"

        full_system = system_prompt
        if context_block:
            full_system += "\n\n" + context_block

        valid_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-10:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        msgs = [{"role": "system", "content": full_system}] + valid_history + [{"role": "user", "content": message}]

        try:
            router = LLMRouter()
            if provider:
                router.providers = [provider]

            full_content = ""
            for chunk in router.chat_stream("", messages=msgs):
                if chunk:
                    full_content += chunk
                    yield f"data: {_json.dumps({'type': 'content', 'data': chunk})}\n\n"

            yield f"data: {_json.dumps({'type': 'done', 'data': {'content': full_content}})}\n\n"
        except Exception as e:
            logger.error(f"AI agent chat stream failed: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_agent_context(agent_id: str, bundle, scores: dict) -> str:
    """按角色裁剪注入的股票上下文块，供 ai_agent_chat 端点使用。"""
    lines = [f"【{bundle.name or bundle.code} 数据】"]
    closes = list(bundle.closes or [])
    volumes = list(bundle.volumes or [])

    if agent_id == "technical_analyst":
        lines.append(f"近20日收盘价（最新在前）：{[round(c, 2) for c in closes[:20]] if closes else '暂无'}")
        lines.append(f"近20日成交量：{[round(v, 0) for v in volumes[:20]] if volumes else '暂无'}")
        lines.append(f"技术评分：{scores.get('trend', '暂无')}  成交量评分：{scores.get('volume', '暂无')}")
        if len(closes) >= 5:
            lines.append(f"MA5：{round(sum(closes[:5]) / 5, 2)}")
        if len(closes) >= 20:
            lines.append(f"MA20：{round(sum(closes[:20]) / 20, 2)}")

    elif agent_id == "fund_analyst":
        lines.append(f"近10日成交量：{[round(v, 0) for v in volumes[:10]] if volumes else '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        lines.append(f"资金评分：{scores.get('fund_flow', '暂无')}")

    elif agent_id == "fundamental_analyst":
        lines.append(f"市盈率(TTM)：{bundle.pe or '暂无'}")
        lines.append(f"市净率(PB)：{bundle.pb or '暂无'}")
        lines.append(f"ROE：{bundle.roe or '暂无'}")
        lines.append(f"毛利率：{bundle.gross_margin or '暂无'}")
        lines.append(f"负债率：{bundle.debt_ratio or '暂无'}")
        lines.append(f"营收同比：{bundle.revenue_growth or '暂无'}")
        lines.append(f"净利润同比：{bundle.profit_growth or '暂无'}")
        lines.append(f"基本面评分：{scores.get('valuation', '暂无')}")

    elif agent_id == "sentiment_analyst":
        news = (bundle.news or [])[:5]
        if news:
            lines.append("最近5条新闻：")
            for n in news:
                date = str(n.get("publish_date", ""))[:10]
                lines.append(f"  [{date}] {n.get('title', '')}")
        else:
            lines.append("暂无相关新闻")

    elif agent_id == "market_analyst":
        lines.append(f"近10日收盘价：{[round(c, 2) for c in closes[:10]] if closes else '暂无'}")
        lines.append(f"近10日成交量：{[round(v, 0) for v in volumes[:10]] if volumes else '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        for n in (bundle.news or [])[:2]:
            lines.append(f"新闻：{n.get('title', '')}")
        lines.append(
            f"综合评分：{scores.get('composite', '暂无')}"
            f"（技术{scores.get('trend', '?')} 基本面{scores.get('valuation', '?')} 资金{scores.get('fund_flow', '?')}）"
        )

    elif agent_id == "risk_analyst":
        lines.append(f"近20日收盘价：{[round(c, 2) for c in closes[:20]] if closes else '暂无'}")
        lines.append(f"PE：{bundle.pe or '暂无'}  PB：{bundle.pb or '暂无'}  ROE：{bundle.roe or '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        lines.append(
            f"各维度评分 — 技术：{scores.get('trend', '?')}  基本面：{scores.get('valuation', '?')}"
            f"  资金：{scores.get('fund_flow', '?')}  综合：{scores.get('composite', '?')}"
        )
        for n in (bundle.news or [])[:3]:
            lines.append(f"新闻：{n.get('title', '')}")

    else:
        if closes:
            lines.append(f"近10日收盘价：{[round(c, 2) for c in closes[:10]]}")
        if bundle.pe:
            lines.append(f"PE：{bundle.pe}  PB：{bundle.pb or '暂无'}")

    return "\n".join(lines)