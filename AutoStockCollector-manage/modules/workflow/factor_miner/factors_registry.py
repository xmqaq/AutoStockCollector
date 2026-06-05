"""注册所有内置因子到 FactorRegistry，保持与原有 batch_*_factors 兼容。"""

from typing import List, Dict, Optional
from .base import Factor, FactorMeta, FactorRegistry, DataStore


# ─────────── 技术面因子 ───────────

class ATRFactor(Factor):
    meta = FactorMeta(name='atr', inverse=True, group='技术面',
                      description='平均真实波幅，高波动不利')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_atr
        klines = _k(store, 'kline_map', code, 21)
        return calc_atr(klines) if klines else None

class Reversal5dFactor(Factor):
    meta = FactorMeta(name='reversal_5d', inverse=True, group='技术面',
                      description='5日反转（短周期均值回复）')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_short_term_reversal
        klines = _k(store, 'kline_map', code, 6)
        return calc_short_term_reversal(klines) if klines else None

class Reversal20dFactor(Factor):
    meta = FactorMeta(name='reversal_20d', inverse=True, group='技术面',
                      description='20日反转（中周期均值回复）')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_medium_term_reversal
        klines = _k(store, 'kline_map', code, 21)
        return calc_medium_term_reversal(klines) if klines else None

class AmihudIlliqFactor(Factor):
    meta = FactorMeta(name='amihud_illiq', inverse=True, group='技术面',
                      description='Amihud非流动性指标，流动性差不利')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_amihud_illiq
        klines = _k(store, 'kline_map', code, 21)
        return calc_amihud_illiq(klines) if klines else None

class VPCFactor(Factor):
    meta = FactorMeta(name='vpc', inverse=False, group='技术面',
                      description='量价相关性，正相关=趋势健康')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_vpc
        klines = _k(store, 'kline_map', code, 21)
        return calc_vpc(klines) if klines else None

class OBVDivergenceFactor(Factor):
    meta = FactorMeta(name='obv_divergence', inverse=False, group='技术面',
                      description='OBV背离，正=量价背离买点')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_obv_divergence
        klines = _k(store, 'kline_map', code, 21)
        return calc_obv_divergence(klines) if klines else None

class DownsideVolFactor(Factor):
    meta = FactorMeta(name='downside_vol', inverse=True, group='技术面',
                      description='下行波动率，高下跌波动不利')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_kline import calc_downside_vol
        klines = _k(store, 'kline_map', code, 21)
        if not klines:
            return None
        closes = [float(k['close']) for k in klines]
        returns = []
        for i in range(len(closes) - 1):
            if closes[i + 1] > 0:
                returns.append((closes[i] - closes[i + 1]) / closes[i + 1])
        return calc_downside_vol(returns)


# ─────────── 资金面因子 ───────────

class MarginChangeFactor(Factor):
    meta = FactorMeta(name='margin_change_5d', inverse=False, group='资金面',
                      description='融资余额5日变化，增加=看多')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_margin import calc_margin_change
        records = _d(store, 'margin_map', code)
        return calc_margin_change(records) if records else None

class ShortRatioFactor(Factor):
    meta = FactorMeta(name='short_ratio', inverse=True, group='资金面',
                      description='融券占比，高=看空')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_margin import calc_short_ratio
        records = _d(store, 'margin_map', code)
        return calc_short_ratio(records) if records else None

class MarginTrendFactor(Factor):
    meta = FactorMeta(name='margin_trend', inverse=False, group='资金面',
                      description='融资趋势，持续增加=强势信号')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_margin import calc_margin_trend
        records = _d(store, 'margin_map', code)
        return calc_margin_trend(records) if records else None

class InflowIntensityFactor(Factor):
    meta = FactorMeta(name='inflow_intensity', inverse=False, group='资金面',
                      description='主力净流入强度，越高越好')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_fund_flow import calc_net_inflow_intensity
        records = _d(store, 'fund_flow_map', code)
        return calc_net_inflow_intensity(records) if records else None

