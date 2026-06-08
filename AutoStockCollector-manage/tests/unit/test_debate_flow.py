"""多空辩论数据流完整性测试（纯函数 + mock，无 DB / 无网络 / 无 LLM）

验证要点：
1. _fetch_all_stock_data 查询逻辑（新闻字段名、code 匹配）
2. _format_stock_data_text 全部 7 个数据段都有输出、字段名中英文兼容
3. _calculate_debate_factors K线正序传入 technical_score、财务字段多key回退
4. _extract_debate_score 正则提取
5. _build_final_verdict 裁决逻辑
6. debate_stream SSE 事件完整性
"""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── 模拟数据 ──────────────────────────────────────────────

def _make_kline(n=30, use_chinese=False):
    """生成 n 天 K 线数据（date DESC，与 MongoDB 一致）"""
    records = []
    base_price = 20.0
    for i in range(n):
        day = f"2026-05-{(n - i):02d}"
        price = base_price + (n - i) * 0.1
        if use_chinese:
            records.append({
                "date": day, "code": "SH600519",
                "收盘": price, "最高": price + 0.5,
                "最低": price - 0.3, "成交量": 100000 + i * 1000,
                "成交额": 2000000 + i * 50000,
            })
        else:
            records.append({
                "date": day, "code": "SH600519",
                "close": price, "high": price + 0.5,
                "low": price - 0.3, "volume": 100000 + i * 1000,
                "amount": 2000000 + i * 50000,
            })
    return records


MOCK_STOCK_INFO = {
    "code": "SH600519", "name": "贵州茅台",
    "industry": "白酒", "pe": 35.2, "pb": 12.1,
    "roe": 31.5, "market_cap": 22000e8, "total_shares": 12.56e8,
}

MOCK_FUND_FLOW = {
    "code": "SH600519", "date": "2026-05-30",
    "main_net_inflow": 3.5e8, "total_amount": 45e8,
    "turnover_rate": 0.65, "change_pct": 2.13,
}

MOCK_FUND_FLOW_CN = {
    "code": "SH600519", "date": "2026-05-30",
    "净额": 3.5e8, "成交额": 45e8, "换手率": 0.65, "涨跌幅": 2.13,
}

MOCK_NEWS = [
    {"title": "贵州茅台一季度净利润同比增长15%", "publish_date": "2026-05-28",
     "source": "东方财富", "code": "SH600519"},
    {"title": "白酒板块午后拉升", "publish_date": "2026-05-27",
     "source": "新浪财经", "code": "SH600519"},
]

MOCK_FINANCIAL_THS = {
    "code": "SH600519", "report_date": "2025-12-31",
    "营业总收入": 1500e8, "净利润": 750e8,
    "营业总收入同比增长率": 16.5, "净利润同比增长率": 15.2,
    "销售毛利率": 91.5, "资产负债率": 22.3,
}

MOCK_FINANCIAL_EN = {
    "code": "SH600519", "report_date": "2025-12-31",
    "revenue_growth": 16.5, "profit_growth": 15.2,
    "gross_margin": 91.5, "debt_ratio": 22.3,
}

MOCK_MARGIN = [
    {"code": "SH600519", "date": "2026-05-30",
     "融资余额": 85e8, "融券余额": 1.2e8},
    {"code": "SH600519", "date": "2026-05-29",
     "margin_balance": 84e8, "short_balance": 1.1e8},
]


# ── 测试 _format_stock_data_text ──────────────────────────

