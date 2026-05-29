"""
API路由定义
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Any, Dict, Optional
import time
import threading
from utils.logger import get_logger

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
    from api.routes.backtest_enhanced import backtest_enhanced_bp
    from api.routes.position import position_bp
    from api.routes.market import market_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(ai_advanced_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(sentiment_bp)
    app.register_blueprint(backtest_enhanced_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(market_bp)

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
    from core.storage.mongo_storage import NewsStorage

    storage = NewsStorage()
    code = request.args.get("code")
    limit = int(request.args.get("limit", 100))

    records = storage.get_latest_news(code=code, limit=limit)

    return jsonify({
        "success": True,
        "count": len(records),
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


@api_bp.route("/strategy/list", methods=["GET"])
def list_strategies():
    from modules.strategies.strategy_manager import StrategyManager

    manager = StrategyManager()
    strategies = manager.list_strategies()

    return jsonify({
        "success": True,
        "strategies": strategies
    })


@api_bp.route("/strategy/<strategy_name>/run", methods=["POST"])
def run_strategy(strategy_name):
    from modules.strategies.strategy_manager import StrategyManager

    data = request.get_json() or {}
    codes = data.get("codes", [])

    manager = StrategyManager()
    try:
        results = manager.run_strategy(strategy_name, codes)
        return jsonify({
            "success": True,
            "results": results
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_bp.route("/backtest", methods=["POST"])
def run_backtest():
    from modules.backtest.backtest_engine import BacktestEngine

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    engine = BacktestEngine()
    try:
        report = engine.run(
            strategy=data.get("strategy"),
            codes=data.get("codes", []),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            initial_cash=data.get("initial_cash", 1000000),
            stop_loss=data.get("stop_loss", 0.05),
            take_profit=data.get("take_profit", 0.10)
        )
        
        report["annualized_return"] = report.get("annual_return", report.get("annualized_return", 0))
        report["final_value"] = report.get("final_value", report.get("initial_cash", 1000000))
        report["winning_trades"] = report.get("winning_trades", 0)
        report["losing_trades"] = report.get("losing_trades", 0)
        report["avg_holding_days"] = report.get("avg_holding_days", 0)
        report["total_return"] = report.get("total_return", 0)
        report["max_drawdown"] = report.get("max_drawdown", 0)
        report["win_rate"] = report.get("win_rate", 0)
        report["sharpe_ratio"] = report.get("sharpe_ratio", 0)
        
        return jsonify({
            "success": True,
            "report": report
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


@api_bp.route("/scheduler/stats", methods=["GET"])
def get_scheduler_stats():
    from core.scheduler.scheduler import scheduler

    stats = scheduler.get_task_statistics()
    return jsonify({
        "success": True,
        "stats": stats
    })


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
    from core.collector.news_collector import NewsCollector
    from core.storage.mongo_storage import NewsStorage

    data = request.get_json() or {}
    codes = data.get("codes")
    limit = data.get("limit", 50)

    collector = NewsCollector()
    storage = NewsStorage()

    start_time = datetime.now()
    if codes:
        all_records = []
        for code in codes[:5]:
            records = collector.collect_single(code)
            if records:
                all_records.extend(records if isinstance(records, list) else [records])
    else:
        all_records = collector.collect_recent_news(limit=limit)

    if all_records:
        storage.save_news_batch(all_records)

    elapsed = (datetime.now() - start_time).total_seconds()
    return jsonify({
        "success": True,
        "collected_count": len(all_records),
        "elapsed_seconds": round(elapsed, 2)
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


@api_bp.route("/db/clear", methods=["POST"])
def clear_collections():
    """清空指定的数据集合，默认清空所有8类数据"""
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    collections = data.get("collections", [
        "kline", "stock_info", "financial", "news",
        "fund_flow", "dragon_tiger", "block", "margin_data"
    ])

    db = DatabaseConfig.get_database()
    results = {}
    for coll in collections:
        try:
            result = db[coll].delete_many({})
            results[coll] = result.deleted_count
        except Exception as e:
            results[coll] = f"error: {e}"

    return jsonify({
        "success": True,
        "deleted": results,
        "timestamp": datetime.now().isoformat()
    })


def _build_history_tasks(start_date: str, end_date: str, task_types=None) -> list:
    """构建历史采集任务（仅区间历史类：kline/financial/dragon_tiger/margin）。

    快照类（news/fund_flow/sector）与名录类（stock_info）无历史区间概念，
    不在历史采集中构建，避免产生"选了日期不生效"的假任务。
    """
    range_tasks = {
        "kline": {"start_date": start_date, "end_date": end_date, "adjust": "qfq"},
        "financial": {"report_type": "annual", "start_date": start_date, "end_date": end_date},
        "dragon_tiger": {"start_date": start_date, "end_date": end_date},
        "margin": {"start_date": start_date, "end_date": end_date},
    }
    selected = task_types if task_types else RANGE_TYPES
    return [
        {"task_type": t, "params": range_tasks[t]}
        for t in RANGE_TYPES
        if t in selected
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


def _compute_update_latest_tasks(stats: dict, task_types=None, today: str = None):
    """根据各类数据当前覆盖情况，计算"更新到最新"应提交的任务。

    stats: _get_collection_stats(db) 的返回，形如
           {type: {"record_count": int, "date_from": str|None, "date_to": str|None}}
    返回: (tasks, skipped)
          tasks  = [{"task_type": str, "params": dict}, ...]
          skipped = [type, ...]  # 区间类已是最新而跳过
    """
    from datetime import datetime, timedelta

    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    all_types = RANGE_TYPES + SNAPSHOT_TYPES + CATALOG_TYPES
    selected = task_types if task_types else all_types

    tasks, skipped = [], []
    for t in selected:
        if t in RANGE_TYPES:
            date_to = (stats.get(t) or {}).get("date_to")
            if date_to and date_to >= today:
                skipped.append(t)
                continue
            if date_to:
                start = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            params = {"start_date": start, "end_date": today}
            if t == "kline":
                params["adjust"] = "qfq"
            elif t == "financial":
                params["report_type"] = "annual"
            tasks.append({"task_type": t, "params": params})
        elif t in SNAPSHOT_TYPES:
            params = {"limit": 500} if t == "news" else {}
            tasks.append({"task_type": t, "params": params})
        elif t in CATALOG_TYPES:
            tasks.append({"task_type": t, "params": {"mode": "incremental"}})
    return tasks, skipped


@api_bp.route("/collect/update_latest", methods=["POST"])
def start_update_latest():
    """一键更新到最新：区间类从 DB 最新日期补到今天，快照类抓最新，名录类增量补新。

    Body 参数:
      task_types (可选) 指定只更新哪几类，默认全部 8 类
    """
    from core.scheduler.scheduler import scheduler
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    task_types = data.get("task_types")

    db = DatabaseConfig.get_database()
    stats = _get_collection_stats(db)
    tasks, skipped = _compute_update_latest_tasks(stats, task_types)

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


def _get_collection_stats(db) -> dict:
    """查询各集合的记录数和数据时间区间，用于 progress_all 展示"""
    from pymongo import ASCENDING, DESCENDING
    from datetime import datetime as _dt

    def _fmt_dt(v):
        if v is None:
            return None
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        s = str(v)
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        return s[:10] if s else None

    meta = {
        "kline":        ("kline",        "date",       ASCENDING),
        "stock_info":   ("stock_info",   None,         None),
        "financial":    ("financial",    "report_date",ASCENDING),
        "news":         ("news",         "datetime",   ASCENDING),
        "fund_flow":    ("fund_flow",    None,         None),
        "dragon_tiger": ("dragon_tiger", "上榜日",      ASCENDING),
        "sector":       ("block",        None,         None),
        "margin":       ("margin_data",  "信用交易日期", ASCENDING),
    }
    result = {}
    for task_type, (coll_name, date_field, _) in meta.items():
        coll = db[coll_name]
        count = coll.count_documents({})
        date_from, date_to = None, None
        if date_field and count > 0:
            try:
                oldest = coll.find_one({date_field: {"$exists": True}}, sort=[(date_field, ASCENDING)])
                newest = coll.find_one({date_field: {"$exists": True}}, sort=[(date_field, DESCENDING)])
                date_from = _fmt_dt(oldest.get(date_field)) if oldest else None
                date_to   = _fmt_dt(newest.get(date_field)) if newest else None
            except Exception:
                pass
        result[task_type] = {"record_count": count, "date_from": date_from, "date_to": date_to}
    return result


@api_bp.route("/collect/progress_all", methods=["GET"])
def progress_all():
    """聚合查询所有8类数据任务的最新进度（始终取最新一次任务）"""
    from core.scheduler.scheduler import scheduler
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    coll_stats = _get_collection_stats(db)

    all_tasks = scheduler.list_tasks(limit=500)

    target_types = ["kline", "stock_info", "financial", "news",
                    "fund_flow", "dragon_tiger", "sector", "margin"]

    # 每种类型只取 task_id 时间戳最大（最新）的那条，忽略状态优先级
    latest_by_type: dict = {}
    for task in all_tasks:
        ttype = task.get("task_type")
        if ttype not in target_types:
            continue
        tid = task.get("task_id", "")
        existing = latest_by_type.get(ttype)
        if not existing or _parse_task_ts(tid) > _parse_task_ts(existing.get("task_id", "")):
            latest_by_type[ttype] = task

    summary = {}
    total_progress = 0
    total_items = 0
    completed_count = 0

    for ttype in target_types:
        task = latest_by_type.get(ttype)
        if not task:
            stats = coll_stats.get(ttype, {})
            summary[ttype] = {
                "task_type": ttype,
                "status": "not_started",
                "progress": 0, "total": 0, "percent": 0.0, "task_id": None,
                "success": 0, "failed": 0, "elapsed_time": 0,
                "record_count": stats.get("record_count", 0),
                "date_from": stats.get("date_from"),
                "date_to": stats.get("date_to"),
            }
            continue

        progress = task.get("progress", 0)
        total = task.get("total", 0)
        status = task.get("status", "unknown")
        percent = round(progress / total * 100, 1) if total > 0 else (100.0 if status == "completed" else 0.0)
        success = task.get("success", 0)
        failed_cnt = task.get("failed", 0)

        stats = coll_stats.get(ttype, {})
        summary[ttype] = {
            "type": ttype,
            "task_type": ttype,
            "status": status,
            "progress": progress,
            "total": total,
            "percent": percent,
            "success": success,
            "failed": failed_cnt,
            "task_id": task.get("task_id"),
            "elapsed_time": round(task.get("elapsed_time", 0), 1),
            "record_count": stats.get("record_count", 0),
            "date_from": stats.get("date_from"),
            "date_to": stats.get("date_to"),
        }

        if status == "completed":
            completed_count += 1
        if total > 0:
            total_progress += progress
            total_items += total

    overall_percent = round(total_progress / total_items * 100, 1) if total_items > 0 else 0.0

    return jsonify({
        "success": True,
        "overall_percent": overall_percent,
        "completed_types": completed_count,
        "total_types": len(target_types),
        "all_done": completed_count == len(target_types),
        "tasks": summary,
        "timestamp": datetime.now().isoformat()
    })


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
    import akshare as ak
    from datetime import datetime

    try:
        df = ak.stock_zh_index_spot_em()
        indices = []
        for idx in MARKET_INDEX_CODES:
            code = idx["code"][2:]
            row = df[df["代码"] == code]
            if not row.empty:
                indices.append({
                    "code": idx["code"].upper(),
                    "name": idx["name"],
                    "price": float(row.iloc[0]["最新价"]),
                    "change": float(row.iloc[0]["涨跌幅"]),
                    "change_amount": float(row.iloc[0]["涨跌额"]),
                    "volume": float(row.iloc[0]["成交量"]),
                    "amount": float(row.iloc[0]["成交额"]),
                    "amplitude": float(row.iloc[0]["振幅"]) if "振幅" in row.columns else 0,
                    "high": float(row.iloc[0]["最高"]) if "最高" in row.columns else None,
                    "low": float(row.iloc[0]["最低"]) if "最低" in row.columns else None,
                    "open": float(row.iloc[0]["今开"]) if "今开" in row.columns else None,
                    "prev_close": float(row.iloc[0]["昨收"]) if "昨收" in row.columns else None,
                })

        return jsonify({
            "success": True,
            "count": len(indices),
            "data": indices,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get market indices: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/market/realtime-quotes", methods=["POST"])
def get_realtime_quotes():
    import akshare as ak
    from datetime import datetime

    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    normalized_codes = [_normalize_code(c) for c in codes]
    unique_codes = list(set(normalized_codes))

    try:
        df = ak.stock_zh_a_spot_em()
        results = []

        for code in unique_codes:
            code_num = code[2:]
            row = df[df["代码"] == code_num]
            if not row.empty:
                results.append({
                    "code": code.upper(),
                    "name": str(row.iloc[0]["名称"]),
                    "price": float(row.iloc[0]["最新价"]) if pd.notna(row.iloc[0]["最新价"]) else None,
                    "change": float(row.iloc[0]["涨跌幅"]) if pd.notna(row.iloc[0]["涨跌幅"]) else 0,
                    "change_amount": float(row.iloc[0]["涨跌额"]) if pd.notna(row.iloc[0]["涨跌额"]) else 0,
                    "volume": float(row.iloc[0]["成交量"]) if pd.notna(row.iloc[0]["成交量"]) else None,
                    "amount": float(row.iloc[0]["成交额"]) if pd.notna(row.iloc[0]["成交额"]) else None,
                    "open": float(row.iloc[0]["今开"]) if pd.notna(row.iloc[0]["今开"]) else None,
                    "high": float(row.iloc[0]["最高"]) if pd.notna(row.iloc[0]["最高"]) else None,
                    "low": float(row.iloc[0]["最低"]) if pd.notna(row.iloc[0]["最低"]) else None,
                    "prev_close": float(row.iloc[0]["昨收"]) if pd.notna(row.iloc[0]["昨收"]) else None,
                    "turnover": float(row.iloc[0]["换手率"]) if pd.notna(row.iloc[0]["换手率"]) else None,
                })

        return jsonify({
            "success": True,
            "count": len(results),
            "data": results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get realtime quotes: {e}")
        return jsonify({"error": str(e)}), 500


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
    if not provider:
        return jsonify({"error": "provider is required"}), 400
    ai_key_manager.update_key(provider, name, enabled, priority, api_key, base_url)
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


@api_bp.route("/pick/smart", methods=["POST"])
def smart_pick():
    from modules.ai.smart_picker import smart_picker
    data = request.get_json() or {}
    top_n = data.get("top_n", 10)
    factors = data.get("factors", ["trend", "volume", "value", "fund_flow"])
    results = smart_picker.pick(top_n=top_n, factors=factors)
    return jsonify({"success": True, "count": len(results), "data": results})


@api_bp.route("/strategy-configs", methods=["GET"])
def get_strategy_configs():
    from modules.strategies.strategy_config_manager import strategy_config_manager

    enabled_only = request.args.get("enabled_only", "false").lower() == "true"
    strategies = strategy_config_manager.list_strategies(enabled_only=enabled_only)

    return jsonify({
        "success": True,
        "count": len(strategies),
        "data": strategies
    })


@api_bp.route("/strategy-configs/<name>", methods=["GET"])
def get_strategy_config(name):
    from modules.strategies.strategy_config_manager import strategy_config_manager

    strategy = strategy_config_manager.get_strategy(name)

    if not strategy:
        return jsonify({"error": "Strategy not found"}), 404

    return jsonify({
        "success": True,
        "data": strategy
    })


@api_bp.route("/strategy-configs", methods=["POST"])
def create_or_update_strategy_config():
    from modules.strategies.strategy_config_manager import strategy_config_manager

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name = data.get("name")
    strategy_type = data.get("strategy_type")
    description = data.get("description", "")
    params = data.get("params", {})
    enabled = data.get("enabled", True)

    if not name or not strategy_type:
        return jsonify({"error": "name and strategy_type are required"}), 400

    success = strategy_config_manager.create_or_update_strategy(
        name=name,
        strategy_type=strategy_type,
        description=description,
        params=params,
        enabled=enabled
    )

    return jsonify({
        "success": success,
        "message": "Strategy saved successfully"
    })


@api_bp.route("/strategy-configs/<name>", methods=["PUT"])
def update_strategy_config(name):
    from modules.strategies.strategy_config_manager import strategy_config_manager

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    params = data.get("params", {})
    success = strategy_config_manager.update_strategy_params(name, params)

    if not success:
        return jsonify({"error": "Strategy not found"}), 404

    return jsonify({
        "success": True,
        "message": "Strategy params updated"
    })


@api_bp.route("/strategy-configs/<name>/toggle", methods=["POST"])
def toggle_strategy_config(name):
    from modules.strategies.strategy_config_manager import strategy_config_manager

    data = request.get_json() or {}
    enabled = data.get("enabled", True)

    success = strategy_config_manager.toggle_strategy(name, enabled)

    if not success:
        return jsonify({"error": "Strategy not found"}), 404

    status_text = "enabled" if enabled else "disabled"
    return jsonify({
        "success": True,
        "message": f"Strategy {status_text}"
    })


@api_bp.route("/strategy-configs/<name>", methods=["DELETE"])
def delete_strategy_config(name):
    from modules.strategies.strategy_config_manager import strategy_config_manager

    success = strategy_config_manager.delete_strategy(name)

    if not success:
        return jsonify({"error": "Strategy not found"}), 404

    return jsonify({
        "success": True,
        "message": "Strategy deleted"
    })


@api_bp.route("/sector", methods=["GET"])
def get_sector_list():
    from core.storage.mongo_storage import BlockStorage

    storage = BlockStorage()
    # block 集合存储中文字段名，无 block_type 字段，直接取全部
    records = storage.find_many({})

    result = []
    for r in records:
        r.pop("_id", None)
        r.pop("_updated_at", None)
        # 兼容中文字段名（采集时直接存 DataFrame 列名）
        name = r.get("name") or r.get("行业") or r.get("block_name", "")
        net_flow = r.get("net_flow") or r.get("净额") or 0
        change_rate = r.get("change_rate") or r.get("行业-涨跌幅") or 0
        if not name:
            continue
        result.append({
            "name": name,
            "net_flow": float(net_flow) if net_flow else 0,
            "change_rate": float(change_rate) if change_rate else 0,
        })

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