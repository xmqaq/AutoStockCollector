"""
估值指标采集器
直接调用东财 API 按股票代码精准查询 PE/PB/总市值等估值指标，
结合 financial 集合中最新财报计算 ROE，写入 stock_valuation 集合。
设计为 5 分钟轮询，盘中高频刷新，盘后/周末自动跳过。
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from core.storage.mongo_storage import ValuationStorage
from utils.logger import get_logger

logger = get_logger(__name__)

_EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_FIELDS = "f2,f3,f9,f12,f14,f20,f21,f23,f8,f10"


class ValuationCollector:
    def __init__(self):
        self.storage = ValuationStorage()
        self._session = requests.Session()
        self._session.trust_env = False

    def collect(self, codes: Optional[List[str]] = None) -> int:
        if not codes:
            return 0
        spot_records = self._fetch_valuation_batch(codes)
        if not spot_records:
            return 0

        roe_map = self._compute_roe_from_financial(codes)
        for rec in spot_records:
            roe = roe_map.get(rec["code"])
            if roe is not None:
                rec["roe"] = roe

        self.storage.save_batch(spot_records)
        logger.info(f"Valuation cache updated: {len(spot_records)} stocks")
        return len(spot_records)

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
            }, timeout=10)
            data = resp.json()
        except Exception as e:
            logger.error(f"EastMoney valuation API failed: {e}")
            return []

        diff = (data.get("data") or {}).get("diff")
        if not diff:
            logger.warning("EastMoney valuation API returned empty diff")
            return []

        now = datetime.now()
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
