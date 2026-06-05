"""
量化多因子选股执行引擎 - 七步流程

步骤1 初始化股票池  → 批量加载全部数据到内存
步骤2 硬性条件过滤  → 排除ST/新股/低市值（纯内存）
步骤3 基本面评分    → ROE/营收增速/净利润增速/负债率（权重30%）
步骤4 技术面评分    → 均线/MACD/RSI/量能趋势（权重25%）
步骤5 资金面评分    → 主力净流入/连续净入/流入占比（权重20%）
步骤6 估值面评分    → PE/PB/行业调整（权重15%）
步骤7 汇总排名输出  → 综合评分排序，输出Top30
"""
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, str, str, float, Optional[Dict[str, Any]]], None]


class QuantMultiFactorExecutor:
    def __init__(
        self,
        workflow_id: str,
        execution_id: str = "",
        progress_callback: Optional[ProgressCallback] = None,
        mining_weight: float = 0.20,
    ):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.progress_callback = progress_callback
        self.mining_weight = mining_weight

        self.stock_info: Dict[str, Dict] = {}
        self.financial_data: Dict[str, List[Dict]] = defaultdict(list)
        self.kline_data: Dict[str, List[Dict]] = defaultdict(list)
        self.fund_flow_data: Dict[str, List[Dict]] = defaultdict(list)
        self.margin_data: Dict[str, List[Dict]] = defaultdict(list)
        self.dragon_data: Dict[str, List[Dict]] = defaultdict(list)
        self.news_data: Dict[str, List[Dict]] = defaultdict(list)

        self.total_analyzed = 0
        self.after_filter = 0

    # ------------------------------------------------------------------ #
    # Progress helpers
    # ------------------------------------------------------------------ #

    def _report(self, node_id: str, label: str, step: str, progress: float, detail: Optional[Dict] = None):
        progress = min(100.0, max(0.0, progress))
        if self.progress_callback:
            try:
                self.progress_callback(node_id, label, step, progress, detail)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def execute(self) -> Dict[str, Any]:
        logger.info(f"QuantMultiFactorExecutor starting for workflow {self.workflow_id}")
        start_time = datetime.now()

        try:
            # --- Step 1 ---
            self._report("step1", "初始化股票池", "批量加载数据到内存...", 2)
            self._step1_load_data()
            self.total_analyzed = len(self.stock_info)
            self._report("step1", "初始化股票池", f"已加载 {self.total_analyzed} 只股票", 15)

            # --- Step 2 ---
            self._report("step2", "硬性条件过滤", "过滤ST / 新股 / 低市值...", 17)
            valid_codes = self._step2_hard_filter()
            self.after_filter = len(valid_codes)
            self._report("step2", "硬性条件过滤", f"过滤后剩余 {self.after_filter} 只进入评分", 25)

            # --- Step 2.5 — 因子挖掘（新增） ---
            self._report("step2_5", "因子挖掘", "计算波动率/反转/量价/融资融券/龙虎榜/情感因子...", 25)
            mining_scores = self._step2_5_factor_mining(valid_codes)
            self._report("step2_5", "因子挖掘", "因子挖掘完成", 27)

            # --- Step 3 ---
            self._report("step3", "基本面评分", "计算ROE / 营收 / 净利润 / 负债率...", 28)
            fundamental_scores = self._step3_fundamental_scoring(valid_codes)
            self._report("step3", "基本面评分", "基本面评分完成", 40)

            # --- Step 4 ---
            self._report("step4", "技术面评分", "计算均线 / MACD / RSI / 量能...", 42)
            technical_scores = self._step4_technical_scoring(valid_codes)
            self._report("step4", "技术面评分", "技术面评分完成", 60)

            # --- Step 5 ---
            self._report("step5", "资金面评分", "计算主力净流入...", 62)
            fund_flow_scores = self._step5_fund_flow_scoring(valid_codes)
            self._report("step5", "资金面评分", "资金面评分完成", 72)

            # --- Step 6 ---
            self._report("step6", "估值面评分", "计算PE / PB / 行业调整...", 74)
            valuation_scores = self._step6_valuation_scoring(valid_codes)
            self._report("step6", "估值面评分", "估值面评分完成", 82)

            # --- Step 7 ---
            self._report("step7", "汇总排名输出", "计算综合评分并排名...", 84)
            results = self._step7_aggregate(
                valid_codes, fundamental_scores, technical_scores,
                fund_flow_scores, valuation_scores, mining_scores
            )
            self._report("step7", "汇总排名输出", f"Top30筛选完成，共分析 {self.total_analyzed} 只", 100)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"QuantMultiFactorExecutor finished in {duration:.1f}s, top30 selected from {self.after_filter} stocks")
            return {
                "success": True,
                "workflow_id": self.workflow_id,
                "result_type": "quant_multi_factor",
                "result_count": len(results),
                "duration": duration,
                "results": results,
                "execution_time": datetime.now().isoformat(),
                "total_analyzed": self.total_analyzed,
                "after_filter": self.after_filter,
            }

        except Exception as e:
            import traceback
            logger.error(f"QuantMultiFactorExecutor error: {e}\n{traceback.format_exc()}")
            duration = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "workflow_id": self.workflow_id,
                "error": str(e),
                "duration": duration,
                "execution_time": datetime.now().isoformat(),
            }

    # ------------------------------------------------------------------ #
    # Step 1 – Bulk data load
    # ------------------------------------------------------------------ #

    def _step1_load_data(self):
        db = DatabaseConfig.get_database()

        # 1. Stock basic info
        cursor = db['stock_info'].find({}, {
            'code': 1, 'name': 1, 'A股简称': 1, '证券简称': 1,
            '总市值': 1, '流通市值': 1,
            '市盈率-动态': 1, '市净率': 1,
            '上市时间': 1, '上市日期': 1, '所属行业': 1,
            'pe': 1, 'pb': 1, 'total_mv': 1, 'market_cap': 1,
            '_id': 0
        })
        for r in cursor:
            code = r.get('code')
            if code:
                r['name'] = r.get('name') or r.get('A股简称') or r.get('证券简称') or ''
                self.stock_info[code] = r
        logger.info(f"Step1: loaded {len(self.stock_info)} stock_info records")
        self._report("step1", "初始化股票池", f"已加载 {len(self.stock_info)} 只股票基础信息", 4)

        # 2. Financial data – latest 4 quarters per code
        self.financial_data = defaultdict(list)
        cursor = db['financial'].find({}, {
            'code': 1, 'report_date': 1,
            '净资产收益率': 1, '营业总收入': 1, '净利润': 1,
            '资产负债率': 1, '销售毛利率': 1,
            '_id': 0
        }).sort('report_date', -1)
        for r in cursor:
            code = r.get('code')
            if code and len(self.financial_data[code]) < 4:
                self.financial_data[code].append(r)
        total_fin = sum(len(v) for v in self.financial_data.values())
        logger.info(f"Step1: loaded {total_fin} financial records for {len(self.financial_data)} stocks")
        self._report("step1", "初始化股票池", f"已加载 {total_fin} 条财务数据（最近4季度）", 7)

        # 3. Kline – recent 90 days, sorted ascending
        cutoff = datetime.now() - timedelta(days=90)
        self.kline_data = defaultdict(list)
        cursor = db['kline'].find(
            {'$expr': {'$gte': ['$date', cutoff]}},
            {'code': 1, 'date': 1, 'close': 1, 'volume': 1,
             'high': 1, 'low': 1, 'open': 1, '_id': 0}
        ).sort('date', 1)
        for r in cursor:
            code = r.get('code')
            if code:
                self.kline_data[code].append(r)
        total_kline = sum(len(v) for v in self.kline_data.values())
        logger.info(f"Step1: loaded {total_kline} kline records")
        self._report("step1", "初始化股票池", f"已加载 {total_kline} 条K线数据（最近90日）", 10)

        # 4. Fund flow – latest 5 days per code, sorted desc
        self.fund_flow_data = defaultdict(list)
        cursor = db['fund_flow'].find({}, {
            'code': 1, 'date': 1,
            'main_net_inflow': 1, 'total_amount': 1,
            '_id': 0
        }).sort('date', -1)
        for r in cursor:
            code = r.get('code')
            if code and len(self.fund_flow_data[code]) < 5:
                self.fund_flow_data[code].append(r)
        total_flow = sum(len(v) for v in self.fund_flow_data.values())
        logger.info(f"Step1: loaded {total_flow} fund_flow records")
        self._report("step1", "初始化股票池", f"已加载 {total_flow} 条资金流向数据", 13)

        # 5. Margin data – latest 20 per code
        codes_in = list(self.stock_info.keys())
        self.margin_data = defaultdict(list)
        cursor = db['margin_data'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1, 'margin_balance': 1, 'short_balance': 1,
             'margin_buy': 1, 'margin_repay': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(self.margin_data[c]) < 20:
                self.margin_data[c].append(r)
        total_margin = sum(len(v) for v in self.margin_data.values())
        logger.info(f"Step1: loaded {total_margin} margin records")

        # 6. Dragon-tiger data – latest 10 per code
        self.dragon_data = defaultdict(list)
        cursor = db['dragon_tiger'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'date': 1, '龙虎榜净买': 1, '买入额': 1, '卖出额': 1, '_id': 0}
        ).sort('date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(self.dragon_data[c]) < 10:
                self.dragon_data[c].append(r)
        total_dragon = sum(len(v) for v in self.dragon_data.values())
        logger.info(f"Step1: loaded {total_dragon} dragon_tiger records")

        # 7. News sentiment – latest 5 per code
        self.news_data = defaultdict(list)
        cursor = db['news'].find(
            {'code': {'$in': codes_in}},
            {'code': 1, 'publish_date': 1, 'sentiment': 1, '_id': 0}
        ).sort('publish_date', -1)
        for r in cursor:
            c = r.get('code')
            if c and len(self.news_data[c]) < 5:
                self.news_data[c].append(r)
        total_news = sum(len(v) for v in self.news_data.values())
        logger.info(f"Step1: loaded {total_news} news records")
        self._report("step1", "初始化股票池", "额外数据加载完成（融资融券/龙虎榜/新闻）", 15)


    # ------------------------------------------------------------------ #
    # Step 2 – Hard filter (in-memory)
    # ------------------------------------------------------------------ #

    def _step2_hard_filter(self) -> List[str]:
        today = datetime.now().date()
        ipo_cutoff = today - timedelta(days=180)
        st_excluded = ipo_excluded = cap_excluded = 0
        valid: List[str] = []

        for code, info in self.stock_info.items():
            name = info.get('name', '') or ''

            # Condition 1: ST
            if 'ST' in name:
                st_excluded += 1
                continue

            # Condition 2: Listed < 180 days
            list_date_raw = info.get('上市时间') or info.get('上市日期') or ''
            if list_date_raw:
                try:
                    s = str(list_date_raw).replace('-', '').replace('/', '').strip()
                    if len(s) >= 8:
                        list_date = datetime.strptime(s[:8], '%Y%m%d').date()
                        if list_date > ipo_cutoff:
                            ipo_excluded += 1
                            continue
                except (ValueError, TypeError):
                    pass  # unparseable → keep

            # Condition 3: Total market cap < 20 億
            raw_cap = (info.get('总市值') or info.get('total_mv') or
                       info.get('market_cap') or info.get('流通市值') or None)
            if raw_cap is not None:
                try:
                    cap = float(str(raw_cap).replace(',', ''))
                    if 0 < cap < 20e8:
                        cap_excluded += 1
                        continue
                except (ValueError, TypeError):
                    pass  # unparseable → keep

            valid.append(code)

        logger.info(f"Step2: ST={st_excluded}, IPO={ipo_excluded}, cap={cap_excluded}, valid={len(valid)}")
        self._report("step2", "硬性条件过滤", f"ST过滤：排除 {st_excluded} 只", 18)
        self._report("step2", "硬性条件过滤", f"新股过滤：排除 {ipo_excluded} 只（上市不足180天）", 19)
        self._report("step2", "硬性条件过滤", f"市值过滤：排除 {cap_excluded} 只（总市值<20亿）", 21)
        self._report("step2", "硬性条件过滤", f"过滤后剩余：{len(valid)} 只股票进入评分阶段", 23)
        return valid

    # ------------------------------------------------------------------ #
    # Step 2.5 – Factor mining（替代人工特征工程）
    # ------------------------------------------------------------------ #

    def _step2_5_factor_mining(self, codes: List[str]) -> Dict[str, float]:
        from .factor_miner import FactorMiner, FactorCacheService

        # 优先读缓存
        cache = FactorCacheService()
        cached = cache.get_cache(codes, max_age_hours=24)
        hit_rate = len(cached) / max(len(codes), 1)

        if hit_rate >= 0.8:
            composite = FactorMiner.composite_mining_score(
                {c: cached.get(c, {}) for c in codes}, codes
            )
            logger.info(f"Factor mining: cache hit {len(cached)}/{len(codes)} ({hit_rate:.0%}), using cached")
            return composite

        logger.info(f"Factor mining: cache hit {len(cached)}/{len(codes)} ({hit_rate:.0%}), computing live...")

        industries = {}
        market_caps = {}
        for code in codes:
            info = self.stock_info.get(code, {})
            industries[code] = info.get('所属行业', '') or '未知'
            raw_cap = (info.get('总市值') or info.get('total_mv') or 0)
            try:
                market_caps[code] = float(str(raw_cap).replace(',', ''))
            except (ValueError, TypeError):
                market_caps[code] = 0

        miner = FactorMiner(industries=industries, market_caps=market_caps)

        fundamental_values = {c: self._calc_fundamental(self.financial_data.get(c, [])) for c in codes}
        valuation_values = {c: self._calc_valuation(self.stock_info.get(c, {})) for c in codes}

        mining_scores = miner.mine_all(
            codes,
            self.kline_data,
            self.margin_data,
            self.dragon_data,
            self.news_data,
            self.fund_flow_data,
            fundamental_values,
            valuation_values,
        )
        composite = FactorMiner.composite_mining_score(mining_scores, codes)

        logger.info(f"Factor mining done for {len(codes)} stocks, "
                    f"score range: {min(composite.values()):.1f}~{max(composite.values()):.1f}")
        return composite

    # ------------------------------------------------------------------ #
    # Step 3 – Fundamental scoring (weight 30%)
    # ------------------------------------------------------------------ #

    def _step3_fundamental_scoring(self, codes: List[str]) -> Dict[str, float]:
        return {code: self._calc_fundamental(self.financial_data.get(code, [])) for code in codes}

    def _calc_fundamental(self, records: List[Dict]) -> float:
        score = 0.0

        # ROE – 30分
        roe = self._f(records[0].get('净资产收益率')) if records else None
        if roe is None:
            score += 15
        elif roe >= 20:
            score += 30
        elif roe >= 15:
            score += 24
        elif roe >= 10:
            score += 18
        elif roe >= 5:
            score += 10
        elif roe >= 0:
            score += 5
        # else 0

        # Revenue growth – 25分
        score += self._growth_score(records, '营业总收入', 25, 12)

        # Net profit growth – 25分
        score += self._growth_score(records, '净利润', 25, 12)

        # Debt ratio – 20分
        debt = self._f(records[0].get('资产负债率')) if records else None
        if debt is None:
            score += 10
        elif debt <= 30:
            score += 20
        elif debt <= 50:
            score += 15
        elif debt <= 70:
            score += 10
        else:
            score += 5

        return min(100.0, score)

    def _growth_score(self, records: List[Dict], field: str, full: int, neutral: int) -> float:
        if len(records) < 2:
            return neutral
        v0 = self._f(records[0].get(field))
        v1 = self._f(records[1].get(field))
        if v0 is None or v1 is None or v1 == 0:
            return neutral
        g = (v0 - v1) / abs(v1) * 100
        if g >= 30:
            return full
        elif g >= 20:
            return full * 0.80
        elif g >= 10:
            return full * 0.60
        elif g >= 0:
            return full * 0.40
        else:
            return full * 0.20

    # ------------------------------------------------------------------ #
    # Step 4 – Technical scoring (weight 25%)
    # ------------------------------------------------------------------ #

    def _step4_technical_scoring(self, codes: List[str]) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for code in codes:
            klines = self.kline_data.get(code, [])
            if len(klines) < 20:
                scores[code] = 50.0
                continue
            closes = [k['close'] for k in klines if k.get('close')]
            volumes = [k['volume'] for k in klines if k.get('volume') is not None]
            scores[code] = self._calc_technical(closes, volumes)
        return scores

    def _calc_technical(self, closes: List[float], volumes: List[float]) -> float:
        if len(closes) < 20:
            return 50.0
        score = 0.0
        current = closes[-1]

        # 1. Moving average trend – 30分
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        has_ma60 = len(closes) >= 60
        ma60 = sum(closes[-60:]) / 60 if has_ma60 else None

        if ma60 and current > ma5 and ma5 > ma20:
            score += 30
        elif current > ma5 and ma5 > ma20:
            score += 25
        elif current > ma20:
            score += 15
        else:
            score += 5

        # 2. MACD – 30分
        md = self._calc_macd(closes)
        if md['dif'] > md['dea'] and md['macd'] > 0:
            score += 30
        elif md['dif'] > md['dea']:
            score += 20
        else:
            score += 10

        # 3. RSI – 20分
        rsi = self._calc_rsi(closes, 14)
        if 40 <= rsi <= 70:
            score += 20
        elif 70 < rsi <= 80:
            score += 15
        elif rsi > 80:
            score += 5
        elif 30 <= rsi < 40:
            score += 15
        else:
            score += 10  # <30 超卖，潜在反弹

        # 4. Volume trend – 20分
        if len(volumes) >= 10:
            r5 = sum(volumes[-5:]) / 5
            p5 = sum(volumes[-10:-5]) / 5
            price_up = closes[-1] > closes[-6] if len(closes) >= 6 else False
            if p5 > 0:
                ratio = r5 / p5
                if ratio >= 1.1 and price_up:
                    score += 20
                elif ratio < 1.0 and price_up:
                    score += 15
                elif 0.9 <= ratio < 1.1:
                    score += 10
                elif ratio >= 1.1:
                    score += 5  # 放量下跌
                else:
                    score += 8  # 缩量下跌
            else:
                score += 10
        else:
            score += 10

        return min(100.0, score)

    def _calc_ema_series(self, data: List[float], period: int) -> List[Optional[float]]:
        if len(data) < period:
            return [None] * len(data)
        mul = 2 / (period + 1)
        result: List[Optional[float]] = [None] * (period - 1)
        ema = sum(data[:period]) / period
        result.append(ema)
        for price in data[period:]:
            ema = (price - ema) * mul + ema
            result.append(ema)
        return result

    def _calc_macd(self, closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        if len(closes) < slow:
            return {'dif': 0.0, 'dea': 0.0, 'macd': 0.0}
        ema12 = self._calc_ema_series(closes, fast)
        ema26 = self._calc_ema_series(closes, slow)
        dif_series = [
            ema12[i] - ema26[i]
            for i in range(len(closes))
            if ema12[i] is not None and ema26[i] is not None
        ]
        if not dif_series:
            return {'dif': 0.0, 'dea': 0.0, 'macd': 0.0}
        dif = dif_series[-1]
        if len(dif_series) < signal:
            return {'dif': dif, 'dea': dif, 'macd': 0.0}
        dea_series = self._calc_ema_series(dif_series, signal)
        dea_valid = [x for x in dea_series if x is not None]
        dea = dea_valid[-1] if dea_valid else dif
        return {'dif': dif, 'dea': dea, 'macd': (dif - dea) * 2}

    def _calc_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [c if c > 0 else 0 for c in changes[-period:]]
        losses = [-c if c < 0 else 0 for c in changes[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + avg_gain / avg_loss))

    # ------------------------------------------------------------------ #
    # Step 5 – Fund flow scoring (weight 20%)
    # ------------------------------------------------------------------ #

    def _step5_fund_flow_scoring(self, codes: List[str]) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for code in codes:
            records = self.fund_flow_data.get(code, [])
            scores[code] = self._calc_fund_flow(records) if records else 50.0
        return scores

    def _calc_fund_flow(self, records: List[Dict]) -> float:
        score = 0.0
        latest_inflow = self._f(records[0].get('main_net_inflow')) or 0.0

        # Latest-day main net inflow – 40分
        if latest_inflow > 5000e4:
            score += 40
        elif latest_inflow > 2000e4:
            score += 32
        elif latest_inflow > 0:
            score += 24
        elif latest_inflow > -2000e4:
            score += 16
        else:
            score += 10

        # Consecutive inflow days – 30分
        consecutive = 0
        for r in records:
            if (self._f(r.get('main_net_inflow')) or 0) > 0:
                consecutive += 1
            else:
                break
        if consecutive >= 3:
            score += 30
        elif consecutive >= 2:
            score += 22
        elif consecutive >= 1:
            score += 15
        else:
            score += 8

        # Inflow / total_amount ratio – 30分
        total_amount = self._f(records[0].get('total_amount')) or 0
        if total_amount > 0:
            ratio = latest_inflow / total_amount * 100
            if ratio > 5:
                score += 30
            elif ratio > 2:
                score += 22
            elif ratio > 0:
                score += 15
            else:
                score += 8
        else:
            score += 15  # neutral when unavailable

        return min(100.0, score)

    # ------------------------------------------------------------------ #
    # Step 6 – Valuation scoring (weight 15%)
    # ------------------------------------------------------------------ #

    def _step6_valuation_scoring(self, codes: List[str]) -> Dict[str, float]:
        return {code: self._calc_valuation(self.stock_info.get(code, {})) for code in codes}

    def _calc_valuation(self, info: Dict) -> float:
        score = 0.0

        # PE – 40分
        pe = self._f(info.get('市盈率-动态') or info.get('pe'))
        if pe is None or pe <= 0:
            score += 15  # 亏损年份或无数据 → 中性
        elif pe <= 15:
            score += 40
        elif pe <= 30:
            score += 32
        elif pe <= 50:
            score += 22
        elif pe <= 100:
            score += 12
        else:
            score += 5

        # PB – 35分
        pb = self._f(info.get('市净率') or info.get('pb'))
        if pb is None or pb <= 0:
            score += 25  # 中性
        elif pb <= 1:
            score += 35
        elif pb <= 2:
            score += 28
        elif pb <= 4:
            score += 20
        elif pb <= 8:
            score += 12
        else:
            score += 5

        # Industry adjustment – 25分
        industry = info.get('所属行业', '') or ''
        tech_keywords = ['科技', '医药', '消费', '软件', '医疗', '生物', '半导体', '互联网', '电子', '信息']
        finance_keywords = ['金融', '地产', '银行', '保险', '证券', '房地产', '能源', '煤炭', '钢铁', '化工']
        if any(kw in industry for kw in finance_keywords):
            score += 25
        else:
            score += 20  # tech/medical/others: same base

        return min(100.0, score)

    # ------------------------------------------------------------------ #
    # Step 7 – Aggregate, rank, output Top30
    # ------------------------------------------------------------------ #

    def _step7_aggregate(
        self,
        codes: List[str],
        fundamental: Dict[str, float],
        technical: Dict[str, float],
        fund_flow: Dict[str, float],
        valuation: Dict[str, float],
        mining_scores: Dict[str, float] = None,
    ) -> List[Dict[str, Any]]:
        scored: List[Dict[str, Any]] = []
        mining_scores = mining_scores or {}

        for code in codes:
            f = fundamental.get(code, 50.0)
            t = technical.get(code, 50.0)
            ff = fund_flow.get(code, 50.0)
            v = valuation.get(code, 50.0)
            m = mining_scores.get(code, 50.0)

            w = self.mining_weight
            total = (
                f * 0.33 * (1 - w) +
                t * 0.28 * (1 - w) +
                ff * 0.22 * (1 - w) +
                v * 0.17 * (1 - w)
            )
            total = total + m * w

            info = self.stock_info.get(code, {})
            records = self.financial_data.get(code, [])

            raw_cap = (info.get('总市值') or info.get('total_mv') or
                       info.get('market_cap') or info.get('流通市值') or 0)
            try:
                cap_yi = round(float(str(raw_cap).replace(',', '')) / 1e8, 1)
            except (ValueError, TypeError):
                cap_yi = 0

            pe = self._f(info.get('市盈率-动态') or info.get('pe'))
            pb = self._f(info.get('市净率') or info.get('pb'))
            roe = self._f(records[0].get('净资产收益率')) if records else None

            rev_growth = None
            if len(records) >= 2:
                r0 = self._f(records[0].get('营业总收入'))
                r1 = self._f(records[1].get('营业总收入'))
                if r0 is not None and r1 and r1 != 0:
                    rev_growth = round((r0 - r1) / abs(r1) * 100, 1)

            debt_ratio = self._f(records[0].get('资产负债率')) if records else None

            scored.append({
                'code': code,
                'name': info.get('name', ''),
                'total_score': round(total, 1),
                'fundamental_score': round(f, 1),
                'technical_score': round(t, 1),
                'fund_flow_score': round(ff, 1),
                'valuation_score': round(v, 1),
                'mining_score': round(m, 1),
                'industry': info.get('所属行业', '') or '',
                'market_cap_yi': cap_yi,
                'pe': round(pe, 1) if pe is not None else None,
                'pb': round(pb, 1) if pb is not None else None,
                'roe': round(roe, 1) if roe is not None else None,
                'revenue_growth': rev_growth,
                'debt_ratio': round(debt_ratio, 1) if debt_ratio is not None else None,
                'reason': self._build_reason(f, t, ff, v, m),
            })

        scored.sort(key=lambda x: x['total_score'], reverse=True)
        top30 = scored[:30]
        for i, item in enumerate(top30):
            item['rank'] = i + 1
        return top30

    def _build_reason(self, f: float, t: float, ff: float, v: float, m: float = 50.0) -> str:
        mapping = [
            (f, "基本面优秀（ROE高/营收增长）"),
            (t, "技术面强势（均线多头/MACD金叉）"),
            (ff, "主力资金持续流入"),
            (v, "估值较低（PE/PB处于低位）"),
            (m, "衍生因子强（波动/动量/融资/情感）"),
        ]
        mapping.sort(key=lambda x: x[0], reverse=True)
        parts = [desc for score_val, desc in mapping[:2] if score_val >= 65]
        return "，".join(parts) if parts else "综合指标均衡"

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def _f(self, val) -> Optional[float]:
        if val is None:
            return None
        try:
            s = str(val).replace(',', '').replace('--', '').strip()
            if not s or s.lower() in ('nan', 'none', 'null', ''):
                return None

            multiplier = 1.0
            if s.endswith('亿'):
                multiplier = 1e8
                s = s[:-1]
            elif s.endswith('万'):
                multiplier = 1e4
                s = s[:-1]
            if s.endswith('%'):
                s = s[:-1]

            return float(s) * multiplier
        except (ValueError, TypeError):
            return None
