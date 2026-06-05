from .normalizer import zscore, percentile_rank, industry_neutral_rank, winsorize, combine_scores
from .factory import FactorMiner
from .factors_kline import (
    calc_atr, calc_beta, calc_downside_vol,
    calc_short_term_reversal, calc_medium_term_reversal,
    calc_amihud_illiq, calc_vpc, calc_obv_divergence,
    batch_kline_factors,
)
from .factors_margin import calc_margin_change, calc_short_ratio, calc_margin_trend, batch_margin_factors
from .factors_dragon import calc_dragon_net_buy_intensity, calc_dragon_frequency, calc_dragon_institutional_ratio, batch_dragon_factors
from .factors_sentiment import calc_avg_sentiment, calc_news_heat, calc_sentiment_trend, batch_sentiment_factors
from .ictest import (
    compute_single_ic, compute_full_ic, compute_multi_period_ic,
    rank_factors_by_ic,
)
from .optimizer import FactorWeightLearner, learn_weights_from_ic
from .pca_synthesis import PCASynthesizer, auto_select_n_components
from .cache_service import FactorCacheService, _FACTOR_FIELDS
from .cache_updater import FactorCacheUpdater

# ── 因子平台（注册中心 + 引擎 + 回测）──
from .base import Factor, FactorMeta, FactorRegistry, DataStore, register
from .engine import FactorEngine
from .backtest import BacktestEngine, ICResult
from .factors_registry import register_all, unregister_all

register_all()  # 自动注册所有内置因子
