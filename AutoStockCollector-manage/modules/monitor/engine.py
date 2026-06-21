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
    BlockAnalyzer,
    LimitUpAnalyzer,
    DragonTigerAnalyzer,
    MarginAnalyzer,
)

logger = get_logger(__name__)


class AdviceContext:
    """建议上下文 — 持有所有分析结果供决策器使用"""

    def __init__(self, **kwargs):
        self.current_price: float = 0
        self.target_price: float = 0
        self.stop_loss: float = 0
        self.buy_low: float = 0
        self.buy_high: float = 0
        self.expected_return: float = 0
        self.max_loss: float = 0
        self.rr: float = 0
        self.stock_type: str = "自选"
        self.shares: int = 0
        self.avg_cost: float = 0
        self.market_value: float = 0
        self.pnl: float = 0
        self.ff_s: float = 50
        self.ff_l: float = 50
        self.rs_s: float = 50
        self.rs_l: float = 50
        self.rs_c: float = 50
        self.tc_s: float = 50
        self.tc_l: float = 50
        self.vl_s: float = 50
        self.cp_s: float = 50
        self.cp_sig: str = "hold"
        self.sc_s: float = 50
        self.sc_l: float = 50
        self.divergence: str = ""
        self.ns_bullish: bool = False
        self.ns_score: float = 50
        self.ns_pos_count: int = 0
        self.dim_divergences: list = []
        self.concepts: List[str] = None
        self.sector_flow: Dict = None
        self.limit_up: Dict = None
        self.dragon_tiger: Dict = None
        self.margin: Dict = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def is_position(self) -> bool:
        return self.stock_type == "持仓"


def _calc_rr(exp_ret: float, max_loss: float) -> float:
    return round(exp_ret / max_loss, 2) if max_loss > 0 else 0


class SellDecider:
    """卖点检测 — 止盈/止损/资金撤退/技术破位/板块退潮"""

    def decide(self, ctx: AdviceContext) -> Optional[Dict]:
        r = []
        # 1 已达目标价
        if ctx.target_price > 0 and ctx.current_price >= ctx.target_price:
            r.append(f"价格{ctx.current_price:.2f}达到目标价{ctx.target_price:.2f}，建议止盈")
            return self._sell(ctx, r, "止盈")
        # 2 跌破止损
        if ctx.stop_loss > 0 and ctx.current_price <= ctx.stop_loss * 1.03:
            r.append(f"价格{ctx.current_price:.2f}接近止损线{ctx.stop_loss:.2f}")
            r.append(f"最大亏损约{ctx.max_loss:.1f}%，建议止损")
            return self._sell(ctx, r, "止损")
        # 3 主力资金持续流出 + 综合看空
        if ctx.ff_s < 35 and ctx.ff_l < 35 and ctx.cp_sig in ("sell", "strong_sell"):
            r.append(f"主力资金短期{ctx.ff_s:.0f}/长期{ctx.ff_l:.0f}持续流出")
            r.append("综合信号偏空，建议减仓/清仓")
            return self._sell(ctx, r, "资金撤退")
        # 4 技术面极弱 + 资金流出
        if ctx.tc_s < 30 and ctx.ff_s < 35:
            r.append(f"技术面评分{ctx.tc_s:.0f}，主力资金{ctx.ff_s:.0f}")
            r.append("技术和资金面双弱，建议离场")
            return self._sell(ctx, r, "技术破位")
        # 5 连续净流出 + 技术走弱
        if ctx.ff_s < 40 and ctx.tc_s < 40 and ctx.cp_s in ("sell", "strong_sell"):
            r.append(f"资金({ctx.ff_s:.0f})和技术({ctx.tc_s:.0f})均走弱")
            r.append("多维度看空，建议减仓")
            return self._sell(ctx, r, "双弱")
        # 6 持仓止盈: 盈利超过30%且信号转弱
        if ctx.is_position and ctx.pnl and ctx.pnl > 0.3 and ctx.sc_s < 55:
            r.append(f"已盈利{ctx.pnl*100:.0f}%且综合评分降至{ctx.sc_s:.0f}")
            r.append("建议部分止盈锁定利润")
            return self._sell(ctx, r, "止盈(持仓)")
        return None

    def _sell(self, ctx: AdviceContext, reasons: List[str], source: str) -> Dict:
        return {
            "action": "卖出", "signal": "sell",
            "reasons": reasons[:3], "source": source,
        }


