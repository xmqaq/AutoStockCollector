"""因子计算引擎 — 按 FactorRegistry 注册表批量算分。"""

from typing import List, Dict, Optional
from collections import defaultdict
from utils.logger import get_logger

from .base import FactorRegistry, DataStore
from .normalizer import winsorize, industry_neutral_rank, percentile_rank

logger = get_logger(__name__)


class FactorEngine:
    """引擎：给定股票列表和数据，按 registry 中的因子依次计算、归一化、加权合成。"""

    def __init__(self, industries: Dict[str, str] = None,
                 market_caps: Dict[str, float] = None,
                 factor_names: List[str] = None):
        """
        Args:
            industries: {code: 行业名}
            market_caps: {code: 市值}
            factor_names: 要计算的因子列表，默认使用 registry 全量
        """
        self.industries = industries or {}
        self.market_caps = market_caps or {}
        self.factor_names = factor_names or FactorRegistry.list_factors()

    def compute_raw(self, codes: List[str],
                    store: DataStore) -> Dict[str, Dict[str, float]]:
        """计算所有因子的原始值。

        Returns:
            {code: {factor_name: raw_value}}
        """
        result: Dict[str, Dict[str, float]] = {}
        for code in codes:
            result[code] = {}

        for name in self.factor_names:
            factor = FactorRegistry.get(name)
            if factor is None:
                logger.warning(f'Factor [{name}] not found in registry, skipping')
                continue

            for code in codes:
                try:
                    val = factor.compute(code, store)
                    if val is not None:
                        result[code][name] = val
                except Exception as e:
                    logger.debug(f'Factor [{name}] compute error for {code}: {e}')

        return result

    def normalize(self, raw: Dict[str, Dict[str, float]],
                  codes: List[str]) -> Dict[str, Dict[str, float]]:
        """对每个因子做 winsorize + 行业中性排名（0-100）。"""
        factor_names = set()
        for factors in raw.values():
            factor_names.update(factors.keys())

        normalized: Dict[str, Dict[str, float]] = {c: {} for c in codes}

        for fname in sorted(factor_names):
            vals = {c: raw[c][fname] for c in codes if fname in raw.get(c, {})}
            if not vals:
                continue

            vals = winsorize(vals)
            meta = FactorRegistry.get(fname)
            inverse = meta.meta.inverse if meta else False

            if len(vals) > 10 and self.industries:
                scores = industry_neutral_rank(vals, self.industries)
            else:
                scores = percentile_rank(vals, inverse)

            for c, s in scores.items():
                normalized[c][fname] = s

        return normalized

    def synthesize(self, normalized: Dict[str, Dict[str, float]],
                   codes: List[str]) -> Dict[str, float]:
        """加权合成综合分。"""
        result = {}
        for code in codes:
            factors = normalized.get(code, {})
            if not factors:
                result[code] = 50.0
                continue
            weights = FactorRegistry.normalize_weight(list(factors.keys()))
            score = sum(factors[k] * weights.get(k, 0) for k in factors)
            result[code] = score
        return result

    def run(self, codes: List[str],
            store: DataStore) -> Dict[str, float]:
        """全流程：计算 → 归一化 → 加权合成。"""
        raw = self.compute_raw(codes, store)
        norm = self.normalize(raw, codes)
        return self.synthesize(norm, codes)

    @staticmethod
    def scores_to_json(scores: Dict[str, float],
                       factors_detail: Dict[str, Dict[str, float]] = None,
                       top_n: int = 30) -> Dict:
        """格式化成前端可用的结果。"""
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for code, total in ranked[:top_n]:
            entry = {'code': code, 'total_score': round(total, 1)}
            if factors_detail and code in factors_detail:
                entry['factors'] = {k: round(v, 2) for k, v in factors_detail[code].items()}
            results.append(entry)
        return {'results': results, 'total_analyzed': len(scores)}
