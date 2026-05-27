"""
板块数据采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import akshare as ak
from .base import BaseCollector
from utils.logger import get_logger


logger = get_logger(__name__)


class BlockCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import BlockStorage
        self.storage = BlockStorage()

    def collect(self, codes: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        all_records = []
        
        industry_records = self.collect_industry_blocks()
        if industry_records:
            all_records.extend(industry_records)
        
        concept_records = self.collect_concept_blocks()
        if concept_records:
            all_records.extend(concept_records)
        
        if all_records and self.storage:
            for record in all_records:
                self.storage.save_block(record)
        
        return all_records

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        try:
            detail = self.collect_block_detail(code)
            if detail:
                return [detail]
            return []
        except Exception as e:
            logger.error(f"Failed to collect block for {code}: {e}")
            return None

    def collect_all_blocks(self) -> List[Dict[str, Any]]:
        return self.collect()

    def _collect_industry_with_multi_source(self) -> List[Dict[str, Any]]:
        data_sources = [
            ("stock_board_industry_name_ths", {}),
            ("stock_board_industry_summary_ths", {}),
            ("stock_board_industry_name_em", {}),  # 东财兜底，优先级最低
        ]

        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for industry blocks")

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is not None and not df.empty:
                    records = []
                    for _, row in df.iterrows():
                        records.append({
                            "code": row.get("板块代码", ""),
                            "name": row.get("板块名称", ""),
                            "涨跌幅": row.get("涨跌幅", 0),
                            "总市值": row.get("总市值", 0),
                            "成交额": row.get("成交额", 0),
                            "block_type": "industry",
                            "_updated_at": datetime.now()
                        })
                    return records

            except Exception as e:
                logger.warning(f"{source_name} failed for industry: {e}")
                continue

        return []

    def _collect_concept_with_multi_source(self) -> List[Dict[str, Any]]:
        data_sources = [
            ("stock_board_concept_name_ths", {}),
            ("stock_board_concept_summary_ths", {}),
            ("stock_board_concept_name_em", {}),  # 东财兜底，优先级最低
        ]

        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for concept blocks")

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is not None and not df.empty:
                    records = []
                    for _, row in df.iterrows():
                        records.append({
                            "code": row.get("板块代码", ""),
                            "name": row.get("板块名称", ""),
                            "涨跌幅": row.get("涨跌幅", 0),
                            "总市值": row.get("总市值", 0),
                            "成交额": row.get("成交额", 0),
                            "block_type": "concept",
                            "_updated_at": datetime.now()
                        })
                    return records

            except Exception as e:
                logger.warning(f"{source_name} failed for concept: {e}")
                continue

        return []

    def collect_industry_blocks(self) -> List[Dict[str, Any]]:
        return self._collect_industry_with_multi_source()

    def collect_concept_blocks(self) -> List[Dict[str, Any]]:
        return self._collect_concept_with_multi_source()

    def collect_block_detail(
        self,
        block_code: str,
        block_type: str = "industry"
    ) -> Optional[Dict[str, Any]]:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_cons_em(symbol=block_code)
            else:
                df = ak.stock_board_concept_cons_em(symbol=block_code)

            if df is None or df.empty:
                return None

            return {
                "block_code": block_code,
                "block_type": block_type,
                "stocks": df.to_dict("records"),
                "_updated_at": datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to collect block detail: {e}")
            return None

    def collect_block_ranking(
        self,
        block_type: str = "industry",
        period: str = "即时"
    ) -> List[Dict[str, Any]]:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_rank_em(indicator=period)
            else:
                df = ak.stock_board_concept_rank_em(indicator=period)

            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append({
                    "排名": row.get("排名", 0),
                    "code": row.get("板块代码", ""),
                    "name": row.get("板块名称", ""),
                    "涨跌幅": row.get("涨跌幅", 0),
                    "总市值": row.get("总市值", 0),
                    "成交额": row.get("成交额", 0),
                    "block_type": block_type,
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect block ranking: {e}")
            return []

    def collect_hot_blocks(self) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_hot_rank_em()
            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append({
                    "rank": row.get("排名", 0),
                    "name": row.get("板块名称", ""),
                    "涨跌幅": row.get("涨跌幅", 0),
                    "hot_rank": row.get("当前排名", 0),
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect hot blocks: {e}")
            return []


class RankCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import DragonTigerStorage
        self.storage = DragonTigerStorage()

    def collect(self, codes: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        try:
            records = self.collect_daily_rank()
            if records and self.storage:
                for record in records:
                    self.storage.save_daily_rank(record)
            return records
        except Exception as e:
            logger.error(f"Failed to collect rank data: {e}")
            return []

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        try:
            records = self.collect_price_rank(datetime.now().strftime("%Y-%m-%d"))
            filtered = [r for r in records if r.get("code") == code]
            return filtered if filtered else None
        except Exception as e:
            logger.error(f"Failed to collect rank for {code}: {e}")
            return None

    def collect_daily_rank(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        data_sources = [
            ("stock_lhb_stock_statistic_em", {}),
            ("stock_zh_a_spot_em", {}),
        ]

        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for daily rank")

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is None or df.empty:
                    continue

                records = []
                for _, row in df.head(100).iterrows():
                    code = row.get("代码", "") or row.get("股票代码", "")
                    if code and code.startswith("6"):
                        code = f"SH{code}"
                    elif code:
                        code = f"SZ{code}"

                    record = {
                        "code": code,
                        "name": row.get("名称", "") or row.get("股票名称", ""),
                        "date": date,
                        "_updated_at": datetime.now()
                    }

                    if "涨跌幅" in row.index:
                        record["涨跌幅"] = row.get("涨跌幅", 0)
                    if "龙虎榜次数" in row.index:
                        record["龙虎榜次数"] = row.get("龙虎榜次数", 0)
                        record["成交额"] = row.get("成交额", 0)
                        record["买入席位"] = row.get("买方席位数", 0)
                        record["卖出席位"] = row.get("卖方席位数", 0)

                    records.append(record)

                return records

            except Exception as e:
                logger.warning(f"{source_name} failed for daily rank: {e}")
                continue

        logger.error("All daily rank sources failed")
        return []

    def collect_price_rank(self, date: str) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return []

            df = df.sort_values("涨跌幅", ascending=False)

            records = []
            for _, row in df.head(100).iterrows():
                code = row.get("代码", "")
                if code.startswith("6"):
                    code = f"SH{code}"
                else:
                    code = f"SZ{code}"

                records.append({
                    "code": code,
                    "name": row.get("名称", ""),
                    "price": row.get("最新价", 0),
                    "涨跌幅": row.get("涨跌幅", 0),
                    "涨速": row.get("涨速", 0),
                    "换手率": row.get("换手率", 0),
                    "成交额": row.get("成交额", 0),
                    "date": date,
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect price rank: {e}")
            return []

    def collect_turnover_rank(self, date: str) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_turnover_rate_em()
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
                    "换手率": row.get("换手率", 0),
                    "涨跌幅": row.get("涨跌幅", 0),
                    "date": date,
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect turnover rank: {e}")
            return []


class IPOCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect_ipo_list(self) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_ipo_summary_cninfo(symbol="IPO")
            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append({
                    "股票代码": row.get("股票代码", ""),
                    "股票名称": row.get("股票名称", ""),
                    "申购代码": row.get("申购代码", ""),
                    "发行价格": row.get("发行价格", 0),
                    "市盈率": row.get("发行市盈率", 0),
                    "申购日期": row.get("申购日期", ""),
                    "上市日期": row.get("上市日期", ""),
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect IPO list: {e}")
            return []

    def collect_new_stock(self) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_new_cninfo()
            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append({
                    "code": row.get("股票代码", ""),
                    "name": row.get("股票名称", ""),
                    "上市日期": row.get("上市日期", ""),
                    "发行价格": row.get("发行价格", 0),
                    "收盘价": row.get("收盘价", 0),
                    "最高价": row.get("最高价", 0),
                    "最低价": row.get("最低价", 0),
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect new stock: {e}")
            return []


class HolderCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect_top_holder(self, code: str) -> List[Dict[str, Any]]:
        symbol = code[2:]

        try:
            df = ak.stock_top10_holder_cninfo(symbol=symbol)
            if df is None or df.empty:
                return []

            df["code"] = code
            df["_updated_at"] = datetime.now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect top holder for {code}: {e}")
            return []

    def collect_float_holder(self, code: str) -> List[Dict[str, Any]]:
        symbol = code[2:]

        try:
            df = ak.stock_float_holder_cninfo(symbol=symbol)
            if df is None or df.empty:
                return []

            df["code"] = code
            df["_updated_at"] = datetime.now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect float holder for {code}: {e}")
            return []