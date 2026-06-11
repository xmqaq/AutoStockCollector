"""内置预设策略，启动时自动写入 DB（当集合为空时）。
基于学术研究与A股实证数据的综合选股策略体系。
"""
from typing import Any, Dict, List


def _ind(key, dim, label, enabled=True, weight=25, params=None, desc=""):
    if params is None:
        params = {}
    return {"key": key, "dimension": dim, "label": label, "enabled": enabled, "weight": weight, "params": params}


_INDICATORS = [
    # fundamental
    _ind("fundamental.roe", "fundamental", "ROE 净资产收益率", True, 35),
    _ind("fundamental.revenue_growth", "fundamental", "营收增速", True, 20),
    _ind("fundamental.profit_growth", "fundamental", "净利润增速", True, 20),
    _ind("fundamental.gross_margin", "fundamental", "毛利率", True, 15),
    _ind("fundamental.debt_ratio", "fundamental", "资产负债率", True, 10),
    # technical
    _ind("technical.ma_trend", "technical", "均线趋势", True, 30),
    _ind("technical.macd", "technical", "MACD 指标", True, 25),
    _ind("technical.rsi", "technical", "RSI 相对强弱", True, 25),
    _ind("technical.momentum", "technical", "价格动量", True, 20),
    # fund_flow
    _ind("fund_flow.net_inflow", "fund_flow", "主力净流入", True, 40),
    _ind("fund_flow.main_ratio", "fund_flow", "主力成交占比", True, 30),
    _ind("fund_flow.turnover", "fund_flow", "换手率", True, 30),
    # valuation
    _ind("valuation.pe", "valuation", "市盈率 (PE-TTM)", True, 50),
    _ind("valuation.pb", "valuation", "市净率 (PB)", True, 50),
]


def _all_indicators():
    return [dict(ind) for ind in _INDICATORS]


def _clone_indicators(overrides: Dict[str, dict]) -> List[Dict[str, Any]]:
    """从全量指标复制并覆写指定 key 的 enabled/weight/params。"""
    result = []
    for ind in _INDICATORS:
        d = dict(ind)
        k = d["key"]
        if k in overrides:
            d.update(overrides[k])
        result.append(d)
    return result


