import numpy as np
from typing import List, Dict, Optional


def calc_net_inflow_intensity(records: List[Dict], window: int = 5) -> Optional[float]:
    if not records:
        return None
    total_amounts = []
    net_inflows = []
    for r in records[:window]:
        net = float(r.get('main_net_inflow', 0) or 0)
        total = float(r.get('total_amount', 0) or 0)
        if total > 0:
            total_amounts.append(total)
            net_inflows.append(net)
    if not total_amounts:
        return None
    ratios = np.array(net_inflows) / np.array(total_amounts)
    return float(np.mean(ratios) * 100)


def calc_consecutive_inflow_days(records: List[Dict], max_lookback: int = 10) -> Optional[float]:
    if not records:
        return None
    count = 0
    for r in records[:max_lookback]:
        if (float(r.get('main_net_inflow', 0) or 0)) > 0:
            count += 1
        else:
            break
    return float(count)


def calc_inflow_volatility(records: List[Dict], window: int = 5) -> Optional[float]:
    if len(records) < window:
        return None
    inflows = np.array([float(r.get('main_net_inflow', 0) or 0) for r in records[:window]])
    if np.std(inflows) == 0:
        return 0.0
    return float(np.std(inflows) / max(abs(np.mean(inflows)), 1))


def batch_fund_flow_factors(codes: List[str],
                            fund_flow_map: Dict[str, List[Dict]]
                            ) -> Dict[str, Dict[str, float]]:
    result = {}
    for code in codes:
        records = fund_flow_map.get(code, [])
        if not records:
            result[code] = {}
            continue

        factors = {}
        intensity = calc_net_inflow_intensity(records)
        if intensity is not None:
            factors['inflow_intensity'] = intensity

        consec = calc_consecutive_inflow_days(records)
        if consec is not None:
            factors['inflow_consecutive'] = consec

        vol = calc_inflow_volatility(records)
        if vol is not None:
            factors['inflow_volatility'] = vol

        result[code] = factors
    return result
