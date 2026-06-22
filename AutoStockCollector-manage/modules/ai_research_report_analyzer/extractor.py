"""行业情绪与主题抽取 — 每行业一次 LLM 调用，聚合标题后分析。"""
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from utils.logger import get_logger

from .prompts.sector_synthesis import SECTOR_SYNTHESIS_PROMPT

logger = get_logger(__name__)


class ReportSignal(BaseModel):
    """单行业研报聚合后的分析信号。"""
    sector: str
    themes: List[Dict[str, Any]] = Field(default_factory=list, description="热点主题")
    sentiment: str = Field(default="neutral", description="整体情绪 bullish/bearish/neutral")
    key_stocks: List[Dict[str, str]] = Field(default_factory=list, description="提及的标的 [{code, name, reason}]")
    key_findings: List[str] = Field(default_factory=list, description="关键发现")
    summary: str = Field(default="", description="行业综述")
    theme_summary: str = Field(default="", description="主题热度分析")
    confidence: int = Field(default=3, ge=1, le=5, description="置信度 1-5")


class Extractor:
    """LLM 驱动的行业主题情绪抽取器 — 每行业一次 LLM 调用。"""

    def __init__(self, llm_max_workers: int = 1):
        self._llm_max_workers = llm_max_workers

    def extract_batch(
        self,
        reports: List[Dict],
        sector: str,
        max_workers: int = 1,
    ) -> List[ReportSignal]:
        """对单个行业的全部研报标题做一次 LLM 分析，返回一个信号。"""
        if not reports:
            return []

        titles = []
        for r in reports:
            title = r.get("title", "").strip()
            if title:
                org = r.get("org", "")
                date = str(r.get("date", ""))[:10]
                titles.append(f"- {title}  ({org}, {date})")

        if not titles:
            return []

        report_text = "\n".join(titles[:60])  # 最多取 60 条，避免超 token
        total = len(reports)

        prompt = SECTOR_SYNTHESIS_PROMPT.format(
            sector=sector,
            total=total,
            report_titles=report_text,
        )

        signal = self._call_llm(prompt, sector, titles)
        return [signal] if signal else []

    def _call_llm(self, prompt: str, sector: str, titles: List[str]) -> Optional[ReportSignal]:
        """调用 LLM 解析行业研报标题，返回结构化的行业分析。"""
        try:
            from modules.ai.foundation.llm_router import LLMRouter
            router = LLMRouter()
            result = router.chat_quick(prompt, use_cache=True)

            if not result or not result.success:
                logger.warning(f"[ResearchAnalyzer] LLM synthesis failed for sector={sector}, using template")
                return self._template_signal(sector, titles)

            parsed = self._parse_json(result.raw)
            if not parsed:
                return self._template_signal(sector, titles)

            key_stocks = parsed.get("key_stocks", [])
            themes = parsed.get("themes", [])
            sentiment = parsed.get("sentiment", "neutral")

            findings = []
            hot_themes = [t["name"] for t in themes if t.get("hot") and t.get("name")]
            if hot_themes:
                findings.append(f"核心热点: {', '.join(hot_themes[:5])}")
            if sentiment == "bullish":
                findings.append("行业情绪偏乐观")
            elif sentiment == "bearish":
                findings.append("行业情绪偏谨慎")

            top_stocks = [s.get("name", "") for s in key_stocks[:5] if s.get("name")]
            if top_stocks:
                findings.append(f"重点关注: {', '.join(top_stocks[:5])}")

            return ReportSignal(
                sector=sector,
                themes=themes,
                sentiment=sentiment,
                key_stocks=key_stocks,
                key_findings=findings,
                summary=parsed.get("summary", ""),
                theme_summary=parsed.get("theme_summary", ""),
                confidence=parsed.get("confidence", 3),
            )
        except Exception as e:
            logger.warning(f"[ResearchAnalyzer] LLM error for sector={sector}: {e}")
            return self._template_signal(sector, titles)

    def _template_signal(self, sector: str, titles: List[str]) -> Optional[ReportSignal]:
        """LLM 不可用时的模板降级。"""
        if not titles:
            return None

        stock_mentions = {}
        for line in titles:
            m = re.findall(r'\((\d{6})\)', line)
            for code in m:
                stock_mentions[code] = stock_mentions.get(code, 0) + 1

        top_stocks = [{"code": k, "name": "", "reason": f"被 {v} 份研报提及"} for k, v in sorted(stock_mentions.items(), key=lambda x: -x[1])[:10]]

        return ReportSignal(
            sector=sector,
            themes=[],
            sentiment="neutral",
            key_stocks=top_stocks,
            key_findings=[f"共 {len(titles)} 篇研报"],
            summary="",
            theme_summary="",
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
