"""
策略回测引擎 - 工业化重构版
对接ai_selector，支持AI策略回测、标准化输出
"""
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
import pandas as pd
import numpy as np
from utils.logger import get_logger


logger = get_logger(__name__)


class BacktestSignal(Enum):
    MA_CROSS = "ma_cross"
    MOMENTUM = "momentum"
    RSI = "rsi"
    VOLUME_BREAKOUT = "volume_breakout"
    FUND_FLOW = "fund_flow"
    AI_SELECTOR = "ai_selector"


@dataclass
class BacktestConfig:
    initial_cash: float = 1000000.0
    commission: float = 0.001
    slippage: float = 0.001
    stop_loss: float = 0.05
    take_profit: float = 0.10
    max_position: float = 0.20
    market_phase: str = "consolidation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_cash": self.initial_cash,
            "commission": self.commission,
            "slippage": self.slippage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_position": self.max_position,
            "market_phase": self.market_phase
        }


@dataclass
class BacktestTrade:
    code: str
    type: str
    price: float
    shares: int
    date: str
    pnl: float = 0.0
    pnl_percent: float = 0.0
    reason: str = ""
    holding_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "type": self.type,
            "price": self.price,
            "shares": self.shares,
            "date": self.date,
            "pnl": round(self.pnl, 2),
            "pnl_percent": round(self.pnl_percent, 2),
            "reason": self.reason,
            "holding_days": self.holding_days
        }


@dataclass
class BacktestMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_profit: float
    avg_loss: float
    max_profit: float
    max_loss: float
    avg_holding_days: float
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": round(self.total_return, 2),
            "annualized_return": round(self.annualized_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "win_rate": round(self.win_rate, 2),
            "profit_loss_ratio": round(self.profit_loss_ratio, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_profit": round(self.avg_profit, 2),
            "avg_loss": round(self.avg_loss, 2),
            "max_profit": round(self.max_profit, 2),
            "max_loss": round(self.max_loss, 2),
            "avg_holding_days": round(self.avg_holding_days, 1)
        }


@dataclass
class BacktestResult:
    code: str
    initial_value: float
    final_value: float
    metrics: BacktestMetrics
    trades: List[BacktestTrade]
    equity_curve: List[float]
    signal_type: str
    start_date: str
    end_date: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "initial_value": round(self.initial_value, 2),
            "final_value": round(self.final_value, 2),
            "metrics": self.metrics.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "signal_type": self.signal_type,
            "start_date": self.start_date,
            "end_date": self.end_date
        }


class SignalGenerator:
    @staticmethod
    def ma_cross(df: pd.DataFrame, fast: int = 10, slow: int = 30) -> pd.Series:
        df = df.sort_values("date").copy()
        close = df["close"]

        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()

        signals = pd.Series(0, index=df.index)
        signals[(ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))] = 1
        signals[(ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))] = -1

        return signals

    @staticmethod
    def momentum(df: pd.DataFrame, period: int = 20, threshold: float = 0.05) -> pd.Series:
        df = df.sort_values("date").copy()
        close = df["close"]

        mom = close.pct_change(period)

        signals = pd.Series(0, index=df.index)
        signals[mom > threshold] = 1
        signals[mom < -threshold] = -1

        return signals

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14, lower: float = 30, upper: float = 70) -> pd.Series:
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
    def volume_breakout(df: pd.DataFrame, period: int = 20, multiplier: float = 1.5) -> pd.Series:
        df = df.sort_values("date").copy()

        if "volume" not in df.columns:
            return pd.Series(0, index=df.index)

        volume = df["volume"]
        avg_vol = volume.rolling(period).mean()

        signals = pd.Series(0, index=df.index)
        signals[(volume > avg_vol * multiplier) & (volume.shift(1) <= avg_vol.shift(1) * multiplier)] = 1

        return signals

    @staticmethod
    def ai_selector(df: pd.DataFrame, scores: Dict[str, float], threshold: float = 60) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        return signals


