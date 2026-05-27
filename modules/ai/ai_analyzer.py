"""
AI智能分析模块
基于大模型实现个股综合分析
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.storage.mongo_storage import KlineStorage, StockInfoStorage, NewsStorage
from utils.logger import get_logger
from .model_manager import model_manager


logger = get_logger(__name__)


class AIAnalyzer:
    def __init__(self):
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.news_storage = NewsStorage()
        self.model_manager = model_manager

    def analyze(
        self,
        code: str,
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        if analysis_type == "comprehensive":
            return self._comprehensive_analysis(code)
        elif analysis_type == "technical":
            return self._technical_analysis(code)
        elif analysis_type == "sentiment":
            return self._sentiment_analysis(code)
        elif analysis_type == "fundamental":
            return self._fundamental_analysis(code)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

    def _comprehensive_analysis(self, code: str) -> Dict[str, Any]:
        kline_data = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )

        stock_info = self.stock_info_storage.get_by_code(code)

        news_data = self.news_storage.get_latest_news(code=code, limit=10)

        technical_analysis = self._analyze_technical_indicators(kline_data)
        sentiment_analysis = self._analyze_sentiment(news_data)

        kline_summary = self._summarize_kline_data(kline_data)

        prompt = self._build_comprehensive_prompt(
            code=code,
            stock_name=stock_info.get("name", "") if stock_info else "",
            kline_summary=kline_summary,
            technical=technical_analysis,
            sentiment=sentiment_analysis
        )

        try:
            response = self.model_manager.call_model(prompt)
            result = self._parse_json_response(response)
        except Exception as e:
            logger.error(f"AI analysis failed for {code}: {e}")
            result = self._generate_fallback_result(code, technical_analysis, sentiment_analysis)

        result["code"] = code
        result["analysis_type"] = "comprehensive"
        result["analyzed_at"] = datetime.now().isoformat()

        self._save_analysis_result(code, "comprehensive", result)

        return result

    def _technical_analysis(self, code: str) -> Dict[str, Any]:
        kline_data = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )

        indicators = self._analyze_technical_indicators(kline_data)

        prompt = f"""
分析股票 {code} 的技术指标：

指标分析结果：
{indicators}

请分析：
1. 当前趋势判断
2. 关键支撑位和压力位
3. 买入/卖出信号
4. 风险提示

请以JSON格式返回分析结果，包含以下字段：
- trend: 趋势判断
- support_levels: 支撑位列表
- resistance_levels: 压力位列表
- buy_signal: 买入信号强度(0-100)
- sell_signal: 卖出信号强度(0-100)
- risk_factors: 风险因素列表
- summary: 总结
"""

        try:
            response = self.model_manager.call_model(prompt)
            result = self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Technical analysis failed: {e}")
            result = indicators

        result["code"] = code
        result["analysis_type"] = "technical"
        result["analyzed_at"] = datetime.now().isoformat()

        return result

    def _sentiment_analysis(self, code: str) -> Dict[str, Any]:
        news_data = self.news_storage.get_latest_news(code=code, limit=20)
        sentiment = self._analyze_sentiment(news_data)

        prompt = f"""
分析股票 {code} 的舆情情绪：

舆情数据：
{news_data}

情绪分析结果：
{sentiment}

请以JSON格式返回分析，包含：
- overall_sentiment: 整体情绪（积极/中性/消极）
- sentiment_score: 情绪评分(0-100)
- key_events: 关键事件列表
- positive_factors: 正面因素
- negative_factors: 负面因素
- summary: 总结
"""

        try:
            response = self.model_manager.call_model(prompt)
            result = self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            result = sentiment

        result["code"] = code
        result["analysis_type"] = "sentiment"
        result["analyzed_at"] = datetime.now().isoformat()

        return result

    def _fundamental_analysis(self, code: str) -> Dict[str, Any]:
        stock_info = self.stock_info_storage.get_by_code(code)

        prompt = f"""
分析股票 {code} 的基本面：

股票信息：
{stock_info}

