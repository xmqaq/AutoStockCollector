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
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
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
    def _compute_pe_pb(financial: Dict[str, Any], latest_close: Optional[float]):
        """从财报数据和最新收盘价估算 PE/PB。"""
        if not financial or not latest_close or latest_close <= 0:
            return None, None
        try:
            eps_str = financial.get("基本每股收益")
            bps_str = financial.get("每股净资产")
            eps = float(eps_str) if eps_str is not None else None
            bps = float(bps_str) if bps_str is not None else None
            # 季报需要年化：报告期含"一季"×4、"半年"×2、"三季"×4/3，年报直接用
            report_period = str(financial.get("报告期", "") or financial.get("report_date", ""))
            if eps and eps > 0:
                if "一季" in report_period:
                    eps *= 4
                elif "半年" in report_period or "-06-" in report_period:
                    eps *= 2
                elif "三季" in report_period or "-09-" in report_period:
                    eps = eps * 4 / 3
            pe = round(latest_close / eps, 2) if eps and eps > 0 else None
            pb = round(latest_close / bps, 2) if bps and bps > 0 else None
            return pe, pb
        except (ValueError, ZeroDivisionError, TypeError):
            return None, None

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
        financial = self.financial_storage.find_one(
            {"code": code}, sort=[("report_date", -1)]
        ) or {}
        dragon = self.dragon_tiger_storage.find_many({"code": code}, limit=10) or []
        margin = self.margin_storage.find_many({"code": code}, sort=[("date", -1)], limit=10) or []

        name = (info.get("name") or info.get("A股简称") or info.get("公司名称") or "")
        pe = info.get("pe") or info.get("市盈率") or info.get("PE")
        pb = info.get("pb") or info.get("市净率") or info.get("PB")
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
        # PE/PB 用实时价计算更准确
        if pe is None and pb is None and financial:
            pe, pb = self._compute_pe_pb(financial, realtime_price or (closes[0] if closes else None))
        else:
            pe = float(pe) if pe is not None else None
            pb = float(pb) if pb is not None else None

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
