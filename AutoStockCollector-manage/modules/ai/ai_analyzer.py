"""
AI智能分析模块 - 工业化重构版
基于ai_selector因子层 + LLMRouter实现结构化分析输出
"""
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
from datetime import datetime
from utils.helpers import beijing_now
from enum import Enum
import json
from utils.logger import get_logger


logger = get_logger(__name__)


class AnalysisType(Enum):
    COMPREHENSIVE = "comprehensive"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"


@dataclass
class TechnicalResult:
    current_price: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    trend: str
    trend_strength: float
    change_pct: float
    volume_ratio: float
    momentum: float
    rsi: float = 50.0
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_price": self.current_price,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma60": self.ma60,
            "trend": self.trend,
            "trend_strength": self.trend_strength,
            "change_pct": self.change_pct,
            "volume_ratio": self.volume_ratio,
            "momentum": self.momentum,
            "rsi": self.rsi,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels
        }


@dataclass
class FundamentalResult:
    pe: float
    pb: float
    ps: float
    roe: float
    revenue_growth: float
    profit_growth: float
    current_ratio: float
    debt_ratio: float
    market_cap: float
    valuation_score: float
    growth_score: float
    health_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pe": self.pe,
            "pb": self.pb,
            "ps": self.ps,
            "roe": self.roe,
            "revenue_growth": self.revenue_growth,
            "profit_growth": self.profit_growth,
            "current_ratio": self.current_ratio,
            "debt_ratio": self.debt_ratio,
            "market_cap": self.market_cap,
            "valuation_score": self.valuation_score,
            "growth_score": self.growth_score,
            "health_score": self.health_score
        }


@dataclass
class SentimentResult:
    sentiment: str
    score: float
    positive_count: int
    negative_count: int
    news_count: int
    key_events: List[str] = field(default_factory=list)
    positive_keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "news_count": self.news_count,
            "key_events": self.key_events,
            "positive_keywords": self.positive_keywords,
            "negative_keywords": self.negative_keywords
        }