def get_selection_presets() -> List[Dict[str, Any]]:
    return [
        # ===========================================================
        # 策略 1：QARP — 质量 + 合理估值
        # 文献：东方证券深度报告 IC_IR=3.3
        # 思路：优质公司（高ROE/高毛利率/低负债）+ 合理价格（非高估）
        # ===========================================================
        {
            "name": "QARP 质量价值",
            "type": "selection",
            "description": "质量+估值复合策略(IC_IR=3.3)：精选高ROE/高毛利/低杠杆的优质公司，以合理估值买入，A股长期年化24-29%",
            "enabled": True,
            "weights": {"fundamental": 0.55, "technical": 0.05, "fund_flow": 0.10, "valuation": 0.30},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 5e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 40, "params": {"threshold": 25, "min": 15}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 15, "params": {"threshold": 20, "min": 5}},
                "fundamental.profit_growth": {"enabled": True, "weight": 10, "params": {"threshold": 20, "min": 5}},
                "fundamental.gross_margin": {"enabled": True, "weight": 20, "params": {"threshold": 50, "min": 25}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 15, "params": {"threshold": 30, "max": 50}},
                "technical.ma_trend": {"enabled": False},
                "technical.macd": {"enabled": False},
                "technical.rsi": {"enabled": True, "weight": 50, "params": {"period": 14, "overbought": 80, "oversold": 30}},
                "technical.momentum": {"enabled": False},
                "fund_flow.net_inflow": {"enabled": False},
                "fund_flow.main_ratio": {"enabled": False},
                "fund_flow.turnover": {"enabled": True, "weight": 100, "params": {"min": 1, "max": 10}},
                "valuation.pe": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 25}},
                "valuation.pb": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 5}},
            }),
        },
        # ===========================================================
        # 策略 2：GARP — 成长 + 合理估值
        # 文献：Peter Lynch PEG 体系
        # 思路：成长性（高营收/利润增速）+ 质量（高ROE）+ 合理PEG
        # ===========================================================
        {
            "name": "GARP 成长价值",
            "type": "selection",
            "description": "成长+估值平衡策略(PEG)：高营收增速(>20%)+高净利润增速+高ROE+合理PE，寻找被低估的成长股",
            "enabled": True,
            "weights": {"fundamental": 0.50, "technical": 0.15, "fund_flow": 0.15, "valuation": 0.20},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 5e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 20, "params": {"threshold": 20, "min": 10}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 30, "params": {"threshold": 40, "min": 20}},
                "fundamental.profit_growth": {"enabled": True, "weight": 30, "params": {"threshold": 40, "min": 20}},
                "fundamental.gross_margin": {"enabled": True, "weight": 10, "params": {"threshold": 50, "min": 25}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 10, "params": {"threshold": 40, "max": 60}},
                "technical.ma_trend": {"enabled": True, "weight": 40, "params": {"fast": 5, "slow": 20}},
                "technical.macd": {"enabled": True, "weight": 30, "params": {"fast": 12, "slow": 26, "signal": 9}},
                "technical.rsi": {"enabled": False},
                "technical.momentum": {"enabled": True, "weight": 30, "params": {"period": 20}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 50, "params": {"min_amount": 0}},
                "fund_flow.main_ratio": {"enabled": False},
                "fund_flow.turnover": {"enabled": True, "weight": 50, "params": {"min": 1, "max": 15}},
                "valuation.pe": {"enabled": True, "weight": 60, "params": {"min": 0, "max": 35}},
                "valuation.pb": {"enabled": True, "weight": 40, "params": {"min": 0, "max": 8}},
            }),
        },
        # ===========================================================
        # 策略 3：红利 + 低波
        # 文献：中证指数 2010-2024 实证，红利+低波因子 A股最有效
        # 思路：高股息 + 低波动 + 合理估值，防御型核心仓位
        # ===========================================================
        {
            "name": "红利低波防御",
            "type": "selection",
            "description": "红利+低波双因子防御策略：高股息+低波动+低估值+盈利稳定，2010-2024年中证指数实证最为稳健的因子组合",
            "enabled": True,
            "weights": {"fundamental": 0.30, "technical": 0.30, "fund_flow": 0.10, "valuation": 0.30},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 3e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 30, "params": {"threshold": 15, "min": 8}},
                "fundamental.revenue_growth": {"enabled": False},
                "fundamental.profit_growth": {"enabled": True, "weight": 25, "params": {"threshold": 15, "min": 0}},
                "fundamental.gross_margin": {"enabled": True, "weight": 20, "params": {"threshold": 40, "min": 20}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 25, "params": {"threshold": 35, "max": 55}},
                "technical.ma_trend": {"enabled": True, "weight": 25, "params": {"fast": 10, "slow": 30}},
                "technical.macd": {"enabled": False},
                "technical.rsi": {"enabled": True, "weight": 35, "params": {"period": 14, "overbought": 60, "oversold": 30}},
                "technical.momentum": {"enabled": True, "weight": 40, "params": {"period": 60}},
                "fund_flow.net_inflow": {"enabled": False},
                "fund_flow.main_ratio": {"enabled": False},
                "fund_flow.turnover": {"enabled": True, "weight": 100, "params": {"min": 0.5, "max": 8}},
                "valuation.pe": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 15}},
                "valuation.pb": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 2}},
            }),
        },
        # ===========================================================
        # 策略 4：五因子增强模型
        # 文献：Fama-French (2015) 五因子 + A股实证（华泰证券2017）
        # 思路：市值(小盘溢价) + 估值(价值) + 盈利(RMW) + 投资(CMA) + 动量
        # ===========================================================
        {
            "name": "五因子增强",
            "type": "selection",
            "description": "Fama-French五因子增强模型：规模+价值+盈利+投资+动量五维度，A股实证GRS检验通过，解释力优于三因子模型",
            "enabled": True,
            "weights": {"fundamental": 0.35, "technical": 0.25, "fund_flow": 0.15, "valuation": 0.25},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 3e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 40, "params": {"threshold": 15, "min": 5}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 20, "params": {"threshold": 20, "min": 0}},
                "fundamental.profit_growth": {"enabled": True, "weight": 20, "params": {"threshold": 20, "min": 0}},
                "fundamental.gross_margin": {"enabled": True, "weight": 10, "params": {"threshold": 40, "min": 15}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 10, "params": {"threshold": 45, "max": 65}},
                "technical.ma_trend": {"enabled": True, "weight": 30, "params": {"fast": 5, "slow": 20}},
                "technical.macd": {"enabled": True, "weight": 25, "params": {"fast": 12, "slow": 26, "signal": 9}},
                "technical.rsi": {"enabled": True, "weight": 20, "params": {"period": 14, "overbought": 70, "oversold": 30}},
                "technical.momentum": {"enabled": True, "weight": 25, "params": {"period": 20}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 40, "params": {"min_amount": -1000}},
                "fund_flow.main_ratio": {"enabled": True, "weight": 30, "params": {"threshold": 25}},
                "fund_flow.turnover": {"enabled": True, "weight": 30, "params": {"min": 1, "max": 15}},
                "valuation.pe": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 30}},
                "valuation.pb": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 6}},
            }),
        },
        # ===========================================================
        # 策略 5：动量 + 资金流因子轮动
        # 文献：Gupta & Kelly (2019) 因子动量；A股因子动量夏普1.15
        # https://doi.org/10.1016/j.empfin.2023.101857
        # 思路：因子自身也有动量→配置近期表现最强的因子
        # ===========================================================
        {
            "name": "因子动量轮动",
            "type": "selection",
            "description": "因子动量策略(夏普1.15)：跟踪各因子近期表现，超配强势因子、低配弱势因子。A股因子动量收益为美国市场的近两倍",
            "enabled": True,
            "weights": {"fundamental": 0.25, "technical": 0.35, "fund_flow": 0.30, "valuation": 0.10},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 5e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 25, "params": {"threshold": 15, "min": 5}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 25, "params": {"threshold": 20, "min": 0}},
                "fundamental.profit_growth": {"enabled": True, "weight": 25, "params": {"threshold": 20, "min": 0}},
                "fundamental.gross_margin": {"enabled": True, "weight": 15, "params": {"threshold": 40, "min": 15}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 10, "params": {"threshold": 50, "max": 70}},
                "technical.ma_trend": {"enabled": True, "weight": 35, "params": {"fast": 5, "slow": 20}},
                "technical.macd": {"enabled": True, "weight": 25, "params": {"fast": 12, "slow": 26, "signal": 9}},
                "technical.rsi": {"enabled": True, "weight": 15, "params": {"period": 14, "overbought": 70, "oversold": 40}},
                "technical.momentum": {"enabled": True, "weight": 25, "params": {"period": 20}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 50, "params": {"min_amount": 0}},
                "fund_flow.main_ratio": {"enabled": True, "weight": 30, "params": {"threshold": 30}},
                "fund_flow.turnover": {"enabled": True, "weight": 20, "params": {"min": 1, "max": 20}},
                "valuation.pe": {"enabled": False},
                "valuation.pb": {"enabled": True, "weight": 100, "params": {"min": 0, "max": 8}},
            }),
        },
        # ===========================================================
        # 策略 6：短周期交易型阿尔法
        # 文献：短周期价量特征多因子阿尔法体系（近200个因子）
        # 思路：全部因子来自价格与成交量数据，高频换仓，捕捉交易行为
        # ===========================================================
        {
            "name": "交易型阿尔法",
            "type": "selection",
            "description": "短周期交易型多因子阿尔法：基于量价特征的短线选股，全部信号来自日频价格与成交量数据，适合T+2~T+5高频换仓",
            "enabled": True,
            "weights": {"fundamental": 0.05, "technical": 0.55, "fund_flow": 0.35, "valuation": 0.05},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 5e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": False},
                "fundamental.revenue_growth": {"enabled": False},
                "fundamental.profit_growth": {"enabled": False},
                "fundamental.gross_margin": {"enabled": False},
                "fundamental.debt_ratio": {"enabled": True, "weight": 100, "params": {"threshold": 50, "max": 70}},
                "technical.ma_trend": {"enabled": True, "weight": 30, "params": {"fast": 5, "slow": 10}},
                "technical.macd": {"enabled": True, "weight": 20, "params": {"fast": 8, "slow": 17, "signal": 9}},
                "technical.rsi": {"enabled": True, "weight": 25, "params": {"period": 7, "overbought": 75, "oversold": 25}},
                "technical.momentum": {"enabled": True, "weight": 25, "params": {"period": 10}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 50, "params": {"min_amount": 0}},
                "fund_flow.main_ratio": {"enabled": True, "weight": 30, "params": {"threshold": 35}},
                "fund_flow.turnover": {"enabled": True, "weight": 20, "params": {"min": 2, "max": 25}},
                "valuation.pe": {"enabled": False},
                "valuation.pb": {"enabled": False},
            }),
        },
        # ===========================================================
        # 策略 7：机器学习多因子综合
        # 文献：基于 XGBoost/Lasso 的多因子选股（沪深300实证）
        # 思路：杠杆因子+流动性因子最重要，综合5种ML算法信号
        # ===========================================================
        {
            "name": "ML多因子综合",
            "type": "selection",
            "description": "机器学习多因子综合选股(OLS/Lasso/RF/XGB/ElasticNet)：研究发现杠杆因子和流动性因子重要性最高，多算法融合稳健超额收益",
            "enabled": True,
            "weights": {"fundamental": 0.30, "technical": 0.25, "fund_flow": 0.30, "valuation": 0.15},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 5e7},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 25, "params": {"threshold": 20, "min": 5}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 20, "params": {"threshold": 25, "min": 0}},
                "fundamental.profit_growth": {"enabled": True, "weight": 20, "params": {"threshold": 25, "min": 0}},
                "fundamental.gross_margin": {"enabled": True, "weight": 15, "params": {"threshold": 45, "min": 15}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 20, "params": {"threshold": 40, "max": 65}},
                "technical.ma_trend": {"enabled": True, "weight": 30, "params": {"fast": 5, "slow": 20}},
                "technical.macd": {"enabled": True, "weight": 25, "params": {"fast": 12, "slow": 26, "signal": 9}},
                "technical.rsi": {"enabled": True, "weight": 20, "params": {"period": 14, "overbought": 70, "oversold": 30}},
                "technical.momentum": {"enabled": True, "weight": 25, "params": {"period": 20}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 40, "params": {"min_amount": 0}},
                "fund_flow.main_ratio": {"enabled": True, "weight": 30, "params": {"threshold": 30}},
                "fund_flow.turnover": {"enabled": True, "weight": 30, "params": {"min": 1, "max": 15}},
                "valuation.pe": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 40}},
                "valuation.pb": {"enabled": True, "weight": 50, "params": {"min": 0, "max": 8}},
            }),
        },
        # ===========================================================
        # 策略 8：行业景气 + 资金流向
        # 思路：行业轮动逻辑——资金率先流入的行业有短期动量，
        # 结合个股基本面和板块资金流，精选龙头
        # ===========================================================
        {
            "name": "行业轮动先锋",
            "type": "selection",
            "description": "行业景气+资金轮动策略：追踪板块资金流向与个股基本面共振，精选各行业资金面与基本面双优的龙头标的",
            "enabled": True,
            "weights": {"fundamental": 0.25, "technical": 0.20, "fund_flow": 0.45, "valuation": 0.10},
            "filters": {"exclude_st": True, "min_kline_bars": 60, "min_avg_amount": 1e8},
            "indicators": _clone_indicators({
                "fundamental.roe": {"enabled": True, "weight": 30, "params": {"threshold": 20, "min": 8}},
                "fundamental.revenue_growth": {"enabled": True, "weight": 20, "params": {"threshold": 25, "min": 5}},
                "fundamental.profit_growth": {"enabled": True, "weight": 20, "params": {"threshold": 25, "min": 5}},
                "fundamental.gross_margin": {"enabled": True, "weight": 15, "params": {"threshold": 45, "min": 20}},
                "fundamental.debt_ratio": {"enabled": True, "weight": 15, "params": {"threshold": 40, "max": 60}},
                "technical.ma_trend": {"enabled": True, "weight": 35, "params": {"fast": 5, "slow": 20}},
                "technical.macd": {"enabled": True, "weight": 25, "params": {"fast": 12, "slow": 26, "signal": 9}},
                "technical.rsi": {"enabled": True, "weight": 15, "params": {"period": 14, "overbought": 70, "oversold": 30}},
                "technical.momentum": {"enabled": True, "weight": 25, "params": {"period": 20}},
                "fund_flow.net_inflow": {"enabled": True, "weight": 50, "params": {"min_amount": 0}},
                "fund_flow.main_ratio": {"enabled": True, "weight": 35, "params": {"threshold": 30}},
                "fund_flow.turnover": {"enabled": True, "weight": 15, "params": {"min": 1, "max": 15}},
                "valuation.pe": {"enabled": False},
                "valuation.pb": {"enabled": True, "weight": 100, "params": {"min": 0, "max": 8}},
            }),
        },
    ]


