"""
资金流向数据采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import akshare as ak
from .base import BaseCollector, ProgressTracker
from core.storage.mongo_storage import FundFlowStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class FundFlowCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = FundFlowStorage()

    @staticmethod
    def _bare_to_full_code(bare: str) -> str:
        """'600519' → 'SH600519', '000001' → 'SZ000001'"""
        bare = str(bare).strip().zfill(6)
        return f"SH{bare}" if bare.startswith("6") or bare.startswith("9") else f"SZ{bare}"

    def collect_individual_snapshot(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """用 stock_fund_flow_individual(symbol='即时') 采集全市场当日个股资金流向快照。
        返回约5000+条，每条含 code(SH/SZ格式)、date、流入资金、流出资金、净额、成交额。
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            df = ak.stock_fund_flow_individual(symbol="即时")
        except Exception as e:
            logger.error(f"stock_fund_flow_individual failed: {e}")
            return []

        if df is None or df.empty:
            logger.warning("stock_fund_flow_individual returned empty")
            return []

        df = df.copy()
        df["date"] = date
        df["_updated_at"] = datetime.now()

        if "股票代码" in df.columns:
            df["code"] = df["股票代码"].apply(self._bare_to_full_code)
        else:
            logger.error("stock_fund_flow_individual返回数据缺少'股票代码'列")
            return []

        # 将中文列名统一映射为英文字段名，与 workflow executor 期望一致
        col_map = {
            "净额":   "main_net_inflow",
            "流入资金": "main_inflow",
            "流出资金": "main_outflow",
            "成交额":  "total_amount",
            "最新价":  "price",
            "涨跌幅":  "change_pct",
            "换手率":  "turnover_rate",
            "股票简称": "name",
            "股票代码": "stock_code",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # 将中文数字字符串（如 "5426.29万", "-2760.14万", "1.36亿"）转换为 float（元）
        def _parse_cn_amount(v) -> float:
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).replace(",", "").strip()
            try:
                if s.endswith("亿"):
                    return float(s[:-1]) * 1e8
                if s.endswith("万"):
                    return float(s[:-1]) * 1e4
                if s.endswith("%"):
                    return float(s[:-1])
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        for col in ("main_net_inflow", "main_inflow", "main_outflow", "total_amount"):
            if col in df.columns:
                df[col] = df[col].apply(_parse_cn_amount)

        records = df.to_dict("records")
        if records:
            self.storage.save_fund_flow_batch(records)
            logger.info(f"fund_flow snapshot saved: {len(records)} records for {date}")
        return records

    def collect(
        self,
        codes: Optional[List[str]] = None,
        period: str = "daily",
        date: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """采集全市场个股资金流向快照（一次调用覆盖全市场）。"""
        return self.collect_individual_snapshot(date=date)

    def collect_single(
        self,
        code: str,
        period: str = "daily",
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """从全市场快照中过滤出单只股票的数据。"""
        snapshot = self.collect_individual_snapshot()
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        return [r for r in snapshot if str(r.get("股票代码", "")) == bare] or None

    def collect_money_flow(
        self,
        market: str = "all"
    ) -> pd.DataFrame:
        try:
            if market == "all":
                df = ak.stock_market_fund_flow()
            elif market == "sh":
                df = ak.stock_market_fund_flow_individual(indicator="sh")
            else:
                df = ak.stock_market_fund_flow_individual(indicator="sz")

            return df

        except Exception as e:
            logger.error(f"Failed to collect money flow: {e}")
            return pd.DataFrame()

    def collect_sector_flow(self) -> pd.DataFrame:
        # stock_fund_flow_industry: 行业资金流向（非东财），优先使用
        # stock_sector_fund_flow_rank: 东财板块排名，代理可能阻断
        for func_name, params in [
            ("stock_fund_flow_industry", {"symbol": "即时"}),
            ("stock_sector_fund_flow_rank", {"indicator": "今日", "sector_type": "行业资金流"}),
        ]:
            try:
                func = getattr(ak, func_name, None)
                if func is None:
                    continue
                df = func(**params)
                if df is not None and not df.empty:
                    logger.info(f"Collected {len(df)} sector records via {func_name}")
                    return df
            except Exception as e:
                logger.warning(f"Sector flow via {func_name} failed: {e}")

        logger.error("Failed to collect sector flow from all sources")
        return pd.DataFrame()


class DragonTigerCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import DragonTigerStorage
        self.storage = DragonTigerStorage()

    def collect(
        self,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # 标准化日期格式为 YYYYMMDD
        def _fmt(d: str) -> str:
            return d.replace("-", "") if d else d

        s = _fmt(start_date) or _fmt(date) or "20260101"
        e = _fmt(end_date) or _fmt(date) or datetime.now().strftime("%Y%m%d")

        try:
            df = ak.stock_lhb_detail_em(start_date=s, end_date=e)

            if df is None or df.empty:
                return []

            df["_updated_at"] = datetime.now()

            records = self.normalize_dataframe(df)
            if records:
                self.storage.save_dragon_tiger_batch(records)
            return records

        except Exception as e:
            logger.error(f"Failed to collect dragon tiger: {e}")
            return []

    def collect_specific_stocks(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        symbol = code[2:]

        try:
            df = ak.stock_lhb_statistic_sina(stock=symbol)

            if df is None or df.empty:
                return []

            df["code"] = code
            df["_updated_at"] = datetime.now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect dragon tiger for {code}: {e}")
            return []

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self.collect_specific_stocks(code, kwargs.get("start_date", ""), kwargs.get("end_date", ""))


class MarginCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import MarginStorage
        self.storage = MarginStorage()

    def collect(self, codes: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        return self.collect_detailed_margin(codes)

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self._collect_single_margin(code)

    def collect_margin_data(self, date: str) -> pd.DataFrame:
        try:
            df = ak.stock_margin_detail_sz(date=date)
            return df
        except Exception as e:
            logger.error(f"Failed to collect margin data: {e}")
            return pd.DataFrame()

    def collect_margin_summary(self, date: str) -> Optional[Dict[str, Any]]:
        try:
            df = ak.stock_margin(start_date=date, end_date=date)
            if df is None or df.empty:
                return None

            return {
                "date": date,
                "margin_balance": df.iloc[0].get("融资余额", 0),
                "margin_buy": df.iloc[0].get("融资买入额", 0),
                "margin_repay": df.iloc[0].get("融资偿还额", 0),
                "short_balance": df.iloc[0].get("融券余额", 0),
                "short_sell": df.iloc[0].get("融券卖出量", 0),
                "short_repay": df.iloc[0].get("融券偿还量", 0),
                "_updated_at": datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to collect margin summary: {e}")
            return None

    def _fetch_sse_margin(self, date: str) -> List[Dict[str, Any]]:
        """采集上交所单日融资融券明细（供并发调用）。date: YYYY-MM-DD 或 YYYYMMDD"""
        date_8 = date.replace("-", "")[:8]
        date_fmt = f"{date_8[:4]}-{date_8[4:6]}-{date_8[6:]}"
        try:
            df = ak.stock_margin_detail_sse(date=date_8)
            if df is not None and not df.empty:
                df = df.copy()
                df["market"] = "sh"
                df["date"] = date_fmt
                df["_updated_at"] = datetime.now()
                if "标的证券代码" in df.columns:
                    df["code"] = df["标的证券代码"].apply(
                        lambda c: f"SH{str(c).strip().zfill(6)}"
                    )
                logger.info(f"SSE margin {date_fmt}: {len(df)} records")
                return df.to_dict("records")
        except Exception as e:
            logger.warning(f"SSE margin {date_fmt} failed: {e}")
        return []

    def _fetch_szse_margin(self, date: str) -> List[Dict[str, Any]]:
        """采集深交所单日融资融券明细（供并发调用）。date: YYYY-MM-DD 或 YYYYMMDD"""
        date_8 = date.replace("-", "")[:8]
        date_fmt = f"{date_8[:4]}-{date_8[4:6]}-{date_8[6:]}"
        try:
            df = ak.stock_margin_detail_szse(date=date_8)
            if df is not None and not df.empty:
                df = df.copy()
                df["market"] = "sz"
                df["date"] = date_fmt
                df["_updated_at"] = datetime.now()
                if "证券代码" in df.columns:
                    df["code"] = df["证券代码"].apply(
                        lambda c: f"SZ{str(c).strip().zfill(6)}"
                    )
                logger.info(f"SZSE margin {date_fmt}: {len(df)} records")
                return df.to_dict("records")
        except Exception as e:
            logger.warning(f"SZSE margin {date_fmt} failed: {e}")
        return []

    def collect_daily_margin(self, date: str) -> List[Dict[str, Any]]:
        """采集指定日期沪深两市所有个股融资融券明细。date 格式: YYYY-MM-DD 或 YYYYMMDD"""
        return self._fetch_sse_margin(date) + self._fetch_szse_margin(date)

    def collect_detailed_margin(
        self,
        codes: Optional[List[str]] = None,
        start_date: str = "20260501",
        end_date: str = "20260527"
    ) -> List[Dict[str, Any]]:
        """按日期遍历，采集沪深两市个股融资融券明细（不再使用市场汇总接口）。"""
        import time
        from utils.helpers import get_trading_days

        start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}" if len(start_date) == 8 else start_date
        end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}" if len(end_date) == 8 else end_date

        trading_days = get_trading_days(start_fmt, end_fmt)
        all_records: List[Dict[str, Any]] = []

        for date in trading_days:
            day_records = self.collect_daily_margin(date)
            if day_records:
                all_records.extend(day_records)
            time.sleep(0.5)

        if all_records:
            logger.info(f"margin collect_detailed: {len(all_records)} records across {len(trading_days)} days")
        return all_records

    def _collect_single_margin(self, code: str) -> List[Dict[str, Any]]:
        symbol = code[2:]
        records = []

        try:
            df = ak.stock_margin_detail_sina(symbol=symbol)
            if df is not None and not df.empty:
                df["code"] = code
                df["_updated_at"] = datetime.now()
                records.extend(self.normalize_dataframe(df, code))
        except Exception as e:
            logger.warning(f"No margin data for {code}: {e}")

        try:
            df_sz = ak.stock_margin_detail_sz(protocol="margin_detail")
            if df_sz is not None and not df_sz.empty:
                code_data = df_sz[df_sz["股票代码"] == symbol]
                if not code_data.empty:
                    code_data = code_data.copy()
                    code_data["code"] = code
                    code_data["_updated_at"] = datetime.now()
                    records.extend(code_data.to_dict("records"))
        except Exception as e:
            logger.warning(f"No SZ margin data for {code}: {e}")

        return records

    def get_margin_ratios(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            klines = self._get_latest_price(code)
            margin_data = self.storage.find_one({"code": code}, sort=[("date", -1)])

            if not margin_data or not klines:
                return None

            market_cap = klines.get("close", 0) * klines.get("volume", 0)

            margin_balance = margin_data.get("margin_balance", 0)
            short_balance = margin_data.get("short_balance", 0)

            margin_ratio = (margin_balance / market_cap * 100) if market_cap > 0 else 0
            short_ratio = (short_balance / market_cap * 100) if market_cap > 0 else 0

            return {
                "code": code,
                "date": margin_data.get("date"),
                "margin_balance": margin_balance,
                "short_balance": short_balance,
                "margin_ratio": round(margin_ratio, 4),
                "short_ratio": round(short_ratio, 4),
                "total_margin": margin_balance + short_balance,
                "total_ratio": round(margin_ratio + short_ratio, 4)
            }
        except Exception as e:
            logger.error(f"Failed to calculate margin ratios: {e}")
            return None

    def _get_latest_price(self, code: str) -> Optional[Dict[str, Any]]:
        from core.storage.mongo_storage import KlineStorage
        storage = KlineStorage()
        return storage.find_one({"code": code}, sort=[("date", -1)])

    def analyze_margin_trend(self, code: str, days: int = 30) -> Dict[str, Any]:
        try:
            records = list(self.storage.find(
                {"code": code}
            ).sort("date", -1).limit(days))

            if len(records) < 5:
                return {"error": "Insufficient data"}

            margin_balances = [r.get("margin_balance", 0) for r in records]
            short_balances = [r.get("short_balance", 0) for r in records]

            margin_trend = "stable"
            if len(margin_balances) >= 2:
                recent_avg = sum(margin_balances[:5]) / min(5, len(margin_balances))
                older_avg = sum(margin_balances[5:10]) / min(5, len(margin_balances[5:]))
                if older_avg > 0:
                    margin_change = (recent_avg - older_avg) / older_avg * 100
                    if margin_change > 10:
                        margin_trend = "increasing"
                    elif margin_change < -10:
                        margin_trend = "decreasing"

            return {
                "code": code,
                "margin_trend": margin_trend,
                "latest_margin_balance": margin_balances[0] if margin_balances else 0,
                "latest_short_balance": short_balances[0] if short_balances else 0,
                "data_points": len(records)
            }
        except Exception as e:
            logger.error(f"Failed to analyze margin trend: {e}")
            return {"error": str(e)}


class BlockCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect_industry_block(self) -> pd.DataFrame:
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            logger.error(f"Failed to collect industry block: {e}")
            return pd.DataFrame()

    def collect_concept_block(self) -> pd.DataFrame:
        try:
            df = ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            logger.error(f"Failed to collect concept block: {e}")
            return pd.DataFrame()

    def collect_block_component(
        self,
        block_code: str,
        block_type: str = "industry"
    ) -> List[Dict[str, Any]]:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_cons_em(symbol=block_code)
            else:
                df = ak.stock_board_concept_cons_em(symbol=block_code)

            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                code = row.get("代码", "")
                if code.startswith("6"):
                    code = f"SH{code}"
                else:
                    code = f"SZ{code}"

                records.append({
                    "code": code,
                    "name": row.get("名称", ""),
                    "block_code": block_code,
                    "block_type": block_type,
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect block component: {e}")
            return []

    def collect_block_ranking(self, block_type: str = "industry") -> pd.DataFrame:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_rank_em()
            else:
                df = ak.stock_board_concept_rank_em()

            return df

        except Exception as e:
            logger.error(f"Failed to collect block ranking: {e}")
            return pd.DataFrame()