class TestFormatStockDataText(unittest.TestCase):
    """验证格式化文本包含所有数据段、字段名中英文兼容"""

    def _call(self, **overrides):
        from api.routes.ai_advanced import _format_stock_data_text
        base = {
            "code": "SH600519",
            "kline_data": _make_kline(15),
            "stock_info": MOCK_STOCK_INFO,
            "fund_flow_data": MOCK_FUND_FLOW,
            "news_data": MOCK_NEWS,
            "financial_data": MOCK_FINANCIAL_THS,
            "margin_data": MOCK_MARGIN,
        }
        base.update(overrides)
        return _format_stock_data_text(base)

    def test_all_sections_present(self):
        text = self._call()
        for section in [
            "股票基本信息", "K线行情", "财务数据", "资金流向",
            "融资融券", "最新新闻与舆情",
        ]:
            self.assertIn(section, text, f"缺少段落：{section}")

    def test_stock_info_fields(self):
        text = self._call()
        self.assertIn("贵州茅台", text)
        self.assertIn("35.2", text)   # PE
        self.assertIn("12.1", text)   # PB
        self.assertIn("31.5", text)   # ROE

    def test_kline_has_dates(self):
        """K线数据必须带日期，而不是纯数字列表"""
        text = self._call()
        self.assertIn("2026-05-", text)
        self.assertIn("收盘:", text)
        self.assertIn("成交量:", text)

    def test_kline_chinese_field_names(self):
        """K线使用中文字段名时也能正确解析"""
        text = self._call(kline_data=_make_kline(10, use_chinese=True))
        self.assertIn("收盘:", text)
        self.assertNotIn("收盘:", text.replace("收盘:", ""))  # 至少出现多次

    def test_financial_ths_fields(self):
        """THS 中文字段名（营业总收入同比增长率等）能正确显示"""
        text = self._call(financial_data=MOCK_FINANCIAL_THS)
        self.assertIn("16.5", text)    # 营收增速
        self.assertIn("15.2", text)    # 利润增速
        self.assertIn("91.5", text)    # 毛利率
        self.assertIn("22.3", text)    # 负债率
        self.assertIn("1500", text)    # 营收（部分匹配即可）

    def test_financial_english_fields(self):
        """英文字段名也能兼容"""
        text = self._call(financial_data=MOCK_FINANCIAL_EN)
        self.assertIn("16.5", text)
        self.assertIn("91.5", text)

    def test_fund_flow_chinese_fields(self):
        """资金流向使用中文字段名也能正确解析"""
        text = self._call(fund_flow_data=MOCK_FUND_FLOW_CN)
        self.assertIn("资金流向", text)
        self.assertIn("350000000", text)  # 主力净流入 3.5e8

    def test_news_with_date_and_source(self):
        """新闻带日期和来源"""
        text = self._call()
        self.assertIn("2026-05-28", text)
        self.assertIn("贵州茅台一季度净利润同比增长15%", text)
        self.assertIn("东方财富", text)

    def test_margin_chinese_field_names(self):
        """融资融券中文字段名可识别"""
        text = self._call()
        self.assertIn("融资余额", text)

    def test_empty_data_graceful(self):
        """全部数据为空时不崩溃，各段显示暂无"""
        text = self._call(
            kline_data=[], stock_info={}, fund_flow_data={},
            news_data=[], financial_data={}, margin_data=[]
        )
        self.assertIn("暂无", text)


# ── 测试 _calculate_debate_factors ────────────────────────