def get_trading_presets() -> List[Dict[str, Any]]:
    return [
        {
            "name": "趋势跟踪",
            "type": "trading",
            "description": "均线金叉买入/死叉卖出，适合趋势行情",
            "enabled": True,
            "filters": {},
            "indicators": [
                {"key": "buy.ma_cross", "dimension": "entry", "label": "均线金叉", "enabled": True, "weight": 40, "params": {"fast": 5, "slow": 20}},
                {"key": "buy.volume_break", "dimension": "entry", "label": "放量突破", "enabled": True, "weight": 30, "params": {"volume_ratio": 1.5}},
                {"key": "buy.macd_golden", "dimension": "entry", "label": "MACD金叉", "enabled": True, "weight": 30, "params": {}},
                {"key": "sell.ma_death", "dimension": "exit", "label": "均线死叉", "enabled": True, "weight": 50, "params": {}},
                {"key": "sell.stop_loss", "dimension": "exit", "label": "止损", "enabled": True, "weight": 50, "params": {"loss_pct": -8}},
            ],
        },
        {
            "name": "超跌反弹",
            "type": "trading",
            "description": "RSI超卖+布林下轨+放量反转，适合震荡市",
            "enabled": True,
            "filters": {},
            "indicators": [
                {"key": "buy.rsi_oversold", "dimension": "entry", "label": "RSI超卖", "enabled": True, "weight": 35, "params": {"threshold": 30}},
                {"key": "buy.bollinger_lower", "dimension": "entry", "label": "布林下轨", "enabled": True, "weight": 35, "params": {}},
                {"key": "buy.volume_surge", "dimension": "entry", "label": "放量反转", "enabled": True, "weight": 30, "params": {"ratio": 2.0}},
                {"key": "sell.profit_target", "dimension": "exit", "label": "止盈", "enabled": True, "weight": 50, "params": {"profit_pct": 15}},
                {"key": "sell.stop_loss", "dimension": "exit", "label": "止损", "enabled": True, "weight": 50, "params": {"loss_pct": -5}},
            ],
        },
        {
            "name": "网格交易",
            "type": "trading",
            "description": "价格区间网格：下跌买入、上涨卖出，适合震荡标的",
            "enabled": True,
            "filters": {},
            "indicators": [
                {"key": "buy.grid_step", "dimension": "entry", "label": "网格买入", "enabled": True, "weight": 100, "params": {"grid_pct": 3, "max_grids": 10}},
                {"key": "sell.grid_step", "dimension": "exit", "label": "网格卖出", "enabled": True, "weight": 100, "params": {"grid_pct": 3}},
            ],
        },
    ]
