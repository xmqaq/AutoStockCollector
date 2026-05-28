"""
PE/ROE专业估值因子模块
实现A股行业估值分化特性下的专业估值因子分析
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from core.storage.mongo_storage import KlineStorage, FinancialStorage, StockInfoStorage
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class ValuationFactor:
    code: str
    name: str
    industry: str

    pe_ratio: float
    pb_ratio: float
    roe: float
    roa: float

    industry_pe_avg: float
    industry_pe_median: float
    industry_pb_avg: float

    pe_percentile: float
    pb_percentile: float

    valuation_label: str
    valuation_score: float

    recommendation: str


class ValuationFactorAnalyzer:
    INDUSTRY_PE_BENCHMARKS = {
        "银行": {"low": 5, "median": 7, "high": 10},
        "证券": {"low": 10, "median": 20, "high": 30},
        "保险": {"low": 8, "median": 15, "high": 25},
        "房地产": {"low": 5, "median": 10, "high": 15},
        "医药": {"low": 20, "median": 35, "high": 50},
        "白酒": {"low": 15, "median": 30, "high": 45},
        "科技": {"low": 25, "median": 40, "high": 60},
        "制造业": {"low": 10, "median": 20, "high": 35},
        "default": {"low": 10, "median": 25, "high": 40},
    }

    def __init__(self):
        self.kline_storage = KlineStorage()
        self.financial_storage = FinancialStorage()
        self.stock_info_storage = StockInfoStorage()

    def analyze(self, code: str) -> ValuationFactor:
        stock_info = self.stock_info_storage.get_by_code(code)
        name = stock_info.get("name", "") if stock_info else ""
        industry = self._normalize_industry(stock_info.get("industry", ""))

        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=1
        )

        current_price = klines[0].get("close", 0) if klines else 0

        financial_data = self._get_latest_financial_data(code)

        pe_ratio = self._calculate_pe_ratio(current_price, financial_data)
        pb_ratio = self._calculate_pb_ratio(current_price, financial_data)
        roe = self._get_roe(financial_data)
        roa = self._get_roa(financial_data)

        benchmarks = self.INDUSTRY_PE_BENCHMARKS.get(
            industry,
            self.INDUSTRY_PE_BENCHMARKS["default"]
        )

        industry_pe_avg = benchmarks["median"]
        industry_pe_median = benchmarks["median"]
        industry_pb_avg = 3.0

        pe_percentile = self._calculate_percentile(pe_ratio, benchmarks)
        pb_percentile = self._calculate_pb_percentile(pb_ratio, industry_pb_avg)

        valuation_label, valuation_score = self._assess_valuation(
            pe_ratio, pb_ratio, roe, industry, benchmarks
        )

        recommendation = self._generate_recommendation(
            valuation_label, roe, valuation_score
        )

        return ValuationFactor(
            code=code,
            name=name,
            industry=industry,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            roe=roe,
            roa=roa,
            industry_pe_avg=industry_pe_avg,
            industry_pe_median=industry_pe_median,
            industry_pb_avg=industry_pb_avg,
            pe_percentile=pe_percentile,
            pb_percentile=pb_percentile,
            valuation_label=valuation_label,
            valuation_score=valuation_score,
            recommendation=recommendation
        )

    def _normalize_industry(self, industry: str) -> str:
        industry_map = {
            "银行": "银行",
            "券商": "证券",
            "证券": "证券",
            "保险": "保险",
            "地产": "房地产",
            "房地产": "房地产",
            "医药生物": "医药",
            "医药": "医药",
            "白酒": "白酒",
            "饮料制造": "白酒",
            "电子": "科技",
            "计算机": "科技",
            "软件": "科技",
            "通信": "科技",
            "机械设备": "制造业",
            "化工": "制造业",
            "汽车": "制造业",
            "电气设备": "制造业",
        }

        for key, value in industry_map.items():
            if key in industry:
                return value

        return "default"

    def _get_latest_financial_data(self, code: str) -> Optional[Dict]:
        records = self.financial_storage.find_many(
            {"code": code},
            sort=[("report_date", -1)],
            limit=4
        )

        if records:
            return records[0]
        return None

    def _calculate_pe_ratio(
        self,
        price: float,
        financial_data: Optional[Dict]
    ) -> float:
        if not financial_data or price <= 0:
            return 0.0

        eps = financial_data.get("eps", 0)
        if eps and eps > 0:
            return round(price / eps, 2)

        return 0.0

    def _calculate_pb_ratio(
        self,
        price: float,
        financial_data: Optional[Dict]
    ) -> float:
        if not financial_data or price <= 0:
            return 0.0

        book_value_per_share = financial_data.get("bps", 0)
        if book_value_per_share and book_value_per_share > 0:
            return round(price / book_value_per_share, 2)

        return 0.0

    def _get_roe(self, financial_data: Optional[Dict]) -> float:
        if not financial_data:
            return 0.0

        roe = financial_data.get("roe", 0)
        if roe:
            return round(roe * 100, 2)

        net_profit = financial_data.get("净利润", 0)
        total_assets = financial_data.get("资产总计", 0)
        equity = financial_data.get("所有者权益合计", 0)

        if equity and equity > 0:
            return round(net_profit / equity * 100, 2)

        return 0.0

    def _get_roa(self, financial_data: Optional[Dict]) -> float:
        if not financial_data:
            return 0.0

        net_profit = financial_data.get("净利润", 0)
        total_assets = financial_data.get("资产总计", 0)

        if total_assets and total_assets > 0:
            return round(net_profit / total_assets * 100, 2)

        return 0.0

    def _calculate_percentile(
        self,
        pe_ratio: float,
        benchmarks: Dict
    ) -> float:
        if pe_ratio <= 0:
            return 50.0

        low = benchmarks["low"]
        high = benchmarks["high"]

        if pe_ratio <= low:
            return 20.0
        elif pe_ratio >= high:
            return 80.0
        else:
            return 50.0 + (pe_ratio - benchmarks["median"]) / (high - low) * 30

    def _calculate_pb_percentile(
        self,
        pb_ratio: float,
        industry_avg_pb: float
    ) -> float:
        if pb_ratio <= 0:
            return 50.0

        if pb_ratio <= industry_avg_pb * 0.7:
            return 30.0
        elif pb_ratio >= industry_avg_pb * 1.3:
            return 70.0
        else:
            return 50.0

    def _assess_valuation(
        self,
        pe_ratio: float,
        pb_ratio: float,
        roe: float,
        industry: str,
        benchmarks: Dict
    ) -> tuple:
        valuation_score = 50.0

        if pe_ratio > 0 and roe > 0:
            peg = pe_ratio / (roe * 100)
            if peg < 1:
                valuation_score += 15
            elif peg > 2:
                valuation_score -= 15

        if pe_ratio > 0:
            if pe_ratio < benchmarks["low"]:
                valuation_score += 20
            elif pe_ratio > benchmarks["high"]:
                valuation_score -= 20
            elif pe_ratio < benchmarks["median"]:
                valuation_score += 10

        if pb_ratio > 0:
            if pb_ratio < 1:
                valuation_score += 10
            elif pb_ratio > 5:
                valuation_score -= 10

        if roe > 15:
            valuation_score += 10
        elif roe > 10:
            valuation_score += 5
        elif roe < 0:
            valuation_score -= 20

        valuation_score = max(0, min(100, valuation_score))

        if valuation_score >= 70:
            label = "低估"
        elif valuation_score >= 40:
            label = "合理"
        else:
            label = "高估"

        return label, round(valuation_score, 2)

    def _generate_recommendation(
        self,
        valuation_label: str,
        roe: float,
        valuation_score: float
    ) -> str:
        if valuation_label == "低估" and roe > 5:
            return "价值洼地，重点关注"
        elif valuation_label == "低估":
            return "估值偏低，谨慎关注"
        elif valuation_label == "合理":
            if roe > 10:
                return "估值合理，盈利能力强"
            else:
                return "估值合理，可持续观察"
        else:
            if valuation_score < 20:
                return "估值泡沫，建议回避"
            else:
                return "估值偏高，注意风险"

    def batch_analyze(
        self,
        codes: List[str]
    ) -> List[ValuationFactor]:
        results = []

        for code in codes:
            try:
                factor = self.analyze(code)
                results.append(factor)
            except Exception as e:
                logger.error(f"Valuation analysis error for {code}: {e}")

        return results


valuation_analyzer = ValuationFactorAnalyzer()