"""统一数据访问层。聚合现有 storage 类，输出单股全维度 StockDataBundle。
能力层只依赖本层，不直接访问 Mongo。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re as _re


def _parse_pct(raw) -> Optional[float]:
    """解析百分比字符串为数值。"10.57%" → 10.57，纯数字原样返回。"""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s or s in ("-", "—", "--", "N/A", "False"):
        return None
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_amount_yuan(raw) -> Optional[float]:
    """将各种格式的金额字符串解析为以元为单位的浮点数。
    支持：数字、"6.43亿"→6.43e8、"2549万"→2549e4、"-6.43亿" 等。
    返回 None 表示无法解析。
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "—", "--"):
        return None
    try:
        # 匹配形如 "-6.43亿" 或 "25.49万"
        m = _re.match(r"^([+-]?\d+\.?\d*)(亿|万)?$", s)
        if m:
            num = float(m.group(1))
            unit = m.group(2)
            if unit == "亿":
                return num * 1e8
            if unit == "万":
                return num * 1e4
            return num
        return float(s)
    except (ValueError, TypeError):
        return None


@dataclass
class StockDataBundle:
    """单股全维度数据。closes/volumes 按时间倒序（[最新, ..., 最早]）。"""
    code: str
    name: str = ""
    closes: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    pe: Optional[float] = None        # TTM PE
    pb: Optional[float] = None        # 最新期末 PB
    ps: Optional[float] = None
    roe: Optional[float] = None       # 最新报告期 ROE（%）
    gross_margin: Optional[float] = None   # 毛利率（%），可能为 None
    debt_ratio: Optional[float] = None    # 资产负债率（%），可能为 None
    revenue_growth: Optional[float] = None  # 营收同比增速（%）
    profit_growth: Optional[float] = None   # 归母净利润同比增速（%）
    net_profit_ttm: Optional[float] = None  # 近四季归母净利润之和（元）
    main_net_inflow: Optional[float] = None   # 近5日平均主力净流入（元），用于评分
    realtime_price: Optional[float] = None   # 最新实时价格（优先于 closes[0]）
    turnover_rate: Optional[float] = None    # 近5日平均换手率（%）
    total_amount: Optional[float] = None     # 近5日平均总成交额（元）
    main_net_inflow_latest: Optional[float] = None  # 最新单日主力净流入（元），用于展示
    turnover_rate_latest: Optional[float] = None     # 最新单日换手率（%）
    total_amount_latest: Optional[float] = None      # 最新单日总成交额（元）
    fund_flow_date: str = ""                          # 最新资金流向日期
    industry: str = ""                       # 所属行业
    financial: Dict[str, Any] = field(default_factory=dict)
    news: List[Dict[str, Any]] = field(default_factory=list)
    dragon_tiger: List[Dict[str, Any]] = field(default_factory=list)
    margin: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FactorInputs:
    """选股打分所需的轻量数据。"""
    code: str
    name: str = ""
    closes: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    main_net_inflow: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    turnover_rate: Optional[float] = None
    total_amount: Optional[float] = None
    price: Optional[float] = None
    industry: str = ""


