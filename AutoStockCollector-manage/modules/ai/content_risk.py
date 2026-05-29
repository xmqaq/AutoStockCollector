"""内容风控过滤器。拦截绝对化/诱导性措辞，替换为稳健表述。纯函数，无 DB/网络。
实现 spec §8.1 内容风控 & 风险提示。
"""
from typing import List, Tuple

RISK_DISCLAIMER = "本内容由 AI 基于历史数据生成，仅供参考，不构成投资建议。市场有风险，决策需谨慎。"

# 绝对化/诱导性措辞 → 稳健替换
_REPLACEMENTS = {
    "必涨": "或有上行空间",
    "必跌": "或有下行压力",
    "保证收益": "存在不确定性",
    "稳赚不赔": "存在波动风险",
    "稳赚": "存在波动风险",
    "一定上涨": "可能上行",
    "一定下跌": "可能下行",
    "包赚": "存在不确定性",
    "全仓": "合理仓位",
    "梭哈": "合理仓位",
    "百分百": "较大概率",
    "100%": "较大概率",
}


def sanitize_text(text: str) -> Tuple[str, List[str]]:
    """净化文本。返回 (净化后文本, 命中的违规词列表)。"""
    if not text:
        return "", []
    hits: List[str] = []
    result = text
    for bad, good in _REPLACEMENTS.items():
        if bad in result:
            hits.append(bad)
            result = result.replace(bad, good)
    return result, hits
