"""量化选股引擎。两阶段漏斗：
  stage-1 全市场多因子初筛(无 LLM) → 候选池
  stage-2 候选池复用 AnalysisEngine 深研(LLM) → top_n
 结果入 ai_pick_results 集合缓存。dal/analysis_engine/result_saver 注入便于测试。
"""
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Callable, Dict, List, Optional

from modules.ai.foundation import factors

from utils.logger import get_logger

logger = get_logger(__name__)

_PROGRESS_KEY = "current"

# Stage-1 硬过滤阈值
_MIN_KLINE_BARS = 20
_MIN_AVG_AMOUNT = 3e7

# Stage-2 深度评分
_STAGE2_WORKERS = 4
_STAGE2_PER_STOCK_SEC = 30

# 精选阶段单行业上限
_MAX_PER_INDUSTRY = 3


def _update_progress(progress: int, status: str, is_running: bool = True,
                     extra: Optional[Dict] = None) -> None:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = {
            "progress": progress,
            "status": status,
            "is_running": is_running,
            "updated_at": beijing_now(),
        }
        if extra:
            doc.update(extra)
        db["pick_progress"].update_one(
            {"key": _PROGRESS_KEY}, {"$set": doc}, upsert=True,
        )
    except Exception:
        pass


_STALE_MINUTES = 10  # 进度超过该时长未推进视为运行已死（正常更新间隔为秒级）


def get_progress() -> Dict[str, Any]:
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["pick_progress"].find_one({"key": _PROGRESS_KEY}, {"_id": 0})
        if not doc:
            return {"is_running": False, "progress": 0, "status": ""}
        # 僵尸进度防护：运行进程被杀时文档永远停在中间态，前端会一直显示"执行中"
        updated = doc.get("updated_at")
        if doc.get("is_running") and updated is not None:
            if beijing_now() - updated > timedelta(minutes=_STALE_MINUTES):
                doc["is_running"] = False
                doc["status"] = f"{doc.get('status', '')}（运行已中断，可重新发起）"
        return doc
    except Exception:
        return {"is_running": False, "progress": 0, "status": ""}


def _acquire_run_lock() -> bool:
    """跨进程选股互斥：原子抢占 pick_progress 文档。
    仅当无运行中任务、或运行已超时僵死时才能拿到锁；
    防止多实例/调度器并发触发的选股互相覆盖进度与结果。
    拿锁环节自身异常时放行（降级为无锁，不因DB抖动阻塞选股）。
    """
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        now = beijing_now()
        stale_before = now - timedelta(minutes=_STALE_MINUTES)
        claimed = db["pick_progress"].find_one_and_update(
            {"key": _PROGRESS_KEY,
             "$or": [{"is_running": {"$ne": True}},
                     {"updated_at": {"$lt": stale_before}}]},
            {"$set": {"is_running": True, "progress": 5,
                      "status": "正在加载股票池...", "updated_at": now}},
        )
        if claimed is not None:
            return True
        if db["pick_progress"].find_one({"key": _PROGRESS_KEY}) is None:
            # 首次运行无文档，直接创建
            db["pick_progress"].update_one(
                {"key": _PROGRESS_KEY},
                {"$set": {"is_running": True, "progress": 5,
                          "status": "正在加载股票池...", "updated_at": now}},
                upsert=True,
            )
            return True
        return False
    except Exception:
        return True


_TEST_RESULTS_KEY = "test_results"


def _save_test_result(result: Dict[str, Any]) -> None:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        db["pick_progress"].update_one(
            {"key": _TEST_RESULTS_KEY}, {"$set": result}, upsert=True,
        )
    except Exception:
        pass