请以JSON格式返回分析，包含：
- valuation: 估值分析
- financial_health: 财务健康状况
- growth_potential: 成长潜力
- risk_level: 风险等级(低/中/高)
- investment_rating: 投资评级(推荐/中性/回避)
- summary: 总结
"""

        try:
            response = self.model_manager.call_model(prompt)
            result = self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Fundamental analysis failed: {e}")
            result = {"code": code, "error": str(e)}

        result["code"] = code
        result["analysis_type"] = "fundamental"
        result["analyzed_at"] = datetime.now().isoformat()

        return result

    def _analyze_technical_indicators(
        self,
        kline_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not kline_data:
            return {"error": "No data"}

        closes = [k.get("close", 0) for k in kline_data]
        volumes = [k.get("volume", 0) for k in kline_data]

        current_price = closes[0] if closes else 0
        ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else current_price
        ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else current_price
        ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current_price

        trend = "unknown"
        if current_price > ma20 > ma10 > ma5:
            trend = "上升趋势"
        elif current_price < ma20 < ma10 < ma5:
            trend = "下降趋势"
        else:
            trend = "震荡"

        change_pct = 0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (closes[0] - closes[1]) / closes[1] * 100

        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        volume_ratio = volumes[0] / avg_volume if avg_volume > 0 else 1

        return {
            "current_price": current_price,
            "ma5": round(ma5, 2),
            "ma10": round(ma10, 2),
            "ma20": round(ma20, 2),
            "trend": trend,
            "change_pct": round(change_pct, 2),
            "volume_ratio": round(volume_ratio, 2),
            "volume": volumes[0] if volumes else 0
        }

    def _analyze_sentiment(
        self,
        news_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not news_data:
            return {"sentiment": "neutral", "score": 50}

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作", "扩张"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险"]

        positive_count = 0
        negative_count = 0

        for news in news_data:
            title = news.get("title", "")
            content = news.get("content", "")
            text = title + content

            for kw in positive_keywords:
                if kw in text:
                    positive_count += 1

            for kw in negative_keywords:
                if kw in text:
                    negative_count += 1

        total = positive_count + negative_count
        if total == 0:
            score = 50
        else:
            score = positive_count / total * 100

        sentiment = "neutral"
        if score > 60:
            sentiment = "positive"
        elif score < 40:
            sentiment = "negative"

        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "news_count": len(news_data)
        }

    def _summarize_kline_data(
        self,
        kline_data: List[Dict[str, Any]]
    ) -> str:
        if not kline_data:
            return "数据不足"

        latest = kline_data[0]
        earliest = kline_data[-1]

        current_price = latest.get("close", 0)
        start_price = earliest.get("close", 0)
        period_change = (current_price - start_price) / start_price * 100 if start_price > 0 else 0

        return f"""
近期K线数据摘要：
- 最新日期：{latest.get("date")}
- 最新价格：{current_price}
- 期间涨跌幅：{period_change:.2f}%
- 最高价：{latest.get("high")}
- 最低价：{latest.get("low")}
- 成交量：{latest.get("volume")}
- 数据天数：{len(kline_data)}
"""

    def _build_comprehensive_prompt(
        self,
        code: str,
        stock_name: str,
        kline_summary: str,
        technical: Dict[str, Any],
        sentiment: Dict[str, Any]
    ) -> str:
        return f"""
请对股票 {code}（{stock_name}）进行全面综合分析。

{kline_summary}

技术分析：
{technical}

舆情分析：
{sentiment}

请以JSON格式返回分析结果，包含以下字段：
- score: 综合评分(0-100)
- recommendation: 建议（买入/观望/回避）
- reasons: 理由列表
- risk_factors: 风险因素列表
- support_levels: 支撑位列表
- resistance_levels: 压力位列表
- stop_loss: 止损位
- target_price: 目标价位
- summary: 总结
"""

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        import json
        import re

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {
            "raw_response": response,
            "error": "Failed to parse JSON"
        }

    def _generate_fallback_result(
        self,
        code: str,
        technical: Dict[str, Any],
        sentiment: Dict[str, Any]
    ) -> Dict[str, Any]:
        score = 50

        if technical.get("trend") == "上升趋势":
            score += 10
        elif technical.get("trend") == "下降趋势":
            score -= 10

        if technical.get("change_pct", 0) > 0:
            score += 5
        else:
            score -= 5

        if sentiment.get("sentiment") == "positive":
            score += 10
        elif sentiment.get("sentiment") == "negative":
            score -= 10

        score = max(0, min(100, score))

        recommendation = "观望"
        if score >= 70:
            recommendation = "买入"
        elif score <= 30:
            recommendation = "回避"

        return {
            "score": score,
            "recommendation": recommendation,
            "reasons": ["基于技术面和舆情分析生成"],
            "risk_factors": ["数据可能不完整"],
            "support_levels": [technical.get("current_price", 0) * 0.95],
            "resistance_levels": [technical.get("current_price", 0) * 1.05],
            "stop_loss": technical.get("current_price", 0) * 0.95,
            "target_price": technical.get("current_price", 0) * 1.10,
            "summary": "基于系统分析生成，结果仅供参考"
        }

    def _save_analysis_result(
        self,
        code: str,
        analysis_type: str,
        result: Dict[str, Any]
    ):
        from config.database import get_collection

        collection = get_collection("ai_analysis_results")
        collection.update_one(
            {
                "code": code,
                "analysis_type": analysis_type,
                "date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "$set": {
                    "result": result,
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )


ai_analyzer = AIAnalyzer()