class BuyDecider:
    """买入/加仓点检测 — 不再因持仓而抑制"""

    def decide(self, ctx: AdviceContext) -> Optional[Dict]:
        r = []
        in_zone = ctx.buy_low <= ctx.current_price <= ctx.buy_high
        above_zone = ctx.current_price > ctx.buy_high
        slightly_above = ctx.current_price <= ctx.buy_high * 1.2
        # 涨停抑制
        if ctx.limit_up and ctx.limit_up.get("is_limit_up"):
            if ctx.limit_up.get("consecutive_limit_days", 0) >= 2:
                return None  # 连板不追

        action = "买入"
        sig = "buy"
        if ctx.is_position:
            action = "加仓"
            sig = "add"

        # 1 在买入区 + 综合评分高 + 资金正向
        if in_zone and ctx.sc_s >= 60 and ctx.ff_s >= 55:
            r.append(f"价格在买入区({ctx.buy_low:.2f}~{ctx.buy_high:.2f})")
            r.append(f"主力资金评分{ctx.ff_s:.0f}，资金正向流入")
            r.append(f"盈亏比{ctx.rr}，预期{ctx.expected_return:+.1f}%")
            if ctx.rs_s >= 55:
                r.append(f"研报短期评分{ctx.rs_s:.0f}，基本面支撑")
            if ctx.ns_bullish:
                r.append(f"舆情偏向利好(评分{ctx.ns_score:.0f})")
            if ctx.dragon_tiger and ctx.dragon_tiger.get("institution_net_buy", 0) > 5e6:
                r.append("龙虎榜机构净买入，主力增仓")
            if ctx.margin and ctx.margin.get("margin_balance_change_pct", 0) > 5:
                r.append("融资余额增加，杠杆资金看好")
            if ctx.sector_flow and ctx.sector_flow.get("industry_change", 0) > 2:
                r.append(f"所属板块涨幅{ctx.sector_flow['industry_change']:.1f}%，板块联动")
            return self._buy(action, sig, r, "多维共振")

        # 2 在买入区 + 盈亏比好 + 至少一个维度看多
        if in_zone and ctx.rr >= 2 and (ctx.ff_s >= 60 or ctx.rs_s >= 55 or ctx.tc_s >= 60):
            r.append(f"价格在买入区，盈亏比{ctx.rr}较好")
            if ctx.ff_s >= 60: r.append(f"主力资金积极(评分{ctx.ff_s:.0f})")
            if ctx.rs_s >= 55: r.append(f"研报短期看好(评分{ctx.rs_s:.0f})")
            if ctx.tc_s >= 60: r.append(f"技术面偏多(评分{ctx.tc_s:.0f})")
            if ctx.ns_bullish:
                r.append(f"舆情偏利好({ctx.ns_pos_count}条)")
            return self._buy(action, sig, r, "盈亏比+单维度")

        # 3 略高于买入区但多维度共振强烈
        if slightly_above and ctx.sc_s >= 65 and ctx.ff_s >= 60 and ctx.tc_s >= 55 and ctx.rr >= 2:
            pct = round((ctx.current_price / ctx.buy_high - 1) * 100, 1)
            r.append(f"价格{ctx.current_price:.2f}仅高于买入区{pct}%")
            r.append(f"资金{ctx.ff_s:.0f}+技术{ctx.tc_s:.0f}+估值{ctx.vl_s:.0f}多维度看多")
            r.append(f"盈亏比{ctx.rr}，预期收益{ctx.expected_return:+.1f}%")
            return self._buy(action, sig, r, "多维度共振")

        # 4 板块轮动驱动: 板块涨幅前列 + 个股资金流入
        if ctx.sector_flow and ctx.sector_flow.get("industry_change", 0) > 3 and ctx.ff_s >= 55:
            r.append(f"所属板块涨幅{ctx.sector_flow['industry_change']:.1f}%，板块强势")
            r.append(f"个股资金评分{ctx.ff_s:.0f}，资金流入")
            r.append(f"盈亏比{ctx.rr}，预期{ctx.expected_return:+.1f}%")
            return self._buy(action, sig, r, "板块轮动")

        # 5 龙虎榜机构大额净买入 + 技术面不差
        if ctx.dragon_tiger and ctx.dragon_tiger.get("institution_net_buy", 0) > 1e7 and ctx.tc_s >= 50:
            r.append(f"龙虎榜机构净买入{ctx.dragon_tiger['institution_net_buy']/1e4:.0f}万")
            if ctx.concepts:
                r.append(f"所属概念: {', '.join(ctx.concepts[:3])}")
            return self._buy(action, sig, r, "龙虎榜机构")

        return None

    def _buy(self, action: str, sig: str, reasons: List[str], source: str) -> Dict:
        return {"action": action, "signal": sig, "reasons": reasons[:4], "source": source}


