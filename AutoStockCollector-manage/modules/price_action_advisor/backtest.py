"""PA 信号回测 — 用历史 K 线跑信号逻辑，统计真实胜率/盈亏比/夏普。
使用 risk_manager.calculate_trade_plan 计算止损，与实盘完全一致。"""
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

from .config import PAConfig
from .market_structure import detect_market_structure
from .supply_demand import analyze_supply_demand
from .signal_generator import generate_signal
from .risk_manager import calculate_trade_plan

BACKTEST_CACHE_TTL = 3600  # 1 小时，与 K 线缓存匹配


def _backtest_cache_key(symbol: str, timeframe: str, num_bars: int, last_bar_date: str) -> str:
    return f"bt|{symbol}|{timeframe}|{num_bars}|{last_bar_date}"


def get_backtest_cache(db, cache_key: str) -> Optional[Dict[str, Any]]:
    doc = db.pa_backtest_cache.find_one(
        {"cache_key": cache_key, "created_at": {"$gte": datetime.now() - timedelta(seconds=BACKTEST_CACHE_TTL)}}
    )
    return doc["backtest_result"] if doc else None


def save_backtest_cache(db, cache_key: str, symbol: str, timeframe: str, backtest_result: Dict[str, Any]) -> None:
    db.pa_backtest_cache.update_one(
        {"cache_key": cache_key},
        {"$set": {
            "cache_key": cache_key,
            "symbol": symbol,
            "timeframe": timeframe,
            "backtest_result": backtest_result,
            "created_at": datetime.now(),
        }},
        upsert=True,
    )

logger = get_logger(__name__)


