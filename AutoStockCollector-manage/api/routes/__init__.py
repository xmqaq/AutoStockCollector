"""
API路由定义
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Any, Dict

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def register_routes(app):
    app.register_blueprint(api_bp)

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

    return jsonify({
        "success": True,
        "code": code,
        "count": len(records),
        "data": records
    })


@api_bp.route("/kline/<code>/latest", methods=["GET"])
def get_latest_kline(code):
    from core.storage.mongo_storage import KlineStorage

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

    storage = StockInfoStorage()
    info = storage.get_by_code(code)

    if not info:
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

    storage = FundFlowStorage()
    # fund_flow 存储的 code 为纯数字，兼容 SH/SZ 前缀入参
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
    group_id = request.args.get("group_id")

    manager = WatchlistManager()
    stocks = manager.get_watchlist(user_id, group_id)

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
    group_id = data.get("group_id", "default")
    priority = data.get("priority", 0)

    if not code:
        return jsonify({"error": "code is required"}), 400

    manager = WatchlistManager()
    success = manager.add_stock(user_id, code, group_id, priority)

    return jsonify({
        "success": success,
        "message": "Added to watchlist" if success else "Failed to add"
    })


@api_bp.route("/watchlist/<code>", methods=["DELETE"])
def remove_from_watchlist(code):
    from modules.watchlist.watchlist import WatchlistManager

    user_id = request.args.get("user_id", "default")

    manager = WatchlistManager()
    success = manager.remove_stock(user_id, code)

    return jsonify({
        "success": success,
        "message": "Removed from watchlist" if success else "Failed to remove"
    })


@api_bp.route("/watchlist/groups", methods=["GET"])
def get_watchlist_groups():
    from modules.watchlist.watchlist import WatchlistManager

    user_id = request.args.get("user_id", "default")

    manager = WatchlistManager()
    groups = manager.get_groups(user_id)

    return jsonify({
        "success": True,
        "groups": groups
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
            initial_cash=data.get("initial_cash", 1000000)
        )
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
    """根据日期范围构建8类数据任务配置"""
    all_tasks = [
        {
            "task_type": "kline",
            "params": {"start_date": start_date, "end_date": end_date, "adjust": "qfq"}
        },
        {
            "task_type": "stock_info",
            "params": {"mode": "full"}
        },
        {
            "task_type": "financial",
            "params": {"report_type": "annual", "start_date": start_date, "end_date": end_date}
        },
        {
            "task_type": "news",
            "params": {"limit": 500, "start_date": start_date, "end_date": end_date}
        },
        {
            "task_type": "fund_flow",
            "params": {"start_date": start_date, "end_date": end_date}
        },
        {
            "task_type": "dragon_tiger",
            "params": {"start_date": start_date, "end_date": end_date}
        },
        {
            "task_type": "sector",
            "params": {}
        },
        {
            "task_type": "margin",
            "params": {"start_date": start_date, "end_date": end_date}
        },
    ]
    if task_types:
        return [t for t in all_tasks if t["task_type"] in task_types]
    return all_tasks


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


def _parse_task_ts(task_id: str) -> int:
    """从 task_id（如 kline_1779931587433）提取毫秒时间戳，用于排序"""
    try:
        return int(task_id.rsplit("_", 1)[-1])
    except Exception:
        return 0


@api_bp.route("/collect/progress_all", methods=["GET"])
def progress_all():
    """聚合查询所有8类数据任务的最新进度（始终取最新一次任务）"""
    from core.scheduler.scheduler import scheduler

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
            summary[ttype] = {"status": "not_started", "progress": 0, "total": 0, "percent": 0.0, "task_id": None}
            continue

        progress = task.get("progress", 0)
        total = task.get("total", 0)
        status = task.get("status", "unknown")
        percent = round(progress / total * 100, 1) if total > 0 else (100.0 if status == "completed" else 0.0)
        success = task.get("success", 0)
        failed_cnt = task.get("failed", 0)

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
    
    storage = DragonTigerStorage()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    code = request.args.get("code")
    limit = int(request.args.get("limit", 100))
    
    filter_doc = {}
    if code:
        filter_doc["code"] = code
    if start_date and end_date:
        filter_doc["date"] = {"$gte": start_date, "$lte": end_date}
    
    records = storage.find_many(filter_doc, sort=[("date", -1)], limit=limit)
    
    for record in records:
        record.pop("_id", None)
        record.pop("_updated_at", None)
    
    result = []
    for r in records:
        result.append({
            "code": r.get("code", ""),
            "name": r.get("name", r.get("股票名称", "")),
            "date": r.get("date", r.get("日期", "")),
            "reason": r.get("reason", r.get("上榜原因", "")),
            "total_amount": r.get("total_amount", r.get("总成交额", 0)),
            "net_buy": r.get("net_buy", r.get("净买入额", 0)),
        })
    
    return jsonify({
        "success": True,
        "count": len(result),
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
    # margin 集合存储的是市场级汇总数据，无法按个股 code 过滤
    if start_date and end_date:
        filter_doc["信用交易日期"] = {"$gte": start_date, "$lte": end_date}

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