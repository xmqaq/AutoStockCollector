"""量化选股引擎。两阶段漏斗：
  stage-1 全市场多因子初筛(无 LLM) → 候选池
  stage-2 候选池复用 AnalysisEngine 深研(LLM) → top_n
结果入 ai_pick_results 集合缓存。dal/analysis_engine/result_saver 注入便于测试。
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from modules.ai.foundation import factors

from utils.logger import get_logger

logger = get_logger(__name__)

_PROGRESS_KEY = "current"


def _update_progress(progress: int, status: str, is_running: bool = True,
                     extra: Optional[Dict] = None) -> None:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = {
            "progress": progress,
            "status": status,
            "is_running": is_running,
            "updated_at": datetime.now(),
        }
        if extra:
            doc.update(extra)
        db["pick_progress"].update_one(
            {"key": _PROGRESS_KEY}, {"$set": doc}, upsert=True,
        )
    except Exception:
        pass


def get_progress() -> Dict[str, Any]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["pick_progress"].find_one({"key": _PROGRESS_KEY}, {"_id": 0})
        return doc or {"is_running": False, "progress": 0, "status": ""}
    except Exception:
        return {"is_running": False, "progress": 0, "status": ""}


def _default_saver(doc: Dict[str, Any]) -> None:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    db["ai_pick_results"].insert_one(doc)


class PickerEngine:
    def __init__(self, dal=None, analysis_engine=None, result_saver: Optional[Callable[[Dict[str, Any]], None]] = None):
        if dal is None:
            from modules.ai.foundation.dal import StockDAL
            dal = StockDAL()
        if analysis_engine is None:
            from modules.ai.engines.analysis import AnalysisEngine
            analysis_engine = AnalysisEngine()
        self.dal = dal
        self.analysis_engine = analysis_engine
        self.result_saver = result_saver or _default_saver

    @staticmethod
    def _strip_preamble(text: str) -> str:
        """裁掉模型在正式结论前夹带的复述题目/思考过程。

        我们的输出格式以 Markdown 标题 `**优先关注**` 开头，因此把第一个
        `**` 之前的所有内容（如「用户提供了…」「首先，我需要分析…」）全部去掉。
        若模型没按格式输出（找不到 `**`），则原样返回（仅去首尾空白）。
        """
        if not text:
            return ""
        idx = text.find("**")
        if idx > 0:
            return text[idx:].strip()
        return text.strip()

    def _generate_summary(self, picks: List[Dict[str, Any]]) -> str:
        """让 LLM 对 top_n 选股结果做整体投资建议。"""
        if not picks:
            return ""
        try:
            from modules.ai.foundation.llm_router import LLMRouter
            from modules.ai.content_risk import sanitize_text
            router = LLMRouter()

            lines = []
            for i, p in enumerate(picks, 1):
                scores = p.get("scores", {})
                warnings = []
                details = p.get("score_details", {})
                for dim_key, dim_data in details.items():
                    d = dim_data.get("details", {}) if isinstance(dim_data, dict) else {}
                    for k, v in d.items():
                        if k.endswith("_warning") and isinstance(v, str):
                            warnings.append(v)
                rec = p.get("recommendation", "")
                line = (
                    f"{i}. {p.get('code','')} {p.get('name','')} "
                    f"综合={scores.get('composite',0):.0f} "
                    f"基本面={scores.get('fundamental',0):.0f} "
                    f"技术面={scores.get('technical',0):.0f} "
                    f"资金面={scores.get('fund_flow',0):.0f} "
                    f"估值面={scores.get('valuation',0):.0f} "
                    f"行业={p.get('industry','')}"
                )
                if rec:
                    line += f" AI评价={rec}"
                if warnings:
                    line += f" ⚠️{'；'.join(warnings)}"
                lines.append(line)

            prompt = (
                "你是一位专业的A股投资顾问。以下是量化选股模型筛选出的股票列表（按综合得分排序）：\n"
                + "\n".join(lines)
                + "\n\n请直接给出投资建议，严格遵守：\n"
                "1. 不要复述题目或股票列表，不要解释你的分析过程或思考步骤，开头直接输出结论；\n"
                "2. 语言简洁，总字数控制在200字以内，不做收益承诺；\n"
                "3. 严格按以下 Markdown 格式输出，不要有任何前置说明文字：\n\n"
                "**优先关注**\n"
                "- 股票名：一句话理由（突出维度+行业）\n"
                "（列1-2只评分高且各维度均衡的）\n\n"
                "**谨慎对待**\n"
                "- 股票名：一句话风险点\n"
                "（列有追高风险/估值极端/AI评价偏谨慎的）\n\n"
                "**配置建议**\n"
                "一句话：分散配置，以XX、XX为核心，总仓位控制在XX%以下。"
            )
            result = router.chat(prompt, use_cache=False, task_type="stock_analysis")
            if result.success and result.data:
                raw = result.data.get("content", "") if isinstance(result.data, dict) else str(result.data)
                text, _ = sanitize_text(str(raw))
                return self._strip_preamble(text)
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
        return ""

    @staticmethod
    def _pick_item(analysis: Dict[str, Any], code: str) -> Dict[str, Any]:
        """把 analyze() 结果转成 picks 列表条目。"""
        return {
            "code": analysis.get("code", code),
            "name": analysis.get("name", ""),
            "composite": analysis.get("scores", {}).get("composite", 50.0),
            "scores": analysis.get("scores", {}),
            "score_details": analysis.get("score_details", {}),
            "recommendation": (analysis.get("llm") or {}).get("recommendation", ""),
            "source": analysis.get("source", "factor"),
            "industry": analysis.get("industry", ""),
        }

    def _factor_fallback(self, code: str) -> Optional[Dict[str, Any]]:
        """LLM 超时/失败时用纯因子评分兜底（不调用 LLM）。失败返回 None。"""
        try:
            analysis = self.analysis_engine.analyze_factor_only(code)
            return self._pick_item(analysis, code)
        except Exception as e:
            logger.warning(f"factor fallback failed for {code}: {e}")
            return None

    def _screen_score(self, fi) -> float:
        """Stage-1 多因子初筛评分（无 LLM）。"""
        closes_asc = list(reversed(fi.closes))
        amounts_asc = list(reversed(fi.volumes))

        fund_s, _ = factors.fundamental_score(
            roe=fi.roe,
            revenue_growth=fi.revenue_growth,
            profit_growth=fi.profit_growth,
            gross_margin=fi.gross_margin,
            debt_ratio=fi.debt_ratio,
            industry=fi.industry,
        )
        tech_s, _ = factors.technical_score(closes_asc, amounts_asc)
        flow_s, _ = factors.fund_flow_detail_score(
            main_net_inflow=fi.main_net_inflow,
            total_amount=fi.total_amount,
            turnover_rate=fi.turnover_rate,
        )
        val_s, _ = factors.valuation_detail_score(
            pe=fi.pe, pb=fi.pb, industry=fi.industry,
        )

        dim_scores = {
            "fundamental": (fund_s, {"data_available": True}),
            "technical":   (tech_s, {"data_available": True}),
            "fund_flow":   (flow_s, {"data_available": fi.main_net_inflow is not None}),
            "valuation":   (val_s, {"data_available": True}),
        }
        comp, _ = factors.composite_score(dim_scores, factors.SCREEN_WEIGHTS)
        return comp

    def run(self, strategy: str = "default", top_n: int = 10,
            candidate_pool: int = 50, use_cache: bool = True) -> Dict[str, Any]:

        try:
            return self._run_internal(strategy, top_n, candidate_pool, use_cache)
        except Exception as e:
            logger.error(f"PickerEngine.run failed: {e}")
            _update_progress(0, f"选股失败: {e}", is_running=False)
            raise

    def _run_internal(self, strategy: str, top_n: int,
                      candidate_pool: int, use_cache: bool) -> Dict[str, Any]:

        _update_progress(5, "正在加载股票池...")
        universe = self.dal.list_universe()
        if not universe:
            _update_progress(100, "选股完成（无可用股票）", is_running=False)
            result = {"strategy": strategy, "picks": [], "timestamp": datetime.now().isoformat()}
            self.result_saver(dict(result))
            return result

        total_u = len(universe)
        _update_progress(8, f"正在批量加载财务/资金数据...")
        self.dal.preload_screen_cache(universe)
        _update_progress(15, f"数据加载完成，开始初筛 {total_u} 只...")
        logger.info(f"Stage-1: screening {total_u} stocks (cache preloaded)")

        # ── Stage-1 初筛 ──
        screened: List[tuple] = []
        report_interval = max(1, total_u // 20)  # 每5%报告一次
        for i, code in enumerate(universe):
            try:
                fi = self.dal.get_factor_inputs(code, kline_limit=30)
                screened.append((code, self._screen_score(fi)))
            except Exception:
                continue
            if (i + 1) % report_interval == 0:
                pct = 15 + int((i + 1) / total_u * 30)  # 15~45
                _update_progress(pct, f"初筛 {i + 1}/{total_u} 只...")

        screened.sort(key=lambda x: x[1], reverse=True)
        candidates = [c for c, _ in screened[:candidate_pool]]
        _update_progress(45, f"初筛完成，候选 {len(candidates)} 只，开始深度评分...")
        logger.info(f"Stage-1 done: {len(candidates)} candidates from {len(screened)} screened")

        # ── Stage-2 深度评分 ──
        # 每只股票的 LLM 深研有 30s 硬性墙钟超时（ThreadPoolExecutor），
        # 超时/异常一律降级为纯因子评分兜底，绝不丢股票、绝不阻塞整体循环；
        # 无论成功/超时/失败都推进进度，保证 50 只全部处理完后能到 100%。
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeout

        deep: List[Dict[str, Any]] = []
        total_c = len(candidates)
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            for i, code in enumerate(candidates):
                try:
                    future = executor.submit(
                        self.analysis_engine.analyze, code, use_cache=use_cache,
                    )
                    analysis = future.result(timeout=30)
                    deep.append(self._pick_item(analysis, code))
                except _FutureTimeout:
                    logger.warning(f"Stage-2 timeout for {code} (>30s)，降级为因子评分")
                    fb = self._factor_fallback(code)
                    if fb:
                        deep.append(fb)
                except Exception as e:
                    logger.warning(f"Stage-2 failed for {code}: {e}，降级为因子评分")
                    fb = self._factor_fallback(code)
                    if fb:
                        deep.append(fb)
                # 无论成功/超时/失败都推进进度，避免卡死
                pct = 50 + int((i + 1) / total_c * 45)  # 50~95
                _update_progress(pct, f"深度评分 {i + 1}/{total_c} 只...")
        finally:
            # 不等待可能仍阻塞的兜底线程，让它们在后台随 HTTP 超时自行退出
            executor.shutdown(wait=False)

        deep.sort(key=lambda x: x["composite"], reverse=True)
        picks = deep[:top_n]

        _update_progress(96, "AI综合研判中...")
        ai_summary = self._generate_summary(picks)

        result = {
            "strategy": strategy,
            "picks": picks,
            "ai_summary": ai_summary,
            "candidate_count": len(candidates),
            "universe_count": total_u,
            "timestamp": datetime.now().isoformat(),

        }
        self.result_saver(dict(result))
        _update_progress(100, "选股完成", is_running=False)
        logger.info(f"Pick done: {len(picks)} picks saved")
        return result
