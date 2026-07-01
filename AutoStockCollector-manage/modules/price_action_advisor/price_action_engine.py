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
from .multi_timeframe import fuse_timefaces
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
        multi_tf_depth: str = "full",
    ) -> Dict[str, Any]:
        """对单只股票执行全链路分析。

        Args:
            symbol: 股票代码（如 "300750" 或 "SZ300750"）
            timeframe: K 线周期
            risk_pct: 单笔风险比例
            account_balance: 账户总资金
            use_ai: 是否启用 LLM 分析解读
            progress_callback: 进度回调 (progress%, message)
            multi_tf_depth: 多周期融合深度 — "full" 拉 weekly+monthly 三级；
                "fast" 仅 weekly 两级（扫描用，防超时）。默认 full。
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
            spot_price = 0.0
            if spot_data:
                norm = _normalize_code(symbol)
                entry = spot_data.get(norm) or spot_data.get(symbol) or None
                if entry:
                    name = entry.get("name", "")
                    spot_price = float(entry.get("price") or entry.get("current_price") or 0.0)
                else:
                    for v in spot_data.values():
                        if v.get("name"):
                            name = v["name"]
                            spot_price = float(v.get("price") or v.get("current_price") or 0.0)
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

            # 实时价守护：spot_price>0 且未偏离 K线收盘价 11% 以上才采用（防停牌/涨停板异常价），
            # 否则回退 bars[-1]["close"]（akshare 回退路径下为昨收，仍优于 0）。
            kline_close = bars[-1].get("close", 0.0) if bars else 0.0
            if spot_price > 0 and (kline_close <= 0 or abs(spot_price - kline_close) / kline_close <= 0.11):
                current_price = spot_price
            else:
                current_price = kline_close

            report(35, "实时行情获取完成")

            market_struct = detect_market_structure(bars)
            report(50, "市场结构分析完成")

            # 多周期融合：daily(触发) + weekly(中期) + monthly(宏观)，权重 monthly>weekly>daily
            tf_structs = self._collect_tf_structs(symbol, timeframe, market_struct, multi_tf_depth)
            fusion = fuse_timefaces(tf_structs)
            report(60, f"多周期融合完成（{fusion['resonance']}）")

            sd_result = analyze_supply_demand(bars)
            report(65, "供需区识别完成")

            signal = generate_signal(symbol, name, bars, market_struct, sd_result,
                                     current_price_override=current_price)
            report(75, "信号生成完成")

            # 融合结果作为宏观约束覆盖触发信号：
            # - fusion NO_TRADE（逆月线）→ 强制 NO_TRADE
            # - fusion WEAK_* → generate_signal 的强信号降为弱信号
            # - fusion NEUTRAL → 保持原值（大周期无趋势，由触发条件决定）
            # - fusion BUY_SETUP/SELL_SETUP → 保持 generate_signal 原值（共振不强行提升，触发条件仍需满足）
            hint = fusion["signal_hint"]
            orig_signal = signal.get("signal", "NO_TRADE")
            if hint == "NO_TRADE" and orig_signal not in ("NO_TRADE", "NO_DATA", "ERROR"):
                signal["signal"] = "NO_TRADE"
                signal["confidence"] = 0
                signal["reasons"].insert(0, f"⚠️ {fusion['resonance']}，逆大势不做")
            elif hint == "WEAK_BUY" and orig_signal == "BUY_SETUP":
                signal["signal"] = "WEAK_BUY"
                signal["confidence"] = max(signal["confidence"] - 1, 1)
                signal["reasons"].insert(0, f"⚠️ {fusion['resonance']}，强信号降级")
            elif hint == "WEAK_SELL" and orig_signal == "SELL_SETUP":
                signal["signal"] = "WEAK_SELL"
                signal["confidence"] = max(signal["confidence"] - 1, 1)
                signal["reasons"].insert(0, f"⚠️ {fusion['resonance']}，强信号降级")

            # 融合置信度调整（三周期共振 +1 封顶 5；月线逆势 -1 最低 1）
            if fusion["confidence_delta"] != 0 and signal.get("confidence", 0) > 0:
                signal["confidence"] = max(min(signal["confidence"] + fusion["confidence_delta"], 5), 1)

            # 融合警告（成熟度/冲突）追加到 reasons，不二次降级
            for w in fusion["warnings"]:
                signal["reasons"].append(f"⚠️ {w}")

            # 回写 htf_* 与 multi_tf 到 signal（修 P1：storage 读这些字段）
            weekly_struct = tf_structs.get("weekly") or {}
            monthly_struct = tf_structs.get("monthly") or {}
            signal["htf_trend"] = weekly_struct.get("trend")
            signal["htf_timeframe"] = "weekly" if weekly_struct else None
            signal["htf_structure"] = weekly_struct.get("structure")
            signal["htf_mature"] = (weekly_struct.get("structure") in ("Strong Bullish", "Strong Bearish")) if weekly_struct else False
            signal["htf_swing_high"] = weekly_struct.get("last_swing_high")
            signal["htf_swing_low"] = weekly_struct.get("last_swing_low")
            signal["trend_warning"] = "; ".join(fusion["warnings"]) if fusion["warnings"] else ""
            signal["trend_conflict"] = None  # 旧字段兼容，融合后不再用 conflict 降级
            signal["multi_tf"] = fusion["multi_tf"]

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
                        # 透传权益曲线与交易明细，供前端可视化（trades 末20条/equity_curve≤20点，增<2KB）
                        "equity_curve": bt_result.get("equity_curve", []),
                        "trades": bt_result.get("trades", []),
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

    def _collect_tf_structs(
        self,
        symbol: str,
        timeframe: str,
        daily_struct: Dict[str, Any],
        depth: str = "full",
    ) -> Dict[str, Dict[str, Any]]:
        """收集多周期市场结构供融合。depth=full 拉 weekly+monthly，fast 仅 weekly。

        主周期(daily/指定 timeframe)结构由调用方已算好传入，避免重复计算。
        HTF 周期映射：daily→weekly→monthly；其他周期升一级（5m→30m 等）。
        """
        tf_structs = {timeframe: daily_struct}
        htf_map = {
            "5m": "30m", "15m": "60m", "30m": "daily", "60m": "daily",
            "daily": "weekly", "weekly": "monthly",
        }
        # fast: 只升一级；full: 升两级（daily→weekly→monthly）
        chain = [htf_map.get(timeframe, "daily")]
        if depth == "full" and htf_map.get(htf_map.get(timeframe)):
            chain.append(htf_map[htf_map[timeframe]])
        for htf in chain:
            if htf == timeframe or htf in tf_structs:
                continue
            try:
                htf_bars = get_kline(symbol, htf, count=PAConfig.KLINE_DAYS)
                if htf_bars and len(htf_bars) >= PAConfig.MIN_KLINE_BARS:
                    tf_structs[htf] = detect_market_structure(htf_bars)
            except Exception as e:
                logger.warning(f"[PAEngine] {symbol} {htf} struct fetch failed: {e}")
        # 归一化 key：把主周期统一记为 daily（融合函数按 daily/weekly/monthly 取）
        if timeframe != "daily" and "daily" not in tf_structs:
            tf_structs["daily"] = daily_struct
        return tf_structs