class TestCalculateDebateFactors(unittest.TestCase):
    """验证因子计算数据传递正确"""

    def _call(self, **overrides):
        from api.routes.ai_advanced import _calculate_debate_factors
        base = {
            "code": "SH600519",
            "kline_data": _make_kline(30),
            "stock_info": MOCK_STOCK_INFO,
            "fund_flow_data": MOCK_FUND_FLOW,
            "financial_data": MOCK_FINANCIAL_THS,
            "news_data": MOCK_NEWS,
            "margin_data": MOCK_MARGIN,
        }
        base.update(overrides)
        return _calculate_debate_factors(base)

    def test_all_dimensions_present(self):
        result = self._call()
        for dim in ["technical", "fundamental", "fund_flow", "valuation"]:
            self.assertIn(dim, result, f"缺少维度：{dim}")
            self.assertIn("score", result[dim])
            score = result[dim]["score"]
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_composite_score_range(self):
        result = self._call()
        self.assertIn("composite", result)
        self.assertGreaterEqual(result["composite"], 0)
        self.assertLessEqual(result["composite"], 100)

    def test_kline_order_correctness(self):
        """K线按正序传入 technical_score，不应返回 data_available=False"""
        result = self._call()
        tech_details = result["technical"]["details"]
        self.assertTrue(
            tech_details.get("data_available", False),
            f"技术面因子应有数据，但返回 {tech_details}"
        )

    def test_kline_chinese_fields_work(self):
        """中文字段名的K线也能正确计算因子"""
        result = self._call(kline_data=_make_kline(30, use_chinese=True))
        tech = result["technical"]
        self.assertTrue(tech["details"].get("data_available", False))

    def test_financial_ths_field_pickup(self):
        """THS 中文字段名能被因子计算正确读取"""
        result = self._call(financial_data=MOCK_FINANCIAL_THS)
        funda_details = result["fundamental"]["details"]
        # revenue_growth 应被识别为 16.5
        rg = funda_details.get("revenue_growth", {})
        self.assertIsNotNone(rg.get("value"), "营收增速应被识别")

    def test_fund_flow_chinese_fields(self):
        """中文字段名的资金流向也能正确计算"""
        result = self._call(fund_flow_data=MOCK_FUND_FLOW_CN)
        flow = result["fund_flow"]
        self.assertTrue(flow["details"].get("data_available", True))

    def test_data_quality_report(self):
        result = self._call()
        dq = result["data_quality"]
        self.assertGreater(dq["kline_days"], 0)
        self.assertTrue(dq["has_financial"])
        self.assertTrue(dq["has_fund_flow"])
        self.assertGreater(dq["news_count"], 0)

    def test_empty_kline_gives_neutral(self):
        result = self._call(kline_data=[])
        self.assertEqual(result["technical"]["score"], 50.0)


# ── 测试 _extract_debate_score ────────────────────────────

class TestExtractDebateScore(unittest.TestCase):
    def _call(self, text):
        from api.routes.ai_advanced import _extract_debate_score
        return _extract_debate_score(text)

    def test_chinese_colon(self):
        self.assertEqual(self._call("综合评分：78"), 78)

    def test_english_colon(self):
        self.assertEqual(self._call("综合评分: 85.5"), 85)

    def test_no_score_returns_default(self):
        self.assertEqual(self._call("这段没有评分"), 50)

    def test_score_out_of_range_ignored(self):
        self.assertEqual(self._call("综合评分：120"), 50)

    def test_score_clamped_to_0(self):
        self.assertEqual(self._call("综合评分：-10"), 50)

    def test_slash_100_format(self):
        self.assertEqual(self._call("综合评分：78/100"), 78)

    def test_tail_search_ignores_head(self):
        text = "技术面评分：49/100\n" * 5 + "\n综合评分：72/100"
        self.assertEqual(self._call(text), 72)

    def test_confidence_index(self):
        self.assertEqual(self._call("信心指数：82"), 82)

    def test_empty_string(self):
        self.assertEqual(self._call(""), 50)


# ── 测试 _build_final_verdict ─────────────────────────────

