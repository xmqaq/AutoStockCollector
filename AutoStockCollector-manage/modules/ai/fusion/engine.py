"""融合选股引擎。整合量化选股的全市场覆盖 + 策略选股的多 Agent 辩论，四阶段流水线：

  Stage 1 全市场硬过滤 + 纯因子初筛（市场环境感知权重）→ 候选池 A
  Stage 2 多策略叠加（在全市场因子缓存上按各策略权重重排），共识来源计数
  Stage 3 深度评分（AnalysisEngine）+ 投资哲学辩论（复用 strategy_pick）
  Stage 4 行业分散精选 + 仓位权重建议（复用 ai_selector.advisor）+ 结果快照

quick 模式跳过 Stage 2/辩论，用于盘中资金异动快速触发。
dal / analysis_engine / result_saver 注入便于测试。
"""
import math
import uuid
from concurrent.futures import (
    ThreadPoolExecutor, as_completed, TimeoutError as _FutureTimeout,
)
from typing import Any, Callable, Dict, List, Optional

from utils.helpers import beijing_now
from utils.logger import get_logger

from modules.ai.foundation import factors
from modules.ai.fusion.market_state import MarketStateDetector
from modules.ai.fusion.progress import (
    update_progress, get_progress, acquire_run_lock,
)

logger = get_logger(__name__)

RESULTS_COL = "fusion_pick_results"
SNAPSHOT_COL = "fusion_pick_snapshots"
PROGRESS_COL = "fusion_pick_progress"

_STAGE1_WORKERS = 8
_STAGE3_WORKERS = 4
_STAGE3_PER_STOCK_SEC = 30
_SUBNEW_DAYS = 180
_MIN_DEEP = 24  # full 模式 LLM 深度评分的最小覆盖数（其余候选纯因子兜底，控制耗时）
# 加分融入融合分的「跨度」：正向 = debate(≤15)+source(≤9)=24，留 1 分余量 → 恒 <100
_BONUS_POS_SPAN = 25.0
_BONUS_NEG_SPAN = 16.0  # debate 最负 -15，留 1 分余量


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _default_result_saver(doc: Dict[str, Any]) -> None:
    """写入 fusion_pick_results 集合，保留最近 50 条。参考 strategy_pick._save_result。"""
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    db[RESULTS_COL].insert_one(doc)
    old = list(db[RESULTS_COL].find({}, {"_id": 1})
               .sort("created_at", -1).skip(50).limit(1000))
    if old:
        db[RESULTS_COL].delete_many({"_id": {"$in": [o["_id"] for o in old]}})


