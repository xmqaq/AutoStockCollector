"""
AI 监控引擎 — 协调各分析器，并行分析股票池，生成短/长期信号
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from core.storage.mongo_storage import StockInfoStorage, WatchlistStorage
from utils.logger import get_logger

from .storage import MonitorStorage
from .backtest import SignalBacktest
from .analyzers import (
    FundFlowAnalyzer,
    PricePredictionAnalyzer,
    ResearchReportAnalyzer,
    TechnicalAnalyzer,
    FundamentalAnalyzer,
    ValuationAnalyzer,
    CompositeAnalyzer,
    StockNewsSentimentAnalyzer,
)

logger = get_logger(__name__)


class MonitorEngine:
    """AI 实时监控主引擎"""

    def __init__(self):
        self._storage = MonitorStorage()
        self._stock_info = StockInfoStorage()
        self._fund_flow = FundFlowAnalyzer()
        self._research = ResearchReportAnalyzer()
        self._technical = TechnicalAnalyzer()
        self._fundamental = FundamentalAnalyzer()
        self._valuation = ValuationAnalyzer()
        self._composite = CompositeAnalyzer()
        self._price_prediction = PricePredictionAnalyzer()
        self._news_sentiment = StockNewsSentimentAnalyzer()
        self._backtest = SignalBacktest()
        self._watchlist = WatchlistStorage()
        self._db = DatabaseConfig.get_database()

    def refresh_all(self) -> Dict[str, Any]:
        stocks = self._collect_stocks()
        if not stocks:
            logger.warning("No stocks to analyze")
            return {"success": True, "analyzed": 0, "total": 0}

        results = []
        errors = 0

        with ThreadPoolExecutor(max_workers=8) as pool:
            fut_map = {
                pool.submit(self._analyze_one, s): s for s in stocks
            }
            for fut in as_completed(fut_map):
                s = fut_map[fut]
                try:
                    result = fut.result()
                    if result:
                        results.append(result)
                        self._storage.upsert_signal(s["code"], result)
                        self._storage.save_history(s["code"], result)
                except Exception as e:
                    errors += 1
                    logger.error(f"Analyze {s.get('code')} failed: {e}")

        # 后台回测
        try:
            self._backtest.store_accuracy_all()
        except Exception as e:
            logger.error(f"Backtest failed: {e}")

        logger.info(f"Refreshed {len(results)} stocks ({errors} errors)")
        return {
            "success": True,
            "analyzed": len(results),
            "total": len(stocks),
            "errors": errors,
        }

    def refresh_stock(self, code: str) -> Optional[Dict[str, Any]]:
        info = self._stock_info.get_by_code(code) or {"code": code, "A股简称": ""}
        s = {
            "code": code,
            "name": info.get("A股简称", info.get("name", "")),
            "type": "manual",
        }
        result = self._analyze_one(s)
        if result:
            self._storage.upsert_signal(code, result)
            self._storage.save_history(code, result)
        return result

    def _collect_stocks(self) -> List[Dict[str, Any]]:
        """收集需要分析的股票: 持仓(positions + paper_account) + 自选(watchlist)"""
        seen = set()
        stocks = []

        # 持仓: positions 集合（实际持仓记录）
        try:
            positions = list(self._db["positions"].find())
            for p in positions:
                code = p.get("code", "")
                if code and code not in seen:
                    seen.add(code)
                    stocks.append({
                        "code": code,
                        "name": p.get("name", ""),
                        "type": "持仓",
                        "shares": p.get("shares", 0),
                        "avg_cost": p.get("avg_cost", 0),
                        "market_value": p.get("market_value", 0),
                        "pnl": p.get("pnl", 0),
                    })
        except Exception as e:
            logger.error(f"Get positions failed: {e}")

        # 持仓: paper_account 集合（备用）
        try:
            accounts = list(self._db["paper_account"].find())
            for acct in accounts:
                holdings = acct.get("holdings", acct.get("positions", []))
                for h in holdings:
                    code = h.get("code", "")
                    if code and code not in seen:
                        seen.add(code)
                        stocks.append({
                            "code": code,
                            "name": h.get("name", ""),
                            "type": "持仓",
                        })
        except Exception as e:
            logger.error(f"Get paper_account failed: {e}")

        # 自选: watchlist 集合 (不分用户)
        try:
            items = self._watchlist.find_many({"enabled": True})
            for item in items:
                code = item.get("code", "")
                if code and code not in seen:
                    seen.add(code)
                    stocks.append({
                        "code": code,
                        "name": item.get("name", item.get("A股简称", "")),
                        "type": "自选",
                    })
        except Exception as e:
            logger.error(f"Get watchlist failed: {e}")

        logger.info(f"Collected {len(stocks)} stocks to analyze ({len(seen)} unique)")
        return stocks

    def _analyze_one(self, stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        code = stock["code"]
        name = stock.get("name", "")
        stock_type = stock.get("type", "自选")
        info = self._stock_info.get_by_code(code) or {}
        industry = info.get("industry", info.get("所属行业", ""))

        try:
            fund_flow = self._fund_flow.analyze(code)
            research = self._research.analyze(code, name)
            technical = self._technical.analyze(code)
            fundamental = self._fundamental.analyze(code)
            valuation = self._valuation.analyze(code)
            price_prediction = self._price_prediction.analyze(code)
            news_sentiment = self._news_sentiment.analyze(code, name, industry)
            composite = self._composite.composite(fund_flow, research, technical, fundamental, valuation, news_sentiment)
        except Exception as e:
            logger.error(f"Analyze {code} failed: {e}")
            return None

        current_price = technical.get("current_price", 0)

        # ── 历史信号反思 ──
        reflection = self._reflect_on_history(code, current_price)

        result = {
            "code": code,
            "name": name or info.get("A股简称", info.get("name", "")),
            "type": stock_type,
            "price": current_price,
            "change_rate": 0.0,
            "industry": info.get("industry", info.get("所属行业", "")),
            "short_term": composite["short_term"],
            "long_term": composite["long_term"],
            "composite": {
                "score": composite["composite_score"],
                "signal": composite["composite_signal"],
                "label": composite["composite_label"],
                "divergence": composite["divergence"],
            },
            "confidence": self._calc_confidence(composite),
            "price_prediction": price_prediction,
            "analysis": {
                "fund_flow": fund_flow,
                "research": research,
                "technical": technical,
                "fundamental": fundamental,
                "valuation": valuation,
                "news_sentiment": news_sentiment,
            },
            "updated_at": datetime.now().isoformat(),
        }

        result["trading_advice"] = self._trading_advice(
            fund_flow, research, technical, composite, price_prediction, valuation, stock_type, reflection, news_sentiment,
        )
        self._update_price_change(result, code)
        return result

    def _trading_advice(
        self,
        fund_flow: Dict, research: Dict,
        technical: Dict, composite: Dict,
        pp: Dict, valuation: Dict,
        stock_type: str = "自选",
        reflection: Optional[Dict] = None,
        news_sentiment: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """多维度买卖点建议 — 融合主力资金、研报、技术面、估值、综合评分"""
        current = pp.get("current_price", 0)
        target = pp.get("target_price", 0)
        stop = pp.get("stop_loss", 0)
        buy_low = pp.get("buy_zone_low", 0)
        buy_high = pp.get("buy_zone_high", 0)
        exp_ret = pp.get("expected_return", 0)
        max_loss = pp.get("max_loss", 0)
        rr = round(exp_ret / max_loss, 2) if max_loss > 0 else 0

        # 各维度得分
        ff_s = fund_flow.get("short_term", {}).get("score", 50)
        ff_l = fund_flow.get("long_term", {}).get("score", 50)
        rs_s = research.get("short_term", {}).get("score", 50)
        rs_l = research.get("long_term", {}).get("score", 50)
        rs_c = research.get("composite_score", 50)
        tc_s = technical.get("short_term", {}).get("score", 50)
        tc_l = technical.get("long_term", {}).get("score", 50)
        vl_s = valuation.get("score", 50)
        cp_s = composite.get("composite_score", 50)
        cp_sig = composite.get("composite_signal", "hold")
        sc_s = composite.get("short_term", {}).get("score", 50)
        sc_l = composite.get("long_term", {}).get("score", 50)
        divergence = composite.get("divergence", "")

        # ── 新闻舆情（利好催化剂） ──
        ns = news_sentiment or {}
        ns_overall = ns.get("overall", {})
        ns_bullish = ns_overall.get("bullish", False)
        ns_score = ns_overall.get("score", 50)
        ns_pos_count = ns.get("positive_count", 0)

        # ── 维度间分歧检测 ──
        dim_divergences = self._detect_dim_divergence(ff_s, ff_l, rs_s, tc_s, vl_s, sc_s, sc_l)

        # ── 置信度估计 ──
        confidence_level = self._calc_advice_confidence(ff_s, rs_s, tc_s, vl_s, sc_s, sc_l)

        # ── 持有期估计 ──
        time_horizon = self._estimate_holding_period(rr, exp_ret, tc_s, ff_s)

        # 位置判断
        if buy_low <= current <= buy_high:
            pos_text = "在买入区内"
        elif current < buy_low:
            pos_text = "低于买入区"
        else:
            pos_text = "高于买入区"

        if current >= target:
            dist_text = f"已到目标价({target:.2f})，建议止盈"
        elif current >= target * 0.95:
            dist_text = f"接近目标价，距目标还有{target-current:+.2f}"
        else:
            d = round((target / current - 1) * 100, 1) if current > 0 else 0
            dist_text = f"距目标还有+{d}%"

        # ── 决策矩阵 ──
        action = "持有"
        sig = "hold"
        buy_reasons = []
        sell_reasons = []
        watch_reasons = []

        # 卖出：价格到了目标
        if target > 0 and current >= target:
            action = "卖出"; sig = "sell"
            sell_reasons.append(f"价格{current:.2f}达到目标价{target:.2F}")
            sell_reasons.append("建议止盈锁定利润")

        # 卖出：跌破止损
        elif stop > 0 and current <= stop * 1.03:
            action = "卖出"; sig = "sell"
            sell_reasons.append(f"价格{current:.2f}接近止损线{stop:.2f}")
            sell_reasons.append(f"最大亏损约{max_loss:.1f}%，建议止损")

        # 卖出：主力资金持续流出 + 信号看空
        elif ff_s < 35 and ff_l < 35 and cp_sig in ("sell", "strong_sell"):
            action = "卖出"; sig = "sell"
            sell_reasons.append(f"主力资金短期{ff_s:.0f}/长期{ff_l:.0f}持续流出")
            sell_reasons.append("综合信号偏空，建议减仓")

        # 卖出：技术面极弱 + 资金流出
        elif tc_s < 30 and ff_s < 35:
            action = "卖出"; sig = "sell"
            sell_reasons.append(f"技术面评分{tc_s:.0f}，主力资金{ff_s:.0f}")
            sell_reasons.append("技术和资金面双弱，建议离场")

        # ── 买入条件 ──
        # 买入：在买入区 + 综合信号买入 + 资金正向
        elif buy_low <= current <= buy_high and sc_s >= 60 and ff_s >= 55:
            action = "买入"; sig = "buy"
            buy_reasons.append(f"价格在买入区({buy_low:.2f}~{buy_high:.2f})")
            buy_reasons.append(f"主力资金评分{ff_s:.0f}，资金正向流入")
            buy_reasons.append(f"盈亏比{rr}，预期{exp_ret:+.1f}%")
            if rs_s >= 55:
                buy_reasons.append(f"研报短期评分{rs_s:.0f}，基本面支撑")
            if ns_bullish:
                buy_reasons.append(f"舆情偏向利好(评分{ns_score:.0f})")
            if dim_divergences:
                buy_reasons.append(f"注意: {'; '.join(dim_divergences[:2])}")

        # 买入：在买入区 + 盈亏比好 + 至少一个维度看多
        elif buy_low <= current <= buy_high and rr >= 2 and (ff_s >= 60 or rs_s >= 55 or tc_s >= 60):
            action = "买入"; sig = "buy"
            buy_reasons.append(f"价格在买入区，盈亏比{rr}较好")
            if ff_s >= 60: buy_reasons.append(f"主力资金积极(评分{ff_s:.0f})")
            if rs_s >= 55: buy_reasons.append(f"研报短期看好(评分{rs_s:.0f})")
            if tc_s >= 60: buy_reasons.append(f"技术面偏多(评分{tc_s:.0f})")
            if ns_bullish:
                buy_reasons.append(f"舆情偏向利好(评分{ns_score:.0f})，{ns_pos_count}条利好新闻")

        # 买入：略高于买入区但多维度共振强烈
        elif current <= buy_high * 1.2 and sc_s >= 65 and ff_s >= 60 and tc_s >= 55 and rr >= 2:
            action = "买入"; sig = "buy"
            pct_above = round((current / buy_high - 1) * 100, 1)
            buy_reasons.append(f"价格{current:.2f}仅高于买入区{pct_above}%({buy_low:.2f}~{buy_high:.2f})")
            buy_reasons.append(f"资金{ff_s:.0f}+技术{tc_s:.0f}+估值{vl_s:.0f}多维度看多")
            buy_reasons.append(f"盈亏比{rr}，预期收益{exp_ret:+.1f}%，建议适量建仓")

        # 买入：高于买入区(10-20%)，资金和技术强势
        elif current <= buy_high * 1.2 and ff_s >= 65 and tc_s >= 60 and rr >= 2:
            action = "买入"; sig = "buy"
            pct_above = round((current / buy_high - 1) * 100, 1)
            buy_reasons.append(f"价格高于买入区{pct_above}%但资金({ff_s:.0f})和技术({tc_s:.0f})强势")
            buy_reasons.append(f"盈亏比{rr}较好，预期{exp_ret:+.1f}%，可控制仓位介入")

        # ── 观望条件 ──
        # 价格在买入区但多维度看空
        elif buy_low <= current <= buy_high and ff_s < 40 and sc_s < 55:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"价格在买入区但主力资金评分{ff_s:.0f}偏低")
            watch_reasons.append("综合评分不足，等待资金确认")

        # 价格低于买入区但信号看多
        elif current < buy_low and sc_s >= 60 and ff_s >= 50:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"价格{current:.2f}低于买入区(当前{buy_low:.2f}~{buy_high:.2f})")
            watch_reasons.append(f"信号偏多(综合{sc_s:.0f}/资金{ff_s:.0f})，可等待回调至买入区")

        # 综合评分很高但价格远离买入区
        elif sc_s >= 65 and current > buy_high * 1.2:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"综合评分{sc_s:.0f}看多但价格超过买入区20%({buy_high:.2f})")
            watch_reasons.append("涨幅已大，等回调再介入")
        elif sc_s >= 65 and current > buy_high * 1.1:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"综合评分{sc_s:.0f}看多但价格略高于买入区上限")
            watch_reasons.append("可小仓位试探，注意回调风险")

        # 舆情利好但价格不配合 → 关注
        elif ns_bullish and ns_score >= 65 and sc_s < 55:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"舆情利好(评分{ns_score:.0f})，{ns_pos_count}条利好新闻")
            watch_reasons.append("但综合评分偏低，可跟踪等待技术确认")

        # 短期长期分歧
        elif divergence and abs(sc_s - sc_l) > 20:
            action = "观望"; sig = "watch"
            watch_reasons.append(f"短期{sc_s:.0f}/长期{sc_l:.0f}分歧较大")
            watch_reasons.append("建议等待方向明确")

        # ── 剩下：持有 ──
        else:
            has_divergence = len(dim_divergences) >= 2
            if ff_s >= 55 or tc_s >= 55 or cp_sig in ("buy", "strong_buy"):
                hold_reason = "各维度信号正常"
                if cp_sig in ("buy", "strong_buy"):
                    hold_reason += f"，综合看多({cp_sig})"
                if has_divergence:
                    hold_reason += f"，{dim_divergences[0]}"
                buy_reasons.append(hold_reason)
                buy_reasons.append(f"持有至目标价{target:.2f}(+{exp_ret:.1f}%)")
                buy_reasons.append(f"止损设在{stop:.2f}(-{max_loss:.1f}%)")
            else:
                buy_reasons.append("暂无强烈买卖信号")
                buy_reasons.append(f"可继续持有观察，止损{stop:.2f}")
            if rr >= 1.5:
                buy_reasons.append(f"盈亏比{rr}尚可")

        # 持仓股票：观望 → 持有（不加仓），买入 → 持有（可加仓）
        if stock_type == "持仓":
            if sig == "watch":
                action = "持有"
                sig = "hold"
                watch_reasons.append("已持仓，控制仓位不加仓")
            elif sig == "buy":
                action = "持有"
                sig = "hold"
                buy_reasons.append("已持仓，可继续持有")

        all_reasons = buy_reasons + sell_reasons + watch_reasons
        # 构建显示文本
        if sig == "sell":
            display_reason = "; ".join(sell_reasons[:3])
        elif sig == "buy":
            display_reason = "; ".join(buy_reasons[:3])
        elif sig == "watch":
            display_reason = "; ".join(watch_reasons[:2])
        else:
            display_reason = "; ".join(buy_reasons[:2]) if buy_reasons else "暂无明确信号"

        # ── 结构化建议 ──
        if sig == "buy" and stock_type == "自选":
            if buy_low <= current <= buy_high:
                advice_summary = f"建议在 {buy_low:.2f}~{buy_high:.2f} 买入"
            else:
                advice_summary = f"当前{current:.2f}略高于买入区({buy_low:.2f}~{buy_high:.2f})"
            advice_summary += f"，目标价 {target:.2f}(+{exp_ret:.1f}%)，止损 {stop:.2f}(-{max_loss:.1f}%)"
        elif sig == "sell":
            if current >= target and target > 0:
                advice_summary = f"建议在 {current:.2f} 止盈，已达目标价 {target:.2f}"
            elif stop > 0 and current <= stop * 1.03:
                advice_summary = f"建议在 {current:.2f} 止损，接近止损线 {stop:.2f}(-{max_loss:.1f}%)"
            else:
                advice_summary = f"建议卖出，目标价 {target:.2f}，止损 {stop:.2f}"
        elif sig == "watch":
            if current < buy_low:
                advice_summary = f"等待回调至 {buy_low:.2f}~{buy_high:.2f} 区间再介入"
            elif current > buy_high * 1.2:
                advice_summary = f"涨幅已大(现价{current:.2f}超过买入区20%)，等回调至 {buy_low:.2f}~{buy_high:.2f} 再介入"
            elif divergence and abs(sc_s - sc_l) > 20:
                advice_summary = f"短长期分歧({sc_s}/{sc_l})较大，等待方向明确"
            else:
                advice_summary = f"暂不建议操作，等待信号确认"
            advice_summary += f"，理想买入区 {buy_low:.2f}~{buy_high:.2f}，目标 {target:.2f}(+{exp_ret:.1f}%)"
        else:
            # 持有
            if buy_low <= current <= buy_high:
                advice_summary = f"建议持有至目标价 {target:.2f}(+{exp_ret:.1f}%)"
            elif current > buy_high:
                advice_summary = f"已持有，持有至目标价 {target:.2f}(+{exp_ret:.1f}%)"
                if stock_type == "持仓":
                    advice_summary += "，不建议加仓"
            else:
                advice_summary = f"建议持有等待反弹，目标价 {target:.2f}(+{exp_ret:.1f}%)"
            advice_summary += f"，止损 {stop:.2f}(-{max_loss:.1f}%)"

        return {
            "action": action,
            "action_signal": sig,
            "reason": display_reason,
            "details": {
                "fund_flow_score": ff_s,
                "research_score": rs_s,
                "technical_score": tc_s,
                "valuation_score": vl_s,
                "composite_score": cp_s,
            },
            "buy_reasons": buy_reasons[:3],
            "sell_reasons": sell_reasons[:3],
            "watch_reasons": watch_reasons[:2],
            "entry_price_range": {"low": round(buy_low, 2), "high": round(buy_high, 2)},
            "take_profit": round(target, 2) if target else 0,
            "stop_loss": round(stop, 2) if stop else 0,
            "expected_return": exp_ret,
            "max_loss": max_loss,
            "risk_reward_ratio": rr,
            "current_position": pos_text,
            "distance_to_target": dist_text,
            "advice": {
                "summary": advice_summary,
                "buy_price_low": round(buy_low, 2),
                "buy_price_high": round(buy_high, 2),
                "target_price": round(target, 2) if target else 0,
                "stop_loss_price": round(stop, 2) if stop else 0,
                "hold_period": f"持有至目标价 {round(target, 2) if target else 0}" if target else "",
                "expected_return": exp_ret,
                "max_loss": max_loss,
                "time_horizon": time_horizon,
                "confidence_level": confidence_level,
                "entry_price": round(current, 2),
            },
            "divergence_warnings": dim_divergences[:3],
            "reflection": reflection,
        }

    def _update_price_change(self, result: Dict, code: str):
        try:
            val = self._fundamental._val.get_by_code(code)
            if val and "change_pct" in val:
                result["change_rate"] = float(val["change_pct"])
        except Exception:
            pass

    def _calc_confidence(self, composite: Dict) -> float:
        s = composite["short_term"]["score"]
        l = composite["long_term"]["score"]
        avg = (s + l) / 2
        consistency = 1 - abs(s - l) / 100
        return round(avg * consistency / 100, 2)

    def _detect_dim_divergence(
        self, ff_s: float, ff_l: float, rs_s: float,
        tc_s: float, vl_s: float, sc_s: float, sc_l: float,
    ) -> List[str]:
        """检测多维度的方向分歧"""
        divergences = []
        if abs(ff_s - tc_s) > 25:
            if ff_s > tc_s:
                divergences.append(f"资金偏多({ff_s:.0f})但技术偏空({tc_s:.0f})")
            else:
                divergences.append(f"技术偏多({tc_s:.0f})但资金偏空({ff_s:.0f})")
        if abs(ff_s - rs_s) > 25:
            if ff_s > rs_s:
                divergences.append(f"资金积极({ff_s:.0f})但研报谨慎({rs_s:.0f})")
            else:
                divergences.append(f"研报看好({rs_s:.0f})但资金流出({ff_s:.0f})")
        if abs(vl_s - tc_s) > 25:
            if vl_s > tc_s:
                divergences.append(f"估值偏低({vl_s:.0f})但有技术压力({tc_s:.0f})")
            else:
                divergences.append(f"技术偏多({tc_s:.0f})但估值偏高({vl_s:.0f})")
        if abs(sc_s - sc_l) > 15:
            divergences.append(f"短期{sc_s:.0f}/长期{sc_l:.0f}方向分歧")
        return divergences

    def _calc_advice_confidence(
        self, ff_s: float, rs_s: float,
        tc_s: float, vl_s: float,
        sc_s: float, sc_l: float,
    ) -> str:
        """计算建议置信度 — 基于维度间一致性"""
        scores = [ff_s, rs_s, tc_s, vl_s]
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        consistency = max(0, 1 - (variance ** 0.5) / 25)
        term_consistency = max(0, 1 - abs(sc_s - sc_l) / 50)
        conf = consistency * 0.6 + term_consistency * 0.4
        if conf >= 0.7:
            return "高"
        elif conf >= 0.4:
            return "中"
        return "低"

    def _estimate_holding_period(
        self, rr: float, exp_ret: float,
        tc_s: float, ff_s: float,
    ) -> str:
        """估计建议持有期"""
        if rr >= 5 and exp_ret >= 30:
            return "中期持有(15-30天)"
        elif rr >= 3 and exp_ret >= 15:
            return "短期持有(5-15天)"
        elif tc_s >= 65 or ff_s >= 65:
            return "短线交易(3-7天)"
        return "中期持有(15-60天)"

    def _reflect_on_history(self, code: str, current_price: float) -> Optional[Dict]:
        """反思历史信号 — 对比上次建议与当前价格变化"""
        try:
            history = list(
                self._db["monitor_signal_history"]
                .find({"code": code})
                .sort("created_at", -1)
                .limit(5)
            )
            if len(history) < 2:
                return None

            prev = history[1]  # 上一次的信号（最新是本次）
            prev_action = prev.get("trading_advice", {}).get("action", "持有")
            prev_price = prev.get("price", 0)
            prev_target = prev.get("price_prediction", {}).get("target_price", 0)

            if prev_price <= 0:
                return None

            change_pct = round((current_price - prev_price) / prev_price * 100, 2)

            parts = [f"上次({prev_action})价{prev_price:.2f}→现{current_price:.2f}({change_pct:+.2f}%)"]
            if prev_action == "买入" and change_pct > 0:
                parts.append("买入建议正确")
            elif prev_action == "买入" and change_pct < -3:
                parts.append("买入后下跌需关注")
            elif prev_action == "卖出" and change_pct < 0:
                parts.append("卖出建议正确")
            elif prev_action == "卖出" and change_pct > 3:
                parts.append("卖出后上涨需重新评估")

            if prev_target > 0:
                if current_price >= prev_target:
                    parts.append("已达上次目标价")
                else:
                    pct_to_target = round((prev_target / current_price - 1) * 100, 1)
                    parts.append(f"距上次目标还差{pct_to_target:+.1f}%")

            return {
                "previous_action": prev_action,
                "previous_price": round(prev_price, 2),
                "current_price": round(current_price, 2),
                "change_pct": change_pct,
                "summary": "，".join(parts) if parts else "",
            }
        except Exception as e:
            logger.debug(f"History reflection failed for {code}: {e}")
            return None
