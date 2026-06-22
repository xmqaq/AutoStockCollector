"""行业情绪与主题抽取 — 每行业一次 LLM 调用，聚合标题后分析。"""
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from utils.logger import get_logger

from .prompts.sector_synthesis import SECTOR_SYNTHESIS_PROMPT

LLM_CACHE_COLLECTION = "research_llm_cache"
LLM_CACHE_TTL = 86400 * 2  # 2 天

logger = get_logger(__name__)


class ReportSignal(BaseModel):
    """单行业研报聚合后的分析信号。"""
    sector: str
    themes: List[Dict[str, Any]] = Field(default_factory=list, description="热点主题")
    sentiment: str = Field(default="neutral", description="整体情绪 bullish/bearish/neutral")
    rating_momentum: str = Field(default="neutral", description="评级动量 positive/negative/neutral")
    key_stocks: List[Dict[str, str]] = Field(default_factory=list, description="提及的标的 [{code, name, reason}]")
    rating_up: int = Field(default=0, description="上调/买入评级次数")
    rating_down: int = Field(default=0, description="下调/卖出评级次数")
    rating_hold: int = Field(default=0, description="中性/持有评级次数")
    avg_target_price: Optional[float] = Field(default=None, description="平均目标价")
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
        rating_positive = 0
        rating_negative = 0
        rating_neutral = 0
        total_targets = 0
        target_sum = 0.0
        for r in reports:
            title = r.get("title", "").strip()
            if title:
                org = r.get("org", "")
                date = str(r.get("date", ""))[:10]
                titles.append(f"- {title}  ({org}, {date})")
            rating = str(r.get("rating", "")).strip()
            if rating in ("买入", "增持", "推荐", "强烈推荐", "买入-A"):
                rating_positive += 1
            elif rating in ("减持", "卖出", "回避"):
                rating_negative += 1
            elif rating in ("中性", "持有", "谨慎推荐"):
                rating_neutral += 1
            tp = r.get("target_price_high")
            if tp and isinstance(tp, (int, float)):
                total_targets += 1
                target_sum += float(tp)

        if not titles:
            return []

        report_text = "\n".join(titles[:60])
        total = len(reports)
        avg_target = round(target_sum / total_targets, 2) if total_targets > 0 else None
        total_ratings = rating_positive + rating_negative + rating_neutral
        rating_summary = ""
        if total_ratings >= 3:
            rating_summary = (
                f"分析师评级统计({total_ratings}次): "
                f"积极(买入/增持) {rating_positive}次, "
                f"中性(持有) {rating_neutral}次, "
                f"消极(减持/卖出) {rating_negative}次"
            )
            if avg_target:
                rating_summary += f", 平均目标价 ¥{avg_target}"

        # 注意：akshare 返回的东财评级是静态评级水平（买入/增持/中性），
        # 非评级变化方向（上调/下调/维持）。"积极"计数表示当前评级为买入/增持的报告数量，
        # 不代表从之前评级上调。如有评级变化数据需求，需额外接入评级变化数据源。

        prompt = SECTOR_SYNTHESIS_PROMPT.format(
            sector=sector,
            total=total,
            report_titles=report_text,
            rating_summary=rating_summary or "无评级数据",
        )

        signal = self._call_llm(
            prompt, sector, titles,
            rating_positive=rating_positive, rating_negative=rating_negative,
            rating_neutral=rating_neutral, avg_target=avg_target,
        )
        return [signal] if signal else []

    def _call_llm(
        self, prompt: str, sector: str, titles: List[str],
        rating_positive: int = 0, rating_negative: int = 0, rating_neutral: int = 0,
        avg_target: Optional[float] = None,
    ) -> Optional[ReportSignal]:
        """调用 LLM 解析行业研报标题，返回结构化的行业分析。"""
        cache_key = f"llm|{sector}|{hashlib.md5(prompt.encode()).hexdigest()}"
        db = None
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
        except Exception:
            pass

        # 尝试 MongoDB 缓存
        if db is not None:
            try:
                doc = db[LLM_CACHE_COLLECTION].find_one({"cache_key": cache_key})
                if doc:
                    cached = doc.get("llm_result")
                    if cached:
                        parsed = self._parse_json(cached)
                        if parsed:
                            logger.info(f"[Extractor] LLM cache hit for sector={sector}")
                            return self._build_signal(
                                parsed, sector, titles,
                                rating_positive=rating_positive, rating_negative=rating_negative,
                                rating_neutral=rating_neutral, avg_target=avg_target,
                            )
            except Exception:
                pass

        try:
            from modules.ai.foundation.llm_router import LLMRouter
            router = LLMRouter()
            result = router.chat_quick(prompt, use_cache=True)

            if not result or not result.success:
                logger.warning(f"[ResearchAnalyzer] LLM synthesis failed for sector={sector}, using template")
                return self._template_signal(sector, titles, rating_positive=rating_positive, rating_negative=rating_negative)

            parsed = self._parse_json(result.raw)
            if not parsed:
                return self._template_signal(sector, titles, rating_positive=rating_positive, rating_negative=rating_negative)

            sig = self._build_signal(
                parsed, sector, titles,
                rating_positive=rating_positive, rating_negative=rating_negative,
                rating_neutral=rating_neutral, avg_target=avg_target,
            )

            # 保存到 MongoDB 缓存
            if db is not None and sig is not None:
                try:
                    db[LLM_CACHE_COLLECTION].update_one(
                        {"cache_key": cache_key},
                        {"$set": {
                            "cache_key": cache_key,
                            "sector": sector,
                            "llm_result": result.raw,
                            "created_at": datetime.now(),
                        }},
                        upsert=True,
                    )
                except Exception:
                    pass

            return sig
        except Exception as e:
            logger.warning(f"[ResearchAnalyzer] LLM error for sector={sector}: {e}")
            return self._template_signal(sector, titles, rating_positive=rating_positive, rating_negative=rating_negative)

    def _build_signal(
        self, parsed: Dict[str, Any], sector: str, titles: List[str],
        rating_positive: int = 0, rating_negative: int = 0, rating_neutral: int = 0,
        avg_target: Optional[float] = None,
    ) -> Optional[ReportSignal]:
        key_stocks = parsed.get("key_stocks", [])
        themes = parsed.get("themes", [])
        sentiment = parsed.get("sentiment", "neutral")
        rating_distribution = parsed.get("rating_distribution") or parsed.get("rating_momentum", "neutral")

        findings = []
        hot_themes = [t["name"] for t in themes if t.get("hot") and t.get("name")]
        if hot_themes:
            findings.append(f"核心热点: {', '.join(hot_themes[:5])}")
        if sentiment == "bullish":
            findings.append("行业情绪偏乐观")
        elif sentiment == "bearish":
            findings.append("行业情绪偏谨慎")
        if rating_distribution == "positive":
            findings.append("分析师积极评级占优")
        elif rating_distribution == "negative":
            findings.append("分析师消极评级占优")

        top_stocks = [s.get("name", "") for s in key_stocks[:5] if s.get("name")]
        if top_stocks:
            findings.append(f"重点关注: {', '.join(top_stocks[:5])}")

        return ReportSignal(
            sector=sector,
            themes=themes,
            sentiment=sentiment,
            rating_momentum=rating_distribution,
            key_stocks=key_stocks,
            rating_up=rating_positive,
            rating_down=rating_negative,
            rating_hold=rating_neutral,
            avg_target_price=avg_target,
            key_findings=findings,
            summary=parsed.get("summary", ""),
            theme_summary=parsed.get("theme_summary", ""),
            confidence=parsed.get("confidence", 3),
        )

    def _template_signal(
        self, sector: str, titles: List[str],
        rating_positive: int = 0, rating_negative: int = 0,
    ) -> Optional[ReportSignal]:
        """LLM 不可用时的模板降级。"""
        if not titles:
            return None

        stock_mentions = {}
        for line in titles:
            m = re.findall(r'\((\d{6})\)', line)
            for code in m:
                stock_mentions[code] = stock_mentions.get(code, 0) + 1

        top_stocks = [{"code": k, "name": "", "reason": f"被 {v} 份研报提及"} for k, v in sorted(stock_mentions.items(), key=lambda x: -x[1])[:10]]

        findings = [f"共 {len(titles)} 篇研报"]
        if rating_positive > rating_negative:
            findings.append(f"积极评级 {rating_positive}次 > 消极 {rating_negative}次")
            rating_momentum = "positive"
        elif rating_negative > rating_positive:
            findings.append(f"消极评级 {rating_negative}次 > 积极 {rating_positive}次")
            rating_momentum = "negative"
        else:
            rating_momentum = "neutral"

        return ReportSignal(
            sector=sector,
            themes=[],
            sentiment="neutral",
            rating_momentum=rating_momentum,
            key_stocks=top_stocks,
            rating_up=rating_positive,
            rating_down=rating_negative,
            key_findings=findings,
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
