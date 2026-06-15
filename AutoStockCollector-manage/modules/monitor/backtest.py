"""
信号回测模块 — 对比历史信号与后续 N 日实际收益，计算准确率
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from config.database import DatabaseConfig
from core.storage.mongo_storage import KlineStorage
from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalBacktest:
    HORIZONS = [1, 3, 5, 10]

    def __init__(self):
        self._db = DatabaseConfig.get_database()
        self._kline = KlineStorage()

    def evaluate(self, code: str, days: int = 60) -> Dict[str, Any]:
        """对某只股票的历史信号进行回测评估"""
        history = self._get_history(code, days)
        if not history:
            return self._empty(code, "无历史信号数据")

        results = []
        for sig in history:
            evaluated = self._evaluate_one(sig)
            if evaluated:
                results.append(evaluated)

        if not results:
            return self._empty(code, "无足够K线数据验证")

        return self._aggregate(code, results)

    def evaluate_all(self, days: int = 60) -> List[Dict[str, Any]]:
        """对所有有历史信号的股票回测"""
        codes = self._db["monitor_signal_history"].distinct("code")
        results = []
        for code in codes:
            try:
                r = self.evaluate(code, days)
                if r.get("total_signals", 0) > 0:
                    results.append(r)
            except Exception as e:
                logger.error(f"Backtest {code} failed: {e}")
        return results

    def _get_history(self, code: str, days: int) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        docs = list(
            self._db["monitor_signal_history"]
            .find({"code": code, "created_at": {"$gte": cutoff}})
            .sort("created_at", -1)
            .limit(200)
        )
        for d in docs:
            d.pop("_id", None)
        return docs

    def _evaluate_one(self, sig: Dict) -> Optional[Dict]:
        """评估单条信号"""
        code = sig.get("code", "")
        created_str = sig.get("created_at", "")
        sig_date = sig.get("signal_date", "")
        if not code:
            return None

        if not sig_date and not created_str:
            return None

        if not sig_date:
            try:
                sig_date = created_str[:10]
            except Exception:
                return None

        # 跳过未来信号（还没有后续K线）
        if sig_date >= datetime.now().strftime("%Y-%m-%d"):
            return None

        short_signal = sig.get("short_term", {}).get("signal", "hold")
        long_signal = sig.get("long_term", {}).get("signal", "hold")
        composite_signal = sig.get("composite", {}).get("signal", "hold")

        # 获取信号发出后的K线
        klines = list(
            self._kline.find_many(
                {"code": code, "date": {"$gte": sig_date}},
                sort=[("date", 1)],
                limit=max(self.HORIZONS) + 2,
            )
        )
        if len(klines) < 2:
            return None

        # 信号发出日的收盘价作为基准
        entry_close = float(klines[0]["close"])
        if entry_close <= 0:
            return None

        returns = {}
        for h in self.HORIZONS:
            if len(klines) > h:
                exit_close = float(klines[h]["close"])
                returns[f"return_{h}d"] = round((exit_close - entry_close) / entry_close * 100, 2)
            else:
                returns[f"return_{h}d"] = None

        # 判断信号方向是否正确
        accuracy = {}
        for h in self.HORIZONS:
            ret = returns.get(f"return_{h}d")
            if ret is None:
                accuracy[f"hit_{h}d"] = None
                continue
            # 买入信号: 预期上涨
            if composite_signal in ("strong_buy", "buy"):
                accuracy[f"hit_{h}d"] = ret > 0
            # 卖出信号: 预期下跌
            elif composite_signal in ("strong_sell", "sell"):
                accuracy[f"hit_{h}d"] = ret < 0
            # 持有: 预期横盘
            else:
                accuracy[f"hit_{h}d"] = abs(ret) < 2

        return {
            "code": code,
            "signal_date": sig_date,
            "entry_price": round(entry_close, 2),
            "composite_signal": composite_signal,
            "short_signal": short_signal,
            "long_signal": long_signal,
            "confidence": sig.get("confidence", 0),
            **returns,
            **accuracy,
        }

    def _aggregate(self, code: str, results: List[Dict]) -> Dict[str, Any]:
        """汇总多条信号的回测结果"""
        total = len(results)

        stats = {"code": code, "total_signals": total}

        for h in self.HORIZONS:
            returns = [r[f"return_{h}d"] for r in results if r.get(f"return_{h}d") is not None]
            hits = [r[f"hit_{h}d"] for r in results if r.get(f"hit_{h}d") is not None]

            if returns:
                avg_ret = np.mean(returns)
                std_ret = np.std(returns) if len(returns) > 1 else 1
                positive_ratio = sum(1 for r in returns if r > 0) / len(returns)
                stats[f"avg_return_{h}d"] = round(float(avg_ret), 2)
                stats[f"std_return_{h}d"] = round(float(std_ret), 2)
                stats[f"positive_ratio_{h}d"] = round(float(positive_ratio), 3)
                stats[f"sharpe_{h}d"] = round(float(avg_ret / std_ret) if std_ret > 0 else 0, 2)
            else:
                stats[f"avg_return_{h}d"] = 0
                stats[f"positive_ratio_{h}d"] = 0
                stats[f"sharpe_{h}d"] = 0

            if hits:
                hit_rate = sum(1 for hh in hits if hh) / len(hits)
                stats[f"hit_rate_{h}d"] = round(float(hit_rate), 3)
            else:
                stats[f"hit_rate_{h}d"] = 0

        stats["overall_score"] = self._calc_overall_score(stats)

        # 最近3条信号展示
        recent = sorted(results, key=lambda r: r["signal_date"], reverse=True)[:3]
        stats["recent_signals"] = [
            {
                "date": r["signal_date"],
                "signal": r["composite_signal"],
                "entry_price": r["entry_price"],
                "return_5d": r.get("return_5d"),
                "hit_5d": r.get("hit_5d"),
            }
            for r in recent
        ]

        return stats

    def _calc_overall_score(self, stats: Dict) -> float:
        """综合评分 0-100，衡量信号质量"""
        hit_5d = stats.get("hit_rate_5d", 0)
        sharpe_5d = stats.get("sharpe_5d", 0)
        pos_5d = stats.get("positive_ratio_5d", 0)
        score = hit_5d * 50 + min(sharpe_5d / 2, 1) * 25 + pos_5d * 25
        return round(float(score), 1)

    def store_accuracy(self, code: str, accuracy: Dict[str, Any]):
        """将回测结果写入 monitor_signals 文档"""
        self._db["monitor_signals"].update_one(
            {"code": code},
            {"$set": {"backtest": accuracy}},
        )

    def store_accuracy_all(self):
        """批量回测并写入"""
        results = self.evaluate_all()
        for r in results:
            if r.get("total_signals", 0) >= 3:
                code = r["code"]
                self.store_accuracy(code, r)
                logger.info(f"Accuracy stored for {code}: hit_rate_5d={r.get('hit_rate_5d', 0):.0%}")
        return results

    def _empty(self, code: str, reason: str) -> Dict:
        return {
            "code": code,
            "total_signals": 0,
            "error": reason,
        }
