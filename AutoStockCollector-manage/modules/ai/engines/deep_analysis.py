"""个股深度分析服务：一次性聚合所有维度数据 + 量化评分 + AI报告。"""
from typing import Any, Dict, List, Optional

from modules.ai.foundation import factors
from modules.ai.foundation.dal import StockDAL, _parse_pct, _parse_amount_yuan
from modules.ai.content_risk import sanitize_text
from utils.logger import get_logger

logger = get_logger(__name__)


def _safe_round(v, n=2):
    if v is None:
        return None
    try:
        return round(float(v), n)
    except (ValueError, TypeError):
        return None


class DeepAnalysisService:
    def __init__(self, dal=None, router=None):
        if dal is None:
            dal = StockDAL()
        self.dal = dal
        self._router = router

    @property
    def router(self):
        if self._router is None:
            from modules.ai.foundation.llm_router import LLMRouter
            self._router = LLMRouter()
        return self._router

    def get_full_data(self, code: str, user_id: str = "default") -> Dict[str, Any]:
        """一次性返回该股票所有分析所需数据。"""
        bundle = self.dal.get_stock_bundle(code, kline_limit=120)

        basic_info = self._build_basic_info(code, bundle)
        kline_data = self._build_kline(code)
        price_info = self._build_price_info(bundle, kline_data, code)
        financial = self._build_financial(code, bundle)
        fund_flow = self._build_fund_flow(code, bundle)
        technical = self._build_technical(bundle)
        scores = self._build_scores(bundle)
        news = self._build_news(bundle)
        reflection = self._build_reflection(code)
        analysis_history = self._build_analysis_history(code, user_id)

        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        beijing = _tz(_td(hours=8))
        return {
            "basic_info": basic_info,
            "price_info": price_info,
            "kline": kline_data[:60],
            "financial": financial,
            "fund_flow": fund_flow,
            "technical": technical,
            "scores": scores,
            "news": news,
            "dragon_margin": self._build_dragon_margin(bundle),
            "data_freshness": self._build_freshness(kline_data, financial, fund_flow),
            "reflection": reflection,
            "analysis_history": analysis_history,
            "analysis_time": _dt.now(beijing).strftime("%Y-%m-%d %H:%M"),

        }

    def ai_report(self, code: str, data: Optional[Dict] = None,
                  user_id: str = "default") -> Dict[str, Any]:
        """基于真实数据生成AI深度分析报告。data为get_full_data返回值，不传则重新获取。"""
        if data is None:
            data = self.get_full_data(code, user_id=user_id)

        prompt = self._build_ai_prompt(data, user_id=user_id)
        system = (
            "你是一位专业的A股投资分析师，擅长从量化数据中提炼投资洞察。"
            "分析时必须基于提供的真实数据，不允许编造数据或假设数据。"
            "语言简洁专业，每个判断必须有数据依据。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        result = self.router.chat(
            prompt,
            schema=None,
            use_cache=True,
            task_type="deep_analysis",
            temperature=0.4,
            max_tokens=4000,
            messages=messages,
        )
        if result.success and result.raw:
            content, _ = sanitize_text(result.raw)
            if len(self._missing_dims(data.get("scores") or {})) >= 2:
                content = "> ⚠️ 本报告生成时部分维度数据缺失,结论仅供参考\n\n" + content
            # 缓存命中也同步决策记录(同日 upsert 幂等),保证展示报告与落库评级一致;
            # 但分析历史记忆只在新生成时写,避免重复刷记录
            self._record_outcome(code, content, user_id,
                                 decision_only=result.from_cache)
            return {
                "success": True,
                "content": content,
                "provider": result.provider,
                "from_cache": result.from_cache,

            }
        return {
            "success": False,
            "error": result.error or "所有AI服务暂不可用",

        }

    def ai_report_stream(self, code: str, user_id: str = "default"):
        """流式生成报告。yield 文本块;结束后做风控清洗与决策落库。"""
        data = self.get_full_data(code, user_id=user_id)
        prompt = self._build_ai_prompt(data, user_id=user_id)
        system = (
            "你是一位专业的A股投资分析师，擅长从量化数据中提炼投资洞察。"
            "分析时必须基于提供的真实数据，不允许编造数据或假设数据。"
            "语言简洁专业，每个判断必须有数据依据。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        full = ""
        for chunk in self.router.chat_stream(prompt, task_type="deep_analysis",
                                             messages=messages):
            full += chunk
            yield chunk
        if full:
            content, _ = sanitize_text(full)
            if len(self._missing_dims(data.get("scores") or {})) >= 2:
                content = "> ⚠️ 本报告生成时部分维度数据缺失,结论仅供参考\n\n" + content
            self._record_outcome(code, content, user_id)

    # ==================== 反思与记忆融合 ====================

    RATING_SCORES = {
        "强烈关注": (80, 20),
        "适度关注": (65, 35),
        "中性观望": (50, 50),
        "谨慎回避": (30, 70),
    }

    _DIM_NAMES = {"fundamental": "基本面", "technical": "技术面",
                  "fund_flow": "资金面", "valuation": "估值面"}

    @classmethod
    def _missing_dims(cls, scores: Dict[str, Any]) -> List[str]:
        missing = []
        for dim, label in cls._DIM_NAMES.items():
            details = (scores.get(dim) or {}).get("details") or {}
            if details.get("data_available", True) is False:
                missing.append(label)
        return missing

    def _build_reflection(self, code: str) -> Dict[str, Any]:
        """补评估历史决策（事后用真实K线核对），返回复盘数据。"""
        try:
            from modules.ai.reflection.decision_logger import DecisionLogger
            from modules.ai.reflection.evaluator import ReflectionEvaluator

            records = DecisionLogger().get_history(code, limit=10)
            evaluator = ReflectionEvaluator()
            reflections = []
            for rec in records:
                if rec.get("evaluated") and rec.get("reflection"):
                    reflections.append(rec["reflection"])
                else:
                    r = evaluator.evaluate(rec)
                    if r:
                        reflections.append(r)

            correct = sum(1 for r in reflections if r.get("accuracy") == "correct")
            wrong = sum(1 for r in reflections if r.get("accuracy") == "wrong")
            return {
                "latest": reflections[0] if reflections else None,
                "history": reflections[:5],
                "stats": {
                    "total": len(reflections),
                    "correct": correct,
                    "wrong": wrong,
                    "partial": len(reflections) - correct - wrong,
                },
            }
        except Exception as e:
            logger.warning(f"Reflection build failed for {code}: {e}")
            return {"latest": None, "history": [], "stats": {"total": 0, "correct": 0, "wrong": 0, "partial": 0}}

    def _build_analysis_history(self, code: str, user_id: str) -> List[Dict[str, Any]]:
        """该股票的历史分析记录（来自记忆系统）。"""
        try:
            from modules.memory.episodic_memory import EpisodicMemory
            return EpisodicMemory().get_stock_analyses(user_id, code, limit=5)
        except Exception:
            return []

    def _get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            from modules.memory.episodic_memory import EpisodicMemory
            profile = EpisodicMemory().get_profile(user_id)
            return profile.to_dict() if profile else None
        except Exception:
            return None

    def _extract_rating(self, content: str) -> str:
        """优先解析末尾【评级】锚定行;失败降级全文最后出现的评级词。"""
        import re
        m = None
        for m in re.finditer(r"【评级】\s*(强烈关注|适度关注|中性观望|谨慎回避)", content):
            pass
        if m:
            return m.group(1)
        best, best_pos = "中性观望", -1
        for rating in self.RATING_SCORES:
            pos = content.rfind(rating)
            if pos > best_pos:
                best, best_pos = rating, pos
        return best

    def _record_outcome(self, code: str, content: str, user_id: str,
                        decision_only: bool = False):
        """报告生成后：落决策记录（供下次复盘）+ 写入分析历史记忆。

        decision_only=True（缓存命中场景）只 upsert 决策记录保持展示/落库一致，
        不重复写分析历史记忆。"""
        rating = self._extract_rating(content)
        bull, bear = self.RATING_SCORES[rating]
        try:
            import uuid
            from modules.ai.reflection.decision_logger import DecisionLogger
            DecisionLogger().log_decision(
                f"deep_{uuid.uuid4().hex[:12]}", code,
                {"decision": rating, "bull_score": bull, "bear_score": bear},
            )
        except Exception as e:
            logger.warning(f"Decision log failed for {code}: {e}")
        if decision_only:
            return
        try:
            from utils.helpers import beijing_now
            from modules.memory.episodic_memory import EpisodicMemory
            from modules.memory.models import AnalysisHistory
            EpisodicMemory().record_analysis(AnalysisHistory(
                user_id=user_id,
                code=code,
                analysis_date=beijing_now().strftime("%Y-%m-%d %H:%M"),
                analysis_type="deep_analysis",
                verdict=rating,
                recommendation=rating,
            ))
        except Exception as e:
            logger.warning(f"Analysis history record failed for {code}: {e}")

    def _build_basic_info(self, code: str, bundle) -> Dict[str, Any]:
        info = self.dal.info_storage.get_by_code(code) or {}
        bare = StockDAL._strip_market_prefix(code)
        cached_val = self.dal._get_cached_valuation(code)
        market_cap = cached_val.get("total_mv")
        if market_cap is None:
            ttm_val = StockDAL._fetch_ttm_valuation(bare)
            market_cap = ttm_val.get("total_mv")
        market_cap_yi = _safe_round(market_cap / 1e8, 2) if market_cap else None

        return {
            "code": code,
            "name": bundle.name,
            "industry": bundle.industry,
            "market_cap_yi": market_cap_yi,
            "list_date": info.get("上市日期") or info.get("list_date"),
        }

    def _build_price_info(self, bundle, kline_data: List[Dict], code: str = "") -> Dict[str, Any]:
        current = bundle.realtime_price or (bundle.closes[0] if bundle.closes else None)

        price_change_pct = None
        if len(kline_data) >= 2 and kline_data[-1].get("close") and kline_data[-2].get("close"):
            today = kline_data[-1]["close"]
            prev = kline_data[-2]["close"]
            if prev > 0:
                price_change_pct = _safe_round((today - prev) / prev * 100, 2)

        # 52周高低：取250条K线覆盖完整一年
        klines_52w = self.dal.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=250
        ) or []
        highs = [float(k["high"]) for k in klines_52w if k.get("high")]
        lows = [float(k["low"]) for k in klines_52w if k.get("low")]
        high_52w = _safe_round(max(highs)) if highs else None
        low_52w = _safe_round(min(lows)) if lows else None

        vols = bundle.volumes[1:] if getattr(bundle, "volume_proxy", False) else bundle.volumes
        vol_today = vols[0] if vols else 0
        vol_avg5 = (sum(vols[1:6]) / min(len(vols) - 1, 5)
                    if len(vols) > 1 else 0)
        volume_ratio = _safe_round(vol_today / vol_avg5, 2) if vol_avg5 > 0 else None

        return {
            "current_price": _safe_round(current),
            "price_change_pct": price_change_pct,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "volume_ratio": volume_ratio,
            "position_52w": (_safe_round((current - low_52w) / (high_52w - low_52w) * 100, 1)
                             if current and high_52w and low_52w and high_52w > low_52w
                             else None),
        }

    @staticmethod
    def _clean_date(raw_date) -> str:
        """将各种日期格式统一为 YYYY-MM-DD 字符串。"""
        if raw_date is None:
            return ""
        s = str(raw_date).strip()
        # ISO 格式 "2026-03-05T00:00:00..." → 取前10位
        if len(s) >= 10 and s[4] == '-':
            return s[:10]
        # 紧凑格式 "20260305" → 插入横线
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        return s[:10] if len(s) > 10 else s

    def _build_kline(self, code: str) -> List[Dict[str, Any]]:
        """返回最近60条K线原始数据，按日期正序（旧→新）。"""
        raw = self.dal.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=60
        ) or []
        result = []
        for k in reversed(raw):
            result.append({
                "date": self._clean_date(k.get("date", "")),
                "open": _safe_round(k.get("open")),
                "high": _safe_round(k.get("high")),
                "low": _safe_round(k.get("low")),
                "close": _safe_round(k.get("close")),
                "volume": _safe_round(k.get("volume") or k.get("amount"), 0),
            })
        return result

    def _build_financial(self, code: str, bundle) -> Dict[str, Any]:
        financials = bundle.financials or self.dal.financial_storage.find_many(
            {"code": code}, sort=[("report_date", -1)], limit=8) or []
        latest = financials[0] if financials else {}

        report_date = str(latest.get("report_date", "") or "")
        q = StockDAL._report_quarter(report_date)
        report_type_map = {1: "一季报", 2: "中报", 3: "三季报", 4: "年报"}
        report_type = report_type_map.get(q, "")

        revenue = _parse_amount_yuan(latest.get("营业总收入") or latest.get("revenue"))
        net_profit = _parse_amount_yuan(latest.get("净利润") or latest.get("net_profit"))
        eps_raw = latest.get("基本每股收益") or latest.get("eps")
        bps_raw = latest.get("每股净资产") or latest.get("bps")

        current_price = bundle.realtime_price or (bundle.closes[0] if bundle.closes else None)
        eps = _parse_pct(eps_raw)
        bps = _parse_pct(bps_raw)
        # 季报 EPS 需年化后再算 PE；优先使用 bundle.pe（来自百度 TTM 接口）
        if eps and eps > 0 and q < 4:
            eps_annualized = eps * 4 / q
        else:
            eps_annualized = eps
        pe = bundle.pe  # TTM PE 优先
        if pe is None and current_price and eps_annualized and eps_annualized > 0:
            pe = _safe_round(current_price / eps_annualized, 2)
        pb = bundle.pb  # 实时 PB 优先
        if pb is None and current_price and bps and bps > 0:
            pb = _safe_round(current_price / bps, 2)

        history = []
        seen_dates = set()
        for f in financials[:8]:
            rd = str(f.get("report_date", "") or "")[:10]
            if rd in seen_dates:
                continue
            seen_dates.add(rd)
            r_q = StockDAL._report_quarter(rd)
            rev = _parse_amount_yuan(f.get("营业总收入") or f.get("revenue"))
            np_ = _parse_amount_yuan(f.get("净利润") or f.get("net_profit"))
            roe_v = _parse_pct(f.get("净资产收益率") or f.get("roe"))
            if roe_v is not None and r_q < 4:
                roe_v = _safe_round(roe_v * 4 / r_q, 2)
            gm = _parse_pct(f.get("销售毛利率") or f.get("gross_margin"))
            history.append({
                "report_date": rd,
                "report_type": report_type_map.get(r_q, ""),
                "revenue_yi": _safe_round(rev / 1e8, 2) if rev else None,
                "net_profit_yi": _safe_round(np_ / 1e8, 2) if np_ else None,
                "roe": _safe_round(roe_v),
                "gross_margin": _safe_round(gm),
            })

        return {
            "report_date": report_date[:10] if report_date else None,
            "report_type": report_type,
            "roe": _safe_round(bundle.roe),
            "revenue_yi": _safe_round(revenue / 1e8, 2) if revenue else None,
            "revenue_growth": _safe_round(bundle.revenue_growth),
            "net_profit_yi": _safe_round(net_profit / 1e8, 2) if net_profit else None,
            "profit_growth": _safe_round(bundle.profit_growth),
            "gross_margin": _safe_round(bundle.gross_margin),
            "debt_ratio": _safe_round(bundle.debt_ratio),
            "eps": _safe_round(eps),
            "net_asset_ps": _safe_round(bps),
            "pe": _safe_round(pe if pe else bundle.pe),
            "pb": _safe_round(pb if pb else bundle.pb),
            "history": history[:6],
            "pe_basis": "TTM" if bundle.pe is not None else "估算(年化EPS)",
            "roe_annualized_note": "年化估算" if q and q < 4 else "",
        }

    def _build_fund_flow(self, code: str, bundle) -> Dict[str, Any]:
        # 最新单日数据用于展示
        latest_inflow = bundle.main_net_inflow_latest
        latest_ta = bundle.total_amount_latest
        # 5日均值数据用于评分
        avg_inflow = bundle.main_net_inflow
        return {
            "date": bundle.fund_flow_date,
            "main_net_inflow": _safe_round(latest_inflow, 0),
            "main_net_inflow_yi": _safe_round(latest_inflow / 1e8, 4) if latest_inflow else None,
            "inflow_ratio": (_safe_round(latest_inflow / latest_ta * 100, 2)
                             if latest_inflow and latest_ta and latest_ta > 0
                             else None),
            "turnover_rate": _safe_round(bundle.turnover_rate_latest),
            "total_amount": _safe_round(latest_ta, 0),
            "total_amount_yi": _safe_round(latest_ta / 1e8, 2) if latest_ta else None,
            "avg5_main_net_inflow_yi": _safe_round(avg_inflow / 1e8, 4) if avg_inflow else None,
            "avg5_turnover_rate": _safe_round(bundle.turnover_rate),
        }

    def _build_technical(self, bundle) -> Dict[str, Any]:
        closes_asc = list(reversed(bundle.closes))
        n = len(closes_asc)
        if n < 5:
            return {"data_available": False}

        cur = closes_asc[-1]
        ma5 = _safe_round(sum(closes_asc[-5:]) / 5)
        ma20 = _safe_round(sum(closes_asc[-20:]) / 20) if n >= 20 else None
        ma60 = _safe_round(sum(closes_asc[-60:]) / 60) if n >= 60 else None

        if ma60 and ma20 and cur > ma5 > ma20 > ma60:
            trend = "强多头排列"
        elif ma20 and cur > ma5 > ma20:
            trend = "多头排列"
        elif ma20 and cur > ma20:
            trend = "站上20日线"
        elif ma20 and cur < ma20:
            trend = "低于20日线"
        else:
            trend = "震荡"

        ema12 = factors._ema(closes_asc, 12)
        ema26 = factors._ema(closes_asc, 26)
        dif_line = [a - b for a, b in zip(ema12, ema26)]
        dea_line = factors._ema(dif_line, 9)
        macd_bar = [(d - e) * 2 for d, e in zip(dif_line, dea_line)]
        dif = dif_line[-1] if dif_line else 0
        dea = dea_line[-1] if dea_line else 0
        bar = macd_bar[-1] if macd_bar else 0
        prev_bar = macd_bar[-2] if len(macd_bar) >= 2 else 0

        if dif > dea and bar > 0 and bar > prev_bar:
            macd_signal = "金叉扩张"
        elif dif > dea and bar > 0:
            macd_signal = "金叉"
        elif dif > dea:
            macd_signal = "DIF>DEA"
        elif dif < dea and len(macd_bar) >= 2 and abs(bar) < abs(prev_bar):
            macd_signal = "空头收窄"
        else:
            macd_signal = "空头"

        rsi14 = factors._rsi(closes_asc, 14)
        lookback = min(20, n - 1)
        base = closes_asc[-(lookback + 1)]
        momentum_20d = _safe_round((cur - base) / base * 100, 2) if base > 0 else None

        return {
            "ma5": ma5,
            "ma20": ma20,
            "ma60": ma60,
            "macd_dif": _safe_round(dif, 4),
            "macd_dea": _safe_round(dea, 4),
            "macd_bar": _safe_round(bar, 4),
            "rsi14": _safe_round(rsi14),
            "momentum_20d": momentum_20d,
            "trend": trend,
            "macd_signal": macd_signal,
            "data_available": True,
        }

    def _build_scores(self, bundle) -> Dict[str, Any]:
        closes_asc = list(reversed(bundle.closes))
        amounts_asc = list(reversed(bundle.volumes))

        fund_s, fund_d = factors.fundamental_score(
            roe=bundle.roe, revenue_growth=bundle.revenue_growth,
            profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
            debt_ratio=bundle.debt_ratio, industry=bundle.industry,
        )
        tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
        flow_s, flow_d = factors.fund_flow_detail_score(
            main_net_inflow=bundle.main_net_inflow,
            total_amount=bundle.total_amount,
            turnover_rate=bundle.turnover_rate,
        )
        val_s, val_d = factors.valuation_detail_score(
            pe=bundle.pe, pb=bundle.pb, industry=bundle.industry,
        )

        dim_scores = {
            "fundamental": (fund_s, fund_d),
            "technical": (tech_s, tech_d),
            "fund_flow": (flow_s, flow_d),
            "valuation": (val_s, val_d),
        }
        comp, comp_details = factors.composite_score(dim_scores, factors.DEFAULT_WEIGHTS)

        return {
            "fundamental": {"score": _safe_round(fund_s), "details": fund_d},
            "technical": {"score": _safe_round(tech_s), "details": tech_d},
            "fund_flow": {"score": _safe_round(flow_s), "details": flow_d},
            "valuation": {"score": _safe_round(val_s), "details": val_d},
            "composite": _safe_round(comp),
        }

    def _build_news(self, bundle) -> List[Dict[str, Any]]:
        result = []
        for n in (bundle.news or [])[:10]:
            result.append({
                "title": n.get("title") or n.get("标题", ""),
                "publish_time": n.get("publish_date") or n.get("发布时间", ""),
                "source": n.get("source") or n.get("来源", ""),
                "content": (n.get("content") or n.get("正文", ""))[:200],
            })
        return result

    def _build_dragon_margin(self, bundle) -> Dict[str, Any]:
        """龙虎榜/两融摘要。字段名按集合实际存储多候选解析。"""
        out = {"dragon_count_30d": 0, "dragon_net_buy_yi": None,
               "margin_balance_yi": None, "margin_trend_pct": None}
        try:
            dragons = bundle.dragon_tiger or []
            out["dragon_count_30d"] = len(dragons)
            net = [
                _parse_amount_yuan(d.get("net_buy") or d.get("净买额") or d.get("龙虎榜净买额"))
                for d in dragons
            ]
            net = [v for v in net if v is not None]
            if net:
                out["dragon_net_buy_yi"] = _safe_round(sum(net) / 1e8, 2)
        except Exception:
            pass
        try:
            margins = bundle.margin or []
            bals = [
                _parse_amount_yuan(m.get("rzye") or m.get("融资余额") or m.get("margin_balance"))
                for m in margins
            ]
            bals = [v for v in bals if v is not None]
            if bals:
                out["margin_balance_yi"] = _safe_round(bals[0] / 1e8, 2)
                if len(bals) >= 2 and bals[-1]:
                    out["margin_trend_pct"] = _safe_round((bals[0] - bals[-1]) / bals[-1] * 100, 2)
        except Exception:
            pass
        return out

    @staticmethod
    def _build_freshness(kline_data, financial, fund_flow) -> Dict[str, Any]:
        from datetime import datetime, timedelta
        from utils.helpers import beijing_now
        kline_date = kline_data[-1]["date"] if kline_data else None
        stale = False
        if kline_date:
            try:
                gap = (beijing_now() - datetime.fromisoformat(kline_date)).days
                stale = gap > 5  # 日历日>5≈缺3个交易日以上
            except ValueError:
                stale = True
        return {
            "kline_date": kline_date,
            "report_date": financial.get("report_date"),
            "fund_flow_date": str(fund_flow.get("date") or "")[:10] or None,
            "kline_stale": stale,
        }

    def _build_context_sections(self, data: Dict, user_id: str) -> str:
        """构建用户画像/历史预测复盘/历史分析记录的 prompt 附加段落。"""
        sections = []

        profile = self._get_user_profile(user_id)
        if profile:
            risk_map = {"conservative": "保守型", "balanced": "平衡型", "aggressive": "激进型"}
            horizon_map = {"short": "短线（≤20天）", "medium": "中线（20-60天）", "long": "长线（>60天）"}
            industries = "、".join(profile.get("preferred_industries") or []) or "无特别偏好"
            sections.append(
                f"【用户画像】\n"
                f"风险偏好：{risk_map.get(profile.get('risk_level'), '平衡型')}\n"
                f"持仓周期偏好：{horizon_map.get(profile.get('holding_horizon'), '中线')}\n"
                f"偏好行业：{industries}"
            )

        reflection = (data.get("reflection") or {}).get("latest")
        if reflection:
            sections.append(
                f"【历史预测复盘】\n"
                f"上次分析时间：{reflection.get('decision_time', 'N/A')[:16]}\n"
                f"当时预测方向：{reflection.get('predicted_direction', 'N/A')}\n"
                f"当时价格：{reflection.get('decision_price', 'N/A')}元 → 当前价格：{reflection.get('current_price', 'N/A')}元\n"
                f"实现收益：{reflection.get('realized_return', 0):+.2f}%\n"
                f"判断结果：{reflection.get('summary', '')}"
            )

        history = data.get("analysis_history") or []
        if history:
            lines = [
                f"  - {h.get('analysis_date', '')} 结论：{h.get('verdict', '')}"
                for h in history[:5]
            ]
            sections.append("【近期分析记录】\n" + "\n".join(lines))

        return ("\n\n" + "\n\n".join(sections)) if sections else ""

    def _build_ai_prompt(self, data: Dict, user_id: str = "default") -> str:
        bi = data.get("basic_info", {})
        pi = data.get("price_info", {})
        fi = data.get("financial", {})
        ff = data.get("fund_flow", {})
        te = data.get("technical", {})
        sc = data.get("scores", {})
        context_sections = self._build_context_sections(data, user_id)

        def _v(val, suffix="", default="N/A"):
            if val is None:
                return default
            return f"{val}{suffix}"

        dm = data.get("dragon_margin", {})
        fresh = data.get("data_freshness", {})
        news_lines = "\n".join(
            f"- [{(n.get('publish_time') or '')[:10]}] {n.get('title', '')}"
            for n in (data.get("news") or [])[:10]) or "（近期无相关新闻）"
        hist_lines = "\n".join(
            f"| {h.get('report_date')} {h.get('report_type', '')} | {_v(h.get('revenue_yi'))} | "
            f"{_v(h.get('net_profit_yi'))} | {_v(h.get('roe'))} | {_v(h.get('gross_margin'))} |"
            for h in (fi.get("history") or [])[:6])
        stale_warn = ("\n⚠️ 注意:K线数据滞后(最新仅到{}),分析时必须明确提示数据滞后风险。"
                      .format(fresh.get("kline_date")) if fresh.get("kline_stale") else "")
        missing = self._missing_dims(sc)
        completeness_warn = (
            f"\n⚠️ 数据不足:{'、'.join(missing)}维度数据缺失,结论仅供参考,"
            "报告开头必须注明此局限。" if len(missing) >= 2 else "")

        return f"""请对以下股票进行深度分析:

【数据截止】K线:{_v(fresh.get('kline_date'))} | 财报:{_v(fresh.get('report_date'))}({_v(fi.get('report_type'))}) | 资金流:{_v(fresh.get('fund_flow_date'))}{stale_warn}{completeness_warn}

【基本信息】
股票:{bi.get('name', '')}（{bi.get('code', '')}）  行业:{bi.get('industry', 'N/A')}
当前价格:{_v(pi.get('current_price'), '元')}  市值:{_v(bi.get('market_cap_yi'), '亿元')}
52周区间:{_v(pi.get('low_52w'))}~{_v(pi.get('high_52w'))}元,52周位置:{_v(pi.get('position_52w'), '%')}(0%=年内最低,100%=年内最高)
量比:{_v(pi.get('volume_ratio'))}

【财务数据({_v(fi.get('report_date'))} {_v(fi.get('report_type'))})】
营收:{_v(fi.get('revenue_yi'), '亿元')},同比{_v(fi.get('revenue_growth'), '%')}
净利润:{_v(fi.get('net_profit_yi'), '亿元')},同比{_v(fi.get('profit_growth'), '%')}
毛利率:{_v(fi.get('gross_margin'), '%')}  ROE:{_v(fi.get('roe'), '%')}  资产负债率:{_v(fi.get('debt_ratio'), '%')}
PE:{_v(fi.get('pe'), '倍')}（口径:{_v(fi.get('pe_basis'), default='TTM')}）,PB:{_v(fi.get('pb'), '倍')}

【财务趋势(近{len(fi.get('history') or [])}期)】
| 报告期 | 营收(亿) | 净利润(亿) | ROE% | 毛利率% |
{hist_lines}

【技术面】
均线趋势:{_v(te.get('trend'))}  MACD:{_v(te.get('macd_signal'))}  RSI(14):{_v(te.get('rsi14'))}  20日动量:{_v(te.get('momentum_20d'), '%')}

【资金面】
主力净流入:{_v(ff.get('main_net_inflow_yi'), '亿元')}  主力占比:{_v(ff.get('inflow_ratio'), '%')}  换手率:{_v(ff.get('turnover_rate'), '%')}
龙虎榜:近期上榜{dm.get('dragon_count_30d', 0)}次(最多统计最近10条),净买入合计{_v(dm.get('dragon_net_buy_yi'), '亿元')}
融资融券:融资余额{_v(dm.get('margin_balance_yi'), '亿元')},区间变化{_v(dm.get('margin_trend_pct'), '%')}

【近期新闻】
{news_lines}

【量化评分(0-100分)】
基本面:{_v(sc.get('fundamental', {}).get('score'), '分')} 技术面:{_v(sc.get('technical', {}).get('score'), '分')} 资金面:{_v(sc.get('fund_flow', {}).get('score'), '分')} 估值面:{_v(sc.get('valuation', {}).get('score'), '分')} 综合:{_v(sc.get('composite'), '分')}{context_sections}

硬性要求:
- 只允许使用上面提供的数据,任何字段为 N/A 时不得臆测,该维度明确说"数据缺失"
- 如数据截止日期明显滞后,须在报告开头提示
- 如提供了【用户画像】,综合评级和操作建议需贴合该风险偏好与持仓周期
- 如提供了【历史预测复盘】,需在综合评级中用一句话回应上次预测的对错及本次修正
- 新闻仅作事件参考,不要把新闻标题当事实复述,需结合数据判断

请按以下格式输出分析报告:

## 公司基本面解读
（盈利能力、成长性、财务健康度,结合财务趋势表看变化方向）

## 技术面分析
（均线、MACD、RSI、动量、52周位置,判断趋势和支撑压力）

## 资金面解读
（主力净流入、换手率、龙虎榜、两融变化,判断主力意图）

## 估值分析
（PE/PB结合行业与52周位置,判断估值是否合理）

## 综合评级
1-2句话说明理由,然后最后单独一行严格输出:
【评级】强烈关注/适度关注/中性观望/谨慎回避（四选一）"""