class VectorBacktestEngine:
    _EXCLUDED_PREFIXES = ("*ST", "ST", "PT", "退市")

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.kline_storage = None

    def run(
        self,
        code: str,
        signal_type: BacktestSignal,
        start_date: str,
        end_date: str,
        signal_params: Optional[Dict[str, Any]] = None,
        ai_scores: Optional[Dict[str, float]] = None
    ) -> Optional[BacktestResult]:
        from core.storage.mongo_storage import KlineStorage

        kline_storage = KlineStorage()
        klines = kline_storage.query_by_date_range(
            code=code,
            date_field="date",
            start_date=start_date,
            end_date=end_date
        )

        if len(klines) < 30:
            logger.warning(f"Insufficient data for {code}")
            return None

        df = pd.DataFrame(klines)
        if "date" not in df.columns:
            return None

        df = df.sort_values("date").reset_index(drop=True)

        if "pct_chg" in df.columns or "涨跌幅" in df.columns:
            pct_col = "pct_chg" if "pct_chg" in df.columns else "涨跌幅"
            df = df[df[pct_col].apply(
                lambda x: abs(float(x)) < 9.8 if x not in (None, "") else True
            )]

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0

        signals = self._generate_signals(df, signal_type, signal_params or {}, ai_scores)

        result = self._execute_backtest(df, code, signals, start_date, end_date, signal_type.value)

        return result

    def _generate_signals(
        self,
        df: pd.DataFrame,
        signal_type: BacktestSignal,
        params: Dict[str, Any],
        ai_scores: Optional[Dict[str, float]]
    ) -> pd.Series:
        if signal_type == BacktestSignal.MA_CROSS:
            return SignalGenerator.ma_cross(df, params.get("fast", 10), params.get("slow", 30))
        elif signal_type == BacktestSignal.MOMENTUM:
            return SignalGenerator.momentum(df, params.get("period", 20), params.get("threshold", 0.05))
        elif signal_type == BacktestSignal.RSI:
            return SignalGenerator.rsi(df, params.get("period", 14), params.get("lower", 30), params.get("upper", 70))
        elif signal_type == BacktestSignal.VOLUME_BREAKOUT:
            return SignalGenerator.volume_breakout(df, params.get("period", 20), params.get("multiplier", 1.5))
        elif signal_type == BacktestSignal.AI_SELECTOR:
            return SignalGenerator.ai_selector(df, ai_scores or {}, params.get("threshold", 60))
        else:
            return SignalGenerator.ma_cross(df)

    def _execute_backtest(
        self,
        df: pd.DataFrame,
        code: str,
        signals: pd.Series,
        start_date: str,
        end_date: str,
        signal_type: str
    ) -> BacktestResult:
        cash = self.config.initial_cash
        position = 0
        shares = 0
        entry_price = 0.0
        entry_date = ""

        trades = []
        equity_curve = [cash]

        stop_loss = self.config.stop_loss
        take_profit = self.config.take_profit

        if self.config.market_phase == "bull":
            stop_loss = 0.07
            take_profit = 0.15
        elif self.config.market_phase == "bear":
            stop_loss = 0.04
            take_profit = 0.06

        for i in range(len(df)):
            current_price = df.iloc[i]["close"]
            current_date = str(df.iloc[i]["date"])[:10]
            buy_price = current_price * (1 + self.config.slippage)
            sell_price = current_price * (1 - self.config.slippage)

            if position == 0 and signals.iloc[i] == 1 and cash >= buy_price:
                position_value = cash * self.config.max_position
                shares_to_buy = int(position_value / buy_price / 100) * 100
                cost = shares_to_buy * buy_price * (1 + self.config.commission)

                if cost <= cash and shares_to_buy > 0:
                    shares = shares_to_buy
                    cash -= cost
                    entry_price = buy_price
                    entry_date = current_date
                    position = 1

                    trades.append(BacktestTrade(
                        code=code, type="buy", price=current_price,
                        shares=shares, date=current_date
                    ))

            elif position == 1:
                pnl_percent = (sell_price - entry_price) / entry_price
                should_sell = False
                reason = ""

                if pnl_percent <= -stop_loss:
                    should_sell = True
                    reason = "stop_loss"
                elif pnl_percent >= take_profit:
                    should_sell = True
                    reason = "take_profit"
                elif signals.iloc[i] == -1:
                    should_sell = True
                    reason = "signal_exit"

                if should_sell:
                    holding_days = (pd.to_datetime(current_date) - pd.to_datetime(entry_date)).days

                    proceeds = shares * sell_price * (1 - self.config.commission)
                    pnl = proceeds - (shares * entry_price * (1 + self.config.commission))
                    pnl_percent = (sell_price - entry_price) / entry_price * 100

                    cash += proceeds

                    trades.append(BacktestTrade(
                        code=code, type="sell", price=current_price,
                        shares=shares, date=current_date,
                        pnl=pnl, pnl_percent=pnl_percent,
                        reason=reason, holding_days=holding_days
                    ))

                    shares = 0
                    entry_price = 0.0
                    position = 0

            current_value = cash + (shares * current_price if position == 1 else 0)
            equity_curve.append(current_value)

        if position == 1:
            final_price = df.iloc[-1]["close"] * (1 - self.config.slippage)
            holding_days = (pd.to_datetime(str(df.iloc[-1]["date"])[:10]) - pd.to_datetime(entry_date)).days
            proceeds = shares * final_price * (1 - self.config.commission)
            pnl = proceeds - (shares * entry_price * (1 + self.config.commission))
            pnl_percent = (final_price - entry_price) / entry_price * 100

            cash += proceeds

            trades.append(BacktestTrade(
                code=code, type="sell", price=final_price,
                shares=shares, date=str(df.iloc[-1]["date"])[:10],
                pnl=pnl, pnl_percent=pnl_percent,
                reason="end_of_period", holding_days=holding_days
            ))

        final_value = cash
        metrics = self._calculate_metrics(self.config.initial_cash, final_value, trades, start_date, end_date)

        return BacktestResult(
            code=code,
            initial_value=self.config.initial_cash,
            final_value=final_value,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            signal_type=signal_type,
            start_date=start_date,
            end_date=end_date
        )

    def _calculate_metrics(
        self,
        initial: float,
        final: float,
        trades: List[BacktestTrade],
        start_date: str,
        end_date: str
    ) -> BacktestMetrics:
        total_return = (final - initial) / initial * 100 if initial > 0 else 0

        days = 365
        try:
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            days = max(1, (end - start).days)
        except:
            pass

        years = days / 365
        annualized_return = ((final / initial) ** (1 / years) - 1) * 100 if years > 0 and initial > 0 else 0

        equity = [initial]
        cumulative = initial
        for t in trades:
            cumulative += t.pnl
            equity.append(cumulative)

        peak = equity[0]
        max_dd = 0.0
        for v in equity:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        closing_trades = [t for t in trades if t.type == "sell"]
        winning = [t for t in closing_trades if t.pnl > 0]
        losing = [t for t in closing_trades if t.pnl < 0]

        win_rate = len(winning) / len(closing_trades) * 100 if closing_trades else 0

        avg_profit = sum(t.pnl for t in winning) / len(winning) if winning else 0
        avg_loss = abs(sum(t.pnl for t in losing) / len(losing)) if losing else 0
        pl_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

        returns = [t.pnl / initial for t in closing_trades if initial > 0]
        sharpe = self._calc_sharpe(returns)

        downside_returns = [r for r in returns if r < 0]
        sortino = self._calc_sortino(returns, downside_returns)

        avg_holding = sum(t.holding_days for t in closing_trades) / len(closing_trades) if closing_trades else 0
        max_profit = max((t.pnl for t in closing_trades), default=0)
        max_loss = min((t.pnl for t in closing_trades), default=0)

        return BacktestMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            win_rate=win_rate,
            profit_loss_ratio=pl_ratio,
            total_trades=len(closing_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            max_profit=max_profit,
            max_loss=max_loss,
            avg_holding_days=avg_holding,
            equity_curve=equity
        )

    def _calc_sharpe(self, returns: List[float], risk_free: float = 0.03) -> float:
        if len(returns) < 2:
            return 0.0
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret == 0:
            return 0.0
        excess = mean_ret - risk_free / 365
        return excess / std_ret * np.sqrt(252)

    def _calc_sortino(self, returns: List[float], downside: List[float]) -> float:
        if len(returns) < 2 or not downside:
            return 0.0
        mean_ret = np.mean(returns)
        down_std = np.std(downside) if len(downside) > 1 else 0
        if down_std == 0:
            return 0.0
        excess = mean_ret - 0.03 / 365
        return excess / down_std * np.sqrt(252)


