"""
资金流因子库
"""
from typing import List, Dict, Any
import numpy as np
from .base import FactorBase, FactorData, factor_registry
from utils.logger import get_logger


logger = get_logger(__name__)


class FundFlowFactor(FactorBase):
    def __init__(self):
        super().__init__(name="fund_flow", category="moneyflow")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        flow_data = kwargs.get("flow_data")
        if not flow_data:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        main_inflow = flow_data.get("main_net_inflow", 0)
        retail_inflow = flow_data.get("retail_net_inflow", 0)
        net_inflow = flow_data.get("net_inflow", 0)

        score = 50.0
        if main_inflow > 1e8:
            score = 85.0
        elif main_inflow > 5e7:
            score = 75.0
        elif main_inflow > 1e7:
            score = 65.0
        elif main_inflow > 0:
            score = 55.0
        elif main_inflow < -1e8:
            score = 25.0
        elif main_inflow < -5e7:
            score = 35.0
        else:
            score = 45.0

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=flow_data.get("name", ""),
            date=flow_data.get("date", ""),
            values={
                "main_net_inflow": float(main_inflow),
                "retail_net_inflow": float(retail_inflow),
                "net_inflow": float(net_inflow),
                "inflow_ratio": float(main_inflow / net_inflow) if net_inflow != 0 else 0.0
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class MoneyFlowIntensityFactor(FactorBase):
    def __init__(self):
        super().__init__(name="money_flow_intensity", category="moneyflow")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 5:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        volumes = np.array([k.get("volume", 0) for k in kline_data])
        closes = np.array([k.get("close", 0) for k in kline_data])

        current_vol = volumes[0]
        avg_vol = np.mean(volumes[1:]) if len(volumes) > 1 else current_vol
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

        flow_data = kwargs.get("flow_data")
        main_inflow = flow_data.get("main_net_inflow", 0) if flow_data else 0

        price_change = 0.0
        if len(closes) >= 2 and closes[1] > 0:
            price_change = (closes[0] - closes[1]) / closes[1] * 100

        score = 50.0
        if main_inflow > 0 and vol_ratio > 1.5 and price_change > 0:
            score = 80.0
        elif main_inflow > 0 and vol_ratio > 1.2:
            score = 70.0
        elif main_inflow > 0:
            score = 60.0
        elif main_inflow < 0 and vol_ratio > 1.5 and price_change < 0:
            score = 30.0
        else:
            score = 50.0

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "volume_ratio": float(vol_ratio),
                "price_change": float(price_change),
                "main_inflow": float(main_inflow),
                "money_intensity": float(vol_ratio * (1 + price_change / 100))
            },
            score=score
        )
        self._save_to_cache(result)
        return result


factor_registry.register(FundFlowFactor())
factor_registry.register(MoneyFlowIntensityFactor())