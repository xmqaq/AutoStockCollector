"""一次性迁移:重置 trading_memory 全部复盘结论(决策价bug修复后惰性重算)。
用法: ./venv/bin/python scripts/reset_reflections_20260612.py [--apply]
默认 dry-run 只统计;--apply 真执行。"""
import sys
sys.path.insert(0, ".")
from config.database import DatabaseConfig

db = DatabaseConfig.get_database()
q = {"type": "trading_decision", "evaluated": True}
n = db["trading_memory"].count_documents(q)
print(f"将重置 {n} 条已评估的决策记录(evaluated→False,清除旧reflection)")
if "--apply" in sys.argv:
    r = db["trading_memory"].update_many(
        q, {"$set": {"evaluated": False}, "$unset": {"reflection": ""}})
    print(f"已重置 {r.modified_count} 条;下次打开个股深度分析页将按新逻辑重算")
else:
    print("dry-run,未修改。加 --apply 执行")
