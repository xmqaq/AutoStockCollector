"""产业链图谱定义 & 瓶颈聚合。

核心算法：Bottleneck Score = Σ(提及频次 * 机构置信度 * 供需系数)
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

from utils.logger import get_logger
from .extractor import ReportSignal

logger = get_logger(__name__)

# 供需系数
_SUPPLY_COEFF = {"tight": 1.5, "mixed": 1.0, "loose": 0.5}


def _load_chain_templates() -> Dict[str, Any]:
    """加载预置产业链模板。"""
    path = Path(__file__).parent / "chain_templates.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load chain_templates.json: {e}")
    return {}


def _get_sector_links(sector: str) -> List[str]:
    """获取某个行业的预置产业链环节列表。"""
    templates = _load_chain_templates()
    sector_data = templates.get(sector, {})
    links = sector_data.get("links", [])
    return [link.get("name", "") for link in links if link.get("name")]


class SupplyChainAggregator:
    """供应链信号聚合器 — 计算瓶颈分数并提取候选标的。"""

    def __init__(self):
        self._templates = _load_chain_templates()

    def aggregate(
        self, sector: str, signals: List[ReportSignal],
    ) -> Dict[str, Any]:
        """聚合多份研报的供应链信号。"""
        link_freq = Counter()
        link_judgments: Dict[str, List[str]] = {}
        link_confidences: Dict[str, List[int]] = {}
        link_findings: Dict[str, List[str]] = {}

        for sig in signals:
            for link in sig.mentioned_links:
                link_freq[link] += 1
                if link not in link_judgments:
                    link_judgments[link] = []
                    link_confidences[link] = []
                    link_findings[link] = []
                judgment = sig.link_judgments.get(link, "mixed")
                link_judgments[link].append(judgment)
                link_confidences[link].append(sig.confidence)
                link_findings[link].extend(sig.key_findings[:2])

        links_result = {}
        for link, freq in link_freq.most_common():
            judgments = link_judgments.get(link, ["mixed"])
            confidences = link_confidences.get(link, [3])
            avg_confidence = sum(confidences) / max(len(confidences), 1)

            # 多数决
            judgment_counts = Counter(judgments)
            dominant = judgment_counts.most_common(1)[0][0]

            # Bottleneck Score
            coeff = _SUPPLY_COEFF.get(dominant, 1.0)
            score = min(100, int(freq * avg_confidence * coeff * 5))

            findings = link_findings.get(link, [])
            links_result[link] = {
                "judgment": dominant,
                "frequency": freq,
                "confidence": round(avg_confidence, 1),
                "score": score,
                "findings": findings[:3],
            }

        return {
            "sector": sector,
            "links": links_result,
            "total_signals": len(signals),
        }

    def extract_candidates(
        self, sector: str, signals: List[ReportSignal],
    ) -> List[Dict[str, Any]]:
        """从所有信号中提取去重候选标的。"""
        seen = {}
        for sig in signals:
            for stock in sig.key_stocks:
                code = stock.get("code", "")
                if not code:
                    continue
                if code not in seen:
                    seen[code] = {
                        "code": code,
                        "name": stock.get("name", ""),
                        "reason": stock.get("reason", ""),
                        "confidence": sig.confidence,
                        "links": sig.mentioned_links.copy(),
                        "mention_count": 1,
                    }
                else:
                    seen[code]["mention_count"] += 1
                    seen[code]["links"].extend(sig.mentioned_links)

        candidates = list(seen.values())
        # 按提及次数排序
        candidates.sort(key=lambda x: x.get("mention_count", 0), reverse=True)
        return candidates
