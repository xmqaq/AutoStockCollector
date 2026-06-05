"""量化选股引擎。两阶段漏斗：
  stage-1 全市场多因子初筛(无 LLM) → 候选池
  stage-2 候选池复用 AnalysisEngine 深研(LLM) → top_n
结果入 ai_pick_results 集合缓存。dal/analysis_engine/result_saver 注入便于测试。
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from modules.ai.foundation import factors
from modules.ai.content_risk import RISK_DISCLAIMER
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
                "以下是量化选股模型筛选出的股票列表（按综合得分排序）：\n"
                + "\n".join(lines)
                + "\n\n请严格按以下格式输出，简洁有重点：\n\n"
                "**优先关注**\n"
                "列出2-3只评分高且各维度均衡的股票，每只说明：核心优势（哪些维度突出）、所属行业、值得关注的理由。2-3句话。\n\n"
                "**谨慎对待**\n"
                "列出有追高风险、估值极端或AI评价偏谨慎的股票，每只说明具体风险点。1-2句话。\n\n"
                "**配置建议**\n"
                "2-3句话：行业集中度风险、建议仓位分配思路、整体风险提示。\n\n"
                "要求：总共200字左右，不做收益承诺，语言直接不啰嗦。"
            )
            result = router.chat(prompt, use_cache=False, task_type="stock_analysis")
            if result.success and result.data:
                raw = result.data.get("content", "") if isinstance(result.data, dict) else str(result.data)
                text, _ = sanitize_text(str(raw))
                return text
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
        return ""

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
            result = {"strategy": strategy, "picks": [], "timestamp": datetime.now().isoformat(), "disclaimer": RISK_DISCLAIMER}
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
        deep: List[Dict[str, Any]] = []
        total_c = len(candidates)
        for i, code in enumerate(candidates):
            try:
                analysis = self.analysis_engine.analyze(code, use_cache=use_cache)
                deep.append({
                    "code": analysis.get("code", code),
                    "name": analysis.get("name", ""),
                    "composite": analysis.get("scores", {}).get("composite", 50.0),
                    "scores": analysis.get("scores", {}),
                    "score_details": analysis.get("score_details", {}),
                    "recommendation": (analysis.get("llm") or {}).get("recommendation", ""),
                    "source": analysis.get("source", "factor"),
                    "industry": analysis.get("industry", ""),
                })
            except Exception as e:
                logger.warning(f"Stage-2 failed for {code}: {e}")
                continue
            pct = 50 + int((i + 1) / total_c * 45)  # 50~95
            _update_progress(pct, f"深度评分 {i + 1}/{total_c} 只...")

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
            "disclaimer": RISK_DISCLAIMER,
        }
        self.result_saver(dict(result))
        _update_progress(100, "选股完成", is_running=False)
        logger.info(f"Pick done: {len(picks)} picks saved")
        return result
