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

print("查看运行中的执行记录详情:")
exec = db.workflow_execution.find_one({
    "status": "running",
    "workflow_id": "smart-stock-picker-v2"
})
if exec:
    print(f"执行ID: {exec.get('id')}")
    print(f"状态: {exec.get('status')}")
    print(f"进度: {exec.get('progress', 0):.1f}%")
    print(f"当前节点: {exec.get('current_node')}")
    print(f"当前步骤: {exec.get('current_step')}")
    print(f"开始时间: {exec.get('started_at')}")
    print(f"步骤数: {len(exec.get('steps', []))}")
    print(f"错误: {exec.get('error')}")

    if exec.get('steps'):
        print("\n步骤详情:")
        for i, step in enumerate(exec['steps'][-5:]):
            print(f"  {i+1}. {step.get('node_label')}: {step.get('step')} ({step.get('progress', 0):.1f}%)")
else:
    print("没有找到运行中的执行记录")