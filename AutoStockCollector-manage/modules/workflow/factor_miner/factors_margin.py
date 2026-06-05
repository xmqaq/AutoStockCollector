from typing import List, Dict, Optional


def calc_margin_change(records: List[Dict], days: int = 5) -> Optional[float]:
    if len(records) < days:
        return None
    current = float(records[0].get('margin_balance', 0) or 0)
    prev = float(records[days - 1].get('margin_balance', 0) or 0)
    if prev == 0:
        return None
    return (current - prev) / prev * 100


def calc_short_ratio(records: List[Dict]) -> Optional[float]:
    if not records:
        return None
    balance = float(records[0].get('margin_balance', 0) or 0)
    short = float(records[0].get('short_balance', 0) or 0)
    total = balance + short
    if total == 0:
        return None
    return short / total * 100


def calc_margin_trend(records: List[Dict]) -> Optional[float]:
    if len(records) < 5:
        return None
    total_buy = sum(float(r.get('margin_buy', 0) or 0) for r in records[:5])
    total_repay = sum(float(r.get('margin_repay', 0) or 0) for r in records[:5])
    balance = float(records[0].get('margin_balance', 0) or 0)
    if balance <= 0:
        return None
    return (total_buy - total_repay) / balance * 100


def batch_margin_factors(codes: List[str],
                         margin_map: Dict[str, List[Dict]]
                         ) -> Dict[str, Dict[str, float]]:
    result = {}
    for code in codes:
        records = margin_map.get(code, [])
        if not records:
            result[code] = {}
            continue
        factors = {}
        mc = calc_margin_change(records)
        if mc is not None:
            factors['margin_change_5d'] = mc
        sr = calc_short_ratio(records)
        if sr is not None:
            factors['short_ratio'] = sr
        mt = calc_margin_trend(records)
        if mt is not None:
            factors['margin_trend'] = mt
        result[code] = factors
    return result