class HoldDecider:
    """持有/减仓评估 — 智能区分持有/加仓/减仓（仅对持仓股）"""

    def decide(self, ctx: AdviceContext) -> Dict:
        r = []
        action = "持有"
        sig = "hold"
        source = "正常"

        if ctx.is_position:
            # 持仓股: 判断减仓/加仓/持有
            # 减仓: 盈利较多 + 信号转弱
            if ctx.pnl and ctx.pnl > 0.2 and ctx.sc_s < 55 and ctx.ff_s < 50:
                action = "减仓"; sig = "reduce"
                r.append(f"已盈利{ctx.pnl*100:.0f}%但信号转弱(综合{ctx.sc_s:.0f})")
                r.append("建议减仓部分锁定利润")
                source = "盈利减仓"
            # 减仓: 接近目标价
            elif ctx.target_price > 0 and ctx.current_price >= ctx.target_price * 0.95 and ctx.ff_s < 55:
                action = "减仓"; sig = "reduce"
                r.append(f"价格{ctx.current_price:.2f}接近目标价{ctx.target_price:.2f}")
                r.append("建议减仓止盈")
                source = "接近目标"
            # 加仓: 持仓浮亏 + 信号向好
            elif ctx.pnl and ctx.pnl < -0.05 and ctx.sc_s >= 60 and ctx.ff_s >= 55:
                action = "加仓"; sig = "add"
                r.append(f"持仓浮亏{ctx.pnl*100:.0f}%但信号转好(综合{ctx.sc_s:.0f}+资金{ctx.ff_s:.0f})")
                r.append("可逢低加仓摊薄成本")
                source = "浮亏加仓"
            # 加仓: 持仓盈利 + 信号向好 + 价格在买入区
            elif ctx.pnl and ctx.pnl > 0 and ctx.buy_low <= ctx.current_price <= ctx.buy_high and ctx.sc_s >= 60:
                action = "加仓"; sig = "add"
                r.append(f"持仓盈利{ctx.pnl*100:.0f}%且仍在买入区，信号向好")
                r.append("可适当加仓")
                source = "盈利加仓"
            else:
                if ctx.ff_s >= 55:
                    r.append("主力资金正常")
                if ctx.tc_s >= 55:
                    r.append("技术面正常")
                if ctx.divergence:
                    r.append(f"注意: {ctx.divergence}")
                if not r:
                    r.append("各维度信号平稳，继续持有")
                if ctx.pnl:
                    r.append(f"当前盈亏: {ctx.pnl*100:+.1f}%")
                source = "平稳持有"
        else:
            # 非持仓股: 判断持有/观察
            has_div = len(ctx.dim_divergences) >= 2
            if ctx.ff_s >= 55 or ctx.tc_s >= 55 or ctx.cp_sig in ("buy", "strong_buy"):
                if ctx.cp_sig in ("buy", "strong_buy"):
                    r.append(f"综合看多({ctx.cp_sig})")
                r.append(f"持有至目标价{ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)")
                r.append(f"止损{ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)")
                if has_div:
                    r.append(ctx.dim_divergences[0])
                source = "信号正常"
            else:
                r.append("暂无强烈买卖信号")
                r.append(f"可继续观察，止损{ctx.stop_loss:.2f}")
                source = "等待"
            if ctx.rr >= 1.5:
                r.append(f"盈亏比{ctx.rr}尚可")

        return {
            "action": action, "signal": sig,
            "reasons": r[:4], "source": source,
        }


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
        self._block = BlockAnalyzer()
        self._limit_up = LimitUpAnalyzer()
        self._dragon_tiger = DragonTigerAnalyzer()
        self._margin = MarginAnalyzer()
        self._backtest = SignalBacktest()
        self._watchlist = WatchlistStorage()
        self._db = DatabaseConfig.get_database()
        self._sell_decider = SellDecider()
        self._buy_decider = BuyDecider()
        self._hold_decider = HoldDecider()

    def refresh_all(self, user_id: str = "default", sync_fusion: bool = True) -> Dict[str, Any]:
        """对「自选股 + 持仓 + AI智选候选」统一做买卖点分析，并维护监控生命周期。
        sync_fusion=False 时跳过智选追踪/过期清理（盘中刷新用，只更新持仓+自选买卖点）。"""
        from modules.monitor.lifecycle import MonitorLifecycle
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine

        lifecycle = MonitorLifecycle()
        positions_synced = lifecycle.sync_positions(user_id)
        if sync_fusion:
            fusion_synced = lifecycle.sync_fusion_pick_tracking(user_id)
            expired_cleaned = lifecycle.cleanup_expired_fusion_picks()
        else:
            fusion_synced = {"skipped": True}
            expired_cleaned = {"skipped": True}

        stocks = self._collect_stocks(user_id)

        analyzed = 0
        advice: List[Dict[str, Any]] = []
        if stocks:
            with ThreadPoolExecutor(max_workers=8) as pool:
                fut_map = {pool.submit(self._analyze_one, self._to_analyze_input(s)): s
                           for s in stocks}
                for fut in as_completed(fut_map):
                    s = fut_map[fut]
                    try:
                        result = fut.result()
                    except Exception as e:
                        logger.error(f"Analyze {s.get('code')} failed: {e}")
                        continue
                    if not result:
                        continue
                    self._attach_lifecycle_fields(result, s)
                    self._storage.upsert_signal(result["code"], result)
                    advice.append(self._advice_item(result))
                    analyzed += 1

        account = PaperAccount().get(user_id) or {"cash_balance": 0}
        try:
            positions, _ = TradeEngine().get_positions(user_id)
        except Exception as e:
            logger.error(f"Get positions failed for {user_id}: {e}")
            positions = []

        anomaly_alerts = self._get_anomaly_alerts(account, positions, stocks)
        portfolio_summary = self._portfolio_summary(account, positions, stocks)

        timestamp = datetime.now().isoformat()
        lifecycle_summary = {
            "positions_synced": positions_synced,
            "fusion_tracking_synced": fusion_synced,
            "expired_cleaned": expired_cleaned,
        }
        # 合成"组合建议"文档，供 /portfolio 路由回读最近一次结果
        self._storage.upsert_signal(f"__monitor_portfolio_{user_id}__", {
            "code": f"__monitor_portfolio_{user_id}__",
            "type": "portfolio_advice",
            "user_id": user_id,
            "advice": advice,
            "portfolio_summary": portfolio_summary,
            "anomaly_alerts": anomaly_alerts,
            "lifecycle_summary": lifecycle_summary,
            "analyzed": analyzed,
            "timestamp": timestamp,
        })

        logger.info(f"Monitor refresh done user={user_id}: analyzed={analyzed}, "
                    f"advice={len(advice)}, alerts={len(anomaly_alerts)}")
        return {
            "success": True,
            "advice": advice,
            "portfolio_summary": portfolio_summary,
            "anomaly_alerts": anomaly_alerts,
            "lifecycle_summary": lifecycle_summary,
            "analyzed": analyzed,
            "timestamp": timestamp,
        }

    @staticmethod
    def _to_analyze_input(s: Dict[str, Any]) -> Dict[str, Any]:
        """把 _collect_stocks 条目转成 _analyze_one 入参；持仓标 type=持仓。"""
        is_pos = "position" in (s.get("sources") or [])
        return {
            "code": s["code"],
            "name": s.get("name", ""),
            "type": "持仓" if is_pos else "自选",
            "shares": s.get("shares", 0),
            "avg_cost": s.get("avg_cost", 0),
            "market_value": s.get("market_value", 0),
            "pnl": s.get("pnl", 0),  # 已是小数口径（见 _collect_stocks）
        }

    @staticmethod
    def _attach_lifecycle_fields(result: Dict[str, Any], meta: Dict[str, Any]) -> None:
        """把来源/连续入选/强化信号写入分析结果；连续≥3天插入强化信号文案。"""
        sources = meta.get("sources", []) or []
        consecutive = int(meta.get("consecutive_days", 0) or 0)
        is_fusion = "fusion_pick" in sources
        strong = is_fusion and consecutive >= 3
        result["sources"] = sources
        result["consecutive_days"] = consecutive if is_fusion else 0
        result["strong_signal"] = strong
        result["first_selected_at"] = meta.get("first_selected_at", "") or ""
        if strong:
            ta = result.get("trading_advice") or {}
            reasons = list(ta.get("reasons") or [])
            tip = f"已连续{consecutive}天入选AI智选，关注度持续走高"
            if tip not in reasons:
                ta["reasons"] = [tip] + reasons
            result["trading_advice"] = ta

    @staticmethod
    def _advice_item(result: Dict[str, Any]) -> Dict[str, Any]:
        """组合建议列表的单项：身份 + 生命周期字段 + 现有 trading_advice 全部字段。
        前端按 sources 自行分组展示（不再分长短线两个数组）。"""
        ta = result.get("trading_advice", {}) or {}
        return {
            "code": result.get("code"),
            "name": result.get("name", ""),
            "price": result.get("price", 0),
            "sources": result.get("sources", []),
            "consecutive_days": result.get("consecutive_days", 0),
            "strong_signal": result.get("strong_signal", False),
            "first_selected_at": result.get("first_selected_at", ""),
            **ta,
        }

    def _get_anomaly_alerts(self, account_info: Dict, current_positions: List[Dict],
                            monitor_stocks: Optional[List[Dict]] = None) -> List[Dict]:
        """主力资金异动：近 N 日 Z-score 聚合，anomaly_score 超阈值才返回。
        阈值/窗口可配（settings）。持仓股优先，其次监控对象，再其余。"""
        try:
            import numpy as np
            from datetime import timedelta
            from config.settings import settings

            threshold = getattr(settings, "MONITOR_ANOMALY_THRESHOLD", 60)
            window_days = getattr(settings, "MONITOR_ANOMALY_WINDOW_DAYS", 5)

            def _bare(c: str) -> str:
                return c[2:] if c[:2] in ("SH", "SZ") else c

            hold = {_bare(p.get("code", "")) for p in current_positions}
            sources_by_bare = {_bare(s.get("code", "")): (s.get("sources") or [])
                               for s in (monitor_stocks or [])}
            days = window_days
            cutoff = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
            pipe = [
                {"$match": {"date": {"$gte": cutoff}}},
                {"$sort": {"date": -1}},
                {"$group": {
                    "_id": "$code",
                    "name": {"$first": "$name"},
                    "latest_date": {"$first": "$date"},
                    "latest_net": {"$first": "$main_net_inflow"},
                    "latest_amount": {"$first": "$total_amount"},
                    "nets": {"$push": "$main_net_inflow"},
                    "count": {"$sum": 1},
                }},
                {"$match": {"count": {"$gte": days - 1}}},
            ]

            results: List[Dict] = []
            for doc in self._db["fund_flow"].aggregate(pipe, allowDiskUse=True):
                code = doc["_id"]
                nets = [float(x or 0) for x in doc["nets"]]
                if len(nets) < 2:
                    continue
                latest_net = float(doc["latest_net"] or 0)
                avg_net = float(np.mean(nets))
                std_net = float(np.std(nets)) if len(nets) > 1 else 1
                z_score = (latest_net - avg_net) / std_net if std_net > 0 else 0

                consec = 0
                for v in nets:
                    if v > 0: consec += 1
                    elif v < 0: consec -= 1
                    else: break

                first_half = float(np.mean(nets[:-2])) if len(nets) > 2 else avg_net
                second_half = float(np.mean(nets[:2])) if len(nets) >= 2 else latest_net
                reversal = second_half > 0 > first_half or second_half < 0 < first_half

                latest_amount = float(doc["latest_amount"] or 1)
                net_ratio = latest_net / latest_amount if latest_amount > 0 else 0
                anomaly_score = abs(z_score) * 40 + abs(consec) * 8 + (20 if reversal else 0) + abs(net_ratio) * 10
                if anomaly_score <= threshold:
                    continue

                anomaly_type = "大幅流入" if latest_net > 0 and z_score > 1.5 else \
                               "大幅流出" if latest_net < 0 and z_score < -1.5 else \
                               "连续流入" if consec >= 3 else \
                               "连续流出" if consec <= -3 else \
                               "趋势反转" if reversal else "关注"
                bare = _bare(code)
                item = {
                    "code": code,
                    "name": doc.get("name", code),
                    "latest_date": doc["latest_date"],
                    "latest_net": round(latest_net, 2),
                    "z_score": round(z_score, 2),
                    "consecutive_days": consec,
                    "reversal": reversal,
                    "anomaly_score": round(anomaly_score, 1),
                    "anomaly_type": anomaly_type,
                    "is_holding": bare in hold,
                }
                if bare in sources_by_bare:
                    item["in_monitor"] = True
                    item["monitor_sources"] = sources_by_bare[bare]
                results.append(item)
            # 排序优先级：持仓 > 监控对象 > 其余异动股
            results.sort(key=lambda r: (not r["is_holding"],
                                        not r.get("in_monitor", False),
                                        -r["anomaly_score"]))
            return results
        except Exception as e:
            logger.error(f"Anomaly alerts failed: {e}")
            return []

    def _portfolio_summary(self, account: Dict, positions: List[Dict],
                           stocks: List[Dict]) -> Dict:
        """组合概览：总市值 + 三来源数量分布 + 重叠数（不再有长短线资金配比）。"""
        cash = (account or {}).get("cash_balance", 0) or 0
        position_value = sum(p.get("market_value", 0) or 0 for p in positions)
        total_value = cash + position_value

        def codes_with(src):
            return {s["code"] for s in stocks if src in (s.get("sources") or [])}

        pos_codes = codes_with("position")
        watch_codes = codes_with("watchlist")
        fusion_codes = codes_with("fusion_pick")
        overlap = ((pos_codes & watch_codes) | (pos_codes & fusion_codes)
                   | (watch_codes & fusion_codes))
        return {
            "total_value": round(total_value, 2),
            "cash": round(cash, 2),
            "position_value": round(position_value, 2),
            "monitor_count": len(stocks),
            "position_count": len(pos_codes),
            "watchlist_count": len(watch_codes),
            "fusion_pick_count": len(fusion_codes),
            "overlap_count": len(overlap),
            "all_three_count": len(pos_codes & watch_codes & fusion_codes),
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

    def _collect_stocks(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """汇总三个来源（持仓 + 自选股 + AI智选最新一轮），按 code 去重并合并 sources。
        返回每项带 sources 列表 + 持仓/智选附带字段，供 refresh_all 统一分析。"""
        merged: Dict[str, Dict[str, Any]] = {}

        def _entry(code: str, name: str = "") -> Dict[str, Any]:
            e = merged.get(code)
            if e is None:
                e = {"code": code, "name": name, "sources": [],
                     "shares": 0, "avg_cost": 0, "market_value": 0, "pnl": 0,
                     "fusion_score": 0, "consecutive_days": 0, "first_selected_at": ""}
                merged[code] = e
            if name and not e.get("name"):
                e["name"] = name
            return e

        def _add_source(e: Dict[str, Any], src: str) -> None:
            if src not in e["sources"]:
                e["sources"].append(src)

        # a) 持仓：模拟盘 TradeEngine（仓位信息以此为准）+ 兼容实盘 positions 集合
        try:
            from modules.paper_trading.trade_engine import TradeEngine
            positions, _ = TradeEngine().get_positions(user_id)
            for p in positions:
                code = p.get("code")
                if not code or (p.get("shares", 0) or 0) <= 0:
                    continue
                e = _entry(code, p.get("name", ""))
                _add_source(e, "position")
                e["shares"] = p.get("shares", 0)
                e["avg_cost"] = p.get("avg_cost", 0)
                e["market_value"] = p.get("market_value", 0)
                e["pnl"] = (p.get("pnl_percent", 0) or 0) / 100  # _analyze_one 用小数口径
        except Exception as e:
            logger.error(f"_collect_stocks paper positions failed: {e}")
        try:
            for p in self._db["positions"].find():
                code = p.get("code")
                if not code or (p.get("shares", 0) or 0) <= 0:
                    continue
                e = _entry(code, p.get("name", ""))
                _add_source(e, "position")
                if not e["shares"]:
                    e["shares"] = p.get("shares", 0)
                    e["avg_cost"] = p.get("avg_cost", 0)
                    e["market_value"] = p.get("market_value", 0)
                    e["pnl"] = p.get("pnl", 0)
        except Exception as e:
            logger.error(f"_collect_stocks legacy positions failed: {e}")

        # b) 自选股
        try:
            for w in self._watchlist.get_user_watchlist(user_id):
                code = w.get("code")
                if not code:
                    continue
                _add_source(_entry(code, w.get("name", w.get("A股简称", ""))), "watchlist")
        except Exception as e:
            logger.error(f"_collect_stocks watchlist failed: {e}")

        # c) AI 智选最新一轮 picks
        try:
            latest = self._db["fusion_pick_results"].find_one(
                {}, sort=[("created_at", -1)])
            for pick in ((latest or {}).get("picks") or []):
                code = pick.get("code")
                if not code:
                    continue
                e = _entry(code, pick.get("name", ""))
                _add_source(e, "fusion_pick")
                e["fusion_score"] = pick.get("fusion_score", 0)
                if pick.get("track"):
                    e["track"] = pick["track"]
        except Exception as e:
            logger.error(f"_collect_stocks fusion picks failed: {e}")

        # 补充智选追踪字段（consecutive_days / first_selected_at 由 lifecycle 写入 monitor_signals）
        try:
            codes = list(merged.keys())
            if codes:
                for d in self._db["monitor_signals"].find(
                        {"code": {"$in": codes}},
                        {"code": 1, "consecutive_days": 1, "first_selected_at": 1}):
                    e = merged.get(d.get("code"))
                    if e:
                        e["consecutive_days"] = d.get("consecutive_days", 0) or 0
                        e["first_selected_at"] = d.get("first_selected_at", "") or ""
        except Exception as e:
            logger.error(f"_collect_stocks tracking enrich failed: {e}")

        stocks = list(merged.values())
        logger.info(f"Collected {len(stocks)} stocks to monitor (user={user_id})")
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
            concepts = self._block.get_concept_details(code)
            sector_flow = self._block.get_sector_flow(code)
            limit_up = self._limit_up.analyze(code)
            dragon_tiger = self._dragon_tiger.analyze(code)
            margin = self._margin.analyze(code)
            composite = self._composite.composite(
                fund_flow, research, technical, fundamental, valuation, news_sentiment,
            )
        except Exception as e:
            logger.error(f"Analyze {code} failed: {e}")
            return None

        current_price = technical.get("current_price", 0)
        reflection = self._reflect_on_history(code, current_price)

        pp = price_prediction
        ctx = AdviceContext(
            current_price=current_price,
            target_price=pp.get("target_price", 0),
            stop_loss=pp.get("stop_loss", 0),
            buy_low=pp.get("buy_zone_low", 0),
            buy_high=pp.get("buy_zone_high", 0),
            expected_return=pp.get("expected_return", 0),
            max_loss=pp.get("max_loss", 0),
            stock_type=stock_type,
            shares=stock.get("shares", 0),
            avg_cost=stock.get("avg_cost", 0),
            market_value=stock.get("market_value", 0),
            pnl=stock.get("pnl", 0),
            ff_s=fund_flow.get("short_term", {}).get("score", 50),
            ff_l=fund_flow.get("long_term", {}).get("score", 50),
            rs_s=research.get("short_term", {}).get("score", 50),
            rs_l=research.get("long_term", {}).get("score", 50),
            rs_c=research.get("composite_score", 50),
            tc_s=technical.get("short_term", {}).get("score", 50),
            tc_l=technical.get("long_term", {}).get("score", 50),
            vl_s=valuation.get("score", 50),
            cp_s=composite.get("composite_score", 50),
            cp_sig=composite.get("composite_signal", "hold"),
            sc_s=composite.get("short_term", {}).get("score", 50),
            sc_l=composite.get("long_term", {}).get("score", 50),
            divergence=composite.get("divergence", ""),
            ns_bullish=(news_sentiment or {}).get("overall", {}).get("bullish", False),
            ns_score=(news_sentiment or {}).get("overall", {}).get("score", 50),
            ns_pos_count=(news_sentiment or {}).get("positive_count", 0),
            dim_divergences=self._detect_dim_divergence(
                fund_flow.get("short_term", {}).get("score", 50),
                research.get("short_term", {}).get("score", 50),
                technical.get("short_term", {}).get("score", 50),
                valuation.get("score", 50),
                composite.get("short_term", {}).get("score", 50),
                composite.get("long_term", {}).get("score", 50),
            ),
            concepts=(concepts or {}).get("concepts", []),
            sector_flow=sector_flow or {},
            limit_up=limit_up or {},
            dragon_tiger=dragon_tiger or {},
            margin=margin or {},
        )
        ctx.rr = _calc_rr(ctx.expected_return, ctx.max_loss)

        sell = self._sell_decider.decide(ctx)
        buy = self._buy_decider.decide(ctx)
        hold = self._hold_decider.decide(ctx)

        action, sig, reasons, source = self._merge_advice(sell, buy, hold, ctx)

        confidence_level = self._calc_advice_confidence(
            ctx.ff_s, ctx.rs_s, ctx.tc_s, ctx.vl_s, ctx.sc_s, ctx.sc_l,
        )
        time_horizon = self._estimate_holding_period(
            ctx.rr, ctx.expected_return, ctx.tc_s, ctx.ff_s,
        )

        result = {
            "code": code,
            "name": name or info.get("A股简称", info.get("name", "")),
            "type": stock_type,
            "price": current_price,
            "change_rate": 0.0,
            "industry": industry,
            "concepts": (concepts or {}).get("concepts", []),
            "concept_details": (concepts or {}).get("concept_details", []),
            "sector_flow": sector_flow or {},
            "limit_up": limit_up or {},
            "dragon_tiger": dragon_tiger or {},
            "margin": margin or {},
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
            "trading_advice": self._build_advice_dict(ctx, action, sig, reasons, source,
                                                      confidence_level, time_horizon, reflection),
            "reflection": reflection,
            "updated_at": datetime.now().isoformat(),
        }
        self._update_price_change(result, code)
        return result

    def _merge_advice(self, sell: Optional[Dict], buy: Optional[Dict],
                      hold: Dict, ctx: AdviceContext) -> tuple:
        """合并卖出/买入/持有建议 — 卖出优先 > 买入 > 持有"""
        if sell:
            return sell["action"], sell["signal"], sell["reasons"], sell["source"]
        if buy:
            return buy["action"], buy["signal"], buy["reasons"], buy["source"]
        return hold["action"], hold["signal"], hold["reasons"], hold["source"]

    def _build_advice_dict(self, ctx: AdviceContext, action: str, sig: str,
                           reasons: List[str], source: str,
                           confidence_level: str, time_horizon: str,
                           reflection: Optional[Dict]) -> Dict:
        display_reason = "; ".join(reasons[:3]) if reasons else "暂无明确信号"

        entry_range = {"low": round(ctx.buy_low, 2), "high": round(ctx.buy_high, 2)}

        if sig == "sell":
            if ctx.current_price >= ctx.target_price and ctx.target_price > 0:
                summary = f"建议在 {ctx.current_price:.2f} 止盈，已达目标价 {ctx.target_price:.2f}"
            elif ctx.stop_loss > 0 and ctx.current_price <= ctx.stop_loss * 1.03:
                summary = f"建议在 {ctx.current_price:.2f} 止损，接近止损线 {ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)"
            else:
                summary = f"建议卖出，目标价 {ctx.target_price:.2f}，止损 {ctx.stop_loss:.2f}"
        elif sig == "buy":
            summary = self._build_buy_summary(ctx)
        elif sig == "add":
            summary = self._build_add_summary(ctx)
        elif sig == "reduce":
            summary = f"建议减仓，当前持仓盈亏{ctx.pnl*100:+.1f}%，目标{ctx.target_price:.2f}"
        else:
            summary = self._build_hold_summary(ctx)

        return {
            "action": action,
            "action_signal": sig,
            "signal_source": source,
            "reason": display_reason,
            "details": {
                "fund_flow_score": round(ctx.ff_s, 1),
                "research_score": round(ctx.rs_s, 1),
                "technical_score": round(ctx.tc_s, 1),
                "valuation_score": round(ctx.vl_s, 1),
                "composite_score": round(ctx.cp_s, 1),
            },
            "reasons": reasons[:5],
            "entry_price_range": entry_range,
            "take_profit": round(ctx.target_price, 2) if ctx.target_price else 0,
            "stop_loss": round(ctx.stop_loss, 2) if ctx.stop_loss else 0,
            "expected_return": ctx.expected_return,
            "max_loss": ctx.max_loss,
            "risk_reward_ratio": ctx.rr,
            "current_position": self._position_text(ctx),
            "distance_to_target": self._dist_text(ctx),
            "advice": {
                "summary": summary,
                "buy_price_low": round(ctx.buy_low, 2),
                "buy_price_high": round(ctx.buy_high, 2),
                "target_price": round(ctx.target_price, 2) if ctx.target_price else 0,
                "stop_loss_price": round(ctx.stop_loss, 2) if ctx.stop_loss else 0,
                "hold_period": f"持有至目标价 {round(ctx.target_price, 2)}" if ctx.target_price else "",
                "expected_return": ctx.expected_return,
                "max_loss": ctx.max_loss,
                "time_horizon": time_horizon,
                "confidence_level": confidence_level,
                "entry_price": round(ctx.current_price, 2),
            },
            "divergence_warnings": ctx.dim_divergences[:3],
            "reflection": reflection,
        }

    def _build_buy_summary(self, ctx: AdviceContext) -> str:
        if ctx.buy_low <= ctx.current_price <= ctx.buy_high:
            s = f"建议在 {ctx.buy_low:.2f}~{ctx.buy_high:.2f} 买入"
        else:
            s = f"当前{ctx.current_price:.2f}略高于买入区({ctx.buy_low:.2f}~{ctx.buy_high:.2f})"
        s += f"，目标价 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)，止损 {ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)"
        return s

    def _build_add_summary(self, ctx: AdviceContext) -> str:
        return (f"建议加仓，当前持仓盈亏{ctx.pnl*100:+.1f}%"
                f"，买入区 {ctx.buy_low:.2f}~{ctx.buy_high:.2f}"
                f"，目标 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)")

    def _build_hold_summary(self, ctx: AdviceContext) -> str:
        if ctx.buy_low <= ctx.current_price <= ctx.buy_high:
            s = f"建议持有至目标价 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)"
        elif ctx.current_price > ctx.buy_high:
            s = f"已持有，持有至目标价 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)"
            if ctx.is_position:
                s += "，不建议加仓"
        else:
            s = f"建议持有等待反弹，目标价 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)"
        s += f"，止损 {ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)"
        return s

    def _position_text(self, ctx: AdviceContext) -> str:
        if ctx.buy_low <= ctx.current_price <= ctx.buy_high:
            return "在买入区内"
        elif ctx.current_price < ctx.buy_low:
            return "低于买入区"
        return "高于买入区"

    def _dist_text(self, ctx: AdviceContext) -> str:
        if ctx.current_price >= ctx.target_price and ctx.target_price > 0:
            return f"已到目标价({ctx.target_price:.2f})，建议止盈"
        if ctx.current_price >= ctx.target_price * 0.95 and ctx.target_price > 0:
            return f"接近目标价，距目标还有{ctx.target_price-ctx.current_price:+.2f}"
        d = round((ctx.target_price / ctx.current_price - 1) * 100, 1) if ctx.current_price > 0 else 0
        return f"距目标还有+{d}%"

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
        self, ff_s: float, rs_s: float,
        tc_s: float, vl_s: float, sc_s: float, sc_l: float,
    ) -> List[str]:
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

    def _calc_advice_confidence(self, ff_s: float, rs_s: float,
                                tc_s: float, vl_s: float,
                                sc_s: float, sc_l: float) -> str:
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

    def _estimate_holding_period(self, rr: float, exp_ret: float, tc_s: float, ff_s: float) -> str:
        if rr >= 5 and exp_ret >= 30:
            return "中期持有(15-30天)"
        elif rr >= 3 and exp_ret >= 15:
            return "短期持有(5-15天)"
        elif tc_s >= 65 or ff_s >= 65:
            return "短线交易(3-7天)"
        return "中期持有(15-60天)"

    def _reflect_on_history(self, code: str, current_price: float) -> Optional[Dict]:
        try:
            history = list(
                self._db["monitor_signal_history"]
                .find({"code": code})
                .sort("created_at", -1)
                .limit(5)
            )
            if len(history) < 2:
                return None

            prev = history[1]
            prev_action = prev.get("trading_advice", {}).get("action", "持有")
            prev_price = prev.get("price", 0)
            prev_target = prev.get("price_prediction", {}).get("target_price", 0)

            if prev_price <= 0:
                return None

            change_pct = round((current_price - prev_price) / prev_price * 100, 2)

            parts = [f"上次({prev_action})价{prev_price:.2f}→现{current_price:.2f}({change_pct:+.2f}%)"]
            if prev_action in ("买入", "加仓") and change_pct > 0:
                parts.append("建议正确")
            elif prev_action in ("买入", "加仓") and change_pct < -3:
                parts.append("买入后下跌需关注")
            elif prev_action == "卖出" and change_pct < 0:
                parts.append("卖出建议正确")
            elif prev_action == "卖出" and change_pct > 3:
                parts.append("卖出后上涨需重新评估")

            if prev_target > 0:
                if current_price >= prev_target:
                    parts.append("已达上次目标价")
                else:
                    pct = round((prev_target / current_price - 1) * 100, 1)
                    parts.append(f"距上次目标还差{pct:+.1f}%")

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
