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


@api_bp.route("/financial/<code>", methods=["GET"])
def get_financial(code):
    from core.storage.mongo_storage import FinancialStorage

    storage = FinancialStorage()
    report_date = request.args.get("report_date")

    if report_date:
        record = storage.get_by_code_and_period(code, report_date)
        records = [record] if record else []
    else:
        records = storage.find_many(
            {"code": code},
            sort=[("report_date", -1)]
        )

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
    record = storage.get_latest_flow(code)

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