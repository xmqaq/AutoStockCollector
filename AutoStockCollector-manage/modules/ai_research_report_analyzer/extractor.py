"""LLM 结构化抽取 — 从研报原文提取供应链信号。"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from threading import Lock

from pydantic import BaseModel, Field
from utils.logger import get_logger

from .prompts.extract_signal import EXTRACT_SIGNAL_PROMPT

logger = get_logger(__name__)


class ReportSignal(BaseModel):
    sector: str
    mentioned_links: List[str] = Field(default_factory=list, description="涉及的产业链环节")
    link_judgments: Dict[str, str] = Field(
        default_factory=dict,
        description="各环节供需判断：tight/loose/mixed",
    )
    key_stocks: List[Dict[str, str]] = Field(
        default_factory=list,
        description="提及的标的 [{code, name, reason}]",
    )
    key_findings: List[str] = Field(default_factory=list, description="关键发现")
    confidence: int = Field(default=3, ge=1, le=5, description="置信度 1-5")


class Extractor:
    """LLM 驱动的供应链信号抽取器。"""

    def __init__(self, llm_max_workers: int = 2):
        self._llm_max_workers = llm_max_workers
        self._lock = Lock()

    def extract_batch(
        self,
        reports: List[Dict],
        sector: str,
        max_workers: int = 2,
    ) -> List[ReportSignal]:
        """批量抽取研报信号。"""
        if not reports:
            return []

        signals: List[Optional[ReportSignal]] = [None] * len(reports)
        worker_count = min(max_workers, len(reports), 4)

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {}
            for i, report in enumerate(reports):
                future = pool.submit(self._extract_single, report, sector)
                futures[future] = i

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    signals[idx] = future.result()
                except Exception as e:
                    logger.warning(
                        f"[ResearchAnalyzer] Extract report {idx} failed: {e}"
                    )

        valid = [s for s in signals if s is not None]
        logger.info(
            f"[ResearchAnalyzer] Extracted {len(valid)}/{len(reports)} "
            f"signals for sector={sector}"
        )
        return valid

    def _extract_single(self, report: Dict, sector: str) -> Optional[ReportSignal]:
        """抽取单篇研报的供应链信号。"""
        title = report.get("title", "")
        abstract = report.get("abstract", "")
        code = report.get("code", "")
        name = report.get("name", "")
        org = report.get("org", "")
        date = report.get("date", "")

        report_text = f"标题：{title}\n日期：{date}\n机构：{org}\n"
        if abstract:
            report_text += f"摘要：{abstract}\n"
        if code and name:
            report_text += f"涉及公司：{name}({code})\n"

        if not abstract and not title:
            return None

        prompt = EXTRACT_SIGNAL_PROMPT.format(
            report_text=report_text.strip(),
            sector=sector,
        )

        try:
            from modules.ai.foundation.llm_router import LLMRouter

            router = LLMRouter()
            result = router.chat_quick(prompt, use_cache=False)

            if not result.success:
                logger.warning(
                    f"[ResearchAnalyzer] LLM extraction failed for report: {title}"
                )
                return self._fallback_signal(report, sector)

            parsed = self._parse_json(result.raw)
            if not parsed:
                return self._fallback_signal(report, sector)

            return ReportSignal(
                sector=sector,
                mentioned_links=parsed.get("mentioned_links", []),
                link_judgments=parsed.get("link_judgments", {}),
                key_stocks=parsed.get("key_stocks", []),
                key_findings=parsed.get("key_findings", []),
                confidence=parsed.get("confidence", 3),
            )
        except Exception as e:
            logger.warning(
                f"[ResearchAnalyzer] LLM error for {title}: {e}"
            )
            return self._fallback_signal(report, sector)

    def _fallback_signal(self, report: Dict, sector: str) -> ReportSignal:
        """LLM 失败时的降级信号（基于关键词简单规则）。"""
        title = report.get("title", "")
        abstract = report.get("abstract", "")
        text = f"{title} {abstract}"
        code = report.get("code", "")
        name = report.get("name", "")

        stock_entry = []
        if code and name:
            stock_entry.append({"code": code, "name": name, "reason": "研报提及"})

        links = []
        judgments = {}

        tight_kw = ["紧缺", "供不应求", "产能瓶颈", "卡脖子", "国产替代", "缺口",
                    "涨价", "供需紧张", "产能不足", "认证壁垒"]
        loose_kw = ["过剩", "产能过剩", "供过于求", "价格下行", "竞争激烈",
                    "红海", "饱和", "库存高"]
        mixed_kw = ["分化", "结构性", "部分紧缺"]

        for kw in tight_kw:
            if kw in text:
                links.append(kw)
                judgments[kw] = "tight"
        if not links:
            for kw in loose_kw:
                if kw in text:
                    links.append(kw)
                    judgments[kw] = "loose"
        if not links:
            for kw in mixed_kw:
                if kw in text:
                    links.append(kw)
                    judgments[kw] = "mixed"

        findings = []
        if links:
            findings.append(f"研报提及供应链关键词: {', '.join(links[:3])}")
        if "景气" in text:
            findings.append("研报提及行业景气度")

        return ReportSignal(
            sector=sector,
            mentioned_links=links,
            link_judgments=judgments,
            key_stocks=stock_entry,
            key_findings=findings,
            confidence=2,
        )

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从 LLM 响应中解析 JSON。"""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        if text.startswith("json"):
            text = text[4:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        return None
