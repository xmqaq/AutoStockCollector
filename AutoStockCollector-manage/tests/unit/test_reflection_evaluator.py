"""ReflectionEvaluator 单测:决策日价格取数与对错判定。"""
from datetime import timedelta
from utils.helpers import beijing_now
from modules.ai.reflection.evaluator import ReflectionEvaluator
from modules.ai.reflection.decision_logger import DecisionLogger


class FakeLoggerCollection:
    def __init__(self):
        self.docs = {}
    def update_one(self, q, u, upsert=False):
        key = (q.get("stock_code"), q.get("date_key"))
        self.docs[key] = u["$set"]
        class R: upserted_id = "new"
        return R()


def test_same_day_decision_upserts_not_inserts():
    col = FakeLoggerCollection()
    lg = DecisionLogger(collection=col)
    lg.log_decision("run1", "sh600000", {"decision": "适度关注", "bull_score": 65, "bear_score": 35})
    lg.log_decision("run2", "sh600000", {"decision": "中性观望", "bull_score": 50, "bear_score": 50})
    assert len(col.docs) == 1                          # 同日同股只剩一条
    only = list(col.docs.values())[0]
    assert only["decision"] == "中性观望"               # 保留最后一次
    assert only["predicted_direction"] == "neutral"


class FakeCollection:
    def __init__(self):
        self.updates = []
    def update_one(self, q, u):
        self.updates.append((q, u))
    def find_one(self, *a, **k):
        return None


def _mk_klines_desc(prices_by_date):
    """[(date, close)] 转降序 kline 文档列表。"""
    return [{"date": d, "close": c} for d, c in
            sorted(prices_by_date, key=lambda x: x[0], reverse=True)]


def _evaluator_with(klines_desc, index_klines_desc=None):
    def kline_loader(code, limit):
        # 指数K线注入:Task 2 基准化判定用
        if code.lower().startswith("sh000001"):
            return (index_klines_desc or [])[:limit]
        return klines_desc[:limit]
    return ReflectionEvaluator(collection=FakeCollection(), kline_loader=kline_loader)


def _record(days_ago, direction="bullish"):
    ts = (beijing_now() - timedelta(days=days_ago)).isoformat()
    return {"_id": "x", "stock_code": "sh600000", "timestamp": ts,
            "predicted_direction": direction}


def test_decision_price_is_nearest_at_or_before_decision_date():
    """决策价必须取最接近且不晚于决策日的K线,不能取窗口最老一根。"""
    now = beijing_now()
    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(12)]
    # 价格随日期递增:最新 21 元,决策日(7天前)14 元,窗口最老 10 元
    prices = [(d, 21.0 - i) for i, d in enumerate(days)]
    ev = _evaluator_with(_mk_klines_desc(prices))
    r = ev.evaluate(_record(days_ago=7))
    assert r is not None
    assert r["decision_price"] == 14.0  # days[7] 对应 21-7
    assert r["current_price"] == 21.0


def test_decision_on_non_trading_day_uses_prior_close():
    """决策日无K线(周末)时,取其前最近一根。"""
    now = beijing_now()
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    prices = [(d(0), 12.0), (d(1), 11.0), (d(5), 10.0), (d(6), 9.0)]
    ev = _evaluator_with(_mk_klines_desc(prices))
    r = ev.evaluate(_record(days_ago=3))   # 决策日 d(3) 无K线 → 用 d(5)=10.0
    assert r["decision_price"] == 10.0


def _index_klines(now, ret_pct, days):
    """构造指数K线:days 天前 100 → 现在 100*(1+ret)。"""
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    return _mk_klines_desc([(d(0), 100.0 * (1 + ret_pct / 100)), (d(days), 100.0)])


def test_bullish_judged_by_excess_over_index():
    """有指数数据:看多,个股+1%但指数+5% → 超额-4% → 错。"""
    now = beijing_now()
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    stock = _mk_klines_desc([(d(0), 10.1), (d(7), 10.0)])      # +1%
    idx = _index_klines(now, ret_pct=5.0, days=7)               # +5%
    ev = _evaluator_with(stock, idx)
    r = ev.evaluate(_record(days_ago=7, direction="bullish"))
    assert r["accuracy"] == "wrong"
    assert r["benchmark"] == "index"
    assert abs(r["excess_return"] - (-3.9)) < 0.2


def test_threshold_fallback_scales_with_days():
    """无指数数据:11天前看多,+5% < 6% 阈值 → partial 而非 correct。"""
    now = beijing_now()
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    stock = _mk_klines_desc([(d(0), 10.5), (d(11), 10.0)])      # +5%
    ev = _evaluator_with(stock, index_klines_desc=[])
    r = ev.evaluate(_record(days_ago=11, direction="bullish"))
    assert r["benchmark"] == "threshold"
    assert r["accuracy"] == "partial"


def test_neutral_correct_when_small_excess():
    now = beijing_now()
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    stock = _mk_klines_desc([(d(0), 10.1), (d(5), 10.0)])
    idx = _index_klines(now, ret_pct=0.0, days=5)
    ev = _evaluator_with(stock, idx)
    r = ev.evaluate(_record(days_ago=5, direction="neutral"))
    assert r["accuracy"] == "correct"


def test_index_return_cached_per_instance():
    """同实例同决策日只查一次指数K线。"""
    now = beijing_now()
    d = lambda i: (now - timedelta(days=i)).strftime("%Y-%m-%d")
    idx = _mk_klines_desc([(d(0), 105.0), (d(7), 100.0)])
    calls = []
    def loader(code, limit):
        if code.lower().startswith("sh000001"):
            calls.append(code)
            return idx
        return _mk_klines_desc([(d(0), 10.1), (d(7), 10.0)])
    ev = ReflectionEvaluator(collection=FakeCollection(), kline_loader=loader)
    day = d(7)
    ev._index_return(day)
    ev._index_return(day)
    assert len(calls) == 1