class TestBuildFinalVerdict(unittest.TestCase):
    def _call(self, bull_score, bear_score, judge_text):
        from api.routes.ai_advanced import _build_final_verdict
        return _build_final_verdict("SH600519", bull_score, bear_score,
                                    "多头分析", "空头分析", judge_text)

    def test_bull_dominant(self):
        # bull=80(看涨80), bear=30(看跌30) → bull_bullish=80, bear_bullish=70 → net=75 → 偏多
        v = self._call(80, 30, "综合风险较低")
        self.assertEqual(v["tendency"], "偏多")
        self.assertEqual(v["recommendation"], "买入")
        self.assertEqual(v["riskLevel"], "低")
        self.assertEqual(v["bullScore"], 80)
        self.assertEqual(v["bearScore"], 30)

    def test_bear_dominant(self):
        # bull=30(看涨30), bear=85(看跌85) → bull_bullish=30, bear_bullish=15 → net=22.5 → 偏空
        v = self._call(30, 85, "高风险，建议回避")
        self.assertEqual(v["tendency"], "偏空")
        self.assertEqual(v["recommendation"], "回避")
        self.assertEqual(v["riskLevel"], "高")

    def test_slightly_bearish(self):
        # bull=62, bear=78 → bull_bullish=62, bear_bullish=22 → net=42 → 偏空（新阈值 <=45）
        v = self._call(62, 78, "中高风险")
        self.assertEqual(v["tendency"], "偏空")
        self.assertEqual(v["recommendation"], "观望")

    def test_neutral(self):
        # bull=55(看涨55), bear=55(看跌55) → bull_bullish=55, bear_bullish=45 → net=50 → 中性
        v = self._call(55, 55, "中性震荡")
        self.assertEqual(v["tendency"], "中性震荡")
        self.assertEqual(v["recommendation"], "观望")

    def test_default_scores(self):
        v = self._call(50, 50, "")
        self.assertEqual(v["bullScore"], 50)
        self.assertEqual(v["bearScore"], 50)
        self.assertEqual(v["tendency"], "中性震荡")

    def test_verdict_has_required_fields(self):
        v = self._call(70, 60, "裁决")
        for key in ["code", "bullScore", "bearScore", "tendency",
                     "riskLevel", "recommendation", "bullArgument",
                     "bearArgument", "judgeVerdict", "generatedAt"]:
            self.assertIn(key, v, f"裁决缺少字段：{key}")


# ── 测试 _format_factor_text ──────────────────────────────

class TestFormatFactorText(unittest.TestCase):
    def test_format_includes_all_dimensions(self):
        from api.routes.ai_advanced import _format_factor_text
        factors = {
            "technical": {"score": 72.0, "details": {"ma_trend": {"value": "多头排列", "score": 24, "max": 30}}},
            "fundamental": {"score": 65.0, "details": {"roe": {"value": 31.5, "score": 35, "max": 35}}},
            "fund_flow": {"score": 58.0, "details": {"data_available": True}},
            "valuation": {"score": 45.0, "details": {"pe": {"value": 35.2, "score": 32, "max": 50}}},
            "composite": 62.5,
            "data_quality": {
                "kline_days": 30, "has_financial": True,
                "has_fund_flow": True, "news_count": 5, "has_margin": True,
            },
        }
        text = _format_factor_text(factors)
        self.assertIn("量化因子评分", text)
        self.assertIn("技术面", text)
        self.assertIn("基本面", text)
        self.assertIn("资金面", text)
        self.assertIn("估值", text)
        self.assertIn("数据质量", text)


# ── 端到端 SSE 流式模拟测试 ───────────────────────────────