class InflowConsecutiveFactor(Factor):
    meta = FactorMeta(name='inflow_consecutive', inverse=False, group='资金面',
                      description='连续净流入天数')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_fund_flow import calc_consecutive_inflow_days
        records = _d(store, 'fund_flow_map', code)
        return calc_consecutive_inflow_days(records) if records else None

class InflowVolatilityFactor(Factor):
    meta = FactorMeta(name='inflow_volatility', inverse=True, group='资金面',
                      description='主力资金流入波动，稳定更好')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_fund_flow import calc_inflow_volatility
        records = _d(store, 'fund_flow_map', code)
        return calc_inflow_volatility(records) if records else None


# ─────────── 情绪面因子 ───────────

class DragonNetBuyFactor(Factor):
    meta = FactorMeta(name='dragon_net_buy_intensity', inverse=False, group='情绪面',
                      description='龙虎榜净买入强度')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_dragon import calc_net_buy_intensity
        records = _d(store, 'dragon_map', code)
        cap = _cap(store, code)
        return calc_net_buy_intensity(records, cap) if records else None

class DragonFrequencyFactor(Factor):
    meta = FactorMeta(name='dragon_frequency', inverse=False, group='情绪面',
                      description='龙虎榜上榜频率')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_dragon import calc_dragon_frequency
        records = _d(store, 'dragon_map', code)
        return calc_dragon_frequency(records) if records else None

class DragonInstRatioFactor(Factor):
    meta = FactorMeta(name='dragon_institutional_ratio', inverse=False, group='情绪面',
                      description='龙虎榜机构买入占比')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_dragon import calc_institutional_ratio
        records = _d(store, 'dragon_map', code)
        return calc_institutional_ratio(records) if records else None

class SentimentAvgFactor(Factor):
    meta = FactorMeta(name='sentiment_avg', inverse=False, group='情绪面',
                      description='平均情感分')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_sentiment import calc_sentiment_avg
        records = _d(store, 'news_map', code)
        return calc_sentiment_avg(records) if records else None

class NewsHeatFactor(Factor):
    meta = FactorMeta(name='news_heat', inverse=False, group='情绪面',
                      description='新闻热度（近期新闻量）')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_sentiment import calc_news_heat
        records = _d(store, 'news_map', code)
        return calc_news_heat(records) if records else None

class SentimentTrendFactor(Factor):
    meta = FactorMeta(name='sentiment_trend', inverse=False, group='情绪面',
                      description='情感趋势（最新-平均）')
    def compute(self, code: str, store: DataStore) -> Optional[float]:
        from .factors_sentiment import calc_sentiment_trend
        records = _d(store, 'news_map', code)
        return calc_sentiment_trend(records) if records else None


# ─────────── 辅助 ───────────

def _k(store: DataStore, attr: str, code: str, min_len: int) -> List:
    data = getattr(store, attr, {}).get(code, [])
    return data if len(data) >= min_len else []

def _d(store: DataStore, attr: str, code: str) -> List:
    return getattr(store, attr, {}).get(code, [])

def _cap(store: DataStore, code: str) -> float:
    return getattr(store, 'market_caps', {}).get(code, 0)


# ─────────── 注册 ───────────

_INTERNAL_FACTORS = [
    ATRFactor, Reversal5dFactor, Reversal20dFactor,
    AmihudIlliqFactor, VPCFactor, OBVDivergenceFactor, DownsideVolFactor,
    MarginChangeFactor, ShortRatioFactor, MarginTrendFactor,
    InflowIntensityFactor, InflowConsecutiveFactor, InflowVolatilityFactor,
    DragonNetBuyFactor, DragonFrequencyFactor, DragonInstRatioFactor,
    SentimentAvgFactor, NewsHeatFactor, SentimentTrendFactor,
]


def register_all():
    for cls in _INTERNAL_FACTORS:
        FactorRegistry.register(cls)


def unregister_all():
    for cls in _INTERNAL_FACTORS:
        name = cls().meta.name
        if name in FactorRegistry._factors:
            del FactorRegistry._factors[name]
            FactorRegistry._weights.pop(name, None)