def backtest_signal(
    symbol: str,
    name: str,
    bars: List[Dict],
    min_lookback: int = 60,
    step: int = 5,
    hold_bars: int = 10,
    atr_multiplier_sl: float = 1.5,
    reward_ratio: float = 2.0,
    account_balance: float = 100000.0,
    risk_pct: float = 0.02,
) -> Dict[str, Any]:
    """在历史 K 线上回测信号逻辑。

    对每根历史 bar（从 min_lookback 开始，每 step 根采样一次），
    用当时的视角（仅看截至该 bar 的数据）运行完整信号生成，
    用 risk_manager 计算止损（与实盘一致），
    然后检查后续 hold_bars 根 bar 的价格行为：
    - 先碰止损 → 亏损
    - 先碰止盈 → 盈利
    - 都没碰 → exit 盈亏

    返回回测统计。
    """
    if len(bars) < min_lookback + hold_bars:
        return {"error": f"数据不足 ({len(bars)} < {min_lookback + hold_bars})"}

    trades = []
    n = len(bars)

    for i in range(min_lookback, n - hold_bars, step):
        window = bars[:i + 1]
        entry_price = bars[i]["close"]

        market_struct = detect_market_structure(window)
        sd_result = analyze_supply_demand(window)
        signal = generate_signal(symbol, name, window, market_struct, sd_result)

        sig_type = signal.get("signal", "NO_TRADE")
        if sig_type not in ("BUY_SETUP", "WEAK_BUY", "SELL_SETUP", "WEAK_SELL"):
            continue

        is_long = sig_type in ("BUY_SETUP", "WEAK_BUY")
        atr = sd_result.get("atr", 0)
        demand_zones = sd_result.get("demand_zones", [])
        supply_zones = sd_result.get("supply_zones", [])

        # 用 risk_manager 计算止损 — 与实盘完全一致
        trade_plan = calculate_trade_plan(
            entry_price=entry_price,
            signal_type=sig_type,
            atr=atr,
            demand_zones=demand_zones,
            supply_zones=supply_zones,
            account_balance=account_balance,
            risk_pct=risk_pct if sig_type in ("BUY_SETUP", "SELL_SETUP") else risk_pct * PAConfig.WEAK_SIGNAL_RISK_FACTOR,
        )
        stop_loss = trade_plan["stop_loss"]
        take_profit = trade_plan["take_profit"]
        sl_distance = abs(entry_price - stop_loss)

        exit_bar = None
        exit_price = None
        outcome = None

        for j in range(i + 1, min(i + 1 + hold_bars, n)):
            bar = bars[j]
            if is_long:
                if bar["low"] <= stop_loss:
                    exit_bar = j
                    exit_price = stop_loss
                    outcome = "loss"
                    break
                if bar["high"] >= take_profit:
                    exit_bar = j
                    exit_price = take_profit
                    outcome = "win"
                    break
            else:
                if bar["high"] >= stop_loss:
                    exit_bar = j
                    exit_price = stop_loss
                    outcome = "loss"
                    break
                if bar["low"] <= take_profit:
                    exit_bar = j
                    exit_price = take_profit
                    outcome = "win"
                    break

        if outcome is None:
            exit_bar = min(i + hold_bars, n - 1)
            exit_price = bars[exit_bar]["close"]
            if is_long:
                outcome = "win" if exit_price > entry_price else "loss"
            else:
                outcome = "win" if exit_price < entry_price else "loss"

        r_multiple = abs(exit_price - entry_price) / sl_distance if sl_distance > 0 else 0
        direction = 1 if is_long else -1
        pnl_pct = direction * (exit_price - entry_price) / entry_price * 100

        trades.append({
            "entry_bar": i,
            "entry_date": bars[i].get("date", ""),
            "exit_bar": exit_bar,
            "exit_date": bars[exit_bar].get("date", ""),
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "outcome": outcome,
            "r_multiple": round(r_multiple, 2),
            "pnl_pct": round(pnl_pct, 2),
            "signal": sig_type,
            "direction": "long" if is_long else "short",
        })

    if not trades:
        return {"total_trades": 0, "message": "历史中未触发交易信号"}

    total = len(trades)
    wins = [t for t in trades if t["outcome"] == "win"]
    losses = [t for t in trades if t["outcome"] == "loss"]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total * 100 if total > 0 else 0

    avg_r_win = sum(t["r_multiple"] for t in wins) / win_count if win_count > 0 else 0
    avg_r_loss = sum(t["r_multiple"] for t in losses) / loss_count if loss_count > 0 else 0
    avg_r = sum(t["r_multiple"] for t in trades) / total

    total_pnl_pct = sum(t["pnl_pct"] for t in trades)

    equity_curve = []
    equity = 1.0
    max_equity = 1.0
    max_drawdown = 0.0
    daily_returns = []

    for t in trades:
        ret = t["pnl_pct"] / 100.0
        equity *= (1 + ret)
        daily_returns.append(ret)
        if equity > max_equity:
            max_equity = equity
        dd = (max_equity - equity) / max_equity * 100
        if dd > max_drawdown:
            max_drawdown = dd
        equity_curve.append(round(equity, 4))

    win_rate_decimal = win_rate / 100.0
    expectancy = win_rate_decimal * avg_r_win - (1 - win_rate_decimal) * avg_r_loss

    max_consecutive_losses = 0
    current_consecutive = 0
    for t in trades:
        if t["outcome"] == "loss":
            current_consecutive += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive)
        else:
            current_consecutive = 0

    sharpe_ratio = 0
    if len(daily_returns) > 1:
        mean_ret = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
        if variance > 0:
            sharpe_ratio = round(mean_ret / math.sqrt(variance) * math.sqrt(252), 2)

    return {
        "total_trades": total,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 1),
        "avg_r": round(avg_r, 2),
        "avg_r_win": round(avg_r_win, 2),
        "avg_r_loss": round(avg_r_loss, 2),
        "expectancy": round(expectancy, 2),
        "profit_factor": round(abs(sum(t["r_multiple"] for t in wins) / max(sum(abs(t["r_multiple"]) for t in losses), 0.001)), 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "max_consecutive_losses": max_consecutive_losses,
        "sharpe_ratio": sharpe_ratio,
        "total_return_pct": round(total_pnl_pct, 2),
        "avg_return_per_trade": round(total_pnl_pct / total if total > 0 else 0, 2),
        "equity_curve": equity_curve,
        "trades": trades[-20:],
    }
