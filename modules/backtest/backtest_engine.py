"""
策略回测引擎 - 优化版
基于 Backtrader 实现量化策略回测，含动态止损止盈与滑点适配
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import math
import backtrader as bt
from core.storage.mongo_storage import KlineStorage
from config.settings import Settings
from utils.logger import get_logger


logger = get_logger(__name__)


class RiskControlMixin:
    def __init__(self):
        self.stop_loss = 0.05
        self.take_profit = 0.10
        self.slippage = 0.001
        self.max_position = 0.20
        self.use_trailing_stop = False
        self.trailing_percent = 0.05

    def set_stop_loss(self, percent: float):
        self.stop_loss = abs(percent)

    def set_take_profit(self, percent: float):
        self.take_profit = abs(percent)

    def set_slippage(self, percent: float):
        self.slippage = abs(percent)

    def set_max_position(self, percent: float):
        self.max_position = min(abs(percent), 0.50)

    def enable_trailing_stop(self, percent: float = 0.05):
        self.use_trailing_stop = True
        self.trailing_percent = abs(percent)

    def apply_slippage(self, price: float, is_buy: bool) -> float:
        if is_buy:
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)

    def check_stop_loss(self, entry_price: float, current_price: float) -> bool:
        if entry_price <= 0:
            return False
        loss_percent = (entry_price - current_price) / entry_price
        return loss_percent >= self.stop_loss

    def check_take_profit(self, entry_price: float, current_price: float) -> bool:
        if entry_price <= 0:
            return False
        profit_percent = (current_price - entry_price) / entry_price
        return profit_percent >= self.take_profit

    def should_exit(self, entry_price: float, current_price: float) -> tuple:
        if self.check_stop_loss(entry_price, current_price):
            return True, "stop_loss"
        if self.check_take_profit(entry_price, current_price):
            return True, "take_profit"
        return False, ""


class BacktestStrategy(bt.Strategy, RiskControlMixin):
    params = (
        ("stop_loss", 0.05),
        ("take_profit", 0.10),
    )

    def __init__(self):
        self.data_live = True
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.trades = []
        self.trade_history = []
        # 将 Backtrader params 同步到 RiskControlMixin 属性
        self.stop_loss = self.params.stop_loss
        self.take_profit = self.params.take_profit

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            try:
                trade_date = self.data.datetime.date(0)
                date_str = str(trade_date)
            except:
                date_str = str(self.data.datetime[0])

            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                trade = {
                    "type": "buy",
                    "price": self.buy_price,
                    "date": date_str,
                    "size": order.executed.size
                }
                self.trades.append(trade)
            else:
                trade = {
                    "type": "sell",
                    "price": order.executed.price,
                    "date": date_str,
                    "size": order.executed.size,
                    "pnl": 0,
                    "pnl_percent": 0
                }
                self.trades.append(trade)

            self.order = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            if self.trades:
                self.trades[-1]["pnl"] = trade.pnl
                self.trades[-1]["pnl_percent"] = trade.pnl / self.buy_price * 100 if self.buy_price else 0

    def _check_exit(self) -> bool:
        """止损/止盈检查，在各子类 next() 开头调用。返回 True 表示已发出卖出指令。"""
        if not self.position or self.order or not self.buy_price:
            return False
        should_exit, _ = self.should_exit(self.buy_price, self.data.close[0])
        if should_exit:
            self.order = self.sell()
            return True
        return False


class MovingAverageStrategy(BacktestStrategy):
    params = (
        ("fast_period", 10),
        ("slow_period", 30),
        ("printlog", False),
    )

    def __init__(self):
        super().__init__()
        self.sma_fast = bt.indicators.SimpleMovingAverage(
            self.data.close,
            period=self.params.fast_period
        )
        self.sma_slow = bt.indicators.SimpleMovingAverage(
            self.data.close,
            period=self.params.slow_period
        )
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.order = self.sell()


class MomentumStrategy(BacktestStrategy):
    params = (
        ("period", 20),
        ("threshold", 0.05),
    )

    def __init__(self):
        super().__init__()
        self.momentum = bt.indicators.Momentum(self.data.close, period=self.params.period)

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        if not self.position:
            if self.momentum > self.params.threshold:
                self.order = self.buy()
        else:
            if self.momentum < -self.params.threshold:
                self.order = self.sell()


class MeanReversionStrategy(BacktestStrategy):
    params = (
        ("period", 20),
        ("devfactor", 2.0),
    )

    def __init__(self):
        super().__init__()
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor
        )

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        if not self.position:
            if self.data.close < self.bb.lines.bot:
                self.order = self.buy()
        else:
            if self.data.close > self.bb.lines.top:
                self.order = self.sell()


class MACDStrategy(BacktestStrategy):
    params = (
        ("fast_period", 12),
        ("slow_period", 26),
        ("signal_period", 9),
    )

    def __init__(self):
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.lines.macd, self.macd.lines.signal)

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.order = self.sell()


class RSIStrategy(BacktestStrategy):
    params = (
        ("period", 14),
        ("upper", 70),
        ("lower", 30),
    )

    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.params.period
        )

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        if not self.position:
            if self.rsi < self.params.lower:
                self.order = self.buy()
        else:
            if self.rsi > self.params.upper:
                self.order = self.sell()


class FundFlowStrategy(BacktestStrategy):
    params = (
        ("inflow_threshold", 10000000),
        ("volume_multiplier", 1.5),
    )

    def __init__(self):
        super().__init__()
        self.volume_sma = bt.indicators.SimpleMovingAverage(
            self.data.volume,
            period=20
        )

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        current_volume = self.data.volume[0]
        avg_volume = self.volume_sma[0]

        if not self.position:
            if current_volume > avg_volume * self.params.volume_multiplier:
                self.order = self.buy()
        else:
            if self.position:
                self.order = self.sell()


class DragonTigerStrategy(BacktestStrategy):
    params = (
        ("holding_days", 5),
        ("institutional_ratio", 0.1),
    )

    def __init__(self):
        super().__init__()
        self.holding_count = 0

    def next(self):
        if self.order:
            return
        if self._check_exit():
            return

        self.holding_count += 1

        if not self.position:
            if self.holding_count >= self.params.holding_days:
                self.order = self.buy()
                self.holding_count = 0
        else:
            if self.position:
                self.order = self.sell()
                self.holding_count = 0


class DataLoader(bt.feeds.PandasData):
    params = (
        ("datetime", None),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", -1),
    )


class PerformanceMetrics:
    @staticmethod
    def calculate_total_return(initial_value: float, final_value: float) -> float:
        if initial_value <= 0:
            return 0.0
        return round((final_value - initial_value) / initial_value * 100, 2)

    @staticmethod
    def calculate_annualized_return(total_return: float, days: int) -> float:
        if days <= 0:
            return 0.0
        years = days / 365
        if years == 0:
            return 0.0
        total_return_decimal = total_return / 100
        annualized = (1 + total_return_decimal) ** (1 / years) - 1
        return round(annualized * 100, 2)

    @staticmethod
    def calculate_max_drawdown(equity_curve: List[float]) -> float:
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100 if peak > 0 else 0
            if drawdown > max_dd:
                max_dd = drawdown

        return round(max_dd, 2)

    @staticmethod
    def calculate_sharpe_ratio(
        returns: List[float],
        risk_free_rate: float = 0.03
    ) -> float:
        if not returns or len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        excess_return = mean_return - risk_free_rate / 365
        sharpe = excess_return / std_dev * math.sqrt(365)

        return round(sharpe, 2)

    @staticmethod
    def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
        if not trades:
            return 0.0

        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        return round(len(winning_trades) / len(trades) * 100, 2) if trades else 0.0

    @staticmethod
    def calculate_profit_loss_ratio(trades: List[Dict[str, Any]]) -> float:
        if not trades:
            return 0.0

        winning_pnls = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
        losing_pnls = [abs(t.get("pnl", 0)) for t in trades if t.get("pnl", 0) < 0]

        if not winning_pnls or not losing_pnls:
            return 0.0

        avg_win = sum(winning_pnls) / len(winning_pnls)
        avg_loss = sum(losing_pnls) / len(losing_pnls)

        if avg_loss == 0:
            return 0.0

        return round(avg_win / avg_loss, 2)

    @staticmethod
    def calculate_sortino_ratio(
        returns: List[float],
        risk_free_rate: float = 0.03
    ) -> float:
        if not returns or len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            return 0.0

        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = math.sqrt(downside_variance)

        if downside_std == 0:
            return 0.0

        excess_return = mean_return - risk_free_rate / 365
        sortino = excess_return / downside_std * math.sqrt(365)

        return round(sortino, 2)

    @staticmethod
    def calculate_calmar_ratio(
        total_return: float,
        max_drawdown: float,
        years: int
    ) -> float:
        if max_drawdown == 0 or years == 0:
            return 0.0

        annualized_return = total_return / years
        return round(annualized_return / max_drawdown, 2)

    @staticmethod
    def generate_report(
        initial_cash: float,
        final_cash: float,
        trades: List[Dict[str, Any]],
        days: int
    ) -> Dict[str, Any]:
        total_return = PerformanceMetrics.calculate_total_return(initial_cash, final_cash)
        annualized_return = PerformanceMetrics.calculate_annualized_return(total_return, days)

        equity_curve = [initial_cash]
        returns = []
        cumulative = initial_cash

        for trade in trades:
            pnl = trade.get("pnl", 0)
            cumulative += pnl
            equity_curve.append(cumulative)
            if initial_cash > 0:
                returns.append(pnl / initial_cash)

        max_drawdown = PerformanceMetrics.calculate_max_drawdown(equity_curve)
        sharpe_ratio = PerformanceMetrics.calculate_sharpe_ratio(returns)
        sortino_ratio = PerformanceMetrics.calculate_sortino_ratio(returns)
        win_rate = PerformanceMetrics.calculate_win_rate(trades)
        profit_loss_ratio = PerformanceMetrics.calculate_profit_loss_ratio(trades)
        calmar_ratio = PerformanceMetrics.calculate_calmar_ratio(
            total_return, max_drawdown, days / 365 if days > 0 else 1
        )

        return {
            "initial_cash": round(initial_cash, 2),
            "final_cash": round(final_cash, 2),
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "total_trades": len(trades),
            "winning_trades": len([t for t in trades if t.get("pnl", 0) > 0]),
            "losing_trades": len([t for t in trades if t.get("pnl", 0) < 0]),
            "total_pnl": round(sum(t.get("pnl", 0) for t in trades), 2),
            "avg_pnl_per_trade": round(
                sum(t.get("pnl", 0) for t in trades) / len(trades), 2
            ) if trades else 0,
            "duration_days": days
        }


class BacktestEngine:
    # ST/退市标识前缀（用于代码/名称过滤）
    _EXCLUDED_PREFIXES = ("*ST", "ST", "PT", "退市")

    def __init__(self):
        self.kline_storage = KlineStorage()
        self.strategy_map = {
            "ma_cross": MovingAverageStrategy,
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "macd": MACDStrategy,
            "rsi": RSIStrategy,
            "fund_flow": FundFlowStrategy,
            "dragon_tiger": DragonTigerStrategy,
        }
        self.default_risk_config = {
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "slippage": 0.001,
            "max_position": 0.20,
            "use_trailing_stop": False,
            "trailing_percent": 0.05,
        }

    def run(
        self,
        strategy: str,
        codes: List[str],
        start_date: str,
        end_date: str,
        initial_cash: float = 1000000,
        commission: float = 0.001,
        stop_loss: float = 0.05,
        take_profit: float = 0.10,
        slippage: float = 0.001,
        max_position: float = 0.20,
        use_trailing_stop: bool = False,
        trailing_percent: float = 0.05
    ) -> Dict[str, Any]:
        if strategy not in self.strategy_map:
            return {"error": f"Unknown strategy: {strategy}"}

        risk_config = {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "slippage": slippage,
            "max_position": max_position,
            "use_trailing_stop": use_trailing_stop,
            "trailing_percent": trailing_percent,
        }

        # 过滤 ST、退市、流动性枯竭标的
        codes = self._filter_excluded_codes(codes)
        if not codes:
            return {"error": "All codes filtered out (ST/delisted/illiquid)"}

        total_results = []
        all_trades = []

        for code in codes:
            try:
                result = self._backtest_single(
                    code=code,
                    strategy_class=self.strategy_map[strategy],
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    commission=commission,
                    risk_config=risk_config
                )

                if result:
                    total_results.append(result)
                    all_trades.extend(result.get("trades", []))

            except Exception as e:
                logger.error(f"Backtest failed for {code}: {e}")

        if not total_results:
            return {"error": "No successful backtests"}

        combined_stats = self._combine_results(total_results, initial_cash)

        metrics_report = PerformanceMetrics.generate_report(
            initial_cash=initial_cash,
            final_cash=combined_stats.get("final_value", initial_cash),
            trades=all_trades,
            days=self._calculate_days(start_date, end_date)
        )

        return {
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "codes_count": len(codes),
            "successful_backtests": len(total_results),
            "initial_cash": initial_cash,
            **combined_stats,
            **metrics_report,
            "trades": all_trades[:100]
        }

    def _filter_excluded_codes(self, codes: List[str]) -> List[str]:
        """过滤 ST、退市、流动性枯竭标的"""
        from core.storage.mongo_storage import StockInfoStorage
        try:
            info_storage = StockInfoStorage()
            valid = []
            for code in codes:
                info = info_storage.get_by_code(code)
                if info:
                    name = info.get("name", "") or ""
                    if any(name.startswith(p) for p in self._EXCLUDED_PREFIXES):
                        logger.info(f"Backtest skip {code} ({name}): ST/delisted")
                        continue
                    status = info.get("status", "")
                    if status in ("退市", "delisted"):
                        logger.info(f"Backtest skip {code}: delisted")
                        continue
                valid.append(code)
            return valid
        except Exception as e:
            logger.warning(f"Code filter failed, using original list: {e}")
            return codes

    def _is_limit_day(self, row: Dict[str, Any]) -> bool:
        """判断是否为涨跌停（无法正常交易）"""
        pct = row.get("pct_chg", row.get("涨跌幅", None))
        if pct is None:
            return False
        try:
            pct = float(pct)
            return abs(pct) >= 9.8
        except (TypeError, ValueError):
            return False

    def _calculate_days(self, start_date: str, end_date: str) -> int:
        from utils.helpers import parse_date
        try:
            start = parse_date(start_date)
            end = parse_date(end_date)
            return max(1, (end - start).days)
        except:
            return 365

    def _backtest_single(
        self,
        code: str,
        strategy_class: type,
        start_date: str,
        end_date: str,
        initial_cash: float,
        commission: float,
        risk_config: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        klines = self.kline_storage.query_by_date_range(
            code=code,
            date_field="date",
            start_date=start_date,
            end_date=end_date
        )

        if len(klines) < 30:
            logger.warning(f"Insufficient data for {code}")
            return None

        import pandas as pd
        df = pd.DataFrame(klines)

        if "date" not in df.columns:
            return None

        df = df.sort_values("date").reset_index(drop=True)

        # 过滤涨跌停日（无法正常交易）
        if "pct_chg" in df.columns or "涨跌幅" in df.columns:
            pct_col = "pct_chg" if "pct_chg" in df.columns else "涨跌幅"
            df = df[df[pct_col].apply(
                lambda x: abs(float(x)) < 9.8 if x not in (None, "") else True
            )]

        df["date"] = pd.to_datetime(df["date"])

        df = df.set_index("date")

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0

        risk_config = risk_config or {}
        stop_loss = risk_config.get("stop_loss", 0.05)
        take_profit = risk_config.get("take_profit", 0.10)
        slippage = risk_config.get("slippage", 0.001)

        cerebro = bt.Cerebro()

        cerebro.addstrategy(strategy_class, stop_loss=stop_loss, take_profit=take_profit)

        data_feed = DataLoader(dataname=df)
        cerebro.adddata(data_feed)

        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)
        cerebro.broker.set_slippage_perc(slippage)

        cerebro.addsizer(bt.sizers.PercentSizer, stake=10)

        try:
            initial_value = cerebro.broker.getvalue()
            strats = cerebro.run()
            final_value = cerebro.broker.getvalue()

            # 从策略实例取实际成交记录（修复之前恒返回空列表的问题）
            trades = strats[0].trades if strats else []

            total_return = PerformanceMetrics.calculate_total_return(initial_value, final_value)

            days = self._calculate_days(start_date, end_date)
            annualized_return = PerformanceMetrics.calculate_annualized_return(total_return, days)

            return {
                "code": code,
                "initial_value": initial_value,
                "final_value": final_value,
                "total_return": total_return,
                "annualized_return": annualized_return,
                "trades": trades
            }

        except Exception as e:
            logger.error(f"Cerebro run failed for {code}: {e}")
            return None

    def _combine_results(
        self,
        results: List[Dict[str, Any]],
        initial_cash: float
    ) -> Dict[str, Any]:
        if not results:
            return {}

        total_returns = [r.get("total_return", 0) for r in results]
        avg_return = sum(total_returns) / len(total_returns) if total_returns else 0

        wins = [r for r in results if r.get("total_return", 0) > 0]
        win_rate = len(wins) / len(results) * 100 if results else 0

        final_values = [r.get("final_value", initial_cash) for r in results]
        total_final_value = sum(final_values)
        total_return = (total_final_value - initial_cash * len(results)) / (initial_cash * len(results)) * 100 if initial_cash > 0 and len(results) > 0 else 0

        max_drawdowns = []
        for r in results:
            ret = r.get("total_return", 0)
            max_drawdowns.append(abs(min(0, ret)))

        avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0

        total_trades = sum(len(r.get("trades", [])) for r in results)

        sharpe_ratio = 0
        if avg_return > 0 and avg_max_drawdown > 0:
            sharpe_ratio = round(avg_return / avg_max_drawdown, 2)

        return {
            "total_return": round(total_return, 2),
            "avg_return": round(avg_return, 2),
            "win_rate": round(win_rate, 2),
            "avg_max_drawdown": round(avg_max_drawdown, 2),
            "total_trades": total_trades,
            "final_value": round(total_final_value, 2),
            "sharpe_ratio": sharpe_ratio
        }

    def run_ai_strategy(
        self,
        ai_results: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        initial_cash: float = 1000000
    ) -> Dict[str, Any]:
        codes = [r["code"] for r in ai_results if r.get("score", 0) >= 60]

        if not codes:
            return {"error": "No valid stocks from AI results"}

        return self.run(
            strategy="ma_cross",
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

    def get_performance_metrics(
        self,
        trades: List[Dict[str, Any]],
        initial_cash: float = 1000000
    ) -> Dict[str, Any]:
        if not trades:
            return {}

        final_cash = initial_cash + sum(t.get("pnl", 0) for t in trades)

        return PerformanceMetrics.generate_report(
            initial_cash=initial_cash,
            final_cash=final_cash,
            trades=trades,
            days=365
        )


backtest_engine = BacktestEngine()