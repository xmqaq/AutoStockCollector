"""平台配置服务：全局单文档配置，存 MongoDB `platform_config` 集合。

当前承载「模拟盘交易费率」，设计上可继续扩展（默认初始资金、撮合规则等）。
读取带进程级 TTL 缓存，避免每笔交易都查库；保存时失效本进程缓存。
跨多 worker 时其他进程最多 _CACHE_TTL 秒后生效。
"""
import time
from typing import Any, Dict

from utils.helpers import beijing_now

# 默认值 = 改造前 trade_engine 的硬编码常量，保证向后兼容。
DEFAULTS: Dict[str, float] = {
    "buy_commission_rate": 0.0003,   # 买入佣金率
    "sell_commission_rate": 0.0003,  # 卖出佣金率
    "min_commission": 5.0,           # 最低佣金（元）
    "stamp_tax_rate": 0.001,         # 印花税率（仅卖出）
}

# 费率类字段（用于范围校验：0 ~ 1%）
_RATE_FIELDS = {"buy_commission_rate", "sell_commission_rate", "stamp_tax_rate"}
_DOC_ID = "default"
_CACHE_TTL = 30.0


class PlatformConfig:
    # 类级缓存：进程内所有实例共享
    _cache: Dict[str, Any] = None
    _cache_at: float = 0.0

    def __init__(self):
        from config.database import DatabaseConfig
        self._col = DatabaseConfig.get_database()["platform_config"]

    def _read_doc(self) -> Dict[str, Any]:
        doc = self._col.find_one({"_id": _DOC_ID}) or {}
        doc.pop("_id", None)
        return doc

    def get(self, force: bool = False) -> Dict[str, Any]:
        """返回合并了默认值的完整配置（始终包含所有字段）。"""
        now = time.time()
        if (not force and PlatformConfig._cache is not None
                and (now - PlatformConfig._cache_at) < _CACHE_TTL):
            return dict(PlatformConfig._cache)
        merged = dict(DEFAULTS)
        try:
            stored = self._read_doc()
            merged.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except Exception:
            pass
        PlatformConfig._cache = merged
        PlatformConfig._cache_at = now
        return dict(merged)

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """校验并保存配置补丁，返回最新完整配置。"""
        clean: Dict[str, float] = {}
        for key, raw in (patch or {}).items():
            if key not in DEFAULTS:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"{key} 必须为数字")
            if val < 0:
                raise ValueError(f"{key} 不能为负数")
            if key in _RATE_FIELDS and val > 0.01:
                raise ValueError(f"{key} 费率不应超过 1%")
            if key == "min_commission" and val > 1000:
                raise ValueError("最低佣金过大")
            clean[key] = val
        if not clean:
            raise ValueError("无有效配置项")
        clean["updated_at"] = beijing_now().isoformat()
        self._col.update_one({"_id": _DOC_ID}, {"$set": clean}, upsert=True)
        PlatformConfig._cache = None  # 失效本进程缓存
        return self.get(force=True)
