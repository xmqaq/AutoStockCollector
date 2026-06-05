import numpy as np
from typing import Dict, List, Optional
from collections import defaultdict


def zscore(values: Dict[str, float]) -> Dict[str, float]:
    codes = list(values.keys())
    arr = np.array([values[c] for c in codes])
    valid = ~np.isnan(arr) & ~np.isinf(arr)
    if not np.any(valid):
        return {c: 50.0 for c in codes}
    mean, std = np.mean(arr[valid]), np.std(arr[valid])
    if std == 0:
        return {c: 50.0 for c in codes}
    z = (arr - mean) / std
    scores = np.clip(z * 10 + 50, 0, 100)
    return {c: float(scores[i]) for i, c in enumerate(codes)}


def percentile_rank(values: Dict[str, float], inverse: bool = False) -> Dict[str, float]:
    codes = list(values.keys())
    arr = np.array([values[c] for c in codes])
    valid = ~np.isnan(arr) & ~np.isinf(arr)
    ranks = np.full(len(codes), 50.0)
    if np.any(valid):
        n_valid = np.sum(valid)
        if n_valid > 1:
            sorted_idx = np.argsort(arr[valid])
            pct = np.arange(n_valid) / (n_valid - 1) * 100
            ranks_sorted = np.full(n_valid, 50.0)
            ranks_sorted[sorted_idx] = pct
            if inverse:
                ranks_sorted = 100 - ranks_sorted
            ranks[valid] = ranks_sorted
    return {c: float(ranks[i]) for i, c in enumerate(codes)}


def industry_neutral_rank(values: Dict[str, float],
                           industries: Dict[str, str]) -> Dict[str, float]:
    groups = defaultdict(dict)
    for code, val in values.items():
        ind = industries.get(code, '未知')
        groups[ind][code] = val
    result = {}
    for grp in groups.values():
        result.update(percentile_rank(grp))
    return result


def winsorize(values: Dict[str, float], limits: tuple = (0.01, 0.99)) -> Dict[str, float]:
    arr = np.array(list(values.values()))
    lo, hi = np.quantile(arr, limits[0]), np.quantile(arr, limits[1])
    codes = list(values.keys())
    result = {}
    for i, c in enumerate(codes):
        result[c] = float(np.clip(arr[i], lo, hi))
    return result


def combine_scores(score_dicts: List[Dict[str, float]],
                   weights: List[float]) -> Dict[str, float]:
    codes = list(score_dicts[0].keys())
    total = sum(weights)
    result = {}
    for c in codes:
        s = sum(w * d.get(c, 50.0) for w, d in zip(weights, score_dicts)) / total
        result[c] = round(float(s), 2)
    return result
