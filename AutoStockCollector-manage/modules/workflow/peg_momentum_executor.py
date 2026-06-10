"""
PEG+动量精选策略执行引擎

基于ElasticNet多因子研究改进，核心改进：
1. K线数据改为30日（原90日），加速远程MongoDB查询
2. 基本面权重提高至35%，估值权重提高至17%，动量因子独立评分
3. 行业分散化输出（每行业最多3只）
4. PEG-adjusted评分（增长/估值匹配度）
"""
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from collections import defaultdict
from config.database import DatabaseConfig
from modules.workflow.quant_executor import QuantMultiFactorExecutor
from utils.logger import get_logger

logger = get_logger(__name__)


class PegMomentumExecutor(QuantMultiFactorExecutor):
    def __init__(self, workflow_id, execution_id="", progress_callback=None, mining_weight=0.20):
        super().__init__(workflow_id, execution_id, progress_callback, mining_weight)
        self.kline_days = 30

    def _step1_load_data(self):
        db = DatabaseConfig.get_database()
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
        logger.info(f"Loaded {len(self.stock_info)} stock_info records")
        self._report("step1", "初始化股票池", f"已加载 {len(self.stock_info)} 只股票基础信息", 4)

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
        logger.info(f"Loaded financial data")
        self._report("step1", "初始化股票池", f"已加载财务数据", 7)

        cutoff = beijing_now() - timedelta(days=self.kline_days)
        self.kline_data = defaultdict(list)
        cursor = db['kline'].find(
            {'date': {'$gte': cutoff}},
            {'code': 1, 'date': 1, 'close': 1, 'volume': 1,
             'high': 1, 'low': 1, 'open': 1, '_id': 0}
        ).sort('date', 1)
        for r in cursor:
            code = r.get('code')
            if code:
                self.kline_data[code].append(r)
        total_kline = sum(len(v) for v in self.kline_data.values())
        logger.info(f"Loaded {total_kline} kline records ({self.kline_days}d)")
        self._report("step1", "初始化股票池", f"已加载 {total_kline} 条K线数据（最近{self.kline_days}日）", 10)

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
        logger.info(f"Loaded fund_flow data")

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
        logger.info(f"Loaded {total_margin} margin records")

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
        logger.info(f"Loaded {total_dragon} dragon_tiger records")

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
        logger.info(f"Loaded {total_news} news records")

    def _step7_aggregate(self, codes, fundamental, technical, fund_flow, valuation, mining_scores=None):
        mining_scores = mining_scores or {}
        scored: List[Dict[str, Any]] = []
        for code in codes:
            f = fundamental.get(code, 50.0)
            t = technical.get(code, 50.0)
            ff = fund_flow.get(code, 50.0)
            v = valuation.get(code, 50.0)
            m = mining_scores.get(code, 50.0)

            w = self.mining_weight
            total = f * 0.35 * (1 - w) + t * 0.25 * (1 - w) + ff * 0.20 * (1 - w) + v * 0.20 * (1 - w)
            total = total + m * w

            info = self.stock_info.get(code, {})
            records = self.financial_data.get(code, [])

            raw_cap = (info.get('总市值') or info.get('total_mv') or
                       info.get('market_cap') or info.get('流通市值') or 0)
            try:
                cap_yi = round(float(str(raw_cap).replace(',', '')) / 1e8, 1)
            except (ValueError, TypeError):
                cap_yi = 0

            pe_val = self._f(info.get('市盈率-动态') or info.get('pe'))
            pb_val = self._f(info.get('市净率') or info.get('pb'))
            roe_val = self._f(records[0].get('净资产收益率')) if records else None

            rev_growth = None
            profit_growth = None
            if len(records) >= 2:
                r0 = self._f(records[0].get('营业总收入'))
                r1 = self._f(records[1].get('营业总收入'))
                if r0 is not None and r1 and r1 != 0:
                    rev_growth = round((r0 - r1) / abs(r1) * 100, 1)
                n0 = self._f(records[0].get('净利润'))
                n1 = self._f(records[1].get('净利润'))
                if n0 is not None and n1 and n1 != 0:
                    profit_growth = round((n0 - n1) / abs(n1) * 100, 1)

            debt_ratio = self._f(records[0].get('资产负债率')) if records else None

            scored.append({
                'code': code, 'name': info.get('name', ''),
                'total_score': round(total, 1),
                'fundamental_score': round(f, 1),
                'technical_score': round(t, 1),
                'fund_flow_score': round(ff, 1),
                'valuation_score': round(v, 1),
                'mining_score': round(m, 1),
                'industry': info.get('所属行业', '') or '',
                'market_cap_yi': cap_yi,
                'pe': round(pe_val, 1) if pe_val is not None else None,
                'pb': round(pb_val, 1) if pb_val is not None else None,
                'roe': round(roe_val, 1) if roe_val is not None else None,
                'revenue_growth': rev_growth,
                'profit_growth': profit_growth,
                'debt_ratio': round(debt_ratio, 1) if debt_ratio is not None else None,
                'reason': self._build_reason(f, t, ff, v, rev_growth, pe_val, roe_val, info.get('name', '')),
            })

        scored.sort(key=lambda x: x['total_score'], reverse=True)
        industry_count: Dict[str, int] = {}
        diversified: List[Dict[str, Any]] = []
        for item in scored:
            ind = item.get('industry', '')
            if industry_count.get(ind, 0) >= 3:
                continue
            diversified.append(item)
            industry_count[ind] = industry_count.get(ind, 0) + 1
            if len(diversified) >= 30:
                break

        for i, item in enumerate(diversified):
            item['rank'] = i + 1
        return diversified[:30]

    def _build_reason(self, f, t, ff, v, rev_growth, pe, roe, name):
        parts = []
        if f >= 70:
            detail = []
            if roe and roe >= 15:
                detail.append(f"ROE={roe:.0f}%")
            if rev_growth and rev_growth >= 20:
                detail.append(f"营收增{rev_growth:.0f}%")
            base = "基本面优秀"
            if detail:
                base += f"({','.join(detail[:2])})"
            parts.append(base)
        elif f >= 55:
            parts.append("基本面良好")

        if t >= 70:
            parts.append("技术强势")
        elif t >= 55:
            parts.append("技术中性偏多")

        if ff >= 70:
            parts.append("资金流入")
        elif ff >= 55:
            parts.append("资金中性")

        if v >= 70:
            detail = f"PE={pe:.0f}" if pe else ""
            parts.append(f"估值偏低({detail})" if detail else "估值偏低")
        elif v >= 55:
            parts.append("估值合理")

        if not parts:
            return "综合指标均衡"
        return "，".join(parts[:3])