def _parse_days_since(raw) -> Optional[int]:
    """解析上市日期，返回距今自然日数。解析失败返回 None（不过滤）。"""
    if raw is None:
        return None
    from datetime import datetime
    s = str(raw).strip()
    if not s or s in ("-", "—", "--", "N/A"):
        return None
    fmt_candidates = []
    digits = s.replace("-", "").replace("/", "").replace(".", "")
    if len(digits) == 8 and digits.isdigit():
        s2 = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    else:
        s2 = s[:10]
    try:
        d = datetime.fromisoformat(s2)
    except (ValueError, TypeError):
        try:
            d = datetime.strptime(s2, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    return (beijing_now().replace(tzinfo=None) - d).days


class FusionPickerEngine:
    def __init__(self, dal=None, analysis_engine=None,
                 result_saver: Optional[Callable[[Dict[str, Any]], None]] = None):
        if dal is None:
            from modules.ai.foundation.dal import StockDAL
            dal = StockDAL()
        if analysis_engine is None:
            from modules.ai.engines.analysis import AnalysisEngine
            analysis_engine = AnalysisEngine(dal=dal)
        self.dal = dal
        self.analysis_engine = analysis_engine
        self.result_saver = result_saver or _default_result_saver
        self.market = MarketStateDetector()

    # ──────────────────────────────────────────────────────────────
    # 公开入口
    # ──────────────────────────────────────────────────────────────

    def run(self, top_n: int = 10, candidate_pool: int = 50,
            strategy_ids: Optional[List[str]] = None,
            philosophy_ids: Optional[List[str]] = None,
            weight_overrides: Optional[dict] = None,
            filter_overrides: Optional[dict] = None,
            use_cache: bool = True, mode: str = "full") -> Dict[str, Any]:
        try:
            return self._run(top_n, candidate_pool, strategy_ids, philosophy_ids,
                             weight_overrides, filter_overrides, use_cache, mode)
        except Exception as e:
            logger.error(f"FusionPickerEngine.run failed: {e}")
            update_progress(0, f"融合选股失败: {e}", is_running=False)
            raise

    # ──────────────────────────────────────────────────────────────
    # 主流程
    # ──────────────────────────────────────────────────────────────

    def _run(self, top_n, candidate_pool, strategy_ids, philosophy_ids,
             weight_overrides, filter_overrides, use_cache, mode) -> Dict[str, Any]:
        strategy_ids = strategy_ids or []
        philosophy_ids = philosophy_ids or []
        filter_overrides = dict(filter_overrides or {})

        if mode == "quick":
            candidate_pool = min(candidate_pool, 20)
            top_n = min(top_n, 5)

        # Stage 1.1 互斥锁。允许调用方（cron/路由）已 pre-acquire 后复用握手锁。
        # ponytail: 握手窗口（progress<=5）内同进程并发直跑会漏判，实际入口是单线程路由，可接受。
        prog = get_progress()
        reused = bool(prog.get("is_running") and (prog.get("progress") or 0) <= 5)
        if not reused:
            if not acquire_run_lock():
                logger.warning("[fusion] 已有融合选股任务运行中，本次跳过")
                return {"skipped": True, "timestamp": beijing_now().isoformat()}
        update_progress(8, "市场环境检测中...")

        run_id = str(uuid.uuid4())[:8]

        # Stage 1.2 市场状态 + 权重
        state = self.market.detect()
        weights = self.market.get_weights(state)
        if weight_overrides:
            weights = {**weights, **weight_overrides}
        market_desc = self.market.get_description(state)

        # Stage 1.3 全市场
        universe = self.dal.list_universe()
        total_u = len(universe)
        if not universe:
            return self._finish_empty(run_id, state, market_desc, weights, mode)
        update_progress(12, f"加载 {total_u} 只股票数据...")
        try:
            self.dal.preload_screen_cache(universe)
        except Exception as e:
            logger.warning(f"[fusion] 预加载缓存失败（降级逐只查）: {e}")

        info_map, trading_codes = self._preload_filter_context()

        # Stage 1.4 + 1.5 硬过滤 + 初筛分（并发）
        update_progress(15, f"全市场初筛 {total_u} 只...")
        pool_a, screen_scores, fi_cache = self._screen_universe(
            universe, info_map, trading_codes, filter_overrides, weights, candidate_pool)
        filtered_count = total_u - len(screen_scores)
        update_progress(42, f"初筛完成，候选池 {len(pool_a)} 只")

        # 来源登记：pool A 记 source=quant
        sources: Dict[str, List[str]] = {c: ["quant"] for c in pool_a}

        # Stage 2 策略叠加（复用 Stage 1 的全市场因子缓存，按各策略权重重排取 top）
        if mode != "quick" and strategy_ids:
            update_progress(46, f"叠加 {len(strategy_ids)} 个策略...")
            self._overlay_strategies(strategy_ids, candidate_pool, sources, fi_cache)

        # 合并候选池：按初筛分排序，截断到 candidate_pool * 1.5
        for code in sources:
            if code not in screen_scores:
                screen_scores[code] = self._safe_screen_score(code, weights)
        merged = sorted(sources.keys(), key=lambda c: screen_scores.get(c, 0), reverse=True)
        cutoff = int(candidate_pool * 1.5)
        candidates = merged[:cutoff]
        update_progress(52, f"候选池 {len(candidates)} 只，深度评分...")

        # Stage 3.1 深度评分（full 模式只对初筛分最高的一段调 LLM，其余纯因子兜底，控制耗时）
        analyses, deep_codes = self._deep_score(candidates, mode, use_cache, top_n)
        update_progress(72, "深度评分完成")

        # Stage 3.2/3.3 哲学辩论（full，仅对深度评分过的股票，逐只推进度）
        debates: Dict[str, tuple] = {}
        if mode != "quick" and deep_codes:
            debates = self._run_debates(deep_codes, philosophy_ids)

        # Stage 3.4 FusionScore
        picks_all = self._assemble_picks(candidates, analyses, sources, debates, mode)
        update_progress(88, "精选 + 仓位建议...")

        # Stage 4 精选 + 行业分散 + 仓位
        picks_all.sort(key=lambda p: p["fusion_score"], reverse=True)
        picks = self._industry_diversify(picks_all, top_n)
        self._fill_weights(picks)

        # Stage 4.5 AI 总结（full）
        ai_summary = ""
        if mode != "quick" and picks:
            update_progress(94, "AI 综合研判中...")
            ai_summary = self._summary(picks)

        timestamp = beijing_now()
        result = {
            "run_id": run_id,
            "picks": picks,
            "market_state": state,
            "market_description": market_desc,
            "weights_used": weights,
            "ai_summary": ai_summary,
            "universe_count": total_u,
            "filtered_count": filtered_count,
            "candidate_count": len(candidates),
            "strategy_count": len(strategy_ids),
            "mode": mode,
            "timestamp": timestamp.isoformat(),
        }

        # Stage 4.6 落库 + 快照
        try:
            saved = dict(result)
            saved["created_at"] = timestamp
            self.result_saver(saved)
        except Exception as e:
            logger.warning(f"[fusion] 结果落库失败: {e}")
        self._save_snapshot(run_id, state, picks, timestamp)

        update_progress(100, "融合选股完成", is_running=False)
        logger.info(f"[fusion] done run_id={run_id} state={state} picks={len(picks)}")
        return result

    def _finish_empty(self, run_id, state, market_desc, weights, mode) -> Dict[str, Any]:
        update_progress(100, "融合选股完成（无可用股票）", is_running=False)
        return {
            "run_id": run_id, "picks": [], "market_state": state,
            "market_description": market_desc, "weights_used": weights,
            "ai_summary": "", "universe_count": 0, "filtered_count": 0,
            "candidate_count": 0, "strategy_count": 0, "mode": mode,
            "timestamp": beijing_now().isoformat(),
        }

    # ──────────────────────────────────────────────────────────────
    # Stage 1 辅助
    # ──────────────────────────────────────────────────────────────

    def _preload_filter_context(self):
        """一次性预加载 stock_info（名称/上市日期）+ 近5日有K线的股票集合（停牌判定）。"""
        info_map: Dict[str, Dict[str, Any]] = {}
        trading_codes: set = set()
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            for rec in db["stock_info"].find(
                    {}, {"_id": 0, "code": 1, "name": 1, "A股简称": 1,
                         "list_date": 1, "上市日期": 1}):
                c = rec.get("code")
                if c:
                    info_map[c] = rec
            recent_dates = sorted(db["kline"].distinct("date"), reverse=True)[:5]
            if recent_dates:
                trading_codes = set(
                    db["kline"].distinct("code", {"date": {"$in": recent_dates}}))
        except Exception as e:
            logger.warning(f"[fusion] 过滤上下文预加载失败: {e}")
        return info_map, trading_codes

    @staticmethod
    def _hard_filter(code, fi, info, trading_codes, hf) -> Optional[str]:
        name = (fi.name or info.get("name") or info.get("A股简称") or "").upper()
        if "ST" in name or "退" in name:
            return "st"
        days = _parse_days_since(info.get("list_date") or info.get("上市日期"))
        if days is not None and days < _SUBNEW_DAYS:
            return "subnew"
        # 停牌：近5个交易日无K线。trading_codes 为空（预加载失败）时不据此过滤。
        if trading_codes and code not in trading_codes:
            return "suspended"
        if len(fi.closes) < hf.get("min_kline_bars", 20):
            return "insufficient_kline"
        if (fi.total_amount or 0) < hf.get("min_avg_amount", 3e7):
            return "low_liquidity"
        roe_min = hf.get("roe_min")
        if roe_min is not None and fi.roe is not None and fi.roe < roe_min:
            return "low_roe"
        rg_min = hf.get("revenue_growth_min")
        if rg_min is not None and fi.revenue_growth is not None and fi.revenue_growth < rg_min:
            return "low_revenue_growth"
        return None

    @staticmethod
    def _screen_score(fi, weights) -> float:
        closes_asc = list(reversed(fi.closes))
        amounts_asc = list(reversed(fi.volumes))
        fund_s, fund_d = factors.fundamental_score(
            roe=fi.roe, revenue_growth=fi.revenue_growth,
            profit_growth=fi.profit_growth, gross_margin=fi.gross_margin,
            debt_ratio=fi.debt_ratio, industry=fi.industry)
        tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
        flow_s, flow_d = factors.fund_flow_detail_score(
            main_net_inflow=fi.main_net_inflow, total_amount=fi.total_amount,
            turnover_rate=fi.turnover_rate)
        val_s, val_d = factors.valuation_detail_score(
            pe=fi.pe, pb=fi.pb, industry=fi.industry)
        comp, _ = factors.composite_score({
            "fundamental": (fund_s, fund_d), "technical": (tech_s, tech_d),
            "fund_flow": (flow_s, flow_d), "valuation": (val_s, val_d),
        }, weights)
        return comp

    def _safe_screen_score(self, code, weights) -> float:
        try:
            fi = self.dal.get_factor_inputs(code, kline_limit=60)
            return self._screen_score(fi, weights)
        except Exception:
            return 0.0

    def _screen_universe(self, universe, info_map, trading_codes, hf, weights, candidate_pool):
        """全市场硬过滤 + 因子初筛。返回 (pool_a, scores, fi_cache)。
        fi_cache 缓存所有通过硬过滤的 FactorInputs，供 Stage 2 策略叠加在全市场上重排，
        避免再次取数。
        """
        screened: List[tuple] = []
        fi_cache: Dict[str, Any] = {}
        ex = ThreadPoolExecutor(max_workers=_STAGE1_WORKERS)

        def _one(code):
            try:
                fi = self.dal.get_factor_inputs(code, kline_limit=60)
                reason = self._hard_filter(code, fi, info_map.get(code, {}),
                                           trading_codes, hf)
                if reason:
                    return None
                return (code, self._screen_score(fi, weights), fi)
            except Exception:
                return None

        try:
            for res in ex.map(_one, universe):
                if res:
                    screened.append((res[0], res[1]))
                    fi_cache[res[0]] = res[2]
        finally:
            ex.shutdown(wait=False)

        screened.sort(key=lambda x: x[1], reverse=True)
        scores = {c: s for c, s in screened}
        pool_a = [c for c, _ in screened[:candidate_pool]]
        return pool_a, scores, fi_cache

    # ──────────────────────────────────────────────────────────────
    # Stage 2 策略叠加
    # ──────────────────────────────────────────────────────────────

    def _overlay_strategies(self, strategy_ids, candidate_pool, sources, fi_cache):
        """对每个策略，用其四维权重 + 流动性过滤，在 Stage 1 的全市场因子缓存上重排取 top，
        命中的股票登记来源（→ source_bonus）。全市场口径，无随机采样。
        ponytail: 策略 indicators 细配（每指标权重/阈值）在初筛打分层不生效——
                  picker 的 _screen_score 本就只吃四维 weights，此处保持一致，差异即四维权重+过滤。
        """
        from modules.ai.strategies.storage import StrategyStorage
        from bson import ObjectId
        storage = StrategyStorage()

        def _one(sid):
            try:
                doc = storage.find_one({"_id": ObjectId(sid)})
                if not doc or doc.get("type") != "selection":
                    return None
                weights = doc.get("weights") or factors.SCREEN_WEIGHTS
                min_amt = (doc.get("filters") or {}).get("min_avg_amount", 0) or 0
                scored = []
                for code, fi in fi_cache.items():
                    if min_amt and (fi.total_amount or 0) < min_amt:
                        continue
                    scored.append((code, self._screen_score(fi, weights)))
                scored.sort(key=lambda x: x[1], reverse=True)
                return doc["name"], [c for c, _ in scored[:candidate_pool]]
            except Exception as e:
                logger.warning(f"[fusion] 策略叠加失败 sid={sid}: {e}")
                return None

        ex = ThreadPoolExecutor(max_workers=min(4, len(strategy_ids)))
        try:
            futs = {ex.submit(_one, sid): sid for sid in strategy_ids}
            for fut in as_completed(futs):
                out = fut.result()
                if not out:
                    continue
                sname, codes = out
                for code in codes:
                    srcs = sources.setdefault(code, [])
                    if sname not in srcs:
                        srcs.append(sname)
        finally:
            ex.shutdown(wait=False)

    # ──────────────────────────────────────────────────────────────
    # Stage 3 深度评分 + 辩论
    # ──────────────────────────────────────────────────────────────

    def _factor_only(self, code):
        try:
            return self.analysis_engine.analyze_factor_only(code)
        except Exception as e:
            logger.warning(f"[fusion] factor-only 失败 {code}: {e}")
            return None

    def _factor_pool(self, codes, out, advance):
        """对一批股票纯因子评分（无 LLM，快），结果写入 out，每完成一只调 advance。"""
        if not codes:
            return
        ex = ThreadPoolExecutor(max_workers=_STAGE3_WORKERS)
        try:
            futs = {ex.submit(self.analysis_engine.analyze_factor_only, c): c for c in codes}
            for fut in as_completed(futs):
                c = futs[fut]
                try:
                    out[c] = fut.result()
                except Exception as e:
                    logger.warning(f"[fusion] 因子评分失败 {c}: {e}")
                advance()
        finally:
            ex.shutdown(wait=False)

    def _deep_score(self, codes, mode, use_cache, top_n, lo=52, hi=72):
        """返回 (analyses, deep_codes)。
        full 模式只对初筛分最高的一段（deep_codes）调 LLM analyze，其余纯因子兜底——
        避免对整个候选池逐只 LLM（含外部行情/估值请求）导致长时间无响应。
        每完成一只刷新进度，既给前端反馈，也持续刷新 updated_at 防 10 分钟僵尸误判。
        ponytail: deep 上限 max(top_n*2, _MIN_DEEP)，覆盖最终精选所需即可，其余低分股不值得 LLM。
        """
        out: Dict[str, Any] = {}
        if not codes:
            return out, []
        total = max(1, len(codes))
        done = [0]

        def advance():
            done[0] += 1
            update_progress(lo + int(done[0] / total * (hi - lo)),
                            f"深度评分 {done[0]}/{total} 只...")

        if mode == "quick":
            self._factor_pool(codes, out, advance)
            return out, []

        deep_limit = min(len(codes), max(top_n * 2, _MIN_DEEP))
        deep_codes = codes[:deep_limit]          # codes 已按初筛分降序
        shallow_codes = codes[deep_limit:]

        # 浅层：纯因子，快速跑完
        self._factor_pool(shallow_codes, out, advance)

        # 深层：LLM analyze + 总预算兜底 + 失败降级因子
        ex = ThreadPoolExecutor(max_workers=_STAGE3_WORKERS)
        try:
            fut_map = {ex.submit(self.analysis_engine.analyze, c, use_cache=use_cache): c
                       for c in deep_codes}
            budget = _STAGE3_PER_STOCK_SEC * max(1, -(-len(deep_codes) // _STAGE3_WORKERS))
            try:
                for fut in as_completed(list(fut_map), timeout=budget):
                    c = fut_map.pop(fut)
                    try:
                        out[c] = fut.result()
                    except Exception as e:
                        logger.warning(f"[fusion] 深度评分失败 {c}: {e}，降级因子")
                        fb = self._factor_only(c)
                        if fb:
                            out[c] = fb
                    advance()
            except _FutureTimeout:
                logger.warning(f"[fusion] 深度评分预算 {budget}s 耗尽，剩余降级因子")
            for fut, c in fut_map.items():
                fut.cancel()
                fb = self._factor_only(c)
                if fb:
                    out[c] = fb
                advance()
        finally:
            ex.shutdown(wait=False)
        return out, deep_codes

    def _run_debates(self, codes, philosophy_ids, lo=72, hi=88) -> Dict[str, tuple]:
        from api.routes.strategy_pick import (
            _get_philosophy_signals, _build_debate_consensus,
        )
        results: Dict[str, tuple] = {}
        total = max(1, len(codes))
        done = 0

        def _one(code):
            try:
                bundle = self.dal.get_stock_bundle(code)
                signals, _dim, _flat, _comp = _get_philosophy_signals(code, bundle)
                if philosophy_ids:
                    signals = [s for s in signals if s.get("agent_id") in philosophy_ids]
                consensus = _build_debate_consensus(signals) if signals else None
                return signals, consensus
            except Exception as e:
                logger.warning(f"[fusion] 辩论失败 {code}: {e}")
                return [], None

        ex = ThreadPoolExecutor(max_workers=_STAGE3_WORKERS)
        try:
            futs = {ex.submit(_one, c): c for c in codes}
            for fut in as_completed(futs):
                c = futs[fut]
                try:
                    results[c] = fut.result(timeout=30)
                except Exception:
                    results[c] = ([], None)
                done += 1
                update_progress(lo + int(done / total * (hi - lo)),
                                f"投资哲学辩论 {done}/{total} 只...")
        finally:
            ex.shutdown(wait=False)
        return results

    @staticmethod
    def _fuse(factor_score: float, debate_bonus: float, source_bonus: float) -> float:
        """加分按「离满分的剩余空间」比例融入，而非直接相加：
        因子分越高、可加空间越小 → 头部不扎堆满分、保留区分度、保序、永不触顶。
        分母留 1 分余量（正向理论上限 15+9=24 用 25；负向 -15 用 16）确保恒 <100、>0。
        """
        combined = debate_bonus + source_bonus
        if combined >= 0:
            fs = factor_score + (100.0 - factor_score) * (combined / _BONUS_POS_SPAN)
        else:
            fs = factor_score + factor_score * (combined / _BONUS_NEG_SPAN)
        return _clamp(fs)

    def _assemble_picks(self, candidates, analyses, sources, debates, mode) -> List[Dict[str, Any]]:
        picks: List[Dict[str, Any]] = []
        for code in candidates:
            a = analyses.get(code)
            if not a:
                continue
            scores = a.get("scores", {}) or {}
            factor_score = float(scores.get("composite", 50.0))

            srcs = sources.get(code, ["quant"])
            source_count = len(srcs)
            source_bonus = min(source_count - 1, 3) * 3

            signals, consensus = debates.get(code, ([], None))
            if mode != "quick" and consensus:
                consensus_level = float(consensus.get("consensus_level", 0) or 0)
                tendency = float(consensus.get("tendency", 0) or 0)
                debate_bonus = _clamp(consensus_level * tendency * 15, -15, 15)
            else:
                consensus_level, tendency, debate_bonus = 0.0, 0.0, 0.0

            fusion_score = self._fuse(factor_score, debate_bonus, source_bonus)

            picks.append({
                "code": code,
                "name": a.get("name", ""),
                "industry": a.get("industry", ""),
                "fusion_score": round(fusion_score, 2),
                "factor_score": round(factor_score, 2),
                "debate_bonus": round(debate_bonus, 2),
                "source_bonus": source_bonus,
                "consensus_level": round(consensus_level, 3),
                "tendency": round(tendency, 3),
                "source_count": source_count,
                "sources": srcs,
                "scores": scores,
                "score_details": a.get("score_details", {}),
                "debate_signals": signals if mode != "quick" else [],
                "debate_consensus": consensus if mode != "quick" else None,
                "llm": a.get("llm"),
                "weight": 0.0,
            })
        return picks

    # ──────────────────────────────────────────────────────────────
    # Stage 4 精选
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _industry_diversify(picks_sorted, top_n) -> List[Dict[str, Any]]:
        max_per_industry = max(1, math.ceil(top_n * 0.4))
        out: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {}
        for p in picks_sorted:
            ind = p.get("industry") or ""
            if ind and counts.get(ind, 0) >= max_per_industry:
                continue
            out.append(p)
            if ind:
                counts[ind] = counts.get(ind, 0) + 1
            if len(out) >= top_n:
                break
        return out

    @staticmethod
    def _fill_weights(picks) -> None:
        from modules.ai_selector.advisor import build_score_weighted_targets
        targets = build_score_weighted_targets([{
            "code": p["code"], "name": p["name"],
            "composite": p["fusion_score"], "industry": p.get("industry", ""),
        } for p in picks])
        wmap = {t["code"]: t["weight"] for t in targets}
        for p in picks:
            p["weight"] = wmap.get(p["code"], 0.0)

    def _summary(self, picks) -> str:
        try:
            from api.routes.strategy_pick import _generate_debate_summary
            debate_results = [{
                "code": p["code"], "name": p.get("name", ""),
                "signals": p.get("debate_signals", []),
                "consensus": p.get("debate_consensus"),
            } for p in picks]
            # _generate_debate_summary 读 p["composite"]，融合分映射过去使摘要分值真实
            summary_picks = [{**p, "composite": p["fusion_score"]} for p in picks]
            return _generate_debate_summary(debate_results, summary_picks)
        except Exception as e:
            logger.warning(f"[fusion] AI 总结失败: {e}")
            return ""

    def _save_snapshot(self, run_id, state, picks, timestamp) -> None:
        """写 fusion_pick_snapshots，仅存回测所需轻量字段（不存 LLM 全文）。"""
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            db[SNAPSHOT_COL].insert_one({
                "run_id": run_id,
                "timestamp": timestamp.isoformat(),
                "market_state": state,
                "picks": [{
                    "code": p["code"],
                    "name": p.get("name", ""),
                    "composite": p["fusion_score"],   # PickTracker 读 composite
                    "fusion_score": p["fusion_score"],
                    "factor_score": p["factor_score"],
                    "debate_bonus": p.get("debate_bonus", 0),
                    "source_count": p["source_count"],
                    "sources": p.get("sources", []),
                    "scores": p.get("scores", {}),
                } for p in picks],
                "created_at": timestamp,
            })
            # 控制体积：保留最近 200 条快照
            old = list(db[SNAPSHOT_COL].find({}, {"_id": 1})
                       .sort("created_at", -1).skip(200).limit(2000))
            if old:
                db[SNAPSHOT_COL].delete_many({"_id": {"$in": [o["_id"] for o in old]}})
        except Exception as e:
            logger.warning(f"[fusion] 快照保存失败: {e}")


if __name__ == "__main__":
    # 冒烟自检：验证深度评分的 deep/shallow 分流（无 DB、无 LLM）
    class _FakeAE:
        def __init__(self):
            self.deep, self.shallow = [], []

        def analyze(self, code, use_cache=True):
            self.deep.append(code)
            return {"code": code, "name": code, "industry": "x",
                    "scores": {"composite": 60}, "score_details": {},
                    "llm": None, "source": "llm"}

        def analyze_factor_only(self, code):
            self.shallow.append(code)
            return {"code": code, "name": code, "industry": "x",
                    "scores": {"composite": 50}, "score_details": {},
                    "llm": None, "source": "factor"}

    fake = _FakeAE()
    eng = FusionPickerEngine(dal=object(), analysis_engine=fake, result_saver=lambda d: None)

    # full：30 候选，top_n=10 → deep=max(20,24)=24 只 LLM，6 只纯因子
    cands = [f"c{i}" for i in range(30)]
    out, deep = eng._deep_score(cands, "full", True, top_n=10)
    assert len(deep) == 24, deep
    assert len(fake.deep) == 24 and len(fake.shallow) == 6, (len(fake.deep), len(fake.shallow))
    assert len(out) == 30 and set(out) == set(cands)
    assert deep == cands[:24]  # 取初筛分最高的前段（codes 已降序）

    # quick：全部纯因子，无 LLM，deep_codes 为空
    fake2 = _FakeAE()
    eng2 = FusionPickerEngine(dal=object(), analysis_engine=fake2, result_saver=lambda d: None)
    out2, deep2 = eng2._deep_score([f"c{i}" for i in range(20)], "quick", True, top_n=5)
    assert deep2 == [] and not fake2.deep and len(fake2.shallow) == 20

    # 候选 < 上限时全部深度
    fake3 = _FakeAE()
    eng3 = FusionPickerEngine(dal=object(), analysis_engine=fake3, result_saver=lambda d: None)
    out3, deep3 = eng3._deep_score([f"c{i}" for i in range(10)], "full", True, top_n=10)
    assert len(deep3) == 10 and len(fake3.deep) == 10 and not fake3.shallow

    # 融合分：永不触顶 100、保序、负辩论扣分、无加分=因子分
    f = FusionPickerEngine._fuse
    assert f(87.7, 9.8, 9.0) < 100 and f(87.7, 9.8, 9.0) > 87.7          # 顶配也 <100、仍加分
    assert f(80, 15, 9) < 100                                            # 理论满额加分仍 <100
    assert f(87.7, 8.9, 9.0) > f(82.1, 8.9, 9.0)                         # 因子分高→融合分高（保序）
    assert f(80, 12, 9) > f(80, 4, 9)                                    # 加分多→融合分高（保序）
    assert f(80, -15, 0) < 80 and f(80, -15, 0) > 0                      # 看空共识→扣分但不为负
    assert f(60, 0, 0) == 60                                             # 无加分=因子分
    # 旧加性会扎堆：87.7/83.8/82.1 + 顶配加分都=100；新公式三者各不相同
    a, b, c = f(87.7, 9.8, 9), f(83.8, 9, 9), f(82.1, 8.9, 9)
    assert a != b != c and a < 100 and b < 100 and c < 100

    print("fusion engine self-check OK")