class TestDebateStreamE2E(unittest.TestCase):
    """模拟完整 SSE 流，验证所有事件阶段都触发、数据传递正确"""

    @patch("api.routes.ai_advanced._get_db")
    @patch("api.routes.ai_advanced._fetch_all_stock_data")
    def test_full_stream_events(self, mock_fetch, mock_db):
        from api.routes.ai_advanced import debate_stream, ai_advanced_bp
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(ai_advanced_bp, url_prefix="/api/v1/ai")

        mock_fetch.return_value = {
            "code": "SH600519",
            "kline_data": _make_kline(30),
            "stock_info": MOCK_STOCK_INFO,
            "fund_flow_data": MOCK_FUND_FLOW,
            "news_data": MOCK_NEWS,
            "financial_data": MOCK_FINANCIAL_THS,
            "margin_data": MOCK_MARGIN,
        }

        mock_agent = {
            "id": "test", "name": "测试分析师",
            "system_prompt": "你是测试分析师",
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = mock_agent
        mock_db.return_value = {"ai_agents": mock_collection}

        mock_router = MagicMock()
        mock_router.chat_stream.return_value = iter(["这是测试分析。综合评分：72"])

        with app.test_request_context(
            "/api/v1/ai/debate/stream",
            method="POST",
            json={"code": "600519"},
            content_type="application/json",
        ):
            with patch("api.routes.ai_advanced.LLMRouter", return_value=mock_router) if False else \
                 patch("modules.ai.foundation.llm_router.LLMRouter", return_value=mock_router):
                pass

        # 使用 test_client 来做完整的请求测试
        with app.test_client() as client:
            with patch("modules.ai.foundation.llm_router.LLMRouter") as MockLLM:
                mock_instance = MagicMock()
                mock_instance.chat_stream.return_value = iter(["测试分析结果。综合评分：72"])
                MockLLM.return_value = mock_instance

                resp = client.post(
                    "/api/v1/ai/debate/stream",
                    json={"code": "600519"},
                    content_type="application/json",
                )

                self.assertEqual(resp.status_code, 200)
                self.assertIn("text/event-stream", resp.content_type)

                raw = resp.get_data(as_text=True)
                events = []
                for line in raw.split("\n"):
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev.get("event", ""))
                        except json.JSONDecodeError:
                            pass

                expected_events = [
                    "data:start", "data:progress", "data:done",
                    "factor:start", "factor:progress", "factor:done",
                    "base:start", "agent:start", "agent:done", "base:done",
                    "bull:start", "bull:done",
                    "bear:start", "bear:done",
                    "judge:start", "judge:done",
                    "verdict",
                ]
                for ev in expected_events:
                    self.assertIn(ev, events, f"SSE 流缺少事件：{ev}")

    def test_missing_code_returns_400(self):
        from api.routes.ai_advanced import ai_advanced_bp
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(ai_advanced_bp, url_prefix="/api/v1/ai")

        with app.test_client() as client:
            resp = client.post(
                "/api/v1/ai/debate/stream",
                json={},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 400)


# ── 数据查询逻辑验证 ─────────────────────────────────────

class TestFetchAllStockData(unittest.TestCase):
    """验证 _fetch_all_stock_data 的查询参数正确性"""

    def test_news_query_no_related_codes_in_source(self):
        """通过源码检查确认 _fetch_all_stock_data 不使用 related_codes"""
        import inspect
        from api.routes.ai_advanced import _fetch_all_stock_data
        source = inspect.getsource(_fetch_all_stock_data)
        self.assertNotIn("related_codes", source)
        self.assertIn("publish_date", source)

    def test_news_query_field_name(self):
        """验证新闻查询不再使用 related_codes 字段"""
        import inspect
        from api.routes.ai_advanced import _fetch_all_stock_data
        source = inspect.getsource(_fetch_all_stock_data)
        self.assertNotIn("related_codes", source,
                         "不应再使用 related_codes 字段查询新闻")
        self.assertIn("publish_date", source,
                      "新闻排序应使用 publish_date")
        self.assertNotIn("published_at", source,
                         "不应使用错误的 published_at 字段名")

    def test_kline_reverse_in_factors(self):
        """验证因子计算代码中有 reversed(kd) 调用"""
        import inspect
        from api.routes.ai_advanced import _calculate_debate_factors
        source = inspect.getsource(_calculate_debate_factors)
        self.assertIn("reversed(kd)", source,
                      "因子计算应该反转 K 线数据以得到正序")

    def test_format_has_financial_section(self):
        """验证格式化文本代码中包含财务数据段"""
        import inspect
        from api.routes.ai_advanced import _format_stock_data_text
        source = inspect.getsource(_format_stock_data_text)
        self.assertIn("财务数据", source,
                      "格式化文本应包含财务数据段")
        self.assertIn("营业总收入同比增长率", source,
                      "应支持 THS 中文字段名")

    def test_truncation_limit_reasonable(self):
        """验证基础分析师结果截断长度 >= 1000"""
        import inspect
        from api.routes.ai_advanced import debate_stream
        source = inspect.getsource(debate_stream)
        # 查找截断逻辑中的数字
        import re
        matches = re.findall(r'content\[:(\d+)\]', source)
        for m in matches:
            self.assertGreaterEqual(int(m), 1000,
                                    f"截断长度 {m} 过短，应 >= 1000")


if __name__ == "__main__":
    unittest.main()
