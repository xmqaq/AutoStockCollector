"""
初始化量化多因子选股工作流：
1. 删除旧工作流记录（智能多维度选股工作流 / 缠中说禅交易策略）
2. 写入新工作流（量化多因子选股，workflow_type=quant_multi_factor）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.workflow.models import Workflow, WorkflowStorage
from datetime import datetime
from utils.helpers import beijing_now


OLD_WORKFLOW_NAMES = [
    "智能多维度选股工作流",
    "缠中说禅交易策略",
]

NEW_WORKFLOW = {
    "id": "quant_multi_factor_v1",
    "name": "量化多因子选股",
    "description": "基于基本面、技术面、资金面、估值面、市场情绪五维度评分，筛选综合质地优良的股票",
    "workflow_type": "quant_multi_factor",
    "nodes": [],
    "edges": [],
    "enabled": True,
    "tags": ["量化", "多因子", "基本面", "技术面", "资金面"],
}


def main():
    storage = WorkflowStorage()
    now = beijing_now().isoformat()

    # 1. Delete old workflows by name
    all_workflows = storage.list_workflows()
    for wf in all_workflows:
        if wf.name in OLD_WORKFLOW_NAMES:
            ok = storage.delete_workflow(wf.id)
            status = "✅ Deleted" if ok else "⚠️  Delete failed"
            print(f"{status}: {wf.name} (id={wf.id})")
        else:
            pass  # keep other workflows

    # 2. Upsert new workflow
    existing = storage.get_workflow(NEW_WORKFLOW["id"])
    if existing:
        print(f"Workflow '{NEW_WORKFLOW['name']}' already exists, updating...")

    wf = Workflow(
        id=NEW_WORKFLOW["id"],
        name=NEW_WORKFLOW["name"],
        description=NEW_WORKFLOW["description"],
        workflow_type=NEW_WORKFLOW["workflow_type"],
        nodes=[],
        edges=[],
        enabled=NEW_WORKFLOW["enabled"],
        created_at=now,
        updated_at=now,
        tags=NEW_WORKFLOW["tags"],
    )
    ok = storage.save_workflow(wf)
    if ok:
        print(f"✅ Created workflow: {wf.name} (id={wf.id})")
    else:
        print(f"❌ Failed to create workflow: {wf.name}")

    print("\nDone. Run the Flask server and open the workflow page to verify.")


if __name__ == "__main__":
    main()
