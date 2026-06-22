"""AnalyzerEngine — 投资研报分析的主编排器。"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from utils.logger import get_logger

from .config import ResearchConfig
from .scraper import get_reports
from .extractor import ReportSignal, Extractor
from .supply_chain import SupplyChainAggregator
from .screener import Screener

logger = get_logger(__name__)


class AnalyzerEngine:
    """研报分析引擎：采集 → LLM 主题抽取 → 聚合 → 筛选 → 合成简报。"""

    def __init__(self):
        self._db = DatabaseConfig.get_database()
        self._extractor = Extractor()
        self._aggregator = SupplyChainAggregator()
        self._screener = Screener()

    def analyze(
        self,
        sectors: List[str],
        top_n: int = 20,
        max_workers: int = 1,
    ) -> Dict[str, Any]:
        """对多个板块执行研报分析。"""
        start = datetime.now()
        logger.info(f"[ResearchAnalyzer] Starting analysis sectors={sectors} top_n={top_n}")

        sector_results = {}
        all_signals: List[ReportSignal] = []
        all_aggregated = {}
        all_candidates = {}

        for sector in sectors:
            result = self._analyze_single(sector)
            sector_results[sector] = {
                "report_count": result.get("report_count", 0),
                "source": result.get("source", "none"),
                "sentiment": result.get("sentiment", "neutral"),
                "error": result.get("error"),
            }
            for sig in result.get("signals", []):
                all_signals.append(sig)
            all_aggregated[sector] = result.get("aggregated", {})
            all_candidates[sector] = result.get("candidates", [])

        chain_view = self._build_chain_view(all_aggregated, all_signals)
        candidate_pool = self._merge_candidates(all_candidates, top_n)

        filtered = self._screener.filter(candidate_pool)
        scored = self._screener.score(filtered)

        report_md = self._synthesize_report(
            sectors, all_aggregated, all_signals, scored, chain_view,
        )

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(
            f"[ResearchAnalyzer] Done sectors={sectors} elapsed={elapsed:.1f}s "
            f"total_signals={len(all_signals)} candidates={len(scored)}"
        )

        return {
            "success": True,
            "sectors": sectors,
            "chain_view": chain_view,
            "candidates": scored[:top_n],
            "candidate_count": len(scored),
            "report_md": report_md,
            "elapsed_seconds": round(elapsed, 1),
            "sector_details": sector_results,
        }

    def _analyze_single(self, sector: str) -> Dict[str, Any]:
        """分析单个行业板块。"""
        try:
            reports, source = get_reports(sector, days=90, min_count=ResearchConfig.CACHE_MIN_COUNT)
            logger.info(f"[ResearchAnalyzer] Source={source}, Sector={sector}, Reports={len(reports)}")

            if not reports:
                return {
                    "signals": [],
                    "aggregated": {},
                    "candidates": [],
                    "report_count": 0,
                    "source": source,
                    "error": "未获取到研报数据",
                }

            signals = self._extractor.extract_batch(reports, sector, max_workers=1)
            aggregated = self._aggregator.aggregate(sector, signals)
            candidates = self._aggregator.extract_candidates(sector, signals)

            return {
                "signals": signals,
                "aggregated": aggregated,
                "candidates": candidates,
                "report_count": len(reports),
                "source": source,
                "sentiment": aggregated.get("sentiment", "neutral"),
            }
        except Exception as e:
            logger.error(f"[ResearchAnalyzer] Sector={sector} analyze failed: {e}")
            return {
                "signals": [],
                "aggregated": {},
                "candidates": [],
                "report_count": 0,
                "source": "error",
                "error": str(e),
            }

    def _build_chain_view(
        self,
        all_aggregated: Dict[str, Dict],
        all_signals: List[ReportSignal],
    ) -> List[Dict[str, Any]]:
        """构建主题视图（替代旧的瓶颈链视图）。"""
        chain_view = []
        for sector, agg in all_aggregated.items():
            themes = agg.get("themes", [])
            if themes:
                for t in themes:
                    chain_view.append({
                        "sector": sector,
                        "link": t.get("name", "未知"),
                        "bottleneck_score": 80 if t.get("hot") else 40,
                        "judgment": "tight" if t.get("hot") else "mixed",
                        "frequency": 5 if t.get("hot") else 2,
                        "confidence": 4 if t.get("hot") else 2,
                        "description": t.get("description", ""),
                    })
            else:
                chain_view.append({
                    "sector": sector,
                    "link": f"整体情绪: {agg.get('sentiment', 'neutral')}",
                    "bottleneck_score": 50,
                    "judgment": "mixed",
                    "frequency": agg.get("total_signals", 0),
                    "confidence": 3,
                    "description": agg.get("summary", "")[:80],
                })

        chain_view.sort(key=lambda x: x["bottleneck_score"], reverse=True)
        return chain_view

    def _merge_candidates(
        self, all_candidates: Dict[str, List], top_n: int,
    ) -> List[Dict]:
        """跨行业去重合并候选标的。"""
        seen = {}
        for sector, stocks in all_candidates.items():
            for s in stocks:
                code = s.get("code", "")
                if not code:
                    continue
                if code not in seen:
                    seen[code] = {**s, "sectors": [sector], "mention_count": 1}
                else:
                    seen[code]["mention_count"] += 1
                    if sector not in seen[code]["sectors"]:
                        seen[code]["sectors"].append(sector)
        merged = sorted(seen.values(), key=lambda x: x.get("mention_count", 0), reverse=True)
        return merged[:top_n]

    def _synthesize_report(
        self,
        sectors: List[str],
        all_aggregated: Dict[str, Dict],
        all_signals: List[ReportSignal],
        scored: List[Dict],
        chain_view: List[Dict],
    ) -> str:
        """合成 Markdown 研报简报。"""
        try:
            from .prompts.synthesize import SYNTHESIZE_PROMPT
            from modules.ai.foundation.llm_router import LLMRouter

            sector_lines = []
            for sector in sectors:
                agg = all_aggregated.get(sector, {})
                themes = agg.get("themes", [])
                sentiment = agg.get("sentiment", "neutral")
                summary = agg.get("summary", "")

                sent_emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "🟡"
                sector_lines.append(f"- {sent_emoji} **{sector}** (情绪={sentiment})")
                for t in themes[:3]:
                    hot_mark = "🔥" if t.get("hot") else "  "
                    sector_lines.append(f"  {hot_mark} {t.get('name', '')} — {t.get('description', '')}")
                if summary:
                    sector_lines.append(f"  > {summary[:100]}")

            stock_lines = []
            for s in scored[:15]:
                star = "⭐" * max(1, min(5, int(s.get("score", 50) / 20)))
                stock_lines.append(
                    f"- {star} **{s.get('name', '')}** ({s.get('code', '')}) "
                    f"评分={s.get('score', 50):.0f}, 板块={','.join(s.get('sectors', []))}"
                )

            theme_scores = "\n".join(
                f"- {cv['sector']}/{cv['link']}: score={cv['bottleneck_score']}, "
                f"judgment={cv['judgment']}"
                for cv in chain_view[:10]
            ) or "无数据"

            combined_sector = "、".join(sectors)
            prompt = SYNTHESIZE_PROMPT.format(
                sector=combined_sector,
                link_summary="\n".join(sector_lines) or "无数据",
                stock_summary="\n".join(stock_lines) or "无数据",
                bottleneck_scores=theme_scores,
            )
            router = LLMRouter()
            result = router.chat_quick(prompt)
            if result.success and result.raw:
                return result.raw.strip()
        except Exception as e:
            logger.warning(f"[ResearchAnalyzer] LLM synthesis failed, using template: {e}")

        return self._template_report(sectors, all_aggregated, scored, chain_view)

    def _template_report(
        self,
        sectors: List[str],
        all_aggregated: Dict[str, Dict],
        scored: List[Dict],
        chain_view: List[Dict],
    ) -> str:
        """LLM 不可用时的降级模板报告。"""
        lines = []
        lines.append("# 投资研报简报\n")
        lines.append(f"**板块**: {'、'.join(sectors)}\n")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append("---\n")

        lines.append("## 行业热点\n")
        for sector, agg in all_aggregated.items():
            themes = agg.get("themes", [])
            sentiment = agg.get("sentiment", "neutral")
            lines.append(f"\n### {sector} (情绪: {sentiment})\n")
            if themes:
                for t in themes[:3]:
                    hot = "🔥" if t.get("hot") else "  "
                    lines.append(f"- {hot} **{t.get('name', '')}**: {t.get('description', '')}")
            else:
                lines.append("暂无热点数据\n")

        lines.append("\n## 核心标的\n")
        for s in scored[:10]:
            lines.append(
                f"- **{s.get('name', '')}** ({s.get('code', '')}) "
                f"评分{s.get('score', 50)}"
            )

        lines.append("\n---\n")
        lines.append("*免责声明：本报告由 AI 自动生成，仅供参考，不构成投资建议。*\n")
        return "\n".join(lines)
