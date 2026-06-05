import numpy as np
from typing import List, Dict, Any, Optional
from collections import defaultdict
from utils.logger import get_logger

from .normalizer import percentile_rank, industry_neutral_rank, combine_scores, winsorize
from .factors_kline import batch_kline_factors
from .factors_margin import batch_margin_factors
from .factors_dragon import batch_dragon_factors
from .factors_sentiment import batch_sentiment_factors
from .factors_fund_flow import batch_fund_flow_factors

logger = get_logger(__name__)


class FactorMiner:
    def __init__(self, industries: Dict[str, str] = None,
                 market_caps: Dict[str, float] = None):
        self.industries = industries or {}
        self.market_caps = market_caps or {}

    def mine_all(self, valid_codes: List[str],
                 kline_map: Dict[str, List[Dict]],
                 margin_map: Dict[str, List[Dict]],
                 dragon_map: Dict[str, List[Dict]],
                 news_map: Dict[str, List[Dict]],
                 fund_flow_map: Dict[str, List[Dict]] = None,
                 fundamental_values: Dict[str, float] = None,
                 valuation_values: Dict[str, float] = None,
                 ) -> Dict[str, Dict[str, float]]:
        fundamental_values = fundamental_values or {}
        valuation_values = valuation_values or {}
        fund_flow_map = fund_flow_map or {}

        kline_factors = batch_kline_factors(valid_codes, kline_map)
        margin_factors = batch_margin_factors(valid_codes, margin_map)
        dragon_factors = batch_dragon_factors(valid_codes, dragon_map, self.market_caps)
        sentiment_factors = batch_sentiment_factors(valid_codes, news_map)
        fund_flow_factors = batch_fund_flow_factors(valid_codes, fund_flow_map)

        all_factors: Dict[str, Dict[str, float]] = {}
        for code in valid_codes:
            factors = {}
            factors.update(kline_factors.get(code, {}))
            factors.update(margin_factors.get(code, {}))
            factors.update(dragon_factors.get(code, {}))
            factors.update(sentiment_factors.get(code, {}))
            factors.update(fund_flow_factors.get(code, {}))
            if code in fundamental_values:
                factors['fundamental_raw'] = fundamental_values[code]
            if code in valuation_values:
                factors['valuation_raw'] = valuation_values[code]
            all_factors[code] = factors

        factor_names = set()
        for factors in all_factors.values():
            factor_names.update(factors.keys())

        normalized: Dict[str, Dict[str, float]] = {}
        for code in valid_codes:
            normalized[code] = {}

        for fname in sorted(factor_names):
            raw = {code: all_factors[code][fname]
                   for code in valid_codes if fname in all_factors[code]}
            if not raw:
                continue

            raw = winsorize(raw)

            inverse = fname in ('atr', 'amihud_illiq', 'downside_vol', 'short_ratio',
                                'reversal_5d', 'reversal_20d', 'inflow_volatility')

            if len(raw) > 10 and self.industries:
                scores = industry_neutral_rank(raw, self.industries)
            else:
                scores = percentile_rank(raw, inverse)

            for code, s in scores.items():
                normalized[code][fname] = s

        return normalized

    @staticmethod
    def composite_mining_score(mining_scores: Dict[str, Dict[str, float]],
                               codes: List[str]) -> Dict[str, float]:
        result = {}
        for code in codes:
            factors = mining_scores.get(code, {})
            if not factors:
                result[code] = 50.0
            else:
                result[code] = float(np.mean(list(factors.values())))
        return result
