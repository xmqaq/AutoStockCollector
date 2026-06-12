"""深度分析 prompt 构建单测:全部用假 data dict,不连库。"""
from modules.ai.engines.deep_analysis import DeepAnalysisService


def _full_data():
    return {
        "basic_info": {"code": "sh600000", "name": "浦发银行", "industry": "银行",
                       "market_cap_yi": 4000.0},
        "price_info": {"current_price": 10.0, "price_change_pct": 1.0,
                       "high_52w": 12.0, "low_52w": 8.0, "volume_ratio": 1.5,
                       "position_52w": 50.0},
        "financial": {"report_date": "2026-03-31", "report_type": "一季报",
                      "roe": 10.0, "revenue_yi": 500.0, "revenue_growth": 5.0,
                      "net_profit_yi": 150.0, "profit_growth": 3.0,
                      "gross_margin": None, "debt_ratio": 91.0,
                      "pe": 5.0, "pb": 0.5,
                      "history": [{"report_date": "2026-03-31", "report_type": "一季报",
                                   "revenue_yi": 500.0, "net_profit_yi": 150.0,
                                   "roe": 10.0, "gross_margin": None}]},
        "fund_flow": {"date": "2026-06-11", "main_net_inflow_yi": 1.2,
                      "inflow_ratio": 3.0, "turnover_rate": 1.1},
        "technical": {"trend": "多头排列", "macd_signal": "金叉", "rsi14": 55.0,
                      "momentum_20d": 4.0, "data_available": True},
        "scores": {"fundamental": {"score": 70, "details": {}},
                   "technical": {"score": 65, "details": {}},
                   "fund_flow": {"score": 60, "details": {}},
                   "valuation": {"score": 75, "details": {}},
                   "composite": 68.0},
        "news": [{"title": "公司发布一季报", "publish_time": "2026-06-10", "source": "x", "content": ""}],
        "dragon_margin": {"dragon_count_30d": 2, "dragon_net_buy_yi": 0.8,
                          "margin_balance_yi": 50.0, "margin_trend_pct": 4.2},
        "reflection": {"latest": None, "history": [], "stats": {}},
        "analysis_history": [],
        "data_freshness": {"kline_date": "2026-06-11", "report_date": "2026-03-31",
                           "fund_flow_date": "2026-06-11", "kline_stale": False},
    }


def test_prompt_contains_new_dimensions():
    svc = DeepAnalysisService(dal=object(), router=object())
    p = svc._build_ai_prompt(_full_data())
    for fragment in ("52周位置", "量比", "财务趋势", "公司发布一季报", "龙虎榜",
                     "融资融券", "数据截止", "2026-06-11", "【评级】"):
        assert fragment in p, f"prompt 缺少: {fragment}"


def test_prompt_marks_stale_kline():
    d = _full_data()
    d["data_freshness"]["kline_stale"] = True
    svc = DeepAnalysisService(dal=object(), router=object())
    p = svc._build_ai_prompt(d)
    assert "数据滞后" in p


def test_extract_rating_prefers_anchor_line():
    svc = DeepAnalysisService(dal=object(), router=object())
    text = "## 综合评级\n理由……\n【评级】谨慎回避\n\n附注:若后续放量可转为适度关注观察。"
    assert svc._extract_rating(text) == "谨慎回避"


def test_extract_rating_falls_back_to_rfind():
    svc = DeepAnalysisService(dal=object(), router=object())
    assert svc._extract_rating("综合来看建议适度关注该股") == "适度关注"


def test_extract_rating_default_neutral():
    svc = DeepAnalysisService(dal=object(), router=object())
    assert svc._extract_rating("没有评级词的文本") == "中性观望"


def test_completeness_warning_when_dims_missing():
    svc = DeepAnalysisService(dal=object(), router=object())
    d = _full_data()
    d["scores"]["fundamental"]["details"] = {"data_available": False}
    d["scores"]["fund_flow"]["details"] = {"data_available": False}
    p = svc._build_ai_prompt(d)
    assert "数据不足" in p and "基本面" in p


def test_no_warning_when_dims_complete():
    svc = DeepAnalysisService(dal=object(), router=object())
    assert "数据不足" not in svc._build_ai_prompt(_full_data())
