"""因子缓存服务：将预计算的因子值存入 MongoDB，工作流执行时直接读缓存。"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from collections import defaultdict
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)

CACHE_COLLECTION = 'factor_cache'

_FACTOR_FIELDS = [
    'atr', 'reversal_5d', 'reversal_20d', 'amihud_illiq',
    'vpc', 'obv_divergence', 'downside_vol',
    'margin_change_5d', 'short_ratio', 'margin_trend',
    'dragon_net_buy_intensity', 'dragon_frequency', 'dragon_institutional_ratio',
    'sentiment_avg', 'news_heat', 'sentiment_trend',
    'inflow_intensity', 'inflow_consecutive', 'inflow_volatility',
    'mining_composite',
]


class FactorCacheService:
    """因子缓存读写服务。"""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = DatabaseConfig.get_database()
        return self._db

    def get_cache(self, codes: List[str],
                  max_age_hours: int = 24) -> Dict[str, Dict[str, float]]:
        """批量读取缓存。返回 {code: {factor_name: value}}。

        Args:
            codes: 股票代码列表
            max_age_hours: 缓存有效期（小时），超过此时间的视为过期
        Returns:
            缓存命中数据（仅有缓存的股票和因子）
        """
        cutoff = beijing_now() - timedelta(hours=max_age_hours)
        cursor = self.db[CACHE_COLLECTION].find(
            {
                'code': {'$in': codes},
                'computed_at': {'$gte': cutoff},
            },
            {'_id': 0}
        )
        result = {}
        for doc in cursor:
            code = doc.get('code', '')
            if not code:
                continue
            factors = {}
            for fname in _FACTOR_FIELDS:
                v = doc.get(fname)
                if v is not None:
                    factors[fname] = float(v)
            if factors:
                result[code] = factors
        return result

    def save_cache(self, factors_map: Dict[str, Dict[str, float]],
                   batch_size: int = 500) -> int:
        """批量写入缓存（upsert）。

        Args:
            factors_map: {code: {factor_name: value}}
            batch_size: 每批写入数量
        Returns:
            写入/更新的记录数
        """
        now = beijing_now()
        ops = []
        for code, factors in factors_map.items():
            doc = {
                'code': code,
                'computed_at': now,
                'date': now.strftime('%Y-%m-%d'),
            }
            doc.update(factors)
            ops.append(doc)

        saved = 0
        for i in range(0, len(ops), batch_size):
            batch = ops[i:i + batch_size]
            try:
                for doc in batch:
                    self.db[CACHE_COLLECTION].update_one(
                        {'code': doc['code']},
                        {'$set': doc},
                        upsert=True,
                    )
                saved += len(batch)
            except Exception as e:
                logger.error(f"Cache save batch error at offset {i}: {e}")
        logger.info(f"Factor cache: saved {saved}/{len(ops)} records")
        return saved

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。"""
        total = self.db[CACHE_COLLECTION].count_documents({})
        latest = self.db[CACHE_COLLECTION].find_one(
            {}, sort=[('computed_at', -1)]
        )
        latest_time = latest.get('computed_at') if latest else None
        return {
            'total_cached': total,
            'latest_update': latest_time,
            'factor_count': len(_FACTOR_FIELDS),
            'stale_hours': (
                (beijing_now() - latest_time).total_seconds() / 3600
                if latest_time else None
            ),
        }

    def get_cache_by_code(self, code: str,
                          max_age_hours: int = 24) -> Optional[Dict[str, float]]:
        """读取单只股票的缓存。"""
        result = self.get_cache([code], max_age_hours)
        return result.get(code)

    def clear_cache(self, older_than_days: int = 7) -> int:
        """清理过期缓存。"""
        cutoff = beijing_now() - timedelta(days=older_than_days)
        result = self.db[CACHE_COLLECTION].delete_many(
            {'computed_at': {'$lt': cutoff}}
        )
        logger.info(f"Cleared {result.deleted_count} stale cache entries")
        return result.deleted_count

    def ensure_index(self):
        """确保索引存在。"""
        self.db[CACHE_COLLECTION].create_index('code', unique=True)
        self.db[CACHE_COLLECTION].create_index('computed_at')
        logger.info("Factor cache indexes ensured")
