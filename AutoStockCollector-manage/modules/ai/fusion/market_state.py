"""市场环境感知。用上证指数 K 线判断牛/熊/震荡，据此选因子权重。

权重优先读 fusion_weight_config（被 WeightOptimizer 回测优化过的），
否则回退到静态 WEIGHT_PRESETS。detect() 结果缓存 30 分钟（模块级）。
"""
from datetime import timedelta
from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)

# 上证指数在 kline 集合里的 code（大小写两种存法都试，见 reflection/evaluator.py）
_INDEX_CODES = ("SH000001", "sh000001")
_CACHE_TTL_MINUTES = 30

# 模块级缓存（按 detect 调用共享，进程内 30 分钟有效）
_cache_state = None
_cache_time = None


class MarketStateDetector:
    WEIGHT_PRESETS = {
        "bull":     {"fundamental": 0.25, "technical": 0.35,
                     "fund_flow": 0.30, "valuation": 0.10},
        "bear":     {"fundamental": 0.45, "technical": 0.10,
                     "fund_flow": 0.15, "valuation": 0.30},
        "volatile": {"fundamental": 0.35, "technical": 0.25,
                     "fund_flow": 0.20, "valuation": 0.20},
    }

    def detect(self) -> str:
        global _cache_state, _cache_time
        if (_cache_state is not None and _cache_time is not None
                and beijing_now() - _cache_time < timedelta(minutes=_CACHE_TTL_MINUTES)):
            return _cache_state
        state = self._detect_uncached()
        _cache_state, _cache_time = state, beijing_now()
        return state

    def _detect_uncached(self) -> str:
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            klines = []
            for code in _INDEX_CODES:
                klines = list(db["kline"].find(
                    {"code": code}, {"_id": 0, "date": 1, "close": 1},
                ).sort("date", -1).limit(80))
                if klines:
                    break
            # 倒序（新→旧）
            closes = [float(k.get("close") or 0) for k in klines if k.get("close")]
            if len(closes) < 60:
                return "volatile"
            cur = closes[0]
            ma20 = sum(closes[:20]) / 20
            ma60 = sum(closes[:60]) / 60
            if len(closes) > 20 and closes[20] > 0:
                ret20 = (cur - closes[20]) / closes[20] * 100
            else:
                ret20 = 0.0
            if cur > ma20 > ma60 and ret20 > 5:
                return "bull"
            if cur < ma20 < ma60 and ret20 < -5:
                return "bear"
            return "volatile"
        except Exception as e:
            logger.warning(f"[fusion] 市场状态检测失败，回退 volatile: {e}")
            return "volatile"

    def get_weights(self, state: str) -> dict:
        """优先读被 WeightOptimizer 更新过的权重，否则用静态预设。"""
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            doc = db["fusion_weight_config"].find_one({"state": state})
            if doc and doc.get("weights"):
                w = doc["weights"]
                if all(k in w for k in ("fundamental", "technical", "fund_flow", "valuation")):
                    return {k: float(w[k]) for k in ("fundamental", "technical", "fund_flow", "valuation")}
        except Exception:
            pass
        return dict(self.WEIGHT_PRESETS.get(state, self.WEIGHT_PRESETS["volatile"]))

    def get_description(self, state: str) -> str:
        return {
            "bull": "牛市（趋势主导，技术面和资金面权重上调）",
            "bear": "熊市（防御为主，基本面和估值权重上调）",
            "volatile": "震荡市（均衡配置）",
        }.get(state, "震荡市（均衡配置）")
