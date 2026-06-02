import os
from pathlib import Path

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from config.database import DatabaseConfig

db = DatabaseConfig.get_database()

print("最近10条执行记录:")
executions = list(db.workflow_execution.find({}).sort("started_at", -1).limit(10))
for e in executions:
    started = e.get("started_at", "")[:19] if e.get("started_at") else "N/A"
    finished = e.get("finished_at", "")[:19] if e.get("finished_at") else "-"
    print(f"\n  工作流: {e.get('workflow_id')}")
    print(f"  执行ID: {e.get('id')}")
    print(f"  状态: {e.get('status')}")
    print(f"  进度: {e.get('progress', 0):.1f}%")
    print(f"  当前步骤: {e.get('current_step', '-')}")
    print(f"  开始时间: {started}")
    print(f"  结束时间: {finished}")
    if e.get('error'):
        print(f"  错误: {e.get('error')[:100]}")
    if e.get('steps'):
        print(f"  步骤数: {len(e.get('steps', []))}")