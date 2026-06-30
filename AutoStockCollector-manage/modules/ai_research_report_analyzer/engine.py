"""AnalyzerEngine — 投资研报分析的主编排器。"""
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from config.database import DatabaseConfig
from utils.helpers import beijing_now, normalize_stock_code_flexible
from utils.logger import get_logger

from .config import ResearchConfig
from .scraper import get_reports
from .extractor import ReportSignal, Extractor
from .supply_chain import SupplyChainAggregator
from .screener import Screener

_PRICE_COLLECTION = "kline"  # 日线数据集合（旧值 "stock_daily" 从未被写入，导致价格 enrich 静默失效）
_FUNDAMENTAL_COLLECTION = "stock_valuation"

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
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        synthesize: bool = True,
        enrich: bool = True,
    ) -> Dict[str, Any]:
        """对多个板块执行研报分析。

        synthesize=False 时跳过批内 _synthesize_report（省一次 LLM 调用），
        供 cron 跨批合并场景使用——批内简报会被 merge_batch_results 丢弃，
        无需合成。单批次独立分析（API 手动触发）仍默认合成。

        enrich=False 时跳过批内 _enrich_with_market_context（省 4 次 Mongo 查询
        含 365 天聚合），供 cron 跨批合并场景使用——批内 enrich 结果会被
        merge_batch_results 丢弃，统一在合并阶段做一次。
        """
        start = datetime.now()
        logger.info(f"[ResearchAnalyzer] Starting analysis sectors={sectors} top_n={top_n}")

        sector_results = {}
        all_signals: List[ReportSignal] = []
        all_aggregated = {}
        all_candidates = {}

        if cancel_check and cancel_check():
            return {"success": False, "error": "任务已取消"}

        def _run_sector(sector: str) -> tuple:
            if cancel_check and cancel_check():
                return sector, {"error": "任务已取消"}
            if progress_callback:
                progress_callback(0, sector)
            r = self._analyze_single(sector)
            return sector, r

        executor = ThreadPoolExecutor(max_workers=max(1, max_workers))
        total = len(sectors)
        futures = [executor.submit(_run_sector, s) for s in sectors]
        for idx, future in enumerate(as_completed(futures)):
            sector, result = future.result()
            if progress_callback:
                progress_callback(int((idx + 1) / total * 80) + 10, sector)
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
        executor.shutdown(wait=False)

        chain_view = self._build_chain_view(all_aggregated, all_signals)
        candidate_pool = self._merge_candidates(all_candidates, top_n)

        filtered = self._screener.filter(candidate_pool)
        scored = self._screener.score(filtered)
        # 批内 enrich：cron 跨批合并场景会丢弃批内 enrich 字段，跳过省 4 次 Mongo 查询
        if enrich:
            scored = self._enrich_with_market_context(scored)

        # 批内简报：cron 跨批合并场景会丢弃批 report_md，跳过省一次 LLM 调用
        report_md = ""
        if synthesize:
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
            # 暴露各板块聚合结果，供 merge_batch_results 合成全市场简报的"行业热点"章节
            "aggregated": all_aggregated,
        }

    def merge_batch_results(self, batch_results: List[Dict], top_n: int = 30) -> Dict[str, Any]:
        """跨批次合并多批 analyze() 结果为一份全市场汇总。

        每批 candidates 已经过批内 _merge_candidates/screener/enrich，这里只需按 code
        扁平去重合并（sectors/reasons/mention_count 累加），再统一 filter/score/enrich，
        最后合成一份全市场简报。失败批次（success=False）跳过。
        """
        start = datetime.now()
        merged_chain_view: List[Dict] = []
        merged_sector_details: Dict[str, Any] = {}
        merged_aggregated: Dict[str, Dict] = {}
        seen: Dict[str, Dict] = {}
        ok_batches = 0
        failed_sectors: List[str] = []

        for br in batch_results:
            if not br or not br.get("success"):
                continue
            ok_batches += 1
            merged_chain_view.extend(br.get("chain_view", []))
            merged_sector_details.update(br.get("sector_details", {}))
            # 收集各板块聚合结果（themes/sentiment/summary），供全市场简报"行业热点"章节使用
            for sector, agg in (br.get("aggregated") or {}).items():
                if agg:
                    merged_aggregated[sector] = agg
            # 收集失败板块
            for sec, det in br.get("sector_details", {}).items():
                if det.get("error"):
                    failed_sectors.append(sec)
            # 扁平合并 candidates（每批 candidates 已是批内合并产物）
            for c in br.get("candidates", []):
                code = c.get("code", "")
                if not code:
                    continue
                if code not in seen:
                    seen[code] = {**c}
                    # 统一 reasons 结构：旧数据可能只有 reason 字段
                    if "reasons" not in seen[code]:
                        seen[code]["reasons"] = (
                            [{"sector": s, "reason": c.get("reason", "")} for s in c.get("sectors", [])]
                            if c.get("reason") else []
                        )
                    seen[code]["mention_count"] = c.get("mention_count", 1)
                else:
                    seen[code]["mention_count"] = (seen[code].get("mention_count", 1) +
                                                  c.get("mention_count", 1))
                    for s in c.get("sectors", []):
                        if s not in seen[code].get("sectors", []):
                            seen[code].setdefault("sectors", []).append(s)
                    # 合并 reasons：把该批 candidate 的 reasons 追加（去重）
                    for r in c.get("reasons", []) or (
                        [{"sector": s, "reason": c.get("reason", "")} for s in c.get("sectors", [])]
                        if c.get("reason") else []
                    ):
                        key = f"{r.get('sector')}|{r.get('reason')}"
                        existing = {f"{x.get('sector')}|{x.get('reason')}" for x in seen[code].get("reasons", [])}
                        if key not in existing:
                            seen[code].setdefault("reasons", []).append(r)

        # 重建 reason_text
        for c in seen.values():
            parts = [f"【{r['sector']}】{r['reason']}" for r in c.get("reasons", []) if r.get("reason")]
            c["reason_text"] = "；".join(parts) if parts else (c.get("reason", "") or "")

        candidate_pool = sorted(seen.values(), key=lambda x: x.get("mention_count", 0), reverse=True)
        filtered = self._screener.filter(candidate_pool)
        scored = self._screener.score(filtered)
        scored = self._enrich_with_market_context(scored)

        merged_chain_view.sort(key=lambda x: x.get("theme_score", 0), reverse=True)
        all_sectors = list(merged_sector_details.keys())
        report_md = self._synthesize_report(
            all_sectors, merged_aggregated, [], scored, merged_chain_view,
        )

        elapsed = (datetime.now() - start).total_seconds()
        total_sectors = len(all_sectors)
        ok_sectors = total_sectors - len(failed_sectors)
        logger.info(
            f"[ResearchAnalyzer] merge_batch_results: batches={ok_batches} "
            f"sectors={total_sectors}(ok={ok_sectors}, failed={len(failed_sectors)}) "
            f"candidates={len(scored)} elapsed={elapsed:.1f}s"
        )

        return {
            "success": True,
            "sectors": ["全市场"],
            "chain_view": merged_chain_view,
            "candidates": scored[:top_n],
            "candidate_count": len(scored),
            "report_md": report_md,
            "elapsed_seconds": round(elapsed, 1),
            "sector_details": merged_sector_details,
            "failed_sectors": failed_sectors,
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
                        "theme_score": 80 if t.get("hot") else 40,
                        "judgment": "tight" if t.get("hot") else "mixed",
                        "frequency": 5 if t.get("hot") else 2,
                        "confidence": 4 if t.get("hot") else 2,
                        "description": t.get("description", ""),
                    })
            else:
                chain_view.append({
                    "sector": sector,
                    "link": f"整体情绪: {agg.get('sentiment', 'neutral')}",
                    "theme_score": 50,
                    "judgment": "mixed",
                    "frequency": agg.get("total_signals", 0),
                    "confidence": 3,
                    "description": agg.get("summary", "")[:80],
                })

        chain_view.sort(key=lambda x: x["theme_score"], reverse=True)
        return chain_view

    def _merge_candidates(
        self, all_candidates: Dict[str, List], top_n: int,
    ) -> List[Dict]:
        """跨行业去重合并候选标的。

        同一股票被多个板块命中时，合并 sectors/mention_count，并把每个板块的
        推荐原因收集到 reasons 列表（避免后续板块的 reason 被丢弃），
        同时拼一个 reason_text 字段供表格兜底展示。
        """
        seen = {}
        for sector, stocks in all_candidates.items():
            for s in stocks:
                code = s.get("code", "")
                if not code:
                    continue
                reason = s.get("reason", "") or ""
                if code not in seen:
                    seen[code] = {
                        **s,
                        "sectors": [sector],
                        "reasons": [{"sector": sector, "reason": reason}],
                        "mention_count": 1,
                    }
                else:
                    seen[code]["mention_count"] += 1
                    if sector not in seen[code]["sectors"]:
                        seen[code]["sectors"].append(sector)
                    seen[code]["reasons"].append({"sector": sector, "reason": reason})
        # 拼接 reason_text 供前端表格兜底展示
        for c in seen.values():
            parts = [f"【{r['sector']}】{r['reason']}" for r in c.get("reasons", []) if r.get("reason")]
            c["reason_text"] = "；".join(parts) if parts else (c.get("reason", "") or "")
        merged = sorted(seen.values(), key=lambda x: x.get("mention_count", 0), reverse=True)
        return merged[:top_n]

    def _enrich_with_market_context(self, candidates: List[Dict]) -> List[Dict]:
        """为候选标的补充价格上下文和 AI 监控信号。

        候选 code 来自 research_reports，是纯数字（如 000001）；而 kline /
        stock_valuation / monitor_signals 存的是带前缀码（SZ000001）。此处统一
        归一化为带前缀码查询，再用 norm_map 反查回候选。
        """
        if not candidates:
            return candidates

        codes = [c["code"] for c in candidates if c.get("code")]
        if not codes:
            return candidates

        # 纯数字 → 带前缀码（kline/stock_valuation/monitor_signals 均按前缀码存储）
        norm_map = {c: normalize_stock_code_flexible(c) for c in codes}
        norm_codes = list({v for v in norm_map.values()})

        # 1. 获取最新价格数据（限于近 365 天，确保 52周高/200日均 正确）
        #    kline.date 存的是 datetime 类型（非字符串），cutoff 必须用 datetime 才能命中 $gte。
        prices = {}
        one_year_ago_dt = beijing_now() - timedelta(days=365)
        try:
            for doc in self._db[_PRICE_COLLECTION].aggregate([
                {"$match": {"code": {"$in": norm_codes}, "date": {"$gte": one_year_ago_dt}}},
                {"$sort": {"date": -1}},
                {"$group": {
                    "_id": "$code",
                    "close": {"$first": "$close"},
                    "high_52w": {"$max": "$high"},
                    "low_52w": {"$min": "$low"},
                    "ma_200": {"$avg": "$close"},
                    "date": {"$first": "$date"},
                }},
            ]):
                prices[doc["_id"]] = doc
        except Exception as e:
            logger.warning(f"[Research] price fetch error: {e}")

        # 2. 获取估值数据
        valuations = {}
        try:
            for doc in self._db[_FUNDAMENTAL_COLLECTION].find(
                {"code": {"$in": norm_codes}},
                {"code": 1, "pe_dynamic": 1, "pb": 1, "total_mv": 1},
            ):
                valuations[doc.get("code", "")] = doc
        except Exception as e:
            logger.warning(f"[Research] valuation fetch error: {e}")

        # 3. 获取 AI 监控信号
        monitor_signals = {}
        try:
            for doc in self._db["monitor_signals"].find(
                {"code": {"$in": norm_codes}},
                {"code": 1, "signal": 1, "composite_score": 1,
                 "technical_score": 1, "sentiment_score": 1, "fund_flow_score": 1,
                 "_id": 0},
            ):
                monitor_signals[doc.get("code", "")] = doc
        except Exception as e:
            logger.warning(f"[Research] monitor signal fetch error: {e}")

        # 4. 获取 PA 信号（限最近 24h 内的分析结果；pa_signals.results.symbol 为纯数字）
        pa_signals = {}
        one_day_ago = beijing_now() - timedelta(hours=24)
        try:
            for doc in self._db["pa_signals"].find(
                {"created_at": {"$gte": one_day_ago}},
                {"results": 1, "_id": 0},
            ).sort("created_at", -1).limit(1):
                for r in doc.get("results", []):
                    code = r.get("symbol", "")
                    if code in codes:
                        pa_signals[code] = r
        except Exception as e:
            logger.warning(f"[Research] PA signal fetch error: {e}")

        for c in candidates:
            code = c["code"]
            norm = norm_map.get(code, code)
            px = prices.get(norm, {})
            val = valuations.get(norm, {})
            monitor = monitor_signals.get(norm, {})
            pa = pa_signals.get(code, {})

            close = px.get("close", 0)
            high_52w = px.get("high_52w", 0)
            low_52w = px.get("low_52w", 0)
            ma_200 = px.get("ma_200", 0)

            c["current_price"] = round(float(close), 2) if close else None
            c["market_cap"] = float(val.get("total_mv", c.get("market_cap", 0)))

            if close and high_52w and high_52w > 0:
                c["pct_from_52w_high"] = round((float(close) - float(high_52w)) / float(high_52w) * 100, 1)
            if close and ma_200 and ma_200 > 0:
                c["pct_from_ma200"] = round((float(close) - float(ma_200)) / float(ma_200) * 100, 1)

            if monitor:
                c["monitor_signal"] = monitor.get("signal", "")
                c["monitor_composite_score"] = monitor.get("composite_score", 0)

                mon_technical = monitor.get("technical_score")
                mon_sentiment = monitor.get("sentiment_score")
                mon_fund_flow = monitor.get("fund_flow_score")
                c["monitor_scores"] = {}
                if mon_technical is not None:
                    c["monitor_scores"]["technical"] = mon_technical
                if mon_sentiment is not None:
                    c["monitor_scores"]["sentiment"] = mon_sentiment
                if mon_fund_flow is not None:
                    c["monitor_scores"]["fund_flow"] = mon_fund_flow

                if c.get("score", 50) and monitor.get("composite_score") is not None:
                    mon_score = float(monitor["composite_score"]) * 10
                    if mon_score < 30 and c["score"] >= 60:
                        c["score_conflict"] = True
                        c["score"] = int(c["score"] * 0.7)

            if pa and pa.get("signal") in ("BUY_SETUP", "SELL_SETUP"):
                c["pa_signal"] = pa.get("signal")
                c["pa_signal_overlap"] = True

        return candidates

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
                f"- {cv['sector']}/{cv['link']}: score={cv['theme_score']}, "
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
        for s in scored[:15]:
            extra = []
            price = s.get("current_price")
            if price:
                pct_52w = s.get("pct_from_52w_high")
                pct_ma = s.get("pct_from_ma200")
                pos = f"¥{price}"
                if pct_52w is not None:
                    pos += f" (距52周高{pct_52w:+.1f}%)"
                if pct_ma is not None:
                    pos += f" (距200日均{pct_ma:+.1f}%)"
                extra.append(pos)
            mon = s.get("monitor_signal")
            if mon:
                mon_score = s.get("monitor_composite_score", 0)
                extra.append(f"监控信号:{mon}({mon_score})")
            pa = s.get("pa_signal", "")
            if pa:
                extra.append(f"PA信号:{pa}")
            conflict = s.get("score_conflict")
            if conflict:
                extra.append("⚠️监控与基本面冲突")
            extra_str = f" | {' '.join(extra)}" if extra else ""
            lines.append(
                f"- **{s.get('name', '')}** ({s.get('code', '')}) "
                f"评分{s.get('score', 50)}{extra_str}"
            )

        lines.append("\n---\n")
        lines.append("*免责声明：本报告由 AI 自动生成，仅供参考，不构成投资建议。*\n")
        return "\n".join(lines)
