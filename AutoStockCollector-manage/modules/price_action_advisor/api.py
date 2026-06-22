"""价格行为学 — Flask Blueprint（异步 + 进度轮询）。"""
import threading
import time
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request
from api.auth_utils import login_required
from utils.logger import get_logger
from .schemas import PriceActionRequest, VALID_TIMEFRAMES

logger = get_logger(__name__)

SYMBOL_RE = re.compile(r"^\d{6}$")


def _parse_price_action_input(data: dict) -> Optional[dict]:
    """统一校验并解析 PriceAction 输入参数。返回 dict 或 None（校验失败时）。"""
    symbols = data.get("symbols", [])
    if not symbols or not isinstance(symbols, list):
        return {"error": "请至少指定一个股票代码"}

    for s in symbols:
        if not isinstance(s, str) or not (SYMBOL_RE.match(s) or re.match(r"^(SH|SZ|BJ)\d{6}$", s)):
            return {"error": f"无效股票代码格式: {s}"}
    if len(symbols) > 50:
        return {"error": "单次最多分析 50 只股票"}

    timeframe = data.get("timeframe", "daily")
    if timeframe not in VALID_TIMEFRAMES:
        return {"error": f"无效 K 线周期: {timeframe}，可选: {', '.join(sorted(VALID_TIMEFRAMES))}"}

    try:
        risk_pct = float(data.get("account_risk", 0.02))
    except (ValueError, TypeError):
        return {"error": "account_risk 必须为数字"}
    if not (0.001 <= risk_pct <= 0.5):
        return {"error": "account_risk 范围 0.001~0.5"}

    try:
        balance = float(data.get("account_balance", 100000))
    except (ValueError, TypeError):
        return {"error": "account_balance 必须为数字"}
    if balance < 1000:
        return {"error": "account_balance 最少 1000"}

    use_ai = bool(data.get("use_ai", False))

    return {
        "symbols": symbols,
        "timeframe": timeframe,
        "risk_pct": risk_pct,
        "balance": balance,
        "use_ai": use_ai,
    }

pa_bp = Blueprint("price_action", __name__, url_prefix="/api/v1/ai")

_engine = None
_engine_lock = threading.Lock()
_tasks = {}
_tasks_lock = threading.Lock()
_TASK_TTL = 300  # 任务完成/失败后保留秒数


def _evict_stale_tasks():
    """清理过期任务，防止内存泄漏。"""
    now = time.time()
    with _tasks_lock:
        stale = [tid for tid, t in list(_tasks.items())
                 if t.get("completed_at", 0) and now - t["completed_at"] > _TASK_TTL]
        for tid in stale:
            del _tasks[tid]
        if stale:
            logger.info(f"[PA] Evicted {len(stale)} stale tasks")


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from .price_action_engine import PriceActionEngine
                _engine = PriceActionEngine()
    return _engine


def _run_analysis(task_id: str, symbols: list, timeframe: str, risk_pct: float, balance: float, use_ai: bool = False):
    try:
        symbols = [s.strip() for s in symbols if s and s.strip()]
        if not symbols:
            with _tasks_lock:
                _tasks[task_id] = {"status": "failed", "progress": 0, "message": "无有效股票代码"}
            return

        with _tasks_lock:
            _tasks[task_id] = {"status": "processing", "progress": 0, "message": "正在初始化..."}

        _evict_stale_tasks()
        engine = _get_engine()
        total = len(symbols)

        results = [None] * total

        def make_callback(sym: str, idx: int):
            def cb(pct: int, msg: str):
                overall = int((idx + pct / 100.0) / total * 100)
                with _tasks_lock:
                    _tasks[task_id]["progress"] = min(overall, 98)
                    _tasks[task_id]["message"] = f"[{sym}] {msg}"
            return cb

        from .config import PAConfig
        concurrency = max(1, min(PAConfig.FETCH_CONCURRENCY, total))

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {}
            for i, symbol in enumerate(symbols):
                future = pool.submit(
                    engine.analyze,
                    symbol, timeframe=timeframe, risk_pct=risk_pct,
                    account_balance=balance, use_ai=use_ai,
                    progress_callback=make_callback(symbol, i),
                )
                futures[future] = i

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning(f"[PA] analyze error {symbols[idx]}: {e}")
                    results[idx] = {"symbol": symbols[idx], "signal": "ERROR", "error": str(e)}

        results = [r for r in results if r is not None]

        with _tasks_lock:
            _tasks[task_id]["progress"] = 98
            _tasks[task_id]["message"] = "保存结果..."

        try:
            from config.database import DatabaseConfig
            from .config import PAConfig
            db = DatabaseConfig.get_database()
            db[PAConfig.RESULTS_COLLECTION].insert_one({
                "task_id": task_id,
                "symbols": symbols,
                "timeframe": timeframe,
                "results": results,
                "created_at": datetime.now(),
            })
        except Exception as e:
            logger.warning(f"[PA] save result error: {e}")

        with _tasks_lock:
            _tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "分析完成",
                "results": results,
                "completed_at": time.time(),
            }
    except Exception as e:
        logger.error(f"[PA] task {task_id} failed: {e}")
        with _tasks_lock:
            _tasks[task_id] = {"status": "failed", "progress": 0, "message": str(e), "completed_at": time.time()}


