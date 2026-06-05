from typing import List, Dict, Optional


def calc_dragon_net_buy_intensity(records: List[Dict],
                                  market_cap: float) -> Optional[float]:
    if not records or market_cap <= 0:
        return None
    net_buy = float(records[0].get('龙虎榜净买', 0) or 0)
    return net_buy / market_cap * 100


def calc_dragon_frequency(records: List[Dict]) -> int:
    return len(records)


def calc_dragon_institutional_ratio(records: List[Dict]) -> Optional[float]:
    if not records:
        return None
    buy = float(records[0].get('买入额', 0) or 0)
    sell = float(records[0].get('卖出额', 0) or 0)
    total = buy + sell
    if total == 0:
        return None
    return buy / total * 100


def batch_dragon_factors(codes: List[str],
                         dragon_map: Dict[str, List[Dict]],
                         market_caps: Dict[str, float]
                         ) -> Dict[str, Dict[str, float]]:
    result = {}
    for code in codes:
        records = dragon_map.get(code, [])
        if not records:
            result[code] = {}
            continue
        factors = {}
        cap = market_caps.get(code, 0)
        ni = calc_dragon_net_buy_intensity(records, cap)
        if ni is not None:
            factors['dragon_net_buy_intensity'] = ni
        factors['dragon_frequency'] = float(calc_dragon_frequency(records))
        ir = calc_dragon_institutional_ratio(records)
        if ir is not None:
            factors['dragon_institutional_ratio'] = ir
        result[code] = factors
    return result