@dataclass
class AnalysisResult:
    code: str
    name: str
    analysis_type: str
    technical: TechnicalResult
    fundamental: FundamentalResult
    sentiment: SentimentResult
    composite_score: float
    recommendation: str
    risk_level: str
    stop_loss: float
    target_price: float
    reasons: List[str]
    risk_factors: List[str]
    support_levels: List[float]
    resistance_levels: List[float]
    analyzed_at: str
    analysis_method: str = "llm"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "analysis_type": self.analysis_type,
            "technical": self.technical.to_dict(),
            "fundamental": self.fundamental.to_dict(),
            "sentiment": self.sentiment.to_dict(),
            "composite_score": self.composite_score,
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "reasons": self.reasons,
            "risk_factors": self.risk_factors,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "analyzed_at": self.analyzed_at,
            "analysis_method": self.analysis_method,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AIAnalyzer:
    _positive_keywords = [
        "增长", "盈利", "突破", "利好", "创新", "合作", "扩张", "订单",
        "签约", "中标", "技术突破", "研发", "业绩预增", "分红", "回购"
    ]
    _negative_keywords = [
        "亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险", "召回",
        "调查", "处罚", "业绩下滑", "商誉减值", "债务违约", "高管离职"
    ]

    def __init__(self):
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage, NewsStorage, FundFlowStorage
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.news_storage = NewsStorage()
        self.fund_flow_storage = FundFlowStorage()
        self._llm_router = None
        self._factor_registry = None

    @property
    def llm_router(self):
        if self._llm_router is None:
            from modules.ai_selector.models import llm_router
            self._llm_router = llm_router
        return self._llm_router

    @property
    def factor_registry(self):
        if self._factor_registry is None:
            from modules.ai_selector.factors import factor_registry
            self._factor_registry = factor_registry
        return self._factor_registry

    def analyze(
        self,
        code: str,
        analysis_type: Literal["comprehensive", "technical", "sentiment", "fundamental"] = "comprehensive",
        use_llm: bool = True
    ) -> Dict[str, Any]:
        if analysis_type == "comprehensive":
            return self._comprehensive_analysis(code, use_llm)
        elif analysis_type == "technical":
            return self._technical_analysis(code, use_llm)
        elif analysis_type == "sentiment":
            return self._sentiment_analysis(code, use_llm)
        elif analysis_type == "fundamental":
            return self._fundamental_analysis(code, use_llm)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

    def _comprehensive_analysis(self, code: str, use_llm: bool = True) -> Dict[str, Any]:
        kline_data = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )
        stock_info = self.stock_info_storage.get_by_code(code)
        news_data = self.news_storage.get_latest_news(code=code, limit=20)
        flow_data = self.fund_flow_storage.get_latest_flow(code)

        technical = self._calculate_technical_indicators(kline_data)
        fundamental = self._calculate_fundamental_indicators(stock_info)
        sentiment = self._calculate_sentiment_indicators(news_data)
        fund_flow = self._calculate_fund_flow_indicators(flow_data)

        composite_score = self._calculate_composite_score(
            technical, fundamental, sentiment, fund_flow
        )

        if use_llm:
            result = self._llm_analysis(code, stock_info, technical, fundamental, sentiment, fund_flow)
            if result:
                self._save_analysis_result(code, "comprehensive", result)
                return result

        result = self._generate_structured_result(
            code=code,
            stock_info=stock_info,
            technical=technical,
            fundamental=fundamental,
            sentiment=sentiment,
            fund_flow=fund_flow,
            composite_score=composite_score,
            use_llm=False
        )

        self._save_analysis_result(code, "comprehensive", result)
        return result

    def _technical_analysis(self, code: str, use_llm: bool = True) -> Dict[str, Any]:
        kline_data = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )

        technical = self._calculate_technical_indicators(kline_data)

        if use_llm:
            result = self._llm_technical_analysis(code, technical)
            if result:
                result["analysis_type"] = "technical"
                result["analyzed_at"] = beijing_now().isoformat()
                self._save_analysis_result(code, "technical", result)
                return result

        result = {
            "code": code,
            "name": kline_data[0].get("name", "") if kline_data else "",
            "analysis_type": "technical",
            "data": technical.to_dict(),
            "analyzed_at": beijing_now().isoformat(),
            "analysis_method": "rule"
        }

        self._save_analysis_result(code, "technical", result)
        return result

    def _sentiment_analysis(self, code: str, use_llm: bool = True) -> Dict[str, Any]:
        news_data = self.news_storage.get_latest_news(code=code, limit=30)
        sentiment = self._calculate_sentiment_indicators(news_data)

        if use_llm:
            result = self._llm_sentiment_analysis(code, sentiment, news_data)
            if result:
                result["analysis_type"] = "sentiment"
                result["analyzed_at"] = beijing_now().isoformat()
                self._save_analysis_result(code, "sentiment", result)
                return result

        result = {
            "code": code,
            "analysis_type": "sentiment",
            "data": sentiment.to_dict(),
            "analyzed_at": beijing_now().isoformat(),
            "analysis_method": "rule"
        }

        self._save_analysis_result(code, "sentiment", result)
        return result

    def _fundamental_analysis(self, code: str, use_llm: bool = True) -> Dict[str, Any]:
        stock_info = self.stock_info_storage.get_by_code(code)
        fundamental = self._calculate_fundamental_indicators(stock_info)

        if use_llm:
            result = self._llm_fundamental_analysis(code, fundamental, stock_info)
            if result:
                result["analysis_type"] = "fundamental"
                result["analyzed_at"] = beijing_now().isoformat()
                self._save_analysis_result(code, "fundamental", result)
                return result

        result = {
            "code": code,
            "name": stock_info.get("name", "") if stock_info else "",
            "analysis_type": "fundamental",
            "data": fundamental.to_dict(),
            "analyzed_at": beijing_now().isoformat(),
            "analysis_method": "rule"
        }

        self._save_analysis_result(code, "fundamental", result)
        return result

    def _calculate_technical_indicators(
        self,
        kline_data: List[Dict[str, Any]]
    ) -> TechnicalResult:
        if not kline_data:
            return TechnicalResult(
                current_price=0, ma5=0, ma10=0, ma20=0, ma60=0,
                trend="unknown", trend_strength=0, change_pct=0,
                volume_ratio=1, momentum=0, rsi=50
            )

        closes = [k.get("close", 0) for k in kline_data]
        volumes = [k.get("volume", 0) for k in kline_data]

        current_price = closes[0]
        ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else current_price
        ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else current_price
        ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current_price
        ma60 = sum(closes[:60]) / 60 if len(closes) >= 60 else current_price

        trend = "震荡"
        trend_strength = 50.0

        if current_price > ma20 > ma10 > ma5:
            trend = "上升趋势"
            trend_strength = 80.0
        elif current_price > ma20 > ma5:
            trend = "偏强"
            trend_strength = 65.0
        elif current_price < ma20 < ma10 < ma5:
            trend = "下降趋势"
            trend_strength = 20.0
        elif current_price < ma20 < ma5:
            trend = "偏弱"
            trend_strength = 35.0

        change_pct = 0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (current_price - closes[1]) / closes[1] * 100

        avg_vol = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = volumes[0] / avg_vol if avg_vol > 0 else 1

        momentum = sum(closes[:5]) / 5 - sum(closes[5:10]) / 5 if len(closes) >= 10 else 0

        rsi = self._calculate_rsi(closes)

        support_levels = [
            round(ma20 * 0.97, 2),
            round(ma20 * 0.95, 2),
            round(ma60 * 0.95, 2)
        ]
        resistance_levels = [
            round(ma20 * 1.03, 2),
            round(ma20 * 1.05, 2),
            round(ma60 * 1.05, 2)
        ]

        return TechnicalResult(
            current_price=round(current_price, 2),
            ma5=round(ma5, 2),
            ma10=round(ma10, 2),
            ma20=round(ma20, 2),
            ma60=round(ma60, 2),
            trend=trend,
            trend_strength=trend_strength,
            change_pct=round(change_pct, 2),
            volume_ratio=round(volume_ratio, 2),
            momentum=round(momentum, 2),
            rsi=round(rsi, 2),
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i + 1] for i in range(len(closes) - 1)]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_fundamental_indicators(
        self,
        stock_info: Optional[Dict[str, Any]]
    ) -> FundamentalResult:
        if not stock_info:
            return FundamentalResult(
                pe=0, pb=0, ps=0, roe=0, revenue_growth=0,
                profit_growth=0, current_ratio=1.5, debt_ratio=0.5,
                market_cap=0, valuation_score=50, growth_score=50, health_score=50
            )

        pe = stock_info.get("pe") or 0
        pb = stock_info.get("pb") or 0
        ps = stock_info.get("ps") or 0
        roe = stock_info.get("roe") or 0
        revenue_growth = stock_info.get("revenue_growth") or 0
        profit_growth = stock_info.get("profit_growth") or 0
        current_ratio = stock_info.get("current_ratio") or 1.5
        debt_ratio = stock_info.get("debt_ratio") or 0.5
        market_cap = stock_info.get("market_cap") or 0

        valuation_score = self._calculate_valuation_score(pe, pb, ps)
        growth_score = self._calculate_growth_score(revenue_growth, profit_growth, roe)
        health_score = self._calculate_health_score(current_ratio, debt_ratio)

        return FundamentalResult(
            pe=float(pe),
            pb=float(pb),
            ps=float(ps),
            roe=float(roe) if roe else 0,
            revenue_growth=float(revenue_growth) if revenue_growth else 0,
            profit_growth=float(profit_growth) if profit_growth else 0,
            current_ratio=float(current_ratio) if current_ratio else 1.5,
            debt_ratio=float(debt_ratio) if debt_ratio else 0.5,
            market_cap=float(market_cap) if market_cap else 0,
            valuation_score=valuation_score,
            growth_score=growth_score,
            health_score=health_score
        )

    def _calculate_valuation_score(self, pe: float, pb: float, ps: float) -> float:
        score = 50.0
        if pe and 5 < pe < 25:
            score += 15
        elif pe and 0 < pe <= 5:
            score += 10
        elif pe and 25 <= pe < 40:
            score += 5
        elif pe and pe >= 40:
            score -= 15

        if pb and 0.5 < pb < 3:
            score += 10
        elif pb and pb >= 3:
            score -= 5

        return max(0, min(100, score))

    def _calculate_growth_score(self, revenue_growth: float, profit_growth: float, roe: float) -> float:
        score = 50.0

        if profit_growth and profit_growth > 30:
            score = 80.0
        elif profit_growth and profit_growth > 15:
            score = 70.0
        elif profit_growth and profit_growth > 0:
            score = 60.0
        elif profit_growth and profit_growth < -20:
            score = 30.0

        if revenue_growth and revenue_growth > 20:
            score = min(100, score + 5)

        if roe and roe > 15:
            score = min(100, score + 5)
        elif roe and roe < 0:
            score = max(0, score - 10)

        return max(0, min(100, score))

    def _calculate_health_score(self, current_ratio: float, debt_ratio: float) -> float:
        score = 50.0

        if debt_ratio and debt_ratio < 0.4:
            score += 15
        elif debt_ratio and debt_ratio < 0.6:
            score += 10
        elif debt_ratio and debt_ratio >= 0.7:
            score -= 15

        if current_ratio and current_ratio > 2:
            score += 10
        elif current_ratio and current_ratio < 1:
            score -= 10

        return max(0, min(100, score))

    def _calculate_sentiment_indicators(
        self,
        news_data: List[Dict[str, Any]]
    ) -> SentimentResult:
        if not news_data:
            return SentimentResult(
                sentiment="neutral", score=50, positive_count=0,
                negative_count=0, news_count=0
            )

        positive_count = 0
        negative_count = 0
        positive_keywords_found = []
        negative_keywords_found = []
        key_events = []

        for news in news_data:
            title = news.get("title", "")
            content = news.get("content", "")
            text = title + content

            for kw in self._positive_keywords:
                if kw in text and kw not in positive_keywords_found:
                    positive_count += 1
                    positive_keywords_found.append(kw)

            for kw in self._negative_keywords:
                if kw in text and kw not in negative_keywords_found:
                    negative_count += 1
                    negative_keywords_found.append(kw)

            if any(kw in title for kw in self._positive_keywords + self._negative_keywords):
                key_events.append(title[:50])

        total = positive_count + negative_count
        if total == 0:
            score = 50.0
        else:
            score = (positive_count / total) * 100

        sentiment = "neutral"
        if score > 65:
            sentiment = "positive"
        elif score < 35:
            sentiment = "negative"

        return SentimentResult(
            sentiment=sentiment,
            score=round(score, 2),
            positive_count=positive_count,
            negative_count=negative_count,
            news_count=len(news_data),
            key_events=key_events[:5],
            positive_keywords=positive_keywords_found[:5],
            negative_keywords=negative_keywords_found[:5]
        )

    @staticmethod
    def _parse_amount(raw) -> float:
        """解析金额字符串为元（支持 '6.43亿'、'2549万'、数字等）。"""
        import re
        if raw is None:
            return 0.0
        if isinstance(raw, (int, float)):
            return float(raw)
        s = str(raw).strip().replace(",", "")
        if not s or s in ("-", "—"):
            return 0.0
        try:
            m = re.match(r"^([+-]?\d+\.?\d*)(亿|万)?$", s)
            if m:
                num = float(m.group(1))
                unit = m.group(2)
                if unit == "亿":
                    return num * 1e8
                if unit == "万":
                    return num * 1e4
                return num
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def _calculate_fund_flow_indicators(
        self,
        flow_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not flow_data:
            return {
                "main_net_inflow": 0,
                "retail_net_inflow": 0,
                "net_inflow": 0,
                "score": 50
            }

        # 兼容旧字段(main_net_inflow数值)和新字段(净额"亿"字符串)
        main_inflow = self._parse_amount(flow_data.get("main_net_inflow") or flow_data.get("净额"))
        retail_inflow = self._parse_amount(flow_data.get("retail_net_inflow"))
        net_inflow = self._parse_amount(flow_data.get("net_inflow") or flow_data.get("净额"))

        score = 50.0
        if main_inflow > 1e8:
            score = 85.0
        elif main_inflow > 5e7:
            score = 75.0
        elif main_inflow > 1e7:
            score = 65.0
        elif main_inflow > 0:
            score = 55.0
        elif main_inflow < -1e8:
            score = 25.0

        return {
            "main_net_inflow": float(main_inflow),
            "retail_net_inflow": float(retail_inflow),
            "net_inflow": float(net_inflow),
            "score": score
        }

    def _calculate_composite_score(
        self,
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult,
        fund_flow: Dict[str, Any]
    ) -> float:
        weights = {
            "technical": 0.25,
            "fundamental": 0.25,
            "sentiment": 0.30,
            "fund_flow": 0.20
        }

        technical_score = technical.trend_strength
        fundamental_score = (fundamental.valuation_score + fundamental.growth_score + fundamental.health_score) / 3
        sentiment_score = sentiment.score
        fund_flow_score = fund_flow.get("score", 50)

        composite = (
            technical_score * weights["technical"] +
            fundamental_score * weights["fundamental"] +
            sentiment_score * weights["sentiment"] +
            fund_flow_score * weights["fund_flow"]
        )

        return max(0, min(100, composite))

    def _llm_analysis(
        self,
        code: str,
        stock_info: Optional[Dict[str, Any]],
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult,
        fund_flow: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        from modules.ai_selector.models import StockSelectionSchema

        prompt = self._build_comprehensive_prompt(
            code=code,
            stock_name=stock_info.get("name", "") if stock_info else "",
            technical=technical,
            fundamental=fundamental,
            sentiment=sentiment,
            fund_flow=fund_flow
        )

        try:
            response = self.llm_router.chat(
                prompt,
                schema=StockSelectionSchema.get_selection_schema()
            )

            if response.success:
                result = json.loads(response.content)
                composite_score = self._calculate_composite_score(
                    technical, fundamental, sentiment, fund_flow
                )

                return self._generate_structured_result(
                    code=code,
                    stock_info=stock_info,
                    technical=technical,
                    fundamental=fundamental,
                    sentiment=sentiment,
                    fund_flow=fund_flow,
                    composite_score=composite_score,
                    llm_result=result,
                    use_llm=True
                )

        except Exception as e:
            logger.warning(f"LLM analysis failed, using rule engine: {e}")

        return None

    def _llm_technical_analysis(
        self,
        code: str,
        technical: TechnicalResult
    ) -> Optional[Dict[str, Any]]:
        schema = {
            "type": "object",
            "properties": {
                "trend": {"type": "string"},
                "support_levels": {"type": "array", "items": {"type": "number"}},
                "resistance_levels": {"type": "array", "items": {"type": "number"}},
                "buy_signal": {"type": "number", "minimum": 0, "maximum": 100},
                "sell_signal": {"type": "number", "minimum": 0, "maximum": 100},
                "risk_factors": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"}
            }
        }

        prompt = f"""分析股票 {code} 技术面：
- 当前价：{technical.current_price}
- MA5：{technical.ma5}，MA20：{technical.ma20}，MA60：{technical.ma60}
- 趋势：{technical.trend}
- 涨跌幅：{technical.change_pct}%
- 成交量比：{technical.volume_ratio}
- RSI：{technical.rsi}

请输出JSON："""

        try:
            response = self.llm_router.chat(prompt, schema=schema)
            if response.success:
                return json.loads(response.content)
        except Exception as e:
            logger.warning(f"LLM technical analysis failed: {e}")

        return None

    def _llm_sentiment_analysis(
        self,
        code: str,
        sentiment: SentimentResult,
        news_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        schema = {
            "type": "object",
            "properties": {
                "overall_sentiment": {"type": "string"},
                "sentiment_score": {"type": "number", "minimum": 0, "maximum": 100},
                "key_events": {"type": "array", "items": {"type": "string"}},
                "positive_factors": {"type": "array", "items": {"type": "string"}},
                "negative_factors": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"}
            }
        }

        recent_news = [n.get("title", "")[:100] for n in news_data[:5]]
        news_text = "\n".join(recent_news) if recent_news else "无近期新闻"

        prompt = f"""分析股票 {code} 舆情情绪：
- 情绪评分：{sentiment.score}
- 情绪：{sentiment.sentiment}
- 正面关键词数：{sentiment.positive_count}
- 负面关键词数：{sentiment.negative_count}
- 近期新闻：{news_text}

请输出JSON："""

        try:
            response = self.llm_router.chat(prompt, schema=schema)
            if response.success:
                return json.loads(response.content)
        except Exception as e:
            logger.warning(f"LLM sentiment analysis failed: {e}")

        return None

    def _llm_fundamental_analysis(
        self,
        code: str,
        fundamental: FundamentalResult,
        stock_info: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        schema = {
            "type": "object",
            "properties": {
                "valuation": {"type": "string"},
                "financial_health": {"type": "string"},
                "growth_potential": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["低", "中", "高"]},
                "investment_rating": {"type": "string"},
                "summary": {"type": "string"}
            }
        }

        prompt = f"""分析股票 {code} 基本面：
- PE：{fundamental.pe}，PB：{fundamental.pb}
- ROE：{fundamental.roe}%
- 营收增长：{fundamental.revenue_growth}%
- 利润增长：{fundamental.profit_growth}%
- 流动比率：{fundamental.current_ratio}
- 资产负债率：{fundamental.debt_ratio}

请输出JSON："""

        try:
            response = self.llm_router.chat(prompt, schema=schema)
            if response.success:
                return json.loads(response.content)
        except Exception as e:
            logger.warning(f"LLM fundamental analysis failed: {e}")

        return None

    def _build_comprehensive_prompt(
        self,
        code: str,
        stock_name: str,
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult,
        fund_flow: Dict[str, Any]
    ) -> str:
        return f"""分析股票 {code}（{stock_name}）投资价值：

【技术面】
- 评分：{technical.trend_strength}
- 趋势：{technical.trend}
- 涨跌幅：{technical.change_pct}%
- 成交量比：{technical.volume_ratio}
- RSI：{technical.rsi}

【基本面】
- PE：{fundamental.pe}，PB：{fundamental.pb}
- 估值评分：{fundamental.valuation_score}
- 成长评分：{fundamental.growth_score}
- 财务健康评分：{fundamental.health_score}

【舆情】
- 情绪评分：{sentiment.score}
- 情绪：{sentiment.sentiment}
- 正面事件：{sentiment.positive_count}，负面事件：{sentiment.negative_count}

【资金流】
- 主力净流入：{fund_flow.get('main_net_inflow', 0):.0f}
- 资金评分：{fund_flow.get('score', 50)}

请输出JSON（必须包含score、recommendation、reasons、risk_factors、stop_loss、target_price）："""

    def _generate_structured_result(
        self,
        code: str,
        stock_info: Optional[Dict[str, Any]],
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult,
        fund_flow: Dict[str, Any],
        composite_score: float,
        llm_result: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        current_price = technical.current_price

        if llm_result:
            score = llm_result.get("score", composite_score)
            recommendation = llm_result.get("recommendation", "观望")
            reasons = llm_result.get("reasons", [])
            risk_factors = llm_result.get("risk_factors", [])
            stop_loss = llm_result.get("stop_loss", current_price * 0.95)
            target_price = llm_result.get("target_price", current_price * 1.15)
        else:
            score = composite_score
            recommendation = self._get_recommendation(score)
            reasons = self._generate_reasons(technical, fundamental, sentiment, fund_flow)
            risk_factors = self._generate_risk_factors(technical, fundamental, sentiment)
            stop_loss = current_price * 0.95 if current_price > 0 else 0
            target_price = current_price * 1.15 if current_price > 0 else 0

        risk_level = "低" if score >= 70 else "高" if score <= 40 else "中"

        return {
            "code": code,
            "name": stock_info.get("name", "") if stock_info else "",
            "analysis_type": "comprehensive",
            "technical": technical.to_dict(),
            "fundamental": fundamental.to_dict(),
            "sentiment": sentiment.to_dict(),
            "composite_score": round(composite_score, 2),
            "score": round(score, 2),
            "recommendation": recommendation,
            "risk_level": risk_level,
            "stop_loss": round(stop_loss, 2),
            "target_price": round(target_price, 2),
            "reasons": reasons,
            "risk_factors": risk_factors,
            "support_levels": technical.support_levels,
            "resistance_levels": technical.resistance_levels,
            "analyzed_at": beijing_now().isoformat(),
            "analysis_method": "llm" if use_llm else "rule"
        }

    def _get_recommendation(self, score: float) -> str:
        if score >= 75:
            return "强烈推荐"
        elif score >= 65:
            return "买入"
        elif score >= 55:
            return "谨慎买入"
        elif score >= 45:
            return "观望"
        elif score >= 35:
            return "谨慎回避"
        else:
            return "回避"

    def _generate_reasons(
        self,
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult,
        fund_flow: Dict[str, Any]
    ) -> List[str]:
        reasons = []

        if technical.trend == "上升趋势":
            reasons.append("技术面呈上升趋势")
        elif technical.trend == "下降趋势":
            reasons.append("技术面呈下降趋势")

        if technical.volume_ratio > 1.5:
            reasons.append(f"成交量放大({technical.volume_ratio}倍)")

        if technical.change_pct > 3:
            reasons.append(f"涨幅较大({technical.change_pct}%)")

        if fundamental.valuation_score >= 65:
            reasons.append("估值处于合理区间")

        if fundamental.growth_score >= 70:
            reasons.append("成长性良好")

        if sentiment.sentiment == "positive":
            reasons.append(f"舆情正面({sentiment.positive_count}个正面事件)")

        if fund_flow.get("main_net_inflow", 0) > 1e7:
            reasons.append("主力资金净流入")

        if not reasons:
            reasons.append("综合评分一般，建议观望")

        return reasons

    def _generate_risk_factors(
        self,
        technical: TechnicalResult,
        fundamental: FundamentalResult,
        sentiment: SentimentResult
    ) -> List[str]:
        risks = []

        if technical.trend == "下降趋势":
            risks.append("技术面趋势向下")

        if technical.volume_ratio < 0.7:
            risks.append("成交量萎缩")

        if fundamental.pe and fundamental.pe > 40:
            risks.append("估值偏高")

        if fundamental.debt_ratio and fundamental.debt_ratio > 0.7:
            risks.append("资产负债率较高")

        if sentiment.sentiment == "negative":
            risks.append(f"舆情偏空({sentiment.negative_count}个负面事件)")

        if technical.rsi > 75:
            risks.append("RSI超买")

        if technical.rsi < 25:
            risks.append("RSI超卖")

        if not risks:
            risks.append("市场存在不确定性")

        return risks

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
                "date": beijing_now().strftime("%Y-%m-%d")
            },
            {
                "$set": {
                    "result": result,
                    "updated_at": beijing_now()
                }
            },
            upsert=True
        )


ai_analyzer = AIAnalyzer()