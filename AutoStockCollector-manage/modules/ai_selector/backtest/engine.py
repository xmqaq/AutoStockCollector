"""
向量化回测引擎
基于 NumPy/Pandas 实现极速回测，支持 AI 策略回测
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import pandas as pd
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    initial_cash: float = 1000000.0
    commission: float = 0.001
    slippage: float = 0.001
    stop_loss: float = 0.05
    take_profit: float = 0.10
    max_position: float = 0.20
    min_position: float = 0.02


@dataclass
class BacktestResult:
    code: str
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    final_value: float
    trades: List[Dict[str, Any]]
    equity_curve: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "profit_loss_ratio": self.profit_loss_ratio,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "final_value": self.final_value,
            "trades_count": len(self.trades)
        }


class VectorizedBacktest:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        initial_cash: float,
        stop_loss: float,
        take_profit: float
    ) -> BacktestResult:
        if "close" not in df.columns or "date" not in df.columns:
            raise ValueError("DataFrame must contain 'close' and 'date' columns")

        df = df.sort_values("date").reset_index(drop=True)
        close_prices = df["close"].values
        dates = df["date"].values if "date" in df.columns else np.arange(len(df))

        cash = initial_cash
        position = 0
        shares = 0.0
        equity_curve = [initial_cash]
        trades = []

        entry_price = 0.0
        entry_date = ""

        for i in range(len(close_prices)):
            current_price = close_prices[i] * (1 + self.config.slippage) if self.config.slippage > 0 else close_prices[i]

            if signals.iloc[i] == 1 and position == 0 and cash >= current_price:
                shares_to_buy = int(cash / current_price * self.config.max_position)
                cost = shares_to_buy * current_price * (1 + self.config.commission)

                if cost <= cash:
                    shares = shares_to_buy
                    cash -= cost
                    position = 1
                    entry_price = current_price
                    entry_date = dates[i]

                    trades.append({
                        "type": "buy",
                        "price": current_price,
                        "shares": shares,
                        "date": str(entry_date),
                        "pnl": 0,
                        "pnl_percent": 0
                    })

            elif position == 1:
                sell_price = current_price * (1 - self.config.slippage) if self.config.slippage > 0 else current_price
                should_sell = False
                reason = ""

                pnl_percent = (sell_price - entry_price) / entry_price

                if pnl_percent <= -stop_loss:
                    should_sell = True
                    reason = "stop_loss"
                elif pnl_percent >= take_profit:
                    should_sell = True
                    reason = "take_profit"

                if should_sell:
                    proceeds = shares * sell_price * (1 - self.config.commission)
                    pnl = proceeds - (shares * entry_price * (1 + self.config.commission))

                    cash += proceeds
                    position = 0

                    trades.append({
                        "type": "sell",
                        "price": sell_price,
                        "shares": shares,
                        "date": str(dates[i]),
                        "pnl": pnl,
                        "pnl_percent": pnl_percent * 100,
                        "reason": reason
                    })

                    shares = 0
                    entry_price = 0.0

            current_value = cash + (shares * close_prices[i] if position == 1 else 0)
            equity_curve.append(current_value)

        if position == 1:
            final_price = close_prices[-1] * (1 - self.config.slippage)
            pnl_percent = (final_price - entry_price) / entry_price
            proceeds = shares * final_price * (1 - self.config.commission)
            pnl = proceeds - (shares * entry_price * (1 + self.config.commission))

            cash += proceeds

            trades.append({
                "type": "sell",
                "price": final_price,
                "shares": shares,
                "date": str(dates[-1]),
                "pnl": pnl,
                "pnl_percent": pnl_percent * 100,
                "reason": "end_of_period"
            })

            shares = 0

        final_value = cash
        total_return = (final_value - initial_cash) / initial_cash * 100

        max_drawdown = self._calculate_max_drawdown(equity_curve)

        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

        avg_win = sum(t.get("pnl", 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t.get("pnl", 0) for t in losing_trades) / len(losing_trades)) if losing_trades else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        sharpe_ratio = self._calculate_sharpe_ratio(trades, initial_cash)

        return BacktestResult(
            code=df["code"].iloc[0] if "code" in df.columns else "UNKNOWN",
            total_return=round(total_return, 2),
            annualized_return=round(total_return * (252 / max(len(df), 1)), 2),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            win_rate=round(win_rate, 2),
            profit_loss_ratio=round(profit_loss_ratio, 2),
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            final_value=round(final_value, 2),
            trades=trades,
            equity_curve=equity_curve
        )

    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
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

        return max_dd

    def _calculate_sharpe_ratio(self, trades: List[Dict[str, Any]], initial_cash: float) -> float:
        if not trades:
            return 0.0

        returns = []
        for t in trades:
            pnl = t.get("pnl", 0)
            if initial_cash > 0:
                returns.append(pnl / initial_cash)

        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        risk_free_rate = 0.03 / 365
        sharpe = (mean_return - risk_free_rate) / std_return * np.sqrt(252)

        return sharpe


class SignalGenerator:
    @staticmethod
    def ma_cross_signals(df: pd.DataFrame, fast: int = 10, slow: int = 30) -> pd.Series:
        df = df.sort_values("date").copy()
        close = df["close"]

        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()

        signals = pd.Series(0, index=df.index)
        signals[(ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))] = 1
        signals[(ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))] = -1

        return signals

    @staticmethod
    def momentum_signals(df: pd.DataFrame, period: int = 20, threshold: float = 0.05) -> pd.Series:
        df = df.sort_values("date").copy()
        close = df["close"]

        momentum = close.pct_change(period)

        signals = pd.Series(0, index=df.index)
        signals[momentum > threshold] = 1
        signals[momentum < -threshold] = -1

        return signals

    @staticmethod
    def rsi_signals(df: pd.DataFrame, period: int = 14, lower: float = 30, upper: float = 70) -> pd.Series:
        df = df.sort_values("date").copy()
        close = df["close"]

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        signals = pd.Series(0, index=df.index)
        signals[(rsi < lower) & (rsi.shift(1) >= lower)] = 1
        signals[(rsi > upper) & (rsi.shift(1) <= upper)] = -1

        return signals

    @staticmethod
    def volume_breakout_signals(df: pd.DataFrame, period: int = 20, multiplier: float = 1.5) -> pd.Series:
        df = df.sort_values("date").copy()

        if "volume" not in df.columns:
            return pd.Series(0, index=df.index)

        volume = df["volume"]
        avg_volume = volume.rolling(period).mean()

        signals = pd.Series(0, index=df.index)
        signals[(volume > avg_volume * multiplier) & (volume.shift(1) <= avg_volume.shift(1) * multiplier)] = 1

        return signals


class AISelectorBacktest:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.backtest_engine = VectorizedBacktest(config)

    def backtest_strategy(
        self,
        codes: List[str],
        signals_func: callable,
        start_date: str,
        end_date: str,
        **kwargs
    ) -> Dict[str, Any]:
        from core.storage.mongo_storage import KlineStorage

        kline_storage = KlineStorage()
        results = []

        for code in codes:
            try:
                klines = kline_storage.query_by_date_range(
                    code=code,
                    date_field="date",
                    start_date=start_date,
                    end_date=end_date
                )

                if len(klines) < 30:
                    continue

                df = pd.DataFrame(klines)
                df["code"] = code

                signals = signals_func(df)

                result = self.backtest_engine.run(
                    df=df,
                    signals=signals,
                    initial_cash=self.config.initial_cash / len(codes),
                    stop_loss=kwargs.get("stop_loss", self.config.stop_loss),
                    take_profit=kwargs.get("take_profit", self.config.take_profit)
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Backtest failed for {code}: {e}")

        return self._aggregate_results(results)

    def _aggregate_results(self, results: List[BacktestResult]) -> Dict[str, Any]:
        if not results:
            return {"error": "No successful backtests"}

        total_returns = [r.total_return for r in results]
        avg_return = sum(total_returns) / len(total_returns)

        wins = [r for r in results if r.total_return > 0]
        win_rate = len(wins) / len(results) * 100

        all_trades = []
        for r in results:
            all_trades.extend(r.trades)

        total_pnl = sum(t.get("pnl", 0) for t in all_trades)
        max_drawdowns = [r.max_drawdown for r in results]
        avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns)

        sharpe_ratios = [r.sharpe_ratio for r in results]
        avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0

        return {
            "total_codes": len(results),
            "avg_return": round(avg_return, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(all_trades),
            "total_pnl": round(total_pnl, 2),
            "avg_max_drawdown": round(avg_max_drawdown, 2),
            "avg_sharpe_ratio": round(avg_sharpe, 2),
            "individual_results": [r.to_dict() for r in results[:10]]
        }


vectorized_backtest = VectorizedBacktest()
ai_backtest = AISelectorBacktest()