def _analyze_single_sync(symbol: str, timeframe: str, risk_pct: float, balance: float, use_ai: bool = False) -> dict:
    """同步分析单只股票（用于单股 API）。"""
    engine = _get_engine()
    return engine.analyze(symbol, timeframe=timeframe, risk_pct=risk_pct, account_balance=balance, use_ai=use_ai)


@pa_bp.route("/price-action", methods=["POST"])
@login_required
def price_action_batch():
    """批量分析 — 异步，返回 task_id。"""
    data = request.get_json(silent=True) or {}
    parsed = _parse_price_action_input(data)
    if parsed is None or "error" in parsed:
        return jsonify({"success": False, "error": parsed.get("error", "参数校验失败")}), 400

    symbols, timeframe, risk_pct, balance, use_ai = (
        parsed["symbols"], parsed["timeframe"],
        parsed["risk_pct"], parsed["balance"], parsed["use_ai"],
    )

    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "progress": 0, "message": "任务已提交"}

    thread = threading.Thread(
        target=_run_analysis,
        args=(task_id, symbols, timeframe, risk_pct, balance, use_ai),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "message": "分析任务已提交，请轮询进度"})


@pa_bp.route("/price-action/result/<task_id>", methods=["GET"])
@login_required
def get_result(task_id: str):
    """轮询分析进度。"""
    with _tasks_lock:
        task = _tasks.get(task_id)

    if task is None:
        return jsonify({"success": False, "error": "任务不存在或已过期"}), 404

    resp = {
        "success": True,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "message": task.get("message", ""),
    }
    ended_at = task.get("completed_at") or 0
    resp["expired"] = bool(ended_at) and (time.time() - ended_at > _TASK_TTL)
    if task["status"] == "completed" and "results" in task:
        resp["data"] = task["results"]
    return jsonify(resp)


@pa_bp.route("/price-action/single", methods=["POST"])
@login_required
def price_action_single():
    """单股分析（异步，返回 task_id，前端轮询）。"""
    data = request.get_json(silent=True) or {}
    symbol = (data.get("symbol", "") or "").strip()
    if not symbol:
        return jsonify({"success": False, "error": "symbol 必填"}), 400
    if not (SYMBOL_RE.match(symbol) or re.match(r"^(SH|SZ|BJ)\d{6}$", symbol)):
        return jsonify({"success": False, "error": f"无效股票代码: {symbol}"}), 400

    timeframe = data.get("timeframe", "daily")
    if timeframe not in VALID_TIMEFRAMES:
        return jsonify({"success": False, "error": f"无效 K 线周期: {timeframe}"}), 400

    try:
        risk_pct = float(data.get("risk", 0.02))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "risk 必须为数字"}), 400
    if not (0.001 <= risk_pct <= 0.5):
        return jsonify({"success": False, "error": "risk 范围 0.001~0.5"}), 400

    try:
        balance = float(data.get("balance", 100000))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "balance 必须为数字"}), 400
    if balance < 1000:
        return jsonify({"success": False, "error": "balance 最少 1000"}), 400

    use_ai = data.get("use_ai", False)

    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "progress": 0, "message": "单股分析已提交"}

    thread = threading.Thread(
        target=_run_analysis,
        args=(task_id, [symbol], timeframe, risk_pct, balance, use_ai),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "message": "单股分析已提交，请轮询进度"})


# ─── 全市场扫描 ───────────────────────────────────────────────────────────

_scan_lock = threading.Lock()
_last_scan_at = 0.0
_SCAN_COOLDOWN = 300  # 两次扫描间隔至少 300 秒
_SCAN_UNIVERSE_CACHE = None
_SCAN_UNIVERSE_CACHE_AT = 0.0
_SCAN_UNIVERSE_TTL = 3600  # 扫描池缓存 1 小时


def _get_scan_universe(min_market_cap: float = 50_0000_0000) -> list:
    """从 DB 动态加载扫描池，按市值过滤，减少无效扫描。

    缓存 1 小时，fallback 到静态列表。
    """
    global _SCAN_UNIVERSE_CACHE, _SCAN_UNIVERSE_CACHE_AT
    now = time.time()
    if _SCAN_UNIVERSE_CACHE and now - _SCAN_UNIVERSE_CACHE_AT < _SCAN_UNIVERSE_TTL:
        return _SCAN_UNIVERSE_CACHE

    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        pipeline = [
            {"$match": {"market_cap": {"$gte": min_market_cap}}},
            {"$sort": {"market_cap": -1}},
            {"$limit": 300},
            {"$project": {"_id": 0, "code": 1}},
        ]
        docs = list(db.stock_valuation.aggregate(pipeline))
        if docs:
            codes = [d["code"] for d in docs if d.get("code")]
            _SCAN_UNIVERSE_CACHE = codes
            _SCAN_UNIVERSE_CACHE_AT = now
            logger.info(f"[PA] Dynamic scan universe: {len(codes)} stocks (cap>={min_market_cap})")
            return codes
    except Exception as e:
        logger.warning(f"[PA] Dynamic scan universe failed, fallback to static: {e}")

    # fallback
    return list(_SCAN_UNIVERSE_STATIC)


# 兼容别名：供 cron.py 等外部模块导入（静态后备列表）
_SCAN_UNIVERSE = list  # placeholder; 在静态列表定义后赋值

_SCAN_UNIVERSE_STATIC = [
    "000001", "000002", "000333", "000568", "000625", "000651", "000725", "000768",
    "000858", "002007", "002049", "002230", "002236", "002241", "002304", "002340",
    "002371", "002415", "002459", "002460", "002466", "002475", "002493", "002594",
    "002601", "002709", "002714", "002812", "002920", "003816",
    "300014", "300015", "300059", "300122", "300124", "300274", "300308", "300413",
    "300433", "300498", "300502", "300750", "300751", "300760", "300782",
    "600000", "600009", "600010", "600011", "600015", "600016", "600019", "600028",
    "600030", "600031", "600036", "600048", "600050", "600085", "600089", "600104",
    "600196", "600276", "600309", "600340", "600346", "600383", "600406", "600436",
    "600438", "600519", "600547", "600570", "600585", "600588", "600690", "600703",
    "600723", "600745", "600809", "600887", "600893", "600900", "600918", "600941",
    "600958", "600999",
    "601012", "601066", "601088", "601111", "601117", "601127", "601138", "601166",
    "601169", "601186", "601211", "601225", "601236", "601288", "601318", "601328",
    "601336", "601360", "601377", "601390", "601398", "601601", "601628", "601633",
    "601658", "601668", "601669", "601688", "601728", "601766", "601788", "601800",
    "601816", "601818", "601857", "601878", "601881", "601888", "601899", "601919",
    "601939", "601985", "601988", "601989", "601995",
    "603259", "603288", "603501", "603986",
    "688008", "688009", "688012", "688036", "688041", "688065", "688111", "688126",
    "688169", "688187", "688223", "688256", "688271", "688303", "688396", "688561",
    "688599", "688777", "688981",
]
_SCAN_UNIVERSE = _SCAN_UNIVERSE_STATIC  # 模块别名供 cron.py 兼容


_SCAN_TIMEOUT = 120  # 扫描超时秒数


