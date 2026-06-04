"""个股深度分析服务：一次性聚合所有维度数据 + 量化评分 + AI报告。"""
from typing import Any, Dict, List, Optional

from modules.ai.foundation import factors
from modules.ai.foundation.dal import StockDAL, _parse_pct, _parse_amount_yuan
from modules.ai.content_risk import sanitize_text, RISK_DISCLAIMER


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

    def get_full_data(self, code: str) -> Dict[str, Any]:
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

        return {
            "basic_info": basic_info,
            "price_info": price_info,
            "kline": kline_data[:60],
            "financial": financial,
            "fund_flow": fund_flow,
            "technical": technical,
            "scores": scores,
            "news": news,
            "disclaimer": RISK_DISCLAIMER,
        }

    def ai_report(self, code: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """基于真实数据生成AI深度分析报告。data为get_full_data返回值，不传则重新获取。"""
        if data is None:
            data = self.get_full_data(code)

        prompt = self._build_ai_prompt(data)
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
            return {
                "success": True,
                "content": content,
                "provider": result.provider,
                "from_cache": result.from_cache,
                "disclaimer": RISK_DISCLAIMER,
            }
        return {
            "success": False,
            "error": result.error or "所有AI服务暂不可用",
            "disclaimer": RISK_DISCLAIMER,
        }

    def _build_basic_info(self, code: str, bundle) -> Dict[str, Any]:
        info = self.dal.info_storage.get_by_code(code) or {}
        bare = StockDAL._strip_market_prefix(code)
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

        vol_today = bundle.volumes[0] if bundle.volumes else 0
        vol_avg5 = (sum(bundle.volumes[1:6]) / min(len(bundle.volumes) - 1, 5)
                    if len(bundle.volumes) > 1 else 0)
        volume_ratio = _safe_round(vol_today / vol_avg5, 2) if vol_avg5 > 0 else None

        return {
            "current_price": _safe_round(current),
            "price_change_pct": price_change_pct,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "volume_ratio": volume_ratio,
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
        financials = self.dal.financial_storage.find_many(
            {"code": code}, sort=[("report_date", -1)], limit=8
        ) or []
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
        }

    def _build_fund_flow(self, code: str, bundle) -> Dict[str, Any]:
        bare = StockDAL._strip_market_prefix(code)
        fund = self.dal.fund_flow_storage.get_latest_flow(bare) or {}
        return {
            "date": fund.get("date"),
            "main_net_inflow": _safe_round(bundle.main_net_inflow, 0),
            "main_net_inflow_yi": _safe_round(bundle.main_net_inflow / 1e8, 4) if bundle.main_net_inflow else None,
            "inflow_ratio": (_safe_round(bundle.main_net_inflow / bundle.total_amount * 100, 2)
                             if bundle.main_net_inflow and bundle.total_amount and bundle.total_amount > 0
                             else None),
            "turnover_rate": _safe_round(bundle.turnover_rate),
            "total_amount": _safe_round(bundle.total_amount, 0),
            "total_amount_yi": _safe_round(bundle.total_amount / 1e8, 2) if bundle.total_amount else None,
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

    def _build_ai_prompt(self, data: Dict) -> str:
        bi = data.get("basic_info", {})
        pi = data.get("price_info", {})
        fi = data.get("financial", {})
        ff = data.get("fund_flow", {})
        te = data.get("technical", {})
        sc = data.get("scores", {})

        def _v(val, suffix="", default="N/A"):
            if val is None:
                return default
            return f"{val}{suffix}"

        return f"""请对以下股票进行深度分析：

【基本信息】
股票：{bi.get('name', '')}（{bi.get('code', '')}）
行业：{bi.get('industry', 'N/A')}
当前价格：{_v(pi.get('current_price'), '元')}
市值：{_v(bi.get('market_cap_yi'), '亿元')}

【财务数据（{_v(fi.get('report_date'))} {_v(fi.get('report_type'))}）】
营收：{_v(fi.get('revenue_yi'), '亿元')}，同比{_v(fi.get('revenue_growth'), '%')}
净利润：{_v(fi.get('net_profit_yi'), '亿元')}，同比{_v(fi.get('profit_growth'), '%')}
毛利率：{_v(fi.get('gross_margin'), '%')}
ROE：{_v(fi.get('roe'), '%')}
资产负债率：{_v(fi.get('debt_ratio'), '%')}
PE(TTM)：{_v(fi.get('pe'), '倍')}，PB：{_v(fi.get('pb'), '倍')}

【技术面】
均线趋势：{_v(te.get('trend'))}
MACD信号：{_v(te.get('macd_signal'))}
RSI(14)：{_v(te.get('rsi14'))}
20日价格动量：{_v(te.get('momentum_20d'), '%')}

【资金面】
主力净流入：{_v(ff.get('main_net_inflow_yi'), '亿元')}
主力占比：{_v(ff.get('inflow_ratio'), '%')}
换手率：{_v(ff.get('turnover_rate'), '%')}

【量化评分（0-100分）】
基本面：{_v(sc.get('fundamental', {}).get('score'), '分')}
技术面：{_v(sc.get('technical', {}).get('score'), '分')}
资金面：{_v(sc.get('fund_flow', {}).get('score'), '分')}
估值面：{_v(sc.get('valuation', {}).get('score'), '分')}
综合：{_v(sc.get('composite'), '分')}

请按以下格式输出分析报告：

## 公司基本面解读
（基于财务数据，分析公司盈利能力、成长性、财务健康度）

## 技术面分析
（基于均线、MACD、RSI、动量，判断当前趋势和潜在支撑压力）

## 资金面解读
（基于主力净流入、换手率，判断主力意图）

## 估值分析
（基于PE/PB，结合行业特点判断估值是否合理）

## 风险提示
（列出2-3个主要风险点，要具体不要泛泛）

## 综合评级
给出：强烈关注/适度关注/中性观望/谨慎回避 四选一
并用1-2句话说明理由"""
