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

    def get_stock_bundle(self, code: str, kline_limit: int = 60, news_limit: int = 10) -> StockDataBundle:
        klines = self.kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=kline_limit
        ) or []
        closes = [float(k.get("close", 0)) for k in klines]
        volumes = [float(k.get("volume", 0)) for k in klines]

        info = self.info_storage.get_by_code(code) or {}
        fund = self.fund_flow_storage.get_latest_flow(code) or {}
        news = self.news_storage.get_latest_news(code=code, limit=news_limit) or []
        financial = self.financial_storage.find_one(
            {"code": code}, sort=[("report_date", -1)]
        ) or {}
        dragon = self.dragon_tiger_storage.find_many({"code": code}, limit=10) or []
        margin = self.margin_storage.find_many({"code": code}, sort=[("date", -1)], limit=10) or []

        # stock_info 字段名按采集来源不同，可能是 name/A股简称/公司名称
        name = (info.get("name") or info.get("A股简称") or info.get("公司名称") or "")
        # PE/PB 在 stock_info 里可能缺失（百度估值接口按需拉，未持久化），
        # 也可能存为中文字段名，做一次兜底读取
        pe = info.get("pe") or info.get("市盈率") or info.get("PE")
        pb = info.get("pb") or info.get("市净率") or info.get("PB")
        ps = info.get("ps")

        return StockDataBundle(
            code=code,
            name=name,
            closes=closes,
            volumes=volumes,
            pe=float(pe) if pe is not None else None,
            pb=float(pb) if pb is not None else None,
            ps=float(ps) if ps is not None else None,
            main_net_inflow=fund.get("main_net_inflow"),
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
        volumes = [float(k.get("volume", 0)) for k in klines]
        info = self.info_storage.get_by_code(code) or {}
        fund = self.fund_flow_storage.get_latest_flow(code) or {}
        pe = info.get("pe") or info.get("市盈率") or info.get("PE")
        pb = info.get("pb") or info.get("市净率") or info.get("PB")
        return FactorInputs(
            code=code,
            closes=closes,
            volumes=volumes,
            pe=float(pe) if pe is not None else None,
            pb=float(pb) if pb is not None else None,
            ps=info.get("ps"),
            main_net_inflow=fund.get("main_net_inflow"),
        )
