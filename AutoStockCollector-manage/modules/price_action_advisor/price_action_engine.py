"""PriceActionEngine — 价格行为学主编排器。"""
import math
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from utils.logger import get_logger
from .config import PAConfig
from .fetcher import get_kline, get_spot, _normalize_code
from .market_structure import detect_market_structure
from .supply_demand import analyze_supply_demand
from .signal_generator import generate_signal
from .risk_manager import calculate_trade_plan
from .backtest import backtest_signal, get_backtest_cache, save_backtest_cache, _backtest_cache_key

logger = get_logger(__name__)


class PriceActionEngine:
    """价格行为分析引擎：获取 K 线 → 市场结构 → 供需区 → 信号 → 风控。"""

    def analyze(
        self,
        symbol: str,
        timeframe: str = "daily",
        risk_pct: float = 0.02,
        account_balance: float = 100000.0,
        use_ai: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """对单只股票执行全链路分析。

        Args:
            symbol: 股票代码（如 "300750" 或 "SZ300750"）
            timeframe: K 线周期
            risk_pct: 单笔风险比例
            account_balance: 账户总资金
            use_ai: 是否启用 LLM 分析解读
            progress_callback: 进度回调 (progress%, message)
        Returns:
            signal dict
        """
        def report(pct: int, msg: str):
            if progress_callback:
                progress_callback(pct, msg)
            logger.info(f"[PAEngine] {pct}% {msg}")

        try:
            report(5, f"开始分析 {symbol} ({timeframe})")

            bars = get_kline(symbol, timeframe, count=PAConfig.KLINE_DAYS)
            if not bars or len(bars) < PAConfig.MIN_KLINE_BARS:
                report(100, "K 线数据不足")
                return {
                    "symbol": symbol,
                    "signal": "NO_DATA",
                    "error": f"K 线数据不足 ({len(bars) if bars else 0}/{PAConfig.MIN_KLINE_BARS})",
                }
            report(20, "K 线数据获取完成")

            spot_data = get_spot([symbol])
            name = ""
            if spot_data:
                norm = _normalize_code(symbol)
                entry = spot_data.get(norm) or spot_data.get(symbol) or None
                if entry:
                    name = entry.get("name", "")
                else:
                    for v in spot_data.values():
                        if v.get("name"):
                            name = v["name"]
                            break

            if not name:
                try:
                    from config.database import DatabaseConfig
                    db = DatabaseConfig.get_database()
                    for col in ("stock_valuation", "stock_info"):
                        info = db[col].find_one({"code": {"$regex": symbol + r"$"}})
                        if info and info.get("name"):
                            name = info["name"]
                            break
                except Exception:
                    pass

            report(35, "实时行情获取完成")

            market_struct = detect_market_structure(bars)
            report(50, "市场结构分析完成")

            # 多周期融合：自动拉高一个周期做趋势过滤
            htf_map = {"5m": "30m", "15m": "60m", "30m": "daily", "60m": "daily", "daily": "weekly", "weekly": "monthly"}
            htf = htf_map.get(timeframe, "daily")
            if htf != timeframe:
                htf_bars = get_kline(symbol, htf, count=PAConfig.KLINE_DAYS)
                if htf_bars and len(htf_bars) >= PAConfig.MIN_KLINE_BARS:
                    htf_struct = detect_market_structure(htf_bars)
                    htf_trend = htf_struct.get("trend", "Ranging")
                    htf_structure = htf_struct.get("structure", "Ranging")
                    current_trend = market_struct.get("trend", "Ranging")
                    is_htf_bullish = htf_trend in ("Bullish", "Strong Bullish")
                    is_htf_bearish = htf_trend in ("Bearish", "Strong Bearish")
                    is_tf_bullish = current_trend in ("Bullish", "Strong Bullish")
                    is_tf_bearish = current_trend in ("Bearish", "Strong Bearish")

                    market_struct["htf_trend"] = htf_trend
                    market_struct["htf_timeframe"] = htf
                    market_struct["htf_structure"] = htf_structure
                    market_struct["htf_swing_high"] = htf_struct.get("last_swing_high")
                    market_struct["htf_swing_low"] = htf_struct.get("last_swing_low")

                    # HTF 趋势成熟度判断：Strong Bullish 表示已经 3 次 HH，可能接近末端
                    htf_mature = htf_structure in ("Strong Bullish", "Strong Bearish")
                    market_struct["htf_mature"] = htf_mature

                    # HTF 支撑/阻力距离
                    current_price = bars[-1]["close"]
                    htf_high = htf_struct.get("last_swing_high")
                    htf_low = htf_struct.get("last_swing_low")
                    if htf_high and current_price:
                        htf_resist_pct = (htf_high - current_price) / current_price * 100
                        market_struct["htf_resist_pct"] = round(htf_resist_pct, 1)
                    if htf_low and current_price:
                        htf_support_pct = (current_price - htf_low) / current_price * 100
                        market_struct["htf_support_pct"] = round(htf_support_pct, 1)

                    trend_conflict = False
                    warnings = []
                    if is_tf_bullish and is_htf_bearish:
                        trend_conflict = True
                        warnings.append(f"次级上升但{htf}下降 — 逆大势信号降级")
                    elif is_tf_bearish and is_htf_bullish:
                        trend_conflict = True
                        warnings.append(f"次级下降但{htf}上升 — 逆大势信号降级")

                    if htf_mature:
                        mature_dir = "上升" if htf_trend == "Bullish" else "下降"
                        warnings.append(f"{htf}趋势已到第3次HH，{mature_dir}可能接近末端")
                        if is_tf_bullish and htf_trend == "Bullish":
                            warnings.append(f"{htf}趋势成熟，做多需谨慎")

                    # 价格靠近 HTF 阻力/支撑
                    if htf_high and current_price and abs(htf_resist_pct) < 3:
                        warnings.append(f"价格接近{htf}阻力 {htf_high}")
                    if htf_low and current_price and abs(htf_support_pct) < 3:
                        warnings.append(f"价格接近{htf}支撑 {htf_low}")

                    market_struct["trend_conflict"] = "conflict" if trend_conflict else None
                    market_struct["trend_warning"] = "; ".join(warnings) if warnings else ""
                else:
                    market_struct["htf_trend"] = None
                    market_struct["trend_conflict"] = None
                    market_struct["trend_warning"] = ""
            else:
                market_struct["htf_trend"] = None
                market_struct["trend_conflict"] = None
                market_struct["trend_warning"] = ""

            sd_result = analyze_supply_demand(bars)
            report(65, "供需区识别完成")

            signal = generate_signal(symbol, name, bars, market_struct, sd_result)
            report(75, "信号生成完成")

            # 若高周期趋势冲突或成熟，降级信号（互斥：冲突 > 成熟）
            conflict = market_struct.get("trend_conflict")
            htf_mature = market_struct.get("htf_mature", False)
            sig_type = signal.get("signal", "NO_TRADE")
            downgraded = False
            if conflict and sig_type in ("BUY_SETUP", "SELL_SETUP"):
                downgrade_map = {"BUY_SETUP": "WEAK_BUY", "SELL_SETUP": "WEAK_SELL"}
                signal["signal"] = downgrade_map.get(sig_type, sig_type)
                signal["confidence"] = max(signal["confidence"] - 1, 1)
                signal["reasons"].insert(0, f"⚠️ {market_struct.get('trend_warning', '')}")
                downgraded = True
            elif htf_mature and not downgraded:
                # HTF 趋势成熟时，同向信号也降一级；若已有冲突降级则不再叠加
                is_long = sig_type in ("BUY_SETUP", "WEAK_BUY")
                htf_bull = market_struct.get("htf_trend") in ("Bullish", "Strong Bullish")
                if is_long and htf_bull:
                    if sig_type == "BUY_SETUP":
                        signal["signal"] = "WEAK_BUY"
                    signal["confidence"] = max(signal["confidence"] - 1, 1)
                    signal["reasons"].insert(0, f"⚠️ {market_struct.get('trend_warning', '')}")
                elif not is_long and not htf_bull:
                    if sig_type == "SELL_SETUP":
                        signal["signal"] = "WEAK_SELL"
                    signal["confidence"] = max(signal["confidence"] - 1, 1)
                    signal["reasons"].insert(0, f"⚠️ {market_struct.get('trend_warning', '')}")

            current_price = bars[-1]["close"]
            demand_zones = sd_result.get("demand_zones", [])
            supply_zones = sd_result.get("supply_zones", [])
            atr = sd_result.get("atr", 0)

            from .risk_manager import VALID_LONG_SIGNALS, VALID_SHORT_SIGNALS
            if signal["signal"] in VALID_LONG_SIGNALS:
                final_risk = risk_pct if signal["signal"] == "BUY_SETUP" else risk_pct * PAConfig.WEAK_SIGNAL_RISK_FACTOR
                trade_plan = calculate_trade_plan(
                    entry_price=current_price,
                    signal_type=signal["signal"],
                    atr=atr,
                    demand_zones=demand_zones,
                    supply_zones=supply_zones,
                    account_balance=account_balance,
                    risk_pct=final_risk,
                )
                signal["trade_plan"] = trade_plan
            elif signal["signal"] in VALID_SHORT_SIGNALS:
                final_risk = risk_pct if signal["signal"] == "SELL_SETUP" else risk_pct * PAConfig.WEAK_SIGNAL_RISK_FACTOR
                trade_plan = calculate_trade_plan(
                    entry_price=current_price,
                    signal_type=signal["signal"],
                    atr=atr,
                    demand_zones=demand_zones,
                    supply_zones=supply_zones,
                    account_balance=account_balance,
                    risk_pct=final_risk,
                )
                signal["trade_plan"] = trade_plan

            # 回测验证：用历史数据验证信号逻辑（带缓存）
            try:
                bt_step = getattr(PAConfig, "BACKTEST_STEP", 5)
                bt_hold = getattr(PAConfig, "BACKTEST_HOLD_BARS", 10)
                bt_cache_key = _backtest_cache_key(symbol, timeframe, len(bars), bars[-1].get("date", ""))
                bt_result = None
                try:
                    from config.database import DatabaseConfig
                    _db = DatabaseConfig.get_database()
                    bt_result = get_backtest_cache(_db, bt_cache_key)
                except Exception:
                    pass
                if bt_result is None:
                    bt_result = backtest_signal(
                        symbol, name, bars,
                        min_lookback=max(60, PAConfig.MIN_KLINE_BARS),
                        step=bt_step, hold_bars=bt_hold,
                        atr_multiplier_sl=PAConfig.ATR_STOP_MULTIPLIER,
                        reward_ratio=PAConfig.REWARD_MULTIPLIER,
                        account_balance=account_balance,
                        risk_pct=risk_pct,
                    )
                    try:
                        save_backtest_cache(_db, bt_cache_key, symbol, timeframe, bt_result)
                    except Exception:
                        pass
                if bt_result.get("total_trades", 0) >= 5:
                    signal["backtest"] = {
                        "total_trades": bt_result["total_trades"],
                        "win_rate": bt_result["win_rate"],
                        "avg_r": bt_result["avg_r"],
                        "profit_factor": bt_result["profit_factor"],
                        "max_drawdown_pct": bt_result["max_drawdown_pct"],
                        "sharpe_ratio": bt_result["sharpe_ratio"],
                        "max_consecutive_losses": bt_result["max_consecutive_losses"],
                        "expectancy": bt_result["expectancy"],
                    }
                    report(82, "回测验证完成")
                else:
                    signal["backtest"] = {"total_trades": 0, "message": "历史信号不足，无法回测"}
            except Exception as e:
                logger.warning(f"[PAEngine] backtest error: {e}")
                signal["backtest"] = {"error": str(e)}

            # 返回 K 线数据供前端渲染图表（最后 60 根）
            signal["timeframe"] = timeframe
            signal["updated_at"] = datetime.now().isoformat()
            signal["kline_bars"] = [
                {"time": b["date"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"]}
                for b in bars[-60:]
            ]

            report(85, "风控计算完成")

            # AI 分析
            if use_ai:
                report(90, "AI 分析中...")
                try:
                    from .ai_analyzer import get_ai_commentary
                    commentary = get_ai_commentary(signal)
                    if commentary:
                        signal["ai_commentary"] = commentary
                        report(95, "AI 分析完成")
                    else:
                        report(95, "AI 分析跳过（无结果）")
                except Exception as e:
                    logger.warning(f"[PAEngine] AI analysis error: {e}")
                    report(95, "AI 分析异常")

            report(100, "分析完成")
            logger.info(
                f"[PAEngine] {symbol} signal={signal['signal']} "
                f"confidence={signal['confidence']} price={current_price}"
            )
            return signal

        except Exception as e:
            logger.error(f"[PAEngine] {symbol} failed: {e}")
            report(100, f"分析失败: {e}")
            return {"symbol": symbol, "signal": "ERROR", "error": str(e)}
