"""因子 IC (Information Coefficient) 测试：衡量每个因子预测未来收益的能力。"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from utils.logger import get_logger

from .factors_kline import (
    calc_atr, calc_short_term_reversal, calc_medium_term_reversal,
    calc_amihud_illiq, calc_vpc, calc_obv_divergence, calc_downside_vol,
)
from .normalizer import winsorize

logger = get_logger(__name__)

_MIN_KLINE = 20


def _spearman_rank_corr(x: np.ndarray, y: np.ndarray) -> float:
    """纯 numpy 实现 Spearman 秩相关系数。"""
    n = len(x)
    if n < 10:
        return 0.0
    x_rank = np.argsort(np.argsort(x)).astype(float)
    y_rank = np.argsort(np.argsort(y)).astype(float)
    d = x_rank - y_rank
    denom = n * (n * n - 1)
    if denom == 0:
        return 0.0
    return float(1 - (6 * np.sum(d * d)) / denom)


def _forward_return(klines: List[Dict], offset: int = 5) -> Optional[float]:
    """从 klines[-offset-1] 到 klines[-1] 的收益率（未来 N 日涨跌幅）。"""
    if len(klines) < offset + 1:
        return None
    start = float(klines[-(offset + 1)]['close'])
    end = float(klines[-1]['close'])
    if start <= 0:
        return None
    return (end - start) / start * 100


_FACTOR_FUNCS = {
    'atr': lambda k, p=14: calc_atr(k, p),
    'reversal_5d': lambda k: calc_short_term_reversal(k),
    'reversal_20d': lambda k: calc_medium_term_reversal(k),
    'amihud_illiq': lambda k: calc_amihud_illiq(k),
    'vpc': lambda k: calc_vpc(k),
    'obv_divergence': lambda k: calc_obv_divergence(k),
    'downside_vol': lambda k: calc_downside_vol(
        [(float(k[i+1]['close']) - float(k[i]['close'])) / float(k[i]['close'])
         for i in range(len(k)-1) if float(k[i]['close']) > 0]
    ),
}


def compute_single_ic(
    codes: List[str],
    kline_map: Dict[str, List[Dict]],
    factor_name: str,
    forward_days: int = 5,
    min_codes: int = 50,
) -> Optional[float]:
    """计算单个因子在某个 forward 窗口下的 IC 值。"""
    factor_func = _FACTOR_FUNCS.get(factor_name)
    if factor_func is None:
        return None

    factor_values = {}
    forward_returns = {}

    for code in codes:
        klines = kline_map.get(code, [])
        if len(klines) < forward_days + _MIN_KLINE:
            continue

        # 分割：前 80% 算因子，后 20% 算收益
        split = int(len(klines) * 0.8)
        factor_klines = klines[:split]
        fwd_klines = klines[split:]

        if len(factor_klines) < 15 or len(fwd_klines) < forward_days:
            continue

        # 因子值
        fv = factor_func(factor_klines)
        if fv is None or np.isnan(fv) or np.isinf(fv):
            continue
        factor_values[code] = fv

        # 未来收益
        fr = _forward_return(fwd_klines, offset=min(forward_days, len(fwd_klines) - 1))
        if fr is None or np.isnan(fr) or np.isinf(fr):
            continue
        forward_returns[code] = fr

    if len(factor_values) < min_codes:
        return None

    # 对齐
    common = [c for c in factor_values if c in forward_returns]
    if len(common) < min_codes:
        return None

    f_arr = np.array([factor_values[c] for c in common])
    r_arr = np.array([forward_returns[c] for c in common])

    # 极值处理
    f_arr = np.clip(f_arr, np.percentile(f_arr, 1), np.percentile(f_arr, 99))
    r_arr = np.clip(r_arr, np.percentile(r_arr, 1), np.percentile(r_arr, 99))

    ic = _spearman_rank_corr(f_arr, r_arr)
    return ic


def compute_full_ic(
    codes: List[str],
    kline_map: Dict[str, List[Dict]],
    forward_days: int = 5,
    min_codes: int = 30,
) -> List[Dict[str, Any]]:
    """计算所有因子的 IC 值，按 |IC| 排序。返回 [{'factor':..., 'ic':..., 'abs_ic':...}, ...]"""
    results = []
    for fname in _FACTOR_FUNCS:
        try:
            ic = compute_single_ic(codes, kline_map, fname, forward_days, min_codes)
            if ic is not None:
                results.append({
                    'factor': fname,
                    'ic': round(ic, 4),
                    'abs_ic': round(abs(ic), 4),
                    'direction': '正相关' if ic > 0 else '负相关',
                    'forward_days': forward_days,
                    'n_stocks': len(codes),
                })
        except Exception as e:
            logger.warning(f"IC calc failed for {fname}: {e}")

    results.sort(key=lambda x: x['abs_ic'], reverse=True)
    return results


def compute_multi_period_ic(
    codes: List[str],
    kline_map: Dict[str, List[Dict]],
    periods: List[int] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """在多个 forward 窗口下计算 IC。"""
    if periods is None:
        periods = [1, 5, 10, 20]
    result = {}
    for p in periods:
        result[p] = compute_full_ic(codes, kline_map, forward_days=p)
        logger.info(f"IC done for forward={p}d: "
                    f"top={result[p][0]['factor'] if result[p] else 'none'} "
                    f"ic={result[p][0]['ic'] if result[p] else 0}")
    return result


def rank_factors_by_ic(ic_results: Dict[int, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """综合多周期 IC 排序：按平均 |IC| 降序排列。"""
    factor_scores = defaultdict(list)
    for period, results in ic_results.items():
        for r in results:
            factor_scores[r['factor']].append(r['abs_ic'])

    ranked = []
    for fname, ics in factor_scores.items():
        ranked.append({
            'factor': fname,
            'avg_abs_ic': round(float(np.mean(ics)), 4),
            'max_abs_ic': round(float(np.max(ics)), 4),
            'ic_stability': round(float(np.std(ics)), 4),
        })
    ranked.sort(key=lambda x: x['avg_abs_ic'], reverse=True)
    return ranked
