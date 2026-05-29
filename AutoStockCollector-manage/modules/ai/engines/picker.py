"""AI智能选股引擎。两阶段漏斗：
  stage-1 全市场因子初筛(无 LLM) → 候选池
  stage-2 候选池复用 AnalysisEngine 深研(LLM) → top_n
结果入 ai_pick_results 集合缓存。dal/analysis_engine/result_saver 注入便于测试。
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from modules.ai.foundation import factors
from modules.ai.content_risk import RISK_DISCLAIMER

# stage-1 因子权重（无 LLM，便宜）
_SCREEN_WEIGHTS = {"technical": 0.4, "fundamental": 0.3, "fund_flow": 0.3}


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

    def _screen_score(self, fi) -> float:
        scores = {
            "technical": factors.trend_score(fi.closes) * 0.7 + factors.volume_score(fi.volumes) * 0.3,
            "fundamental": factors.valuation_score(fi.pe, fi.pb, fi.ps),
            "fund_flow": factors.fund_flow_score(fi.main_net_inflow),
        }
        return factors.composite_score(scores, _SCREEN_WEIGHTS)

    def run(self, strategy: str = "default", top_n: int = 10, candidate_pool: int = 50, use_cache: bool = True) -> Dict[str, Any]:
        universe = self.dal.list_universe()
        if not universe:
            result = {"strategy": strategy, "picks": [], "timestamp": datetime.now().isoformat(), "disclaimer": RISK_DISCLAIMER}
            self.result_saver(dict(result))
            return result

        screened: List[tuple] = []
        for code in universe:
            try:
                fi = self.dal.get_factor_inputs(code)
                screened.append((code, self._screen_score(fi)))
            except Exception:
                continue
        screened.sort(key=lambda x: x[1], reverse=True)
        candidates = [c for c, _ in screened[:candidate_pool]]

        deep: List[Dict[str, Any]] = []
        for code in candidates:
            try:
                analysis = self.analysis_engine.analyze(code, use_cache=use_cache)
                deep.append({
                    "code": analysis.get("code", code),
                    "name": analysis.get("name", ""),
                    "composite": analysis.get("scores", {}).get("composite", 50.0),
                    "recommendation": (analysis.get("llm") or {}).get("recommendation", ""),
                    "source": analysis.get("source", "factor"),
                })
            except Exception:
                continue
        deep.sort(key=lambda x: x["composite"], reverse=True)
        picks = deep[:top_n]

        result = {
            "strategy": strategy,
            "picks": picks,
            "candidate_count": len(candidates),
            "universe_count": len(universe),
            "timestamp": datetime.now().isoformat(),
            "disclaimer": RISK_DISCLAIMER,
        }
        self.result_saver(dict(result))
        return result
