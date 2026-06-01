"""统一数据访问层。聚合现有 storage 类，输出单股全维度 StockDataBundle。
能力层只依赖本层，不直接访问 Mongo。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    main_net_inflow: Optional[float] = None
    realtime_price: Optional[float] = None   # 最新实时价格（优先于 closes[0]）
    financial: Dict[str, Any] = field(default_factory=dict)
    news: List[Dict[str, Any]] = field(default_factory=list)
    dragon_tiger: List[Dict[str, Any]] = field(default_factory=list)
    margin: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FactorInputs:
    """选股打分所需的轻量数据（不含 news/龙虎/两融/财报）。"""
    code: str
    closes: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    main_net_inflow: Optional[float] = None


class StockDAL:
    """股票数据访问层。storage 依赖注入，便于测试。"""

    def __init__(
        self,
        kline_storage=None,
        info_storage=None,
        fund_flow_storage=None,
        news_storage=None,
        financial_storage=None,
        dragon_tiger_storage=None,
        margin_storage=None,
    ):
        if kline_storage is None:
            from core.storage.mongo_storage import (
                KlineStorage, StockInfoStorage, FinancialStorage, NewsStorage,
                FundFlowStorage, DragonTigerStorage, MarginStorage,
            )
            kline_storage = KlineStorage()
            info_storage = StockInfoStorage()
            fund_flow_storage = FundFlowStorage()
            news_storage = NewsStorage()
            financial_storage = FinancialStorage()
            dragon_tiger_storage = DragonTigerStorage()
            margin_storage = MarginStorage()
        self.kline_storage = kline_storage
        self.info_storage = info_storage
        self.fund_flow_storage = fund_flow_storage
        self.news_storage = news_storage
        self.financial_storage = financial_storage
        self.dragon_tiger_storage = dragon_tiger_storage
        self.margin_storage = margin_storage

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

    @staticmethod
    def _fetch_ttm_valuation(bare_code: str) -> Dict[str, Optional[float]]:
        """通过百度估值接口拉取 TTM PE / PB / 总市值。
        与路由层 _fetch_valuation 逻辑相同，让分析引擎也能用上实时估值。
        """
        result: Dict[str, Optional[float]] = {"pe": None, "pb": None, "total_mv": None}
        try:
            import akshare as ak
            for field, ind in [("pe", "市盈率(TTM)"), ("pb", "市净率"), ("total_mv_yi", "总市值")]:
                try:
                    df = ak.stock_zh_valuation_baidu(symbol=bare_code, indicator=ind, period="近一年")
                    if df is not None and not df.empty:
                        val = df.iloc[-1].get("value")
                        if val is not None:
                            if field == "total_mv_yi":
                                result["total_mv"] = float(val) * 1e8
                            else:
                                result[field] = float(val)
                except Exception:
                    continue
        except Exception:
            pass
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
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

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

    def get_stock_bundle(self, code: str, kline_limit: int = 60, news_limit: int = 10) -> StockDataBundle:
        klines = self.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=kline_limit
        ) or []
        closes = [float(k.get("close", 0)) for k in klines]
        # kline 集合存 amount（成交额，万元）而非 volume，用作量能代理
        volumes = [float(k.get("volume") or k.get("amount") or 0) for k in klines]

        info = self.info_storage.get_by_code(code) or {}
        # fund_flow 以裸代码（无 SH/SZ 前缀）存储
        bare = self._strip_market_prefix(code)
        fund = self.fund_flow_storage.get_latest_flow(bare) or {}
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

        # 实时价优先级：腾讯行情 > fund_flow 成交价 > kline 最新收盘
        realtime_price = (
            self._fetch_realtime_price(code)
            or (float(fund["成交价格"]) if fund.get("成交价格") else None)
            or (float(fund["当前价"]) if fund.get("当前价") else None)
            or (closes[0] if closes else None)
        )
        # 若实时价比 kline 最新收盘更新，注入 closes 首位使技术分析反映当天行情
        if realtime_price and closes and abs(realtime_price - closes[0]) > 0.001:
            closes = [realtime_price] + closes
            volumes = [volumes[0] if volumes else 0] + volumes  # 复用最近量

        # ── PE/PB：优先使用百度实时 TTM 估值，不可用时回退到财报推算 ──
        ttm_val = self._fetch_ttm_valuation(bare)
        pe = ttm_val.get("pe")
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
        def _fv(r: Dict, *keys) -> Optional[float]:
            for k in keys:
                v = r.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
            return None

        roe = _fv(financial, "roe", "ROE", "净资产收益率")
        gross_margin = _fv(financial, "gross_margin", "毛利率", "销售毛利率")
        debt_ratio = _fv(financial, "debt_ratio", "资产负债率", "负债率")

        # 营收/利润同比增速：若财报有两期则计算，否则取字段直接值
        revenue_growth: Optional[float] = _fv(financial, "revenue_growth", "营收增速", "营业收入增速")
        profit_growth: Optional[float] = _fv(financial, "profit_growth", "利润增速", "净利润增速")
        if revenue_growth is None and len(financials) >= 2:
            rev_now = _fv(financials[0], "营业收入", "revenue")
            rev_prev = _fv(financials[1], "营业收入", "revenue")
            if rev_now and rev_prev and rev_prev != 0:
                revenue_growth = round((rev_now - rev_prev) / abs(rev_prev) * 100, 2)
        if profit_growth is None and len(financials) >= 2:
            p_now = _fv(financials[0], "净利润", "net_profit")
            p_prev = _fv(financials[1], "净利润", "net_profit")
            if p_now and p_prev and p_prev != 0:
                profit_growth = round((p_now - p_prev) / abs(p_prev) * 100, 2)

        # 净额字段（万元）→ 元；fund_flow_score 以 1亿元为基准刻度
        raw_flow = fund.get("main_net_inflow") or fund.get("净额")
        main_net_inflow = float(raw_flow) * 10_000 if raw_flow is not None else None

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
            financial=financial,
            news=news,
            dragon_tiger=dragon,
            margin=margin,
        )

    def list_universe(self) -> List[str]:
        """全市场可交易代码（kline 集合 distinct code）。"""
        codes = self.kline_storage.distinct("code") or []
        return [c for c in codes if c]

    def get_factor_inputs(self, code: str, kline_limit: int = 30) -> FactorInputs:
        """轻量取数：仅打分必需字段。"""
        klines = self.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=kline_limit
        ) or []
        closes = [float(k.get("close", 0)) for k in klines]
        volumes = [float(k.get("volume") or k.get("amount") or 0) for k in klines]
        info = self.info_storage.get_by_code(code) or {}
        bare = self._strip_market_prefix(code)
        fund = self.fund_flow_storage.get_latest_flow(bare) or {}
        # stage-1 初筛不查 financial（5208 支逐一查太慢），PE/PB 缺失时估值因子取中性 50
        pe = info.get("pe") or info.get("市盈率") or info.get("PE")
        pb = info.get("pb") or info.get("市净率") or info.get("PB")
        pe = float(pe) if pe is not None else None
        pb = float(pb) if pb is not None else None
        raw_flow = fund.get("main_net_inflow") or fund.get("净额")
        main_net_inflow = float(raw_flow) * 10_000 if raw_flow is not None else None
        return FactorInputs(
            code=code,
            closes=closes,
            volumes=volumes,
            pe=pe,
            pb=pb,
            ps=info.get("ps"),
            main_net_inflow=main_net_inflow,
        )
