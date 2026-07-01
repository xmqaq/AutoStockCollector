"""买卖点决策器 — 基于多维评分的规则决策（从 engine.py 迁出，精简）。

重构去掉对 limit_up / margin / dragon_tiger / sector_flow 的依赖：
- 涨跌停改用实时 change_rate 粗判（≥9.8% 视为涨停，连板不追）
- 板块轮动/龙虎榜/融资融券分支删除（对短线决策价值低且数据 T+1）
- 估值维度 vl_s 复用 fundamental.score（valuation.py 已并入 fundamental）
保留：止盈止损、资金流、技术面、综合评分、盈亏比、舆情等核心决策维度。
"""
from typing import Any, Dict, List, Optional

# 涨停阈值：主板 10%，ST 5%，这里取 9.8% 粗判（含误差）
_LIMIT_UP_THRESHOLD = 9.8


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
        self.ff_s: float = 50          # 资金流短期
        self.ff_l: float = 50          # 资金流长期
        self.rs_s: float = 50          # 研报短期
        self.rs_l: float = 50          # 研报长期
        self.rs_c: float = 50          # 研报综合
        self.tc_s: float = 50          # 技术短期
        self.tc_l: float = 50          # 技术长期
        self.vl_s: float = 50          # 估值（复用 fundamental.score）
        self.cp_s: float = 50          # 综合评分
        self.cp_sig: str = "hold"      # 综合信号
        self.sc_s: float = 50          # 短期综合
        self.sc_l: float = 50          # 长期综合
        self.divergence: str = ""
        self.ns_bullish: bool = False  # 舆情利好
        self.ns_score: float = 50
        self.ns_pos_count: int = 0
        self.change_rate: float = 0.0  # 实时涨跌幅（用于涨停粗判）
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def is_position(self) -> bool:
        return self.stock_type == "持仓"

    @property
    def is_limit_up(self) -> bool:
        """粗判涨停：实时涨幅 ≥9.8%。（连板天数无法从实时数据获取，仅做涨停抑制）"""
        return self.change_rate >= _LIMIT_UP_THRESHOLD


def _calc_rr(exp_ret: float, max_loss: float) -> float:
    return round(exp_ret / max_loss, 2) if max_loss > 0 else 0


class SellDecider:
    """卖点检测 — 止盈/止损/资金撤退/技术破位/双弱"""

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
        return {"action": "卖出", "signal": "sell", "reasons": reasons[:3], "source": source}


class BuyDecider:
    """买入/加仓点检测 — 涨停抑制 + 买入区 + 多维共振/盈亏比"""

    def decide(self, ctx: AdviceContext) -> Optional[Dict]:
        # 涨停抑制：涨停不追（连板天数无法从实时数据获取，涨停即不追）
        if ctx.is_limit_up:
            return None

        r = []
        in_zone = ctx.buy_low <= ctx.current_price <= ctx.buy_high
        slightly_above = ctx.current_price <= ctx.buy_high * 1.2

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
            pct = round((ctx.current_price / ctx.buy_high - 1) * 100, 1) if ctx.buy_high else 0
            r.append(f"价格{ctx.current_price:.2f}仅高于买入区{pct}%")
            r.append(f"资金{ctx.ff_s:.0f}+技术{ctx.tc_s:.0f}+估值{ctx.vl_s:.0f}多维度看多")
            r.append(f"盈亏比{ctx.rr}，预期收益{ctx.expected_return:+.1f}%")
            return self._buy(action, sig, r, "多维度共振")

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
            if ctx.ff_s >= 55 or ctx.tc_s >= 55 or ctx.cp_sig in ("buy", "strong_buy"):
                if ctx.cp_sig in ("buy", "strong_buy"):
                    r.append(f"综合看多({ctx.cp_sig})")
                r.append(f"持有至目标价{ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)")
                r.append(f"止损{ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)")
                source = "信号正常"
            else:
                r.append("暂无强烈买卖信号")
                r.append(f"可继续观察，止损{ctx.stop_loss:.2f}")
                source = "等待"
            if ctx.rr >= 1.5:
                r.append(f"盈亏比{ctx.rr}尚可")

        return {"action": action, "signal": sig, "reasons": r[:4], "source": source}


def merge_advice(sell: Optional[Dict], buy: Optional[Dict], hold: Dict) -> tuple:
    """合并卖出/买入/持有建议 — 卖出优先 > 买入 > 持有"""
    if sell:
        return sell["action"], sell["signal"], sell["reasons"], sell["source"]
    if buy:
        return buy["action"], buy["signal"], buy["reasons"], buy["source"]
    return hold["action"], hold["signal"], hold["reasons"], hold["source"]


def build_advice(ctx: AdviceContext, action: str, sig: str,
                 reasons: List[str], source: str) -> Dict[str, Any]:
    """构造 trading_advice 字典（精简版：去掉 divergence_warnings/reflection 文案）。"""
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
        summary = _build_buy_summary(ctx)
    elif sig == "add":
        summary = _build_add_summary(ctx)
    elif sig == "reduce":
        summary = f"建议减仓，当前持仓盈亏{ctx.pnl*100:+.1f}%，目标{ctx.target_price:.2f}"
    else:
        summary = _build_hold_summary(ctx)

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
        "advice": {
            "summary": summary,
            "buy_price_low": round(ctx.buy_low, 2),
            "buy_price_high": round(ctx.buy_high, 2),
            "target_price": round(ctx.target_price, 2) if ctx.target_price else 0,
            "stop_loss_price": round(ctx.stop_loss, 2) if ctx.stop_loss else 0,
            "expected_return": ctx.expected_return,
            "max_loss": ctx.max_loss,
            "entry_price": round(ctx.current_price, 2),
        },
    }


def _build_buy_summary(ctx: AdviceContext) -> str:
    if ctx.buy_low <= ctx.current_price <= ctx.buy_high:
        s = f"建议在 {ctx.buy_low:.2f}~{ctx.buy_high:.2f} 买入"
    else:
        s = f"当前{ctx.current_price:.2f}略高于买入区({ctx.buy_low:.2f}~{ctx.buy_high:.2f})"
    s += f"，目标价 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)，止损 {ctx.stop_loss:.2f}(-{ctx.max_loss:.1f}%)"
    return s


def _build_add_summary(ctx: AdviceContext) -> str:
    return (f"建议加仓，当前持仓盈亏{ctx.pnl*100:+.1f}%"
            f"，买入区 {ctx.buy_low:.2f}~{ctx.buy_high:.2f}"
            f"，目标 {ctx.target_price:.2f}(+{ctx.expected_return:.1f}%)")


def _build_hold_summary(ctx: AdviceContext) -> str:
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