def get_test_result() -> Dict[str, Any]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["pick_progress"].find_one({"key": _TEST_RESULTS_KEY}, {"_id": 0})
        if doc:
            for k in ("timestamp", "updated_at"):
                if k in doc and hasattr(doc[k], "isoformat"):
                    doc[k] = doc[k].isoformat()
            return doc
    except Exception:
        pass
    return {"is_running": False, "picks": [], "status": ""}


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
        if not text:
            return ""
        idx = text.find("**")
        if idx > 0:
            return text[idx:].strip()
        return text.strip()

    def _generate_summary(self, picks: List[Dict[str, Any]]) -> str:
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
        try:
            analysis = self.analysis_engine.analyze_factor_only(code)
            return self._pick_item(analysis, code)
        except Exception as e:
            logger.warning(f"factor fallback failed for {code}: {e}")
            return None

    def preview(self, strategy: str = "preview", top_n: int = 10,
                 candidate_pool: int = 30,
                 weight_overrides: Optional[Dict[str, float]] = None,
                 filter_overrides: Optional[Dict[str, Any]] = None,
                 indicator_config: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """轻量预览：随机采样 100 只，Stage-1 因子筛选，无 LLM。"""
        universe = self.dal.list_universe()
        _save_test_result({"is_running": True, "progress": 2, "status": f"股票池 {len(universe)} 只，采样中...", "strategy": strategy, "picks": []})
        import random
        rng = random.Random(42)
        sampled = rng.sample(universe, min(100, len(universe)))

        screen_weights = dict(factors.SCREEN_WEIGHTS)
        if weight_overrides:
            screen_weights.update(weight_overrides)
        hard_filters = {
            "min_kline_bars": _MIN_KLINE_BARS,
            "min_avg_amount": _MIN_AVG_AMOUNT,
        }
        if filter_overrides:
            hard_filters.update(filter_overrides)

        total_u = len(sampled)
        _save_test_result({"is_running": True, "progress": 5, "status": f"扫描 {total_u} 只...", "strategy": strategy, "picks": []})
        screened: List[tuple] = []
        filtered: Dict[str, int] = {"st": 0, "insufficient_kline": 0, "low_liquidity": 0}
        report_interval = max(1, total_u // 10)
        for i, code in enumerate(sampled):
            try:
                fi = self.dal.get_factor_inputs(code, kline_limit=60)
                reason = self._hard_filter(fi, hard_filters)
                if reason:
                    filtered[reason] += 1
                else:
                    screened.append((code, fi, self._screen_score(fi, weight_overrides, indicator_config)))
            except Exception:
                continue
            if (i + 1) % report_interval == 0 or (i + 1) == total_u:
                pct = 5 + int((i + 1) / total_u * 90)
                _save_test_result({
                    "is_running": True, "progress": pct,
                    "status": f"扫描 {i + 1}/{total_u} 只...",
                    "strategy": strategy, "picks": [],
                })

        _save_test_result({"is_running": True, "progress": 93, "status": "计算综合评分...", "strategy": strategy, "picks": []})
        screened.sort(key=lambda x: x[2], reverse=True)
        candidates = screened[:candidate_pool]

        picks = []
        for code, fi, _ in candidates[:top_n]:
            dim_scores = {}
            try:
                fund_s, _ = factors.fundamental_score(roe=fi.roe, revenue_growth=fi.revenue_growth,
                    profit_growth=fi.profit_growth, gross_margin=fi.gross_margin,
                    debt_ratio=fi.debt_ratio, industry=fi.industry)
                dim_scores["fundamental"] = fund_s
            except Exception:
                dim_scores["fundamental"] = 0
            try:
                tech_s, _ = factors.technical_score(list(reversed(fi.closes)), list(reversed(fi.volumes)))
                dim_scores["technical"] = tech_s
            except Exception:
                dim_scores["technical"] = 0
            try:
                flow_s, _ = factors.fund_flow_detail_score(
                    main_net_inflow=fi.main_net_inflow, total_amount=fi.total_amount,
                    turnover_rate=fi.turnover_rate)
                dim_scores["fund_flow"] = flow_s
            except Exception:
                dim_scores["fund_flow"] = 0
            try:
                val_s, _ = factors.valuation_detail_score(pe=fi.pe, pb=fi.pb, industry=fi.industry)
                dim_scores["valuation"] = val_s
            except Exception:
                dim_scores["valuation"] = 0

            picks.append({
                "code": code,
                "name": getattr(fi, "name", ""),
                "industry": getattr(fi, "industry", ""),
                "composite": (sum(dim_scores.values()) / len(dim_scores)) / 20 if dim_scores else 0,
                "dim_scores": {k: v / 20 for k, v in dim_scores.items()},
            })

        return {
            "strategy": strategy,
            "picks": picks,
            "candidate_count": len(candidates),
            "universe_count": len(universe),
            "filtered_count": sum(filtered.values()),
            "filtered_detail": filtered,
            "timestamp": beijing_now().isoformat(),
        }

    @staticmethod
    def _hard_filter(fi, filter_overrides: Optional[Dict[str, Any]] = None) -> Optional[str]:
        name = (fi.name or "").upper()
        if (filter_overrides or {}).get("exclude_st", True):
            if "ST" in name or "退" in name:
                return "st"
        min_bars = (filter_overrides or {}).get("min_kline_bars", _MIN_KLINE_BARS)
        if len(fi.closes) < min_bars:
            return "insufficient_kline"
        min_amount = (filter_overrides or {}).get("min_avg_amount", _MIN_AVG_AMOUNT)
        if fi.total_amount is not None and fi.total_amount < min_amount:
            return "low_liquidity"
        return None

    def _screen_score(self, fi,
                     weight_overrides: Optional[Dict[str, float]] = None,
                     indicator_config: Optional[List[Dict[str, Any]]] = None) -> float:
        closes_asc = list(reversed(fi.closes))
        amounts_asc = list(reversed(fi.volumes))

        fund_s, fund_d = factors.fundamental_score(
            roe=fi.roe, revenue_growth=fi.revenue_growth,
            profit_growth=fi.profit_growth, gross_margin=fi.gross_margin,
            debt_ratio=fi.debt_ratio, industry=fi.industry,
        )
        tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
        flow_s, flow_d = factors.fund_flow_detail_score(
            main_net_inflow=fi.main_net_inflow, total_amount=fi.total_amount,
            turnover_rate=fi.turnover_rate,
        )
        val_s, val_d = factors.valuation_detail_score(
            pe=fi.pe, pb=fi.pb, industry=fi.industry,
        )

        dim_scores = {
            "fundamental": (fund_s, fund_d),
            "technical":   (tech_s, tech_d),
            "fund_flow":   (flow_s, flow_d),
            "valuation":   (val_s, val_d),
        }
        weights = dict(factors.SCREEN_WEIGHTS)
        if weight_overrides:
            weights.update(weight_overrides)
        comp, _ = factors.composite_score(dim_scores, weights)
        return comp

    def run(self, strategy: str = "default", top_n: int = 10,
            candidate_pool: int = 50, use_cache: bool = True,
            weight_overrides: Optional[Dict[str, float]] = None,
            filter_overrides: Optional[Dict[str, Any]] = None,
            indicator_config: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        try:
            return self._run_internal(strategy, top_n, candidate_pool, use_cache,
                                      weight_overrides, filter_overrides, indicator_config)
        except Exception as e:
            logger.error(f"PickerEngine.run failed: {e}")
            _update_progress(0, f"选股失败: {e}", is_running=False)
            raise

    def _run_internal(self, strategy: str, top_n: int,
                      candidate_pool: int, use_cache: bool,
                      weight_overrides: Optional[Dict[str, float]] = None,
                      filter_overrides: Optional[Dict[str, Any]] = None,
                      indicator_config: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:

        screen_weights = dict(factors.SCREEN_WEIGHTS)
        if weight_overrides:
            screen_weights.update(weight_overrides)

        hard_filters = {
            "min_kline_bars": _MIN_KLINE_BARS,
            "min_avg_amount": _MIN_AVG_AMOUNT,
        }
        if filter_overrides:
            hard_filters.update(filter_overrides)

        if not _acquire_run_lock():
            logger.warning("检测到另一选股任务正在运行（可能来自其他实例/调度器），本次跳过")
            return {"strategy": strategy, "picks": [], "skipped": True,
                    "timestamp": beijing_now().isoformat()}

        universe = self.dal.list_universe()
        if not universe:
            _update_progress(100, "选股完成（无可用股票）", is_running=False)
            result = {"strategy": strategy, "picks": [], "timestamp": beijing_now().isoformat()}
            self.result_saver(dict(result))
            return result

        total_u = len(universe)
        _update_progress(8, f"正在批量加载财务/资金数据...")
        self.dal.preload_screen_cache(universe)
        _update_progress(15, f"数据加载完成，开始初筛 {total_u} 只...")
        logger.info(f"Stage-1: screening {total_u} stocks (cache preloaded)")

        # ── Stage-1 初筛（并行） ──
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _STAGE1_WORKERS = 8

        def _screen_one(code: str) -> Optional[tuple]:
            try:
                fi = self.dal.get_factor_inputs(code, kline_limit=60)
                reason = self._hard_filter(fi, hard_filters)
                if reason:
                    return ("filtered", reason)
                return ("ok", code, self._screen_score(fi, weight_overrides, indicator_config))
            except Exception:
                return ("fail",)

        screened: List[tuple] = []
        screen_failures = 0
        filtered: Dict[str, int] = {"st": 0, "insufficient_kline": 0, "low_liquidity": 0}
        done_count = 0
        screen_exec = ThreadPoolExecutor(max_workers=_STAGE1_WORKERS)
        try:
            fut_map = {screen_exec.submit(_screen_one, code): code for code in universe}
            report_interval = max(1, total_u // 20)
            for fut in as_completed(fut_map):
                code = fut_map[fut]
                try:
                    result = fut.result()
                    tag = result[0]
                    if tag == "filtered":
                        filtered[result[1]] = filtered.get(result[1], 0) + 1
                    elif tag == "ok":
                        screened.append((result[1], result[2]))
                except Exception:
                    screen_failures += 1
                    if screen_failures <= 5:
                        logger.warning(f"Stage-1 screen failed for {code}")
                done_count += 1
                if done_count % report_interval == 0:
                    pct = 15 + int(done_count / total_u * 30)
                    _update_progress(pct, f"初筛 {done_count}/{total_u} 只...")
        finally:
            screen_exec.shutdown(wait=False)

        if screen_failures > total_u * 0.5:
            logger.error(
                f"Stage-1: {screen_failures}/{total_u} stocks failed screening, "
                "结果不可信，请检查数据层/取数逻辑")
        filtered_count = sum(filtered.values())
        screened.sort(key=lambda x: x[1], reverse=True)
        candidates = [c for c, _ in screened[:candidate_pool]]
        _update_progress(45, f"初筛完成，剔除 {filtered_count} 只(ST/次新/低流动性)，候选 {len(candidates)} 只，开始深度评分...")
        logger.info(
            f"Stage-1 done: {len(candidates)} candidates from {len(screened)} screened, "
            f"filtered={filtered}, {screen_failures} failed")

        # ── Stage-2 深度评分 ──
        from concurrent.futures import (
            ThreadPoolExecutor, as_completed, TimeoutError as _FutureTimeout,
        )

        deep: List[Dict[str, Any]] = []
        total_c = len(candidates)
        done_n = 0

        def _advance(status_n: int) -> None:
            pct = 50 + int(status_n / total_c * 45)
            _update_progress(pct, f"深度评分 {status_n}/{total_c} 只...")

        executor = ThreadPoolExecutor(max_workers=_STAGE2_WORKERS)
        try:
            future_map = {
                executor.submit(self.analysis_engine.analyze, code, use_cache=use_cache): code
                for code in candidates
            }
            budget = _STAGE2_PER_STOCK_SEC * max(1, -(-total_c // _STAGE2_WORKERS))
            try:
                for future in as_completed(list(future_map), timeout=budget):
                    code = future_map.pop(future)
                    try:
                        deep.append(self._pick_item(future.result(), code))
                    except Exception as e:
                        logger.warning(f"Stage-2 failed for {code}: {e}，降级为因子评分")
                        fb = self._factor_fallback(code)
                        if fb:
                            deep.append(fb)
                    done_n += 1
                    _advance(done_n)
            except _FutureTimeout:
                logger.warning(
                    f"Stage-2 总预算 {budget}s 耗尽，剩余 {len(future_map)} 只降级为因子评分")

            for future, code in future_map.items():
                future.cancel()
                fb = self._factor_fallback(code)
                if fb:
                    deep.append(fb)
                done_n += 1
                _advance(done_n)
        finally:
            executor.shutdown(wait=False)

        # ── 精选 ──
        deep.sort(key=lambda x: x["composite"], reverse=True)
        picks: List[Dict[str, Any]] = []
        industry_count: Dict[str, int] = {}
        for item in deep:
            ind = item.get("industry") or ""
            if ind and industry_count.get(ind, 0) >= _MAX_PER_INDUSTRY:
                continue
            picks.append(item)
            if ind:
                industry_count[ind] = industry_count.get(ind, 0) + 1
            if len(picks) >= top_n:
                break
        if len(picks) < min(top_n, len(deep)):
            logger.info(
                f"行业分散约束生效：{len(deep)} 只候选按单行业≤{_MAX_PER_INDUSTRY}只取出 {len(picks)} 只")

        _update_progress(96, "AI综合研判中...")
        ai_summary = self._generate_summary(picks)

        result = {
            "strategy": strategy,
            "picks": picks,
            "ai_summary": ai_summary,
            "candidate_count": len(candidates),
            "universe_count": total_u,
            "filtered_count": filtered_count,
            "filtered_detail": filtered,
            "timestamp": beijing_now().isoformat(),

        }
        self.result_saver(dict(result))
        _update_progress(100, "选股完成", is_running=False)
        logger.info(f"Pick done: {len(picks)} picks saved")
        return result
