"""PriceActionEngine — 价格行为学主编排器。"""
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from utils.logger import get_logger
from .config import PAConfig
from .fetcher import get_kline, get_spot
from .market_structure import detect_market_structure
from .supply_demand import analyze_supply_demand
from .signal_generator import generate_signal
from .risk_manager import calculate_trade_plan

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
                norm = list(spot_data.keys())[0]
                name = spot_data[norm].get("name", "")

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

            sd_result = analyze_supply_demand(bars)
            report(65, "供需区识别完成")

            signal = generate_signal(symbol, name, bars, market_struct, sd_result)
            report(75, "信号生成完成")

            current_price = bars[-1]["close"]
            demand_zones = sd_result.get("demand_zones", [])
            supply_zones = sd_result.get("supply_zones", [])
            atr = sd_result.get("atr", 0)

            if signal["signal"] in ("BUY_SETUP", "SELL_SETUP"):
                trade_plan = calculate_trade_plan(
                    entry_price=current_price,
                    signal_type=signal["signal"],
                    atr=atr,
                    demand_zones=demand_zones,
                    supply_zones=supply_zones,
                    account_balance=account_balance,
                    risk_pct=risk_pct,
                )
                signal["trade_plan"] = trade_plan
            elif signal["signal"] in ("WEAK_BUY", "WEAK_SELL"):
                trade_plan = calculate_trade_plan(
                    entry_price=current_price,
                    signal_type=signal["signal"],
                    atr=atr,
                    demand_zones=demand_zones,
                    supply_zones=supply_zones,
                    account_balance=account_balance,
                    risk_pct=risk_pct * PAConfig.WEAK_SIGNAL_RISK_FACTOR,
                )
                signal["trade_plan"] = trade_plan

            signal["timeframe"] = timeframe
            signal["updated_at"] = datetime.now().isoformat()

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
