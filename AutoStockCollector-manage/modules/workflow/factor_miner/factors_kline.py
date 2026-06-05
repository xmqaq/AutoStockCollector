import numpy as np
from typing import List, Dict, Optional


def calc_atr(klines: List[Dict], period: int = 14) -> Optional[float]:
    if len(klines) < period + 1:
        return None
    closes = np.array([float(k['close']) for k in klines])
    highs = np.array([float(k.get('high', k['close'])) for k in klines])
    lows = np.array([float(k.get('low', k['close'])) for k in klines])

    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1])
        )
    )
    atr = np.mean(tr[-period:])
    return float(atr / closes[-1] * 100) if closes[-1] > 0 else None


def calc_beta(stock_returns: List[float], idx_returns: List[float]) -> Optional[float]:
    if len(stock_returns) < 30 or len(idx_returns) < 30:
        return None
    sr = np.array(stock_returns[-60:])
    ir = np.array(idx_returns[-60:])
    valid = ~np.isnan(sr) & ~np.isnan(ir)
    if np.sum(valid) < 20:
        return None
    cov = np.cov(sr[valid], ir[valid])[0, 1]
    var = np.var(ir[valid])
    return float(cov / var) if var > 0 else 1.0


def calc_downside_vol(returns: List[float]) -> Optional[float]:
    arr = np.array(returns)
    downside = arr[arr < 0]
    if len(downside) < 5:
        return None
    return float(np.sqrt(np.mean(downside ** 2)) * np.sqrt(252))


def calc_short_term_reversal(klines: List[Dict]) -> Optional[float]:
    if len(klines) < 6:
        return None
    c0 = float(klines[0]['close'])
    c5 = float(klines[5]['close'])
    return (c0 - c5) / c5 * 100 if c5 > 0 else None


def calc_medium_term_reversal(klines: List[Dict]) -> Optional[float]:
    if len(klines) < 21:
        return None
    c0 = float(klines[0]['close'])
    c20 = float(klines[20]['close'])
    return (c0 - c20) / c20 * 100 if c20 > 0 else None


def calc_amihud_illiq(klines: List[Dict]) -> Optional[float]:
    if len(klines) < 20:
        return None
    closes = np.array([float(k['close']) for k in klines[-21:]])
    amounts = np.array([float(k.get('amount', 0) or 0) * 10000 for k in klines[-21:]])
    returns = np.abs(np.diff(closes) / closes[:-1])
    # returns[i] = |close[i+1] - close[i]| / close[i], 对应 amounts[i+1] 日的成交额
    r = returns
    a = amounts[1:]
    valid = (a > 0) & ~np.isnan(r) & ~np.isinf(r)
    if np.sum(valid) < 5:
        return None
    illiq = r[valid] / a[valid]
    return float(np.mean(illiq) * 1e6)


def calc_vpc(klines: List[Dict], period: int = 20) -> Optional[float]:
    if len(klines) < period + 1:
        return None
    closes = np.array([float(k['close']) for k in klines[:period + 1]])
    volumes = np.array([float(k.get('amount', 0) or 0) for k in klines[:period + 1]])
    returns = np.diff(closes) / closes[:-1]
    vol = volumes[:-1]
    valid = ~np.isnan(returns) & ~np.isnan(vol) & (vol > 0)
    if np.sum(valid) < 10:
        return None
    corr = np.corrcoef(returns[valid], vol[valid])[0, 1]
    return float(corr)


def calc_obv_divergence(klines: List[Dict], period: int = 20) -> Optional[float]:
    if len(klines) < period + 1:
        return None
    closes = np.array([float(k['close']) for k in klines[:period + 1]])
    amounts = np.array([float(k.get('amount', 0) or 0) for k in klines[:period + 1]])

    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + amounts[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - amounts[i]
        else:
            obv[i] = obv[i - 1]

    x = np.arange(period)
    slope_obv = np.polyfit(x, obv[-period:], 1)[0]
    slope_price = np.polyfit(x, closes[-period:], 1)[0]
    if abs(slope_price) < 1e-6:
        return 0.0
    return float(slope_obv / abs(slope_price) - np.sign(slope_price))


def batch_kline_factors(codes: List[str],
                        kline_map: Dict[str, List[Dict]]
                        ) -> Dict[str, Dict[str, float]]:
    result = {}
    for code in codes:
        klines = kline_map.get(code, [])
        if len(klines) < 20:
            result[code] = {}
            continue

        factors = {}
        atr = calc_atr(klines)
        if atr is not None:
            factors['atr'] = atr

        rev5 = calc_short_term_reversal(klines)
        if rev5 is not None:
            factors['reversal_5d'] = rev5
        rev20 = calc_medium_term_reversal(klines)
        if rev20 is not None:
            factors['reversal_20d'] = rev20

        illiq = calc_amihud_illiq(klines)
        if illiq is not None:
            factors['amihud_illiq'] = illiq
        vpc = calc_vpc(klines)
        if vpc is not None:
            factors['vpc'] = vpc
        obv = calc_obv_divergence(klines)
        if obv is not None:
            factors['obv_divergence'] = obv

        closes = [float(k['close']) for k in klines]
        returns = []
        for i in range(len(closes) - 1):
            if closes[i + 1] > 0:
                returns.append((closes[i] - closes[i + 1]) / closes[i + 1])
        dv = calc_downside_vol(returns)
        if dv is not None:
            factors['downside_vol'] = dv

        result[code] = factors
    return result