class BacktestEngine:
    _EXCLUDED_PREFIXES = ("*ST", "ST", "PT", "退市")

    def __init__(self):
        from core.storage.mongo_storage import KlineStorage
        self.kline_storage = KlineStorage()
        self.vector_engine = VectorBacktestEngine()
        self._strategy_map = {
            "ma_cross": BacktestSignal.MA_CROSS,
            "momentum": BacktestSignal.MOMENTUM,
            "rsi": BacktestSignal.RSI,
            "volume_breakout": BacktestSignal.VOLUME_BREAKOUT,
            "fund_flow": BacktestSignal.VOLUME_BREAKOUT,
        }

    def run(
        self,
        strategy: str,
        codes: List[str],
        start_date: str,
        end_date: str,
        config: Optional[BacktestConfig] = None,
        signal_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        signal_type = self._strategy_map.get(strategy, BacktestSignal.MA_CROSS)

        codes = self._filter_excluded_codes(codes)
        if not codes:
            return {"error": "All codes filtered out (ST/delisted/illiquid)"}

        self.vector_engine.config = config or BacktestConfig()

        results = []
        all_trades = []

        for code in codes:
            try:
                result = self.vector_engine.run(
                    code=code,
                    signal_type=signal_type,
                    start_date=start_date,
                    end_date=end_date,
                    signal_params=signal_params
                )
                if result:
                    results.append(result)
                    all_trades.extend(result.trades)
            except Exception as e:
                logger.error(f"Backtest failed for {code}: {e}")

        if not results:
            return {"error": "No successful backtests"}

        aggregated = self._aggregate_results(results, len(codes))

        return {
            "strategy": strategy,
            "signal_type": signal_type.value,
            "start_date": start_date,
            "end_date": end_date,
            "total_codes": len(codes),
            "successful_backtests": len(results),
            "config": self.vector_engine.config.to_dict(),
            **aggregated,
            "sample_trades": [t.to_dict() for t in all_trades[:20]]
        }

    def run_ai_selector(
        self,
        selection_results: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        config: Optional[BacktestConfig] = None,
        signal_type: str = "ma_cross"
    ) -> Dict[str, Any]:
        codes = [r["code"] for r in selection_results if r.get("score", 0) >= 60]

        if not codes:
            return {"error": "No valid stocks from AI selection results"}

        return self.run(
            strategy=signal_type,
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            config=config
        )

    def run_comparison(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        strategies: List[str],
        config: Optional[BacktestConfig] = None
    ) -> Dict[str, Any]:
        comparison_results = {}

        for strategy in strategies:
            try:
                result = self.run(
                    strategy=strategy,
                    codes=codes,
                    start_date=start_date,
                    end_date=end_date,
                    config=config
                )
                if "error" not in result:
                    comparison_results[strategy] = {
                        "total_return": result.get("total_return", 0),
                        "win_rate": result.get("win_rate", 0),
                        "sharpe_ratio": result.get("sharpe_ratio", 0),
                        "max_drawdown": result.get("max_drawdown", 0),
                        "total_trades": result.get("total_trades", 0)
                    }
            except Exception as e:
                logger.error(f"Strategy {strategy} comparison failed: {e}")

        best_strategy = max(
            comparison_results.items(),
            key=lambda x: x[1].get("sharpe_ratio", 0) if x[1].get("total_return", 0) > 0 else 0,
            default=(None, {})
        )

        return {
            "comparison": comparison_results,
            "best_strategy": best_strategy[0],
            "best_metrics": best_strategy[1] if best_strategy[1] else {},
            "timestamp": datetime.now().isoformat()
        }

    def _filter_excluded_codes(self, codes: List[str]) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage
        try:
            info_storage = StockInfoStorage()
            valid = []
            for code in codes:
                info = info_storage.get_by_code(code)
                if info:
                    name = info.get("name", "") or ""
                    if any(name.startswith(p) for p in self._EXCLUDED_PREFIXES):
                        continue
                    status = info.get("status", "")
                    if status in ("退市", "delisted"):
                        continue
                valid.append(code)
            return valid
        except Exception as e:
            logger.warning(f"Code filter failed: {e}")
            return codes

    def _aggregate_results(self, results: List[BacktestResult], total_codes: int) -> Dict[str, Any]:
        total_returns = [r.metrics.total_return for r in results]
        avg_return = sum(total_returns) / len(total_returns) if total_returns else 0

        wins = [r for r in results if r.metrics.total_return > 0]
        win_rate = len(wins) / len(results) * 100 if results else 0

        final_values = [r.final_value for r in results]
        total_final = sum(final_values)
        total_return = (total_final - self.vector_engine.config.initial_cash * len(results)) / (self.vector_engine.config.initial_cash * len(results)) * 100 if self.vector_engine.config.initial_cash > 0 and len(results) > 0 else 0

        max_drawdowns = [r.metrics.max_drawdown for r in results]
        avg_max_dd = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0

        all_trades = []
        for r in results:
            all_trades.extend(r.trades)

        total_trades = len([t for t in all_trades if t.type == "sell"])

        sharpe_ratios = [r.metrics.sharpe_ratio for r in results]
        avg_sharpe = sum(s for s in sharpe_ratios if s > 0) / max(1, sum(1 for s in sharpe_ratios if s > 0))

        return {
            "total_return": round(total_return, 2),
            "avg_return": round(avg_return, 2),
            "win_rate": round(win_rate, 2),
            "avg_max_drawdown": round(avg_max_dd, 2),
            "total_trades": total_trades,
            "avg_sharpe_ratio": round(avg_sharpe, 2),
            "final_value": round(total_final, 2)
        }


backtest_engine = BacktestEngine()