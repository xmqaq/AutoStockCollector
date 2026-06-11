from typing import Any, Dict, List, Optional, TypedDict


class IndicatorConfig(TypedDict, total=False):
    key: str
    dimension: str
    label: str
    enabled: bool
    weight: float
    params: Dict[str, Any]


class StrategyRule(TypedDict, total=False):
    name: str
    type: str  # "selection" | "trading"
    description: str
    enabled: bool
    indicators: List[IndicatorConfig]
    weights: Dict[str, float]
    filters: Dict[str, Any]
    created_at: Any
    updated_at: Any


# ============================================================
# 指标目录 —— 所有可选指标的定义
# ============================================================

INDICATOR_CATALOG: List[Dict[str, Any]] = [
    # ── 基本面 ──
    {"key": "fundamental.roe", "dimension": "fundamental", "label": "ROE 净资产收益率",
     "default_weight": 35, "description": "≥阈值满分",
     "params": {"threshold": 25, "min": 0}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": 1, "max": 100, "step": 1},
         {"key": "min", "label": "最低要求(%)", "min": -50, "max": 100, "step": 1},
     ]},
    {"key": "fundamental.revenue_growth", "dimension": "fundamental", "label": "营收增速",
     "default_weight": 20, "description": "≥阈值满分",
     "params": {"threshold": 30, "min": -10}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": -50, "max": 200, "step": 5},
         {"key": "min", "label": "最低要求(%)", "min": -100, "max": 100, "step": 5},
     ]},
    {"key": "fundamental.profit_growth", "dimension": "fundamental", "label": "净利润增速",
     "default_weight": 20, "description": "≥阈值满分",
     "params": {"threshold": 30, "min": -10}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": -50, "max": 200, "step": 5},
         {"key": "min", "label": "最低要求(%)", "min": -100, "max": 100, "step": 5},
     ]},
    {"key": "fundamental.gross_margin", "dimension": "fundamental", "label": "毛利率",
     "default_weight": 15, "description": "≥阈值满分",
     "params": {"threshold": 60, "min": 10}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": 0, "max": 100, "step": 5},
         {"key": "min", "label": "最低要求(%)", "min": -20, "max": 100, "step": 5},
     ]},
    {"key": "fundamental.debt_ratio", "dimension": "fundamental", "label": "资产负债率",
     "default_weight": 10, "description": "≤阈值满分（越低越好）",
     "params": {"threshold": 30, "max": 80}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": 0, "max": 100, "step": 5},
         {"key": "max", "label": "最高容忍(%)", "min": 20, "max": 100, "step": 5},
     ]},
    # ── 技术面 ──
    {"key": "technical.ma_trend", "dimension": "technical", "label": "均线趋势",
     "default_weight": 30, "description": "多头/空头排列",
     "params": {"fast": 5, "slow": 20}, "param_schema": [
         {"key": "fast", "label": "快线周期(日)", "min": 2, "max": 60, "step": 1},
         {"key": "slow", "label": "慢线周期(日)", "min": 5, "max": 120, "step": 1},
     ]},
    {"key": "technical.macd", "dimension": "technical", "label": "MACD 指标",
     "default_weight": 25, "description": "金叉/死叉/柱状线",
     "params": {"fast": 12, "slow": 26, "signal": 9}, "param_schema": [
         {"key": "fast", "label": "快线(日)", "min": 2, "max": 60, "step": 1},
         {"key": "slow", "label": "慢线(日)", "min": 5, "max": 120, "step": 1},
         {"key": "signal", "label": "信号线(日)", "min": 2, "max": 30, "step": 1},
     ]},
    {"key": "technical.rsi", "dimension": "technical", "label": "RSI 相对强弱",
     "default_weight": 25, "description": "超买超卖区域",
     "params": {"period": 14, "overbought": 70, "oversold": 30}, "param_schema": [
         {"key": "period", "label": "计算周期(日)", "min": 2, "max": 60, "step": 1},
         {"key": "overbought", "label": "超买线", "min": 60, "max": 95, "step": 1},
         {"key": "oversold", "label": "超卖线", "min": 5, "max": 40, "step": 1},
     ]},
    {"key": "technical.momentum", "dimension": "technical", "label": "价格动量",
     "default_weight": 20, "description": "近期涨跌幅",
     "params": {"period": 20}, "param_schema": [
         {"key": "period", "label": "计算周期(日)", "min": 5, "max": 120, "step": 5},
     ]},
    # ── 资金面 ──
    {"key": "fund_flow.net_inflow", "dimension": "fund_flow", "label": "主力净流入",
     "default_weight": 40, "description": "主力资金净流入额",
     "params": {"min_amount": 0}, "param_schema": [
         {"key": "min_amount", "label": "最低净流入(万)", "min": -100000, "max": 100000, "step": 100},
     ]},
    {"key": "fund_flow.main_ratio", "dimension": "fund_flow", "label": "主力成交占比",
     "default_weight": 30, "description": "主力成交额占比",
     "params": {"threshold": 30}, "param_schema": [
         {"key": "threshold", "label": "满分阈值(%)", "min": 5, "max": 80, "step": 1},
     ]},
    {"key": "fund_flow.turnover", "dimension": "fund_flow", "label": "换手率",
     "default_weight": 30, "description": "流通股换手率",
     "params": {"min": 1, "max": 15}, "param_schema": [
         {"key": "min", "label": "最低(%)", "min": 0, "max": 20, "step": 0.5},
         {"key": "max", "label": "最高(%)", "min": 1, "max": 50, "step": 0.5},
     ]},
    # ── 估值面 ──
    {"key": "valuation.pe", "dimension": "valuation", "label": "市盈率 (PE-TTM)",
     "default_weight": 50, "description": "行业调整后评分",
     "params": {"min": 0, "max": 60}, "param_schema": [
         {"key": "min", "label": "最低PE", "min": -100, "max": 50, "step": 5},
         {"key": "max", "label": "最高PE", "min": 10, "max": 300, "step": 5},
     ]},
    {"key": "valuation.pb", "dimension": "valuation", "label": "市净率 (PB)",
     "default_weight": 50, "description": "行业调整后评分",
     "params": {"min": 0, "max": 10}, "param_schema": [
         {"key": "min", "label": "最低PB", "min": -10, "max": 5, "step": 0.5},
         {"key": "max", "label": "最高PB", "min": 1, "max": 50, "step": 0.5},
     ]},
]
