"""
板块轮动题材选股策略
"""
from typing import List, Dict, Any
from .base import BaseStrategy, SelectionResult
from utils.logger import get_logger


logger = get_logger(__name__)


class SectorRotationStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="板块轮动题材选股",
            description="基于板块轮动题材选股"
        )
        self.min_score = 60.0
        self.max_stocks = 20

    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage
        from core.collector.fund_flow_collector import BlockCollector

        info_storage = StockInfoStorage()
        block_collector = BlockCollector()

        hot_blocks = block_collector.collect_hot_blocks() or []
        if not hot_blocks:
            return codes

        hot_block_names = set()
        for block in hot_blocks[:10]:
            name = block.get("name", "")
            if name:
                hot_block_names.add(name)

        filtered = []
        for code in codes:
            info = info_storage.get_by_code(code)
            if not info:
                continue

            name = info.get("name", "")
            if any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                continue

            industry = info.get("industry", "")
            in_hot_sector = any(
                block_name in industry or industry in block_name
                for block_name in hot_block_names
            )

            if in_hot_sector:
                filtered.append(code)

        return filtered

    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage

        kline_storage = KlineStorage()
        info_storage = StockInfoStorage()

        factors = {}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=20
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]

            factors["current_price"] = current
            factors["name"] = klines[0].get("name", "")

            if len(closes) >= 2 and closes[1] > 0:
                factors["change_pct"] = (current - closes[1]) / closes[1] * 100
            else:
                factors["change_pct"] = 0

            ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else current
            factors["ma10"] = ma10
            factors["trend"] = 1 if current > ma10 else -1

            recent_change = 0
            for i in range(min(5, len(closes) - 1)):
                if closes[i + 1] > 0:
                    change = (closes[i] - closes[i + 1]) / closes[i + 1] * 100
                    recent_change += change

            factors["momentum"] = recent_change
            factors["technical_score"] = 50 + recent_change * 2
        else:
            factors["current_price"] = 0
            factors["name"] = ""
            factors["change_pct"] = 0
            factors["ma10"] = 0
            factors["trend"] = 0
            factors["momentum"] = 0
            factors["technical_score"] = 50.0

        info = info_storage.get_by_code(code)
        if info:
            factors["industry"] = info.get("industry", "")
        else:
            factors["industry"] = ""

        factors["sector_score"] = self._calculate_sector_score(factors)

        factors["fundamental_score"] = 50.0
        factors["sentiment_score"] = 50.0
        factors["fund_flow_score"] = 50.0

        return factors

    def _calculate_sector_score(self, factors: Dict[str, float]) -> float:
        from core.collector.fund_flow_collector import BlockCollector

        block_collector = BlockCollector()
        hot_blocks = block_collector.collect_hot_blocks() or []

        industry = factors.get("industry", "")

        for block in hot_blocks[:10]:
            block_name = block.get("name", "")
            if block_name and (industry in block_name or block_name in industry):
                rank = block.get("rank", 50)
                return max(0, 100 - rank * 5)

        return 30.0

    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        technical = factors.get("technical_score", 50.0)
        sector = factors.get("sector_score", 50.0)

        total_score = technical * 0.7 + sector * 0.3

        return max(0, min(100, total_score))