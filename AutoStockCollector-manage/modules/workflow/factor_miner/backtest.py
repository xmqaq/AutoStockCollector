"""因子回测引擎 — IC 分析 / 分层收益 / 权重优化。"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from utils.logger import get_logger

from .base import FactorRegistry, DataStore
from .engine import FactorEngine

logger = get_logger(__name__)


def spearman_rank(x: np.ndarray, y: np.ndarray) -> float:
    n = len(x)
    if n < 5:
        return 0.0
    d = np.argsort(x) - np.argsort(y)
    return 1.0 - (6.0 * np.sum(d ** 2)) / (n * (n * n - 1))


class ICResult:
    def __init__(self):
        self.period_ic: Dict[int, List[float]] = defaultdict(list)
        self.factor_ic: Dict[str, Dict[int, List[float]]] = defaultdict(
            lambda: defaultdict(list))

    def add(self, period: int, ic: float):
        self.period_ic[period].append(ic)

    def add_factor(self, name: str, period: int, ic: float):
        self.factor_ic[name][period].append(ic)

    def summary(self) -> Dict:
        result = {}
        for period, ics in self.period_ic.items():
            arr = np.array(ics)
            result[f'{period}d_IC'] = {
                'mean': float(np.mean(arr)),
                'std': float(np.std(arr)),
                'ir': float(np.mean(arr) / max(np.std(arr), 1e-6)),
                'positive_ratio': float(np.sum(arr > 0) / max(len(arr), 1)),
                'count': len(arr),
            }
        return result


class BacktestEngine:
    """回测引擎：滑动窗口计算因子 IC、分层收益、权重优化。

    用法:
        engine = BacktestEngine(db)
        result = engine.run_period_ic('2025-01-01', '2026-06-01', periods=[1, 5, 10])
    """

    def __init__(self, db):
        self.db = db

    def _load_kline_window(self, date: datetime,
                           window: int = 60) -> Dict[str, List[Dict]]:
        """加载截止到 date 的 window 天 kline。"""
        cutoff = date - timedelta(days=window)
        kline_data = defaultdict(list)
        cursor = self.db['kline'].find(
            {'date': {'$gte': cutoff, '$lte': date}},
            {'code': 1, 'date': 1, 'close': 1, 'amount': 1,
             'high': 1, 'low': 1, 'open': 1, '_id': 0}
        ).sort('date', 1)
        for r in cursor:
            c = r.get('code')
            if c:
                kline_data[c].append(r)
        return dict(kline_data)

    def _load_forward_return(self, date: datetime, codes: List[str],
                             periods: List[int]) -> Dict[str, Dict[int, float]]:
        """计算每只股票在 date 之后 periods 天的收益。"""
        result: Dict[str, Dict[int, float]] = {}
        for code in codes:
            closes = []
            cursor = self.db['kline'].find(
                {'code': code, 'date': {'$gte': date}},
                {'date': 1, 'close': 1, '_id': 0}
            ).sort('date', 1).limit(max(periods) + 1)
            for r in cursor:
                closes.append(r['close'])
            if len(closes) < 2:
                continue
            result[code] = {}
            base = closes[0]
            if base <= 0:
                continue
            for p in periods:
                if p < len(closes):
                    result[code][p] = (closes[p] - base) / base * 100
        return result

    def run_period_ic(self, start_date: str, end_date: str,
                      periods: List[int] = None,
                      rebalance_days: int = 20,
                      factor_names: List[str] = None) -> ICResult:
        """滚动回测：每隔 rebalance_days 天算一次截面 IC。

        Args:
            start_date: 起始日 'YYYY-MM-DD'
            end_date: 结束日
            periods: 持有期列表，如 [1, 5, 10, 20]
            rebalance_days: 调仓间隔（交易日数）
            factor_names: 要测试的因子，默认全量
        """
        periods = periods or [1, 5, 10, 20]
        factor_names = factor_names or FactorRegistry.list_factors()

        ic_result = ICResult()

        dates = self._get_trade_dates(start_date, end_date)
        step = max(rebalance_days, 1)

        for i in range(0, len(dates), step):
            date = dates[i]
            logger.info(f'IC test at {date.date()} ({i}/{len(dates)})')

            # 加载 kline 窗口数据
            kline = self._load_kline_window(date, window=60)
            codes = list(kline.keys())
            if not codes:
                continue

            # 计算因子
            store = DataStore(kline_map=kline, codes=codes)
            engine = FactorEngine(factor_names=factor_names)
            scores = engine.compute_raw(codes, store)

            # 计算截面 IC（每个因子 vs 未来收益）
            forward = self._load_forward_return(date, codes, periods)
            codes_with_forward = [c for c in codes if c in forward]

            for period in periods:
                rank_scores = []
                rank_returns = []
                for code in codes_with_forward:
                    if period not in forward[code]:
                        continue
                    # 合成综合分（等权）
                    fs = scores.get(code, {})
                    vals = [fs.get(n) for n in factor_names if n in fs]
                    if len(vals) < 2:
                        continue
                    score = float(np.mean(vals))
                    rank_scores.append(score)
                    rank_returns.append(forward[code][period])

                if len(rank_scores) < 10:
                    continue
                ic = spearman_rank(
                    np.array(rank_scores), np.array(rank_returns)
                )
                ic_result.add(period, ic)

                # 单因子 IC
                for name in factor_names:
                    factor_vals = []
                    factor_ret = []
                    for code in codes_with_forward:
                        if period not in forward[code]:
                            continue
                        v = scores.get(code, {}).get(name)
                        if v is None:
                            continue
                        factor_vals.append(v)
                        factor_ret.append(forward[code][period])
                    if len(factor_vals) >= 10:
                        fic = spearman_rank(
                            np.array(factor_vals), np.array(factor_ret)
                        )
                        ic_result.add_factor(name, period, fic)

        return ic_result

    def _get_trade_dates(self, start: str, end: str) -> List[datetime]:
        """获取交易日期列表。"""
        from datetime import datetime as dt
        start_dt = dt.strptime(start, '%Y-%m-%d')
        end_dt = dt.strptime(end, '%Y-%m-%d')
        dates = []
        cursor = self.db['kline'].find(
            {'date': {'$gte': start_dt, '$lte': end_dt}},
            {'date': 1, '_id': 0}
        ).sort('date', -1)
        seen = set()
        for r in cursor:
            d = r['date']
            if d not in seen:
                seen.add(d)
                dates.append(d)
        return sorted(dates)

    def optimize_weights(self, start_date: str, end_date: str,
                         periods: List[int] = None) -> Dict[str, float]:
        """用历史 IC 均值优化因子权重。"""
        periods = periods or [5, 10]
        ic_result = self.run_period_ic(start_date, end_date, periods)
        weights = {}
        for name in FactorRegistry.list_factors():
            ics = []
            for period in periods:
                lst = ic_result.factor_ic.get(name, {}).get(period, [])
                ics.extend(lst)
            if ics:
                weights[name] = float(np.mean(ics))
            else:
                weights[name] = 0

        # 负 IC 因子置零（无效或反向因子）
        weights = {k: max(v, 0) for k, v in weights.items()}
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        return weights

    def run_backtest(self, start_date: str, end_date: str,
                     weights: Dict[str, float] = None,
                     rebalance_days: int = 20,
                     top_n: int = 30) -> Dict:
        """全流程回测：调仓日选股 → 持有 → 计算收益。"""
        periods = [1, 5, 10, 20]
        weights = weights or FactorRegistry.normalize_weight()
        dates = self._get_trade_dates(start_date, end_date)
        step = max(rebalance_days, 1)

        daily_returns = []

        for i in range(0, len(dates), step):
            date = dates[i]
            kline = self._load_kline_window(date, window=60)
            codes = list(kline.keys())
            if not codes:
                continue

            # 计算因子综合分
            store = DataStore(kline_map=kline, codes=codes)
            engine = FactorEngine(factor_names=list(weights.keys()))
            raw = engine.compute_raw(codes, store)
            norm = engine.normalize(raw, codes)
            scores = engine.synthesize(norm, codes)

            # 选 Top N
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            selected = [c for c, _ in ranked[:top_n]]

            # 到下次调仓日之间的收益（简单等权）
            next_idx = min(i + step, len(dates) - 1)
            if next_idx <= i:
                continue
            next_date = dates[next_idx]

            forward_returns = self._load_forward_return(
                date, selected, periods
            )
            for period in periods:
                rets = []
                for c in selected:
                    if c in forward_returns and period in forward_returns[c]:
                        rets.append(forward_returns[c][period])
                if rets:
                    daily_returns.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'next_date': next_date.strftime('%Y-%m-%d'),
                        f'hold_{period}d_return': float(np.mean(rets)),
                        'n_stocks': len(rets),
                    })

        if not daily_returns:
            return {'error': 'no data'}

        # 汇总
        rets_5d = [r.get('hold_5d_return', 0) for r in daily_returns]
        rets_10d = [r.get('hold_10d_return', 0) for r in daily_returns]
        arr5 = np.array(rets_5d)
        arr10 = np.array(rets_10d)

        return {
            'n_periods': len(daily_returns),
            'hold_5d': {
                'mean_return': float(np.mean(arr5)),
                'std': float(np.std(arr5)),
                'sharpe': float(np.mean(arr5) / max(np.std(arr5), 1e-6) * np.sqrt(252 / 5)),
                'positive_ratio': float(np.sum(arr5 > 0) / max(len(arr5), 1)),
                'max_drawdown': float(np.min(np.minimum.accumulate(arr5) - np.maximum.accumulate(arr5))),
            },
            'hold_10d': {
                'mean_return': float(np.mean(arr10)),
                'std': float(np.std(arr10)),
                'sharpe': float(np.mean(arr10) / max(np.std(arr10), 1e-6) * np.sqrt(252 / 10)),
                'positive_ratio': float(np.sum(arr10 > 0) / max(len(arr10), 1)),
            },
            'periods': daily_returns,
        }