def _run_scan(scan_id: str, symbols: list, timeframe: str, risk_pct: float, balance: float):
    try:
        concurrency = max(1, min(PAConfig.FETCH_CONCURRENCY, len(symbols) // 2, 8))

        # 过滤空/无效代码
        symbols = [s.strip() for s in symbols if s and s.strip()]
        if not symbols:
            with _tasks_lock:
                _tasks[scan_id] = {"status": "failed", "progress": 0, "message": "无有效股票代码"}
            return

        with _tasks_lock:
            _tasks[scan_id] = {"status": "processing", "progress": 0, "message": f"全市场扫描中（{concurrency} 并发）..."}

        total = len(symbols)
        engine = _get_engine()
        results = []
        _scan_results_lock = threading.Lock()
        _abort = threading.Event()
        _scan_start = time.monotonic()

        def scan_one(symbol: str):
            if _abort.is_set():
                return
            if not symbol or not SYMBOL_RE.match(symbol):
                return
            try:
                sig = engine.analyze(symbol, timeframe=timeframe, risk_pct=risk_pct, account_balance=balance, use_ai=False)
                if sig.get("signal") in ("BUY_SETUP", "SELL_SETUP", "WEAK_BUY", "WEAK_SELL"):
                    with _scan_results_lock:
                        results.append(sig)
            except Exception as e:
                logger.warning(f"[Scan] {symbol} error: {e}")

        done_count = 0
        _done_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(scan_one, s): s for s in symbols}
            for future in as_completed(futures):
                with _done_lock:
                    done_count += 1
                elapsed = time.monotonic() - _scan_start
                if not _abort.is_set() and elapsed > _SCAN_TIMEOUT:
                    _abort.set()
                    logger.warning(f"[Scan] 扫描超时 ({elapsed:.0f}s)，中止剩余 {total - done_count} 只")
                    with _tasks_lock:
                        _tasks[scan_id]["message"] = f"扫描超时，已处理 {done_count}/{total}"
                if done_count % 20 == 0 or done_count == total:
                    with _tasks_lock:
                        _tasks[scan_id]["progress"] = int(done_count / total * 100)
                        _tasks[scan_id]["message"] = f"扫描中 {done_count}/{total}"

        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        try:
            from config.database import DatabaseConfig
            from .config import PAConfig
            db = DatabaseConfig.get_database()
            db["pa_scan_results"].insert_one({
                "scan_id": scan_id,
                "timeframe": timeframe,
                "total_scanned": total,
                "signal_count": len(results),
                "results": results,
                "created_at": datetime.now(),
            })
        except Exception as e:
            logger.warning(f"[Scan] save error: {e}")

        with _tasks_lock:
            _tasks[scan_id] = {
                "status": "completed", "progress": 100,
                "message": f"扫描完成: {len(results)}/{total} 个信号",
                "results": results,
                "completed_at": time.time(),
            }
    except Exception as e:
        logger.error(f"[Scan] scan failed: {e}")
        with _tasks_lock:
            _tasks[scan_id] = {"status": "failed", "progress": 0, "message": str(e), "completed_at": time.time()}


@pa_bp.route("/price-action/scan", methods=["POST"])
@login_required
def price_action_scan():
    """全市场扫描 — 异步，返回发现的信号。"""
    global _last_scan_at
    with _scan_lock:
        now = time.time()
        if now - _last_scan_at < _SCAN_COOLDOWN:
            remaining = int(_SCAN_COOLDOWN - (now - _last_scan_at))
            # 返回最近一次扫描的 task_id
            for tid, t in list(_tasks.items()):
                if t.get("status") in ("completed", "processing") and t.get("progress", 0) > 0:
                    return jsonify({
                        "success": True, "task_id": tid,
                        "message": f"扫描冷却中（还剩{remaining}s），返回最近任务",
                        "cached": True,
                    })
            return jsonify({"success": False, "error": f"扫描冷却中，请 {remaining} 秒后再试"}), 429
        _last_scan_at = now

    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols", _get_scan_universe())
    timeframe = data.get("timeframe", "daily")
    if timeframe not in VALID_TIMEFRAMES:
        return jsonify({"success": False, "error": f"无效 K 线周期: {timeframe}"}), 400
    try:
        risk_pct = float(data.get("account_risk", 0.02))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "account_risk 必须为数字"}), 400
    if not (0.001 <= risk_pct <= 0.5):
        return jsonify({"success": False, "error": "account_risk 范围 0.001~0.5"}), 400
    try:
        balance = float(data.get("account_balance", 100000))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "account_balance 必须为数字"}), 400
    if balance < 1000:
        return jsonify({"success": False, "error": "account_balance 最少 1000"}), 400

    scan_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[scan_id] = {"status": "queued", "progress": 0, "message": "扫描任务已提交"}

    thread = threading.Thread(
        target=_run_scan,
        args=(scan_id, symbols, timeframe, risk_pct, balance),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": scan_id, "message": "全市场扫描已启动"})


@pa_bp.route("/price-action/scan/latest", methods=["GET"])
@login_required
def get_latest_scan():
    """获取最近一次全市场扫描结果。"""
    try:
        from config.database import DatabaseConfig
        from .config import PAConfig
        db = DatabaseConfig.get_database()
        doc = db["pa_scan_results"].find_one(
            {}, sort=[("created_at", -1)],
        )
        if not doc:
            return jsonify({"success": False, "error": "暂无扫描记录"}), 404
        doc.pop("_id", None)
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.warning(f"[PA] scan latest error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@pa_bp.route("/price-action/history", methods=["GET"])
@login_required
def get_history():
    """获取最近的分析历史。"""
    try:
        from config.database import DatabaseConfig
        from .config import PAConfig
        db = DatabaseConfig.get_database()
        docs = list(
            db[PAConfig.RESULTS_COLLECTION]
            .find({}, {"results": 0})
            .sort("created_at", -1)
            .limit(20)
        )
        for d in docs:
            d.pop("_id", None)
        return jsonify({"success": True, "count": len(docs), "data": docs})
    except Exception as e:
        logger.warning(f"[PA] history error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
