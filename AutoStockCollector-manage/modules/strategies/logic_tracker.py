"""
标的逻辑存续追踪模块
每日复盘已选标的，动态校验选股逻辑存续性
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from core.storage.mongo_storage import KlineStorage, StockInfoStorage, NewsStorage, FundFlowStorage
from config.database import get_collection
from utils.logger import get_logger


logger = get_logger(__name__)


class LogicStatus(Enum):
    VALID = "valid"
    WEAKENING = "weakening"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass
class LogicCheckResult:
    code: str
    name: str
    status: LogicStatus
    score_change: float
    alert_type: str
    description: str
    recommendation: str
    check_date: str


class LogicPersistenceTracker:
    def __init__(self):
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.news_storage = NewsStorage()
        self.fund_flow_storage = FundFlowStorage()
        self.collection = get_collection("logic_persistence_tracking")

    def track_stock_logic(
        self,
        code: str,
        selection_date: str,
        selection_reasons: List[str]
    ) -> LogicCheckResult:
        stock_info = self.stock_info_storage.get_by_code(code)
        name = stock_info.get("name", "") if stock_info else ""

        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if len(klines) < 5:
            return LogicCheckResult(
                code=code,
                name=name,
                status=LogicStatus.UNKNOWN,
                score_change=0.0,
                alert_type="data_insufficient",
                description="数据不足，无法判断",
                recommendation="保持观望",
                check_date=datetime.now().strftime("%Y-%m-%d")
            )

        trend_status = self._check_trend_persistence(klines, selection_date)
        fund_flow_status = self._check_fund_flow_persistence(code, selection_date)
        sentiment_status = self._check_sentiment_persistence(code, selection_date)
        fundamental_status = self._check_fundamental_persistence(code)

        overall_status, score_change, alert_type, description = self._aggregate_status(
            trend_status, fund_flow_status, sentiment_status, fundamental_status
        )

        recommendation = self._generate_recommendation(overall_status, score_change)

        result = LogicCheckResult(
            code=code,
            name=name,
            status=overall_status,
            score_change=score_change,
            alert_type=alert_type,
            description=description,
            recommendation=recommendation,
            check_date=datetime.now().strftime("%Y-%m-%d")
        )

        self._save_tracking_result(result, selection_date, selection_reasons)

        return result

    def _check_trend_persistence(
        self,
        klines: List[Dict],
        selection_date: str
    ) -> Dict[str, Any]:
        closes = [k.get("close", 0) for k in klines]

        if len(closes) < 20:
            return {"status": LogicStatus.UNKNOWN, "change": 0.0, "description": "数据不足"}

        current_price = closes[0]
        ma20 = sum(closes[:20]) / 20
        ma60_sum = sum(closes[:min(60, len(closes))])
        ma60 = ma60_sum / min(60, len(closes))

        trend_change = (current_price - ma20) / ma20 * 100 if ma20 > 0 else 0

        status = LogicStatus.VALID
        if trend_change < -10:
            status = LogicStatus.INVALID
        elif trend_change < 0:
            status = LogicStatus.WEAKENING

        return {
            "status": status,
            "change": trend_change,
            "current_price": current_price,
            "ma20": ma20,
            "description": f"趋势变化{trend_change:.2f}%"
        }

    def _check_fund_flow_persistence(
        self,
        code: str,
        selection_date: str
    ) -> Dict[str, Any]:
        try:
            flow_data = self.fund_flow_storage.get_latest_flow(code)

            if not flow_data:
                return {"status": LogicStatus.UNKNOWN, "change": 0.0, "description": "无资金流数据"}

            main_inflow = flow_data.get("main_net_inflow", 0)

            if main_inflow > 100000000:
                status = LogicStatus.VALID
            elif main_inflow > 0:
                status = LogicStatus.WEAKENING
            else:
                status = LogicStatus.INVALID

            return {
                "status": status,
                "change": main_inflow / 100000000,
                "main_inflow": main_inflow,
                "description": f"主力净流入{main_inflow/100000000:.2f}亿"
            }

        except Exception as e:
            logger.error(f"Fund flow check error: {e}")
            return {"status": LogicStatus.UNKNOWN, "change": 0.0, "description": "检查异常"}

    def _check_sentiment_persistence(
        self,
        code: str,
        selection_date: str
    ) -> Dict[str, Any]:
        try:
            recent_news = self.news_storage.get_latest_news(code=code, limit=20)

            if not recent_news:
                return {"status": LogicStatus.UNKNOWN, "change": 0.0, "description": "无新闻数据"}

            positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "业绩"]
            negative_keywords = ["亏损", "下跌", "减持", "利空", "诉讼", "风险"]

            recent_positive = 0
            recent_negative = 0

            for news in recent_news[:10]:
                text = news.get("title", "") + news.get("content", "")
                recent_positive += sum(1 for kw in positive_keywords if kw in text)
                recent_negative += sum(1 for kw in negative_keywords if kw in text)

            net_sentiment = recent_positive - recent_negative

            if net_sentiment >= 2:
                status = LogicStatus.VALID
            elif net_sentiment >= 0:
                status = LogicStatus.WEAKENING
            else:
                status = LogicStatus.INVALID

            return {
                "status": status,
                "change": net_sentiment,
                "positive_count": recent_positive,
                "negative_count": recent_negative,
                "description": f"舆情正向{recent_positive}条，负向{recent_negative}条"
            }

        except Exception as e:
            logger.error(f"Sentiment check error: {e}")
            return {"status": LogicStatus.UNKNOWN, "change": 0.0, "description": "检查异常"}

    def _check_fundamental_persistence(self, code: str) -> Dict[str, Any]:
        try:
            stock_info = self.stock_info_storage.get_by_code(code)

            if not stock_info:
                return {"status": LogicStatus.UNKNOWN, "description": "无基本面数据"}

            is_st = stock_info.get("is_st", False)
            if is_st or "ST" in stock_info.get("name", ""):
                return {"status": LogicStatus.INVALID, "description": "股票被ST处理"}

            return {"status": LogicStatus.VALID, "description": "基本面无重大变化"}

        except Exception as e:
            logger.error(f"Fundamental check error: {e}")
            return {"status": LogicStatus.UNKNOWN, "description": "检查异常"}

    def _aggregate_status(
        self,
        trend: Dict,
        fund_flow: Dict,
        sentiment: Dict,
        fundamental: Dict
    ) -> tuple:
        status_map = {
            LogicStatus.VALID: 2,
            LogicStatus.WEAKENING: 1,
            LogicStatus.INVALID: -2,
            LogicStatus.UNKNOWN: 0
        }

        total_score = (
            status_map.get(trend.get("status"), 0) * 0.4 +
            status_map.get(fund_flow.get("status"), 0) * 0.3 +
            status_map.get(sentiment.get("status"), 0) * 0.2 +
            status_map.get(fundamental.get("status"), 0) * 0.1
        )

        score_change = total_score * 10

        if total_score >= 1:
            status = LogicStatus.VALID
            alert_type = "logic_valid"
            description = "选股逻辑仍然有效"
        elif total_score >= 0:
            status = LogicStatus.WEAKENING
            alert_type = "logic_weakening"
            description = "选股逻辑有所弱化"
        else:
            status = LogicStatus.INVALID
            alert_type = "logic_invalid"
            description = "选股逻辑已失效"

        return status, score_change, alert_type, description

    def _generate_recommendation(self, status: LogicStatus, score_change: float) -> str:
        if status == LogicStatus.VALID:
            return "继续持有"
        elif status == LogicStatus.WEAKENING:
            if score_change < -10:
                return "考虑减仓"
            else:
                return "保持观察"
        else:
            return "建议调仓"

    def _save_tracking_result(
        self,
        result: LogicCheckResult,
        selection_date: str,
        selection_reasons: List[str]
    ):
        try:
            doc = {
                "code": result.code,
                "name": result.name,
                "status": result.status.value,
                "score_change": result.score_change,
                "alert_type": result.alert_type,
                "description": result.description,
                "recommendation": result.recommendation,
                "check_date": result.check_date,
                "selection_date": selection_date,
                "selection_reasons": selection_reasons,
                "updated_at": datetime.now()
            }

            self.collection.update_one(
                {"code": result.code, "check_date": result.check_date},
                {"$set": doc},
                upsert=True
            )

        except Exception as e:
            logger.error(f"Failed to save tracking result: {e}")

    def batch_track(
        self,
        stocks: List[Dict]
    ) -> List[LogicCheckResult]:
        results = []

        for stock in stocks:
            code = stock.get("code")
            selection_date = stock.get("selection_date", datetime.now().strftime("%Y-%m-%d"))
            selection_reasons = stock.get("reasons", [])

            try:
                result = self.track_stock_logic(code, selection_date, selection_reasons)
                results.append(result)
            except Exception as e:
                logger.error(f"Track error for {code}: {e}")

        return results

    def get_tracking_history(
        self,
        code: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            records = list(self.collection.find(
                {
                    "code": code,
                    "check_date": {
                        "$gte": start_date.strftime("%Y-%m-%d"),
                        "$lte": end_date.strftime("%Y-%m-%d")
                    }
                }
            ).sort("check_date", -1))

            for record in records:
                record.pop("_id", None)

            return records

        except Exception as e:
            logger.error(f"Failed to get tracking history: {e}")
            return []


logic_tracker = LogicPersistenceTracker()