"""
估值指标采集器
通过东财 ulist.np 接口分批查询全市场 PE/PB/总市值等估值指标，
结合 financial 集合中最新财报计算 ROE，写入 stock_valuation 集合。
设计为 5 分钟轮询，盘中高频刷新，盘后/周末自动跳过。
全市场约 5000 只股票，分批查询耗时约 5 秒。
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.helpers import beijing_now
import requests
from core.storage.mongo_storage import ValuationStorage
from utils.logger import get_logger

logger = get_logger(__name__)

_EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_FIELDS = "f2,f3,f9,f12,f14,f20,f21,f23,f8,f10"
_BATCH_SIZE = 200


class ValuationCollector:
    def __init__(self):
        self.storage = ValuationStorage()
        self._session = requests.Session()
        self._session.trust_env = False

    def collect(self, codes: Optional[List[str]] = None) -> int:
        if not codes:
            codes = self._get_all_stock_codes()
        if not codes:
            return 0

        spot_records = self._fetch_valuation_all(codes)
        if not spot_records:
            return 0

        roe_map = self._compute_roe_from_financial(
            [r["code"] for r in spot_records]
        )
        for rec in spot_records:
            roe = roe_map.get(rec["code"])
            if roe is not None:
                rec["roe"] = roe

        self.storage.save_batch(spot_records)
        logger.info(f"Valuation cache updated: {len(spot_records)} stocks")
        return len(spot_records)

    def _get_all_stock_codes(self) -> List[str]:
        try:
            from core.storage.mongo_storage import StockInfoStorage
            docs = StockInfoStorage().collection.find({}, {"code": 1, "_id": 0})
            return [d["code"] for d in docs if d.get("code")]
        except Exception as e:
            logger.error(f"Failed to load stock codes from DB: {e}")
            return []

    def _fetch_valuation_all(self, codes: List[str]) -> List[Dict[str, Any]]:
        all_records: List[Dict[str, Any]] = []
        for i in range(0, len(codes), _BATCH_SIZE):
            batch = codes[i:i + _BATCH_SIZE]
            records = self._fetch_valuation_batch(batch)
            all_records.extend(records)
        return all_records

    def _fetch_valuation_batch(self, codes: List[str]) -> List[Dict[str, Any]]:
        secids = []
        for code in codes:
            bare = code[2:] if code[:2] in ("SH", "SZ") else code
            market = "1" if bare.startswith("6") else "0"
            secids.append(f"{market}.{bare}")

        try:
            resp = self._session.get(_EASTMONEY_URL, params={
                "fltt": 2,
                "fields": _FIELDS,
                "secids": ",".join(secids),
            }, timeout=15)
            data = resp.json()
        except Exception as e:
            logger.error(f"EastMoney valuation API failed: {e}")
            return []

        diff = (data.get("data") or {}).get("diff")
        if not diff:
            return []

        now = beijing_now()
        records = []
        for item in diff:
            bare = str(item.get("f12", ""))
            if not bare or len(bare) != 6:
                continue
            prefix = "SH" if bare.startswith("6") else "SZ"
            full_code = f"{prefix}{bare}"

            rec: Dict[str, Any] = {
                "code": full_code,
                "name": item.get("f14", ""),
                "updated_at": now,
            }
            field_map = {
                "f2": "price",
                "f3": "change_pct",
                "f9": "pe_dynamic",
                "f23": "pb",
                "f20": "total_mv",
                "f21": "circulating_mv",
                "f8": "turnover_rate",
                "f10": "volume_ratio",
            }
            for api_field, db_field in field_map.items():
                val = item.get(api_field)
                if val is not None and val != "-":
                    try:
                        rec[db_field] = float(val)
                    except (ValueError, TypeError):
                        pass

            records.append(rec)

        return records

    def _compute_roe_from_financial(self, codes: List[str]) -> Dict[str, Optional[float]]:
        from config.database import get_collection
        fin_col = get_collection("financial")

        pipeline = [
            {"$match": {"code": {"$in": codes}}},
            {"$sort": {"report_date": -1}},
            {"$group": {
                "_id": "$code",
                "roe_raw": {"$first": {"$ifNull": ["$净资产收益率", "$roe"]}},
                "report_date": {"$first": "$report_date"},
            }},
        ]
        roe_map: Dict[str, Optional[float]] = {}
        try:
            for doc in fin_col.aggregate(pipeline):
                code = doc["_id"]
                raw = doc.get("roe_raw")
                if raw is None:
                    continue
                try:
                    val = float(str(raw).replace("%", ""))
                    rd = str(doc.get("report_date", ""))
                    q = self._report_quarter(rd)
                    if q < 4:
                        val = round(val * 4 / q, 2)
                    roe_map[code] = val
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.warning(f"ROE aggregation failed: {e}")

        return roe_map

    @staticmethod
    def _report_quarter(report_date: str) -> int:
        s = str(report_date)
        if s.endswith("-03-31") or s.endswith("0331"):
            return 1
        if s.endswith("-06-30") or s.endswith("0630"):
            return 2
        if s.endswith("-09-30") or s.endswith("0930"):
            return 3
        return 4
