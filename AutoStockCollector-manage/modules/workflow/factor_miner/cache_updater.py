"""因子缓存更新器：批量预计算所有股票的最新因子值并写入缓存。"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from config.database import DatabaseConfig
from utils.logger import get_logger

from .cache_service import FactorCacheService
from .factory import FactorMiner

logger = get_logger(__name__)


class FactorCacheUpdater:
    """批量预计算因子值并写入缓存，供工作流执行时快速读取。"""

    def __init__(self, kline_days: int = 30):
        self.kline_days = kline_days
        self.cache = FactorCacheService()
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = DatabaseConfig.get_database()
        return self._db

    def _load_raw_data(self) -> dict:
        """加载计算因子所需的全部原始数据（类似 _step1_load_data 的逻辑）。"""
        codes_in = []

        logger.info("Loading stock_info...")
        stock_info = {}
        cursor = self.db['stock_info'].find({}, {
            'code': 1, 'name': 1, '总市值': 1, 'total_mv': 1,
            'market_cap': 1, '所属行业': 1, '_id': 0
        })
        for r in cursor:
            c = r.get('code')
            if c:
                r['name'] = r.get('name') or ''
                stock_info[c] = r
                codes_in.append(c)
        logger.info(f"Loaded {len(stock_info)} stock_info")

        logger.info("Loading financial data...")
        financial_data = defaultdict(list)
        cursor = self.db['financial'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'report_date': 1,
             '净资产收益率': 1, '营业总收入': 1, '净利润': 1,
             '资产负债率': 1, '销售毛利率': 1, '_id': 0}
        ).sort('report_date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(financial_data[c]) < 4:
                financial_data[c].append(r)

        logger.info(f"Loading kline ({self.kline_days}d, {len(codes_in)} stocks)...")
        cutoff = datetime.now() - timedelta(days=self.kline_days)
        kline_data = defaultdict(list)

        # 分批查询 kline 避免 $in 超长
        # 使用 $expr 绕过远程 MongoDB $gte 查询计划损坏的问题
        batch_size = 1000
        for i in range(0, len(codes_in), batch_size):
            batch_codes = codes_in[i:i + batch_size]
            cursor = self.db['kline'].find(
                {'code': {'$in': batch_codes}, '$expr': {'$gte': ['$date', cutoff]}},
                {'code': 1, 'date': 1, 'close': 1, 'volume': 1,
                 'high': 1, 'low': 1, 'open': 1, '_id': 0}
            ).sort('date', 1)
            for r in cursor:
                c = r.get('code')
                if c:
                    kline_data[c].append(r)
            logger.info(f"  kline batch {i // batch_size + 1}/{(len(codes_in) + batch_size - 1) // batch_size}: "
                        f"{sum(1 for v in kline_data.values() if any(True for _ in v))} stocks so far")
        logger.info(f"Loaded kline data: {sum(len(v) for v in kline_data.values())} records")

        logger.info("Loading fund_flow...")
        fund_flow_data = defaultdict(list)
        cursor = self.db['fund_flow'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1,
             'main_net_inflow': 1, 'total_amount': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(fund_flow_data[c]) < 5:
                fund_flow_data[c].append(r)

        logger.info("Loading fund_flow...")
        fund_flow_data = defaultdict(list)
        cursor = self.db['fund_flow'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1, 'main_net_inflow': 1, 'total_amount': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(fund_flow_data[c]) < 5:
                fund_flow_data[c].append(r)

        logger.info("Loading margin data...")
        margin_data = defaultdict(list)
        cursor = self.db['margin_data'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1, 'margin_balance': 1, 'short_balance': 1,
             'margin_buy': 1, 'margin_repay': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(margin_data[c]) < 20:
                margin_data[c].append(r)

        logger.info("Loading dragon_tiger...")
        dragon_data = defaultdict(list)
        cursor = self.db['dragon_tiger'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1, '龙虎榜净买': 1, '买入额': 1, '卖出额': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(dragon_data[c]) < 10:
                dragon_data[c].append(r)

        logger.info("Loading news...")
        news_data = defaultdict(list)
        cursor = self.db['news'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'publish_date': 1, 'sentiment': 1, '_id': 0}
        ).sort('publish_date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(news_data[c]) < 5:
                news_data[c].append(r)

        return {
            'stock_info': stock_info,
            'codes_in': codes_in,
            'financial_data': financial_data,
            'kline_data': kline_data,
            'fund_flow_data': fund_flow_data,
            'margin_data': margin_data,
            'dragon_data': dragon_data,
            'news_data': news_data,
        }

    def update_all(self, progress_callback=None) -> Dict[str, int]:
        """全量更新所有股票的因子缓存。

        Returns:
            {'saved': 写入数, 'failed': 失败数, 'total': 总股票数}
        """
        start = datetime.now()
        self.cache.ensure_index()

        raw = self._load_raw_data()
        stock_info = raw['stock_info']
        codes_in = raw['codes_in']
        financial_data = raw['financial_data']
        kline_data = raw['kline_data']
        fund_flow_data = raw['fund_flow_data']
        margin_data = raw['margin_data']
        dragon_data = raw['dragon_data']
        news_data = raw['news_data']

        total = len(codes_in)
        logger.info(f"Computing factors for {total} stocks...")

        # 构建 miners 需要的 industries / market_caps
        industries = {}
        market_caps = {}
        for code in codes_in:
            info = stock_info.get(code, {})
            industries[code] = info.get('所属行业', '') or '未知'
            raw_cap = (info.get('总市值') or info.get('total_mv') or 0)
            try:
                market_caps[code] = float(str(raw_cap).replace(',', ''))
            except (ValueError, TypeError):
                market_caps[code] = 0

        # 因子挖掘（不含基本面/估值，引擎内部已独立计算）
        miner = FactorMiner(industries=industries, market_caps=market_caps)
        mining_scores = miner.mine_all(
            codes_in, kline_data, margin_data, dragon_data,
            news_data, fund_flow_data,
        )

        composite = FactorMiner.composite_mining_score(mining_scores, codes_in)

        factors_map = {}
        for code in codes_in:
            factors = dict(mining_scores.get(code, {}))
            factors['mining_composite'] = composite.get(code, 50.0)
            factors_map[code] = factors

        saved = self.cache.save_cache(factors_map)
        duration = (datetime.now() - start).total_seconds()

        logger.info(
            f"Factor cache update complete: {saved}/{total} saved "
            f"in {duration:.1f}s"
        )
        return {'saved': saved, 'failed': total - saved, 'total': total}