class StockDAL:
    """股票数据访问层。storage 依赖注入，便于测试。"""

    _TTM_NEG_CACHE: Dict[str, Any] = {}  # 类级 dict;CPython 下单键赋值原子,选股多线程并发写同一 key 最坏重复拉取一轮,可接受,勿加锁
    _TTM_NEG_TTL_HOURS = 2

    def __init__(
        self,
        kline_storage=None,
        info_storage=None,
        fund_flow_storage=None,
        news_storage=None,
        financial_storage=None,
        dragon_tiger_storage=None,
        margin_storage=None,
        valuation_storage=None,
    ):
        if kline_storage is None:
            from core.storage.mongo_storage import (
                KlineStorage, StockInfoStorage, FinancialStorage, NewsStorage,
                FundFlowStorage, DragonTigerStorage, MarginStorage, ValuationStorage,
            )
            kline_storage = KlineStorage()
            info_storage = StockInfoStorage()
            fund_flow_storage = FundFlowStorage()
            news_storage = NewsStorage()
            financial_storage = FinancialStorage()
            dragon_tiger_storage = DragonTigerStorage()
            margin_storage = MarginStorage()
            valuation_storage = ValuationStorage()
        self.kline_storage = kline_storage
        self.info_storage = info_storage
        self.fund_flow_storage = fund_flow_storage
        self.news_storage = news_storage
        self.financial_storage = financial_storage
        self.dragon_tiger_storage = dragon_tiger_storage
        self.margin_storage = margin_storage
        self.valuation_storage = valuation_storage

    @staticmethod
    def _fetch_realtime_price(code: str) -> Optional[float]:
        """调腾讯行情接口取当前价，失败静默返回 None（约 200ms，按需调用）。"""
        import re
        try:
            import requests as _req
            r = _req.get(
                f"https://qt.gtimg.cn/q={code.lower()}",
                proxies={"http": "", "https": ""},
                timeout=5,
            )
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if m:
                parts = m.group(1).split("~")
                if len(parts) > 3:
                    v = parts[3]
                    return float(v) if v else None
        except Exception:
            pass
        return None

    @staticmethod
    def _strip_market_prefix(code: str) -> str:
        """去除 SH/SZ 前缀，用于匹配不带前缀存储的集合（如 fund_flow）。"""
        return code[2:] if code[:2] in ("SH", "SZ") else code

    @staticmethod
    def _report_quarter(report_period: str) -> int:
        """解析报告期字符串，返回季度数（1/2/3/4），用于年化系数。"""
        s = str(report_period)
        if "一季" in s or s.endswith("-03-31") or s.endswith("0331"):
            return 1
        if "半年" in s or "中报" in s or s.endswith("-06-30") or s.endswith("0630"):
            return 2
        if "三季" in s or s.endswith("-09-30") or s.endswith("0930"):
            return 3
        return 4  # 年报 or 未知按全年处理

    @staticmethod
    def _compute_pe_pb(financial: Dict[str, Any], latest_close: Optional[float]):
        """从单条财报数据和最新收盘价估算 PE/PB（fallback）。

        TTM PE 首选 _fetch_ttm_valuation；此函数仅作最后兜底。
        年化方式：季报 EPS 按季度比例推算全年，非 TTM。
        """
        if not financial or not latest_close or latest_close <= 0:
            return None, None
        try:
            eps_str = (financial.get("基本每股收益") or financial.get("eps")
                       or financial.get("EPS") or financial.get("每股收益"))
            bps_str = (financial.get("每股净资产") or financial.get("bps")
                       or financial.get("BPS"))
            eps = float(eps_str) if eps_str is not None else None
            bps = float(bps_str) if bps_str is not None else None
            report_period = str(financial.get("报告期", "") or financial.get("report_date", ""))
            q = StockDAL._report_quarter(report_period)
            if eps and eps > 0 and q < 4:
                eps = eps * 4 / q  # 季报→年化
            pe = round(latest_close / eps, 2) if eps and eps > 0 else None
            pb = round(latest_close / bps, 2) if bps and bps > 0 else None
            return pe, pb
        except (ValueError, ZeroDivisionError, TypeError):
            return None, None

    def _get_cached_valuation(self, code: str) -> Dict[str, Optional[float]]:
        """从 stock_valuation 缓存读取 PE/PB/ROE/总市值。
        缓存由 ValuationCollector 每5分钟刷新，避免每次分析都调外部 API。
        """
        result: Dict[str, Any] = {
            "pe": None, "pb": None, "roe": None, "total_mv": None, "name": None,
        }
        try:
            if hasattr(self, "_val_cache"):
                cached = self._val_cache.get(code)
            elif self.valuation_storage is not None:
                cached = self.valuation_storage.get_by_code(code)
            else:
                return result
            if cached:
                result["name"] = cached.get("name")
                result["pe"] = cached.get("pe_dynamic")
                result["pb"] = cached.get("pb")
                result["roe"] = cached.get("roe")
                total_mv = cached.get("total_mv")
                if total_mv is not None:
                    result["total_mv"] = float(total_mv)
        except Exception:
            pass
        return result

    @staticmethod
    def _fetch_one_ttm_indicator(bare_code: str, field: str, ind: str) -> Optional[float]:
        """拉取单个百度估值指标，失败返回 None。"""
        try:
            import akshare as ak
            df = ak.stock_zh_valuation_baidu(symbol=bare_code, indicator=ind, period="近一年")
            if df is not None and not df.empty:
                val = df.iloc[-1].get("value")
                if val is not None:
                    return float(val)
        except Exception:
            pass
        return None

    @classmethod
    def _fetch_ttm_valuation(cls, bare_code: str, _fetch_one=None) -> Dict[str, Optional[float]]:
        """百度估值接口拉 TTM PE/PB/总市值。三指标并行；全部失败负缓存2小时。"""
        from datetime import timedelta
        from utils.helpers import beijing_now
        result: Dict[str, Optional[float]] = {"pe": None, "pb": None, "total_mv": None}

        failed_at = cls._TTM_NEG_CACHE.get(bare_code)
        if failed_at and beijing_now() - failed_at < timedelta(hours=cls._TTM_NEG_TTL_HOURS):
            return result

        fetch = _fetch_one or cls._fetch_one_ttm_indicator
        plan = [("pe", "市盈率(TTM)"), ("pb", "市净率"), ("total_mv_yi", "总市值")]
        from concurrent.futures import ThreadPoolExecutor, as_completed
        # 注意:不用 with(其 shutdown(wait=True) 会等挂死的 akshare 线程);
        # as_completed 整体限时 15s,超时的线程由 wait=False 放弃(线程泄漏可接受,akshare 请求最终会结束)
        ex = ThreadPoolExecutor(max_workers=3)
        futs = {ex.submit(fetch, bare_code, f, ind): f for f, ind in plan}
        try:
            for fut in as_completed(futs, timeout=15):
                field = futs[fut]
                try:
                    val = fut.result()
                except Exception:
                    val = None
                if val is None:
                    continue
                if field == "total_mv_yi":
                    result["total_mv"] = val * 1e8
                else:
                    result[field] = val
        except Exception:
            pass  # as_completed 整体超时:已收到的结果保留,未完成的放弃
        finally:
            ex.shutdown(wait=False)

        if all(v is None for v in result.values()):
            # 仅全部失败才负缓存;部分成功(如只有pe)下次仍整组重拉,属已知取舍
            cls._TTM_NEG_CACHE[bare_code] = beijing_now()
        return result

    @staticmethod
    def _compute_ttm_net_profit(financials: List[Dict[str, Any]]) -> Optional[float]:
        """从多条财报记录计算 TTM 归母净利润（元）。

        TTM = 最近年报净利润 + (最新中报/季报累计净利润 - 上年同期累计净利润)
        若只有年报数据，直接取最新年报。
        所有金额字段单位：元（AKShare 同花顺接口原始值）。
        """
        if not financials:
            return None

        def _get_profit(r: Dict) -> Optional[float]:
            v = (r.get("净利润") or r.get("net_profit") or
                 r.get("归属于上市公司股东的净利润") or r.get("净利润(元)"))
            return _parse_amount_yuan(v)

        def _report_date(r: Dict) -> str:
            d = r.get("report_date") or r.get("报告期") or ""
            return str(d)[:10]

        records = sorted(
            [r for r in financials if _get_profit(r) is not None],
            key=lambda r: _report_date(r),
            reverse=True,
        )
        if not records:
            return None

        latest = records[0]
        latest_date = _report_date(latest)
        latest_q = StockDAL._report_quarter(latest_date)

        if latest_q == 4:
            # 最新报告已是全年，直接用
            return _get_profit(latest)

        # 找上年同期
        latest_year = latest_date[:4]
        prev_year = str(int(latest_year) - 1)
        # 最近年报（上年末）
        annual_record = next(
            (r for r in records if _report_date(r).startswith(prev_year) and _report_date(r).endswith("-12-31")),
            None,
        )
        # 上年同期（同季度）
        same_q_suffix = latest_date[4:]  # 如 "-09-30"
        prev_same = next(
            (r for r in records if _report_date(r).startswith(prev_year) and _report_date(r).endswith(same_q_suffix)),
            None,
        )
        if annual_record and prev_same:
            annual_profit = _get_profit(annual_record)
            latest_ytd = _get_profit(latest)
            prev_ytd = _get_profit(prev_same)
            if annual_profit and latest_ytd and prev_ytd:
                return annual_profit + latest_ytd - prev_ytd

        # 兜底：最新报告年化
        p = _get_profit(latest)
        if p and latest_q:
            return p * 4 / latest_q
        return p

    @staticmethod
    def _compute_ttm_roe(financials: List[Dict[str, Any]]) -> Optional[float]:
        """用 TTM 净利润 / 最新期末净资产 计算年化 ROE（%）。
        季报 ROE 反映的是期间累计而非年化，直接用会低估全年盈利能力。
        """
        if not financials:
            return None
        ttm_profit = StockDAL._compute_ttm_net_profit(financials)
        if not ttm_profit:
            return None
        latest = financials[0]
        bps = latest.get("每股净资产") or latest.get("bps")
        if bps is None:
            return None
        try:
            bps_f = float(bps)
            if bps_f <= 0:
                return None
            # 近似总股本 = 净利润 / EPS
            eps_str = latest.get("基本每股收益") or latest.get("eps")
            np_str = latest.get("净利润")
            if eps_str and np_str:
                eps_f = float(eps_str)
                np_f = _parse_amount_yuan(np_str) or 0
                if eps_f > 0 and np_f > 0:
                    shares = np_f / eps_f
                    net_assets = bps_f * shares
                    return round(ttm_profit / net_assets * 100, 2)
            # 兜底：用最新季报 ROE 的报告期年化
            q = StockDAL._report_quarter(str(latest.get("report_date", "")))
            raw_roe = _parse_pct(latest.get("净资产收益率") or latest.get("roe"))
            if raw_roe is not None and q < 4:
                return round(raw_roe * 4 / q, 2)
            return raw_roe
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def _stable_growth(financials: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """优先取最近年报的增速；若最近年报距今>15个月则回退到最新季报。
        避免 Q1 单季同比波动过大误导评分。
        """
        result: Dict[str, Optional[float]] = {"revenue_growth": None, "profit_growth": None}
        if not financials:
            return result

        def _report_date(r: Dict) -> str:
            return str(r.get("report_date") or r.get("报告期") or "")[:10]

        latest_date = _report_date(financials[0])
        latest_q = StockDAL._report_quarter(latest_date)

        if latest_q == 4:
            # 最新就是年报，直接用
            result["revenue_growth"] = _parse_pct(
                financials[0].get("营业总收入同比增长率") or financials[0].get("revenue_growth"))
            result["profit_growth"] = _parse_pct(
                financials[0].get("净利润同比增长率") or financials[0].get("profit_growth"))
            return result

        # 找最近的年报
        for r in financials[1:]:
            if StockDAL._report_quarter(_report_date(r)) == 4:
                result["revenue_growth"] = _parse_pct(
                    r.get("营业总收入同比增长率") or r.get("revenue_growth"))
                result["profit_growth"] = _parse_pct(
                    r.get("净利润同比增长率") or r.get("profit_growth"))
                return result

        # 无年报可用，回退到最新季报
        result["revenue_growth"] = _parse_pct(
            financials[0].get("营业总收入同比增长率") or financials[0].get("revenue_growth"))
        result["profit_growth"] = _parse_pct(
            financials[0].get("净利润同比增长率") or financials[0].get("profit_growth"))
        return result

    def _get_fund_flow_avg(self, code: str, days: int = 5) -> Dict[str, Any]:
        """取近 N 日资金流向的均值（用于评分平滑）+ 最新单日数据（用于展示）。"""
        bare = self._strip_market_prefix(code)
        # FundFlowStorage.get_latest_flow 支持带/不带前缀，但 find_many 需要匹配实际存储
        # 构造候选 code 列表
        candidates = [bare]
        prefix = "SH" if bare.startswith(("6", "9")) else "SZ"
        candidates.append(f"{prefix}{bare}")
        if code != bare:
            candidates.append(code)

        records = self.fund_flow_storage.find_many(
            {"code": {"$in": candidates}},
            sort=[("date", -1)],
            limit=days,
        ) or []

        result: Dict[str, Any] = {
            "main_net_inflow": None, "turnover_rate": None, "total_amount": None,
            "main_net_inflow_latest": None, "turnover_rate_latest": None,
            "total_amount_latest": None, "fund_flow_date": "",
            "latest_record": {},
        }
        if not records:
            return result

        result["latest_record"] = records[0]
        result["fund_flow_date"] = str(records[0].get("date", ""))

        # 最新单日
        result["main_net_inflow_latest"] = _parse_amount_yuan(
            records[0].get("main_net_inflow") or records[0].get("净额"))
        result["turnover_rate_latest"] = _parse_pct(records[0].get("turnover_rate"))
        ta = records[0].get("total_amount")
        result["total_amount_latest"] = float(ta) if ta is not None else None

        # N 日均值
        inflows, trs, tas = [], [], []
        for r in records:
            v = _parse_amount_yuan(r.get("main_net_inflow") or r.get("净额"))
            if v is not None:
                inflows.append(v)
            tr = _parse_pct(r.get("turnover_rate"))
            if tr is not None:
                trs.append(tr)
            ta_v = r.get("total_amount")
            if ta_v is not None:
                tas.append(float(ta_v))

        result["main_net_inflow"] = sum(inflows) / len(inflows) if inflows else None
        result["turnover_rate"] = sum(trs) / len(trs) if trs else None
        result["total_amount"] = sum(tas) / len(tas) if tas else None
        return result

    def get_stock_bundle(self, code: str, kline_limit: int = 60, news_limit: int = 10) -> StockDataBundle:
        klines = self.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=kline_limit
        ) or []
        closes = [float(k.get("close", 0)) for k in klines]
        # kline 集合存 amount（成交额，万元）而非 volume，用作量能代理
        volumes = [float(k.get("volume") or k.get("amount") or 0) for k in klines]

        info = self.info_storage.get_by_code(code) or {}
        bare = self._strip_market_prefix(code)
        # 资金面：取近5日均值用于评分 + 最新单日用于展示
        ff_avg = self._get_fund_flow_avg(code, days=5)
        fund = ff_avg["latest_record"]
        news = self.news_storage.get_latest_news(code=code, limit=news_limit) or []
        # 取最近 8 条财报（覆盖 2 年×4个季度），用于 TTM 计算
        financials = self.financial_storage.find_many(
            {"code": code}, sort=[("report_date", -1)], limit=8
        ) or []
        financial = financials[0] if financials else {}
        dragon = self.dragon_tiger_storage.find_many({"code": code}, limit=10) or []
        margin = self.margin_storage.find_many({"code": code}, sort=[("date", -1)], limit=10) or []

        name = (info.get("name") or info.get("A股简称") or info.get("公司名称") or "")
        ps = info.get("ps")

        industry = info.get("所属行业", "")

        # 实时价优先级：估值缓存 > 腾讯行情 > fund_flow.price > kline 最新收盘
        _val_price = None
        try:
            _val_doc = self.valuation_storage.get_by_code(code) if self.valuation_storage else None
            if _val_doc and _val_doc.get("price") is not None:
                _val_price = float(_val_doc["price"])
        except Exception:
            pass
        _ff_price = (
            fund.get("price")
            or fund.get("最新价")
            or fund.get("当前价")
            or fund.get("成交价格")
        )
        realtime_price = (
            _val_price
            or self._fetch_realtime_price(code)
            or (float(_ff_price) if _ff_price is not None else None)
            or (closes[0] if closes else None)
        )
        # 若实时价比 kline 最新收盘更新，注入 closes 首位使技术分析反映当天行情
        if realtime_price and closes and abs(realtime_price - closes[0]) > 0.001:
            closes = [realtime_price] + closes
            volumes = [volumes[0] if volumes else 0] + volumes  # 复用最近量

        # ── PE/PB/ROE：优先读 DB 缓存 → 百度 API → 财报推算 ──
        cached_val = self._get_cached_valuation(code)
        pe = cached_val.get("pe")
        pb = cached_val.get("pb")
        cached_roe = cached_val.get("roe")

        if pe is None or pb is None:
            ttm_val = self._fetch_ttm_valuation(bare)
            if pe is None:
                pe = ttm_val.get("pe")
            if pb is None:
                pb = ttm_val.get("pb")

        if pe is None or pb is None:
            fallback_pe, fallback_pb = self._compute_pe_pb(
                financial, realtime_price or (closes[0] if closes else None)
            )
            if pe is None:
                pe = fallback_pe
            if pb is None:
                pb = fallback_pb

        # ── TTM 净利润（用于估值分位计算备用） ──
        net_profit_ttm = self._compute_ttm_net_profit(financials)

        # ── 从最新财报提取基本面维度 ──
        roe = cached_roe or self._compute_ttm_roe(financials) or _parse_pct(
            financial.get("净资产收益率") or financial.get("roe"))
        gross_margin = _parse_pct(financial.get("销售毛利率") or financial.get("gross_margin"))
        debt_ratio = _parse_pct(financial.get("资产负债率") or financial.get("debt_ratio"))
        growth = self._stable_growth(financials)
        revenue_growth = growth["revenue_growth"]
        profit_growth = growth["profit_growth"]

        # 资金面：5日均值用于评分，最新单日用于展示
        main_net_inflow = ff_avg["main_net_inflow"]
        turnover_rate = ff_avg["turnover_rate"]
        total_amount = ff_avg["total_amount"]

        return StockDataBundle(
            code=code,
            name=name,
            closes=closes,
            volumes=volumes,
            pe=pe,
            pb=pb,
            ps=float(ps) if ps is not None else None,
            roe=roe,
            gross_margin=gross_margin,
            debt_ratio=debt_ratio,
            revenue_growth=revenue_growth,
            profit_growth=profit_growth,
            net_profit_ttm=net_profit_ttm,
            main_net_inflow=main_net_inflow,
            realtime_price=realtime_price,
            turnover_rate=turnover_rate,
            total_amount=total_amount,
            main_net_inflow_latest=ff_avg["main_net_inflow_latest"],
            turnover_rate_latest=ff_avg["turnover_rate_latest"],
            total_amount_latest=ff_avg["total_amount_latest"],
            fund_flow_date=ff_avg["fund_flow_date"],
            industry=industry,
            financial=financial,
            news=news,
            dragon_tiger=dragon,
            margin=margin,
        )

    def list_universe(self) -> List[str]:
        """全市场可交易代码（kline 集合 distinct code）。"""
        codes = self.kline_storage.distinct("code") or []
        return [c for c in codes if c]

    def preload_screen_cache(self, codes: List[str]) -> None:
        """批量预加载初筛所需数据到内存缓存，避免逐只查DB。"""
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()

        # 五张表互不依赖，并行批量拉取（pymongo 连接池线程安全）
        from concurrent.futures import ThreadPoolExecutor
        loaders = (self._preload_financial, self._preload_fund_flow,
                   self._preload_info, self._preload_valuation,
                   self._preload_kline)
        with ThreadPoolExecutor(max_workers=len(loaders)) as ex:
            futures = [ex.submit(fn, db) for fn in loaders]
            for f in futures:
                f.result()  # 任一表加载失败直接冒泡，避免半套缓存

    def _preload_financial(self, db) -> None:
        # 批量加载最新一期财报（按 code 分组取 report_date 最大的）
        pipeline = [
            {"$sort": {"report_date": -1}},
            {"$group": {"_id": "$code", "doc": {"$first": "$$ROOT"}}},
        ]
        self._fin_cache: Dict[str, Dict] = {}
        for rec in db["financial"].aggregate(pipeline, allowDiskUse=True):
            self._fin_cache[rec["_id"]] = rec["doc"]

    def _preload_fund_flow(self, db) -> None:
        # 批量加载 fund_flow（取最近5个交易日，按 code 聚合均值）
        recent_dates = db["fund_flow"].distinct("date")
        recent_dates = sorted(recent_dates, reverse=True)[:5]
        self._ff_cache: Dict[str, Dict] = {}
        if recent_dates:
            raw_records: Dict[str, list] = {}
            for rec in db["fund_flow"].find({"date": {"$in": recent_dates}}):
                c = rec.get("code", "")
                if c:
                    raw_records.setdefault(c, []).append(rec)
            for c, recs in raw_records.items():
                inflows, trs, tas = [], [], []
                for r in recs:
                    v = _parse_amount_yuan(r.get("main_net_inflow") or r.get("净额"))
                    if v is not None:
                        inflows.append(v)
                    tr = _parse_pct(r.get("turnover_rate"))
                    if tr is not None:
                        trs.append(tr)
                    ta = r.get("total_amount")
                    if ta is not None:
                        tas.append(float(ta))
                latest = max(recs, key=lambda r: r.get("date", ""))
                avg_rec = dict(latest)
                if inflows:
                    avg_rec["main_net_inflow"] = sum(inflows) / len(inflows)
                if trs:
                    avg_rec["turnover_rate"] = sum(trs) / len(trs)
                if tas:
                    avg_rec["total_amount"] = sum(tas) / len(tas)
                self._ff_cache[c] = avg_rec

    def _preload_info(self, db) -> None:
        # 批量加载 stock_info
        self._info_cache: Dict[str, Dict] = {}
        for rec in db["stock_info"].find({}, {"_id": 0}):
            c = rec.get("code", "")
            if c:
                self._info_cache[c] = rec

    def _preload_valuation(self, db) -> None:
        # 批量加载估值缓存，避免初筛阶段逐只远程查询 stock_valuation
        self._val_cache: Dict[str, Dict] = {}
        for rec in db["stock_valuation"].find({}, {"_id": 0}):
            c = rec.get("code", "")
            if c:
                self._val_cache[c] = rec

    def _preload_kline(self, db) -> None:
        # 批量加载 K 线：取最近 90 个交易日窗口一次拉取（初筛最多用 60 条）。
        # 停牌超过窗口的股票会因 K 线不足被硬过滤剔除——本就不应入选。
        self._kline_cache: Dict[str, Dict[str, List[float]]] = {}
        kline_dates = sorted(db["kline"].distinct("date"), reverse=True)[:90]
        if kline_dates:
            cutoff = kline_dates[-1]
            grouped: Dict[str, List[tuple]] = {}
            cursor = db["kline"].find(
                {"date": {"$gte": cutoff}},
                {"_id": 0, "code": 1, "date": 1, "close": 1, "volume": 1, "amount": 1},
            )
            for rec in cursor:
                c = rec.get("code")
                if not c:
                    continue
                grouped.setdefault(c, []).append((
                    rec.get("date"),
                    float(rec.get("close", 0)),
                    float(rec.get("volume") or rec.get("amount") or 0),
                ))
            for c, rows in grouped.items():
                rows.sort(key=lambda r: r[0], reverse=True)
                self._kline_cache[c] = {
                    "closes": [r[1] for r in rows],
                    "volumes": [r[2] for r in rows],
                }

    def get_factor_inputs(self, code: str, kline_limit: int = 30) -> FactorInputs:
        """轻量取数：仅打分必需字段。有预加载缓存时走缓存。"""
        if hasattr(self, '_kline_cache'):
            kl = self._kline_cache.get(code) or {"closes": [], "volumes": []}
            closes = kl["closes"][:kline_limit]
            volumes = kl["volumes"][:kline_limit]
        else:
            klines = self.kline_storage.find_many(
                {"code": code}, sort=[("date", -1)], limit=kline_limit
            ) or []
            closes = [float(k.get("close", 0)) for k in klines]
            volumes = [float(k.get("volume") or k.get("amount") or 0) for k in klines]

        # 走缓存或单次查询
        if hasattr(self, '_info_cache'):
            info = self._info_cache.get(code, {})
        else:
            info = self.info_storage.get_by_code(code) or {}

        if hasattr(self, '_ff_cache'):
            fund = self._ff_cache.get(code, {})
        else:
            bare = self._strip_market_prefix(code)
            fund = self.fund_flow_storage.get_latest_flow(bare) or {}

        if hasattr(self, '_fin_cache'):
            financial = self._fin_cache.get(code, {})
        else:
            financial = self.financial_storage.find_one(
                {"code": code}, sort=[("report_date", -1)]
            ) or {}

        # PE/PB/ROE: 优先读 DB 缓存，回退到财报推算
        cached_val = self._get_cached_valuation(code)
        pe: Optional[float] = cached_val.get("pe")
        pb: Optional[float] = cached_val.get("pb")
        roe: Optional[float] = cached_val.get("roe")

        # name 优先取估值缓存（5分钟刷新，带最新 ST/退市标记），用于硬过滤
        name = (cached_val.get("name") or fund.get("name")
                or info.get("name") or info.get("A股简称") or "")

        price = fund.get("price")
        if price is not None:
            price = float(price)

        if pe is None or pb is None:
            eps_val = _parse_pct(financial.get("基本每股收益"))
            bps_val = _parse_pct(financial.get("每股净资产"))
            latest_close = price or (closes[0] if closes else None)
            if pe is None and latest_close and eps_val and eps_val > 0:
                pe = round(latest_close / eps_val, 2)
            if pb is None and latest_close and bps_val and bps_val > 0:
                pb = round(latest_close / bps_val, 2)

        main_net_inflow = _parse_amount_yuan(fund.get("main_net_inflow") or fund.get("净额"))
        turnover_rate = _parse_pct(fund.get("turnover_rate"))
        total_amount = fund.get("total_amount")
        if total_amount is not None:
            total_amount = float(total_amount)

        rd = str(financial.get("report_date") or financial.get("报告期") or "")
        q = self._report_quarter(rd)
        if roe is None:
            roe = _parse_pct(financial.get("净资产收益率") or financial.get("roe"))
            if roe is not None and q < 4:
                roe = round(roe * 4 / q, 2)

        # 增速: 初筛阶段只有单条缓存，无法取年报。
        # 对 Q1 数据做保守折算（Q1 同比波动大，打 6 折平滑）
        revenue_growth = _parse_pct(financial.get("营业总收入同比增长率") or financial.get("revenue_growth"))
        profit_growth = _parse_pct(financial.get("净利润同比增长率") or financial.get("profit_growth"))
        if q == 1:
            if revenue_growth is not None:
                revenue_growth = round(revenue_growth * 0.6, 2)
            if profit_growth is not None:
                profit_growth = round(profit_growth * 0.6, 2)

        return FactorInputs(
            code=code,
            name=name,
            closes=closes,
            volumes=volumes,
            pe=pe,
            pb=pb,
            ps=info.get("ps"),
            main_net_inflow=main_net_inflow,
            roe=roe,
            gross_margin=_parse_pct(financial.get("销售毛利率")),
            debt_ratio=_parse_pct(financial.get("资产负债率")),
            revenue_growth=revenue_growth,
            profit_growth=profit_growth,
            turnover_rate=turnover_rate,
            total_amount=total_amount,
            price=price,
            industry=info.get("所属行业", ""),
        )
