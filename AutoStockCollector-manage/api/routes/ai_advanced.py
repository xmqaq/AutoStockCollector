"""
AI高级分析接口
包含：批量分析、多Agent协作分析、实时进度追踪
支持MongoDB持久化存储
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading
import time
import uuid

ai_advanced_bp = Blueprint("ai_advanced", __name__, url_prefix="/api/v1/ai")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


def _save_batch_task_to_db(task_id: str, task_data: Dict):
    """保存批量任务到MongoDB"""
    db = _get_db()
    task_data["task_id"] = task_id
    task_data["updated_at"] = datetime.now().isoformat()

    existing = db["batch_tasks"].find_one({"task_id": task_id})
    if existing:
        db["batch_tasks"].update_one(
            {"task_id": task_id},
            {"$set": task_data}
        )
    else:
        task_data["created_at"] = datetime.now().isoformat()
        db["batch_tasks"].insert_one(task_data)


def _get_batch_task_from_db(task_id: str) -> Optional[Dict]:
    """从MongoDB获取批量任务"""
    db = _get_db()
    task = db["batch_tasks"].find_one({"task_id": task_id})
    if task:
        task.pop("_id", None)
    return task


def _save_multi_agent_task_to_db(task_id: str, task_data: Dict):
    """保存多Agent任务到MongoDB"""
    db = _get_db()
    task_data["task_id"] = task_id
    task_data["updated_at"] = datetime.now().isoformat()

    existing = db["multi_agent_tasks"].find_one({"task_id": task_id})
    if existing:
        db["multi_agent_tasks"].update_one(
            {"task_id": task_id},
            {"$set": task_data}
        )
    else:
        task_data["created_at"] = datetime.now().isoformat()
        db["multi_agent_tasks"].insert_one(task_data)


def _get_multi_agent_task_from_db(task_id: str) -> Optional[Dict]:
    """从MongoDB获取多Agent任务"""
    db = _get_db()
    task = db["multi_agent_tasks"].find_one({"task_id": task_id})
    if task:
        task.pop("_id", None)
    return task


def _get_batch_tasks_from_db(limit: int = 20) -> List[Dict]:
    """获取所有批量任务"""
    db = _get_db()
    tasks = list(db["batch_tasks"].find(
        sort=[("created_at", -1)],
        limit=limit
    ))
    for task in tasks:
        task.pop("_id", None)
    return tasks


def _get_multi_agent_tasks_from_db(limit: int = 20) -> List[Dict]:
    """获取所有多Agent任务"""
    db = _get_db()
    tasks = list(db["multi_agent_tasks"].find(
        sort=[("created_at", -1)],
        limit=limit
    ))
    for task in tasks:
        task.pop("_id", None)
    return tasks


@ai_advanced_bp.route("/batch-analyze", methods=["POST"])
def batch_analyze():
    """批量AI分析接口"""
    data = request.get_json() or {}
    codes = data.get("codes", [])
    analysis_type = data.get("type", "comprehensive")

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    task_id = f"batch_{uuid.uuid4().hex[:12]}"
    task_data = {
        "codes": codes,
        "type": analysis_type,
        "status": "pending",
        "total": len(codes),
        "completed": 0,
        "failed": 0,
        "results": [],
        "errors": [],
        "current": None,
        "started_at": None,
        "completed_at": None,
    }

    _save_batch_task_to_db(task_id, task_data)

    thread = threading.Thread(
        target=_simulate_batch_analysis,
        args=(task_id, codes, analysis_type)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "total": len(codes),
        "message": "批量分析任务已创建"
    })


def _simulate_batch_analysis(task_id: str, codes: List[str], analysis_type: str):
    """模拟批量分析任务"""
    task_data = {
        "status": "running",
        "started_at": datetime.now().isoformat()
    }
    _save_batch_task_to_db(task_id, task_data)

    from modules.ai.ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer()

    for i, code in enumerate(codes):
        task_data = {
            "completed": i,
            "current": code
        }
        _save_batch_task_to_db(task_id, task_data)

        try:
            result = analyzer.analyze(code, analysis_type)
            task_data = {
                "results": [{"code": code, **result}]
            }
            _save_batch_task_to_db(task_id, task_data)
        except Exception as e:
            task_data = {
                "errors": [{"code": code, "error": str(e)}]
            }
            _save_batch_task_to_db(task_id, task_data)

        time.sleep(0.5)

    task_data = {
        "status": "completed",
        "completed": len(codes),
        "completed_at": datetime.now().isoformat()
    }
    _save_batch_task_to_db(task_id, task_data)


@ai_advanced_bp.route("/batch-progress/<task_id>", methods=["GET"])
def get_batch_progress(task_id: str):
    """获取批量分析进度"""
    task = _get_batch_task_from_db(task_id)

    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status"),
        "total": task.get("total"),
        "completed": task.get("completed"),
        "failed": task.get("failed"),
        "current": task.get("current"),
        "results": task.get("results", [])[-50:],
        "errors": task.get("errors", [])[-10:],
    })


@ai_advanced_bp.route("/batch-tasks", methods=["GET"])
def list_batch_tasks():
    """列出所有批量分析任务"""
    tasks = _get_batch_tasks_from_db()
    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks
    })


@ai_advanced_bp.route("/multi-agent", methods=["POST"])
def multi_agent_analyze():
    """多Agent协作分析"""
    data = request.get_json() or {}
    code = data.get("code")
    analysis_type = data.get("type", "comprehensive")

    if not code:
        return jsonify({"error": "code is required"}), 400

    task_id = f"agent_{uuid.uuid4().hex[:12]}"

    agents_info = {
        "market": {"name": "市场分析师", "role": "market"},
        "technical": {"name": "技术分析师", "role": "technical"},
        "fund": {"name": "资金分析师", "role": "fund"},
        "sentiment": {"name": "舆情分析师", "role": "sentiment"},
        "risk": {"name": "风控分析师", "role": "risk"},
        "commander": {"name": "决策指挥官", "role": "commander"},
    }

    task_data = {
        "code": code,
        "type": analysis_type,
        "status": "pending",
        "agents": {agent_id: {
            **agent_info,
            "status": "idle",
            "progress": 0,
            "result": None,
            "error": None,
        } for agent_id, agent_info in agents_info.items()},
        "aggregated_result": None,
        "started_at": None,
        "completed_at": None,
    }

    _save_multi_agent_task_to_db(task_id, task_data)

    thread = threading.Thread(
        target=_simulate_multi_agent_analysis,
        args=(task_id, code, analysis_type)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "多Agent分析任务已创建"
    })


def _simulate_multi_agent_analysis(task_id: str, code: str, analysis_type: str):
    """模拟多Agent协作分析"""
    task_data = {
        "status": "running",
        "started_at": datetime.now().isoformat()
    }
    _save_multi_agent_task_to_db(task_id, task_data)

    agent_order = ["market", "technical", "fund", "sentiment", "risk", "commander"]

    for agent_id in agent_order:
        for p in range(10, 101, 20):
            task_data = {
                "agents": {
                    agent_id: {
                        "status": "running",
                        "progress": p
                    }
                }
            }
            _save_multi_agent_task_to_db(task_id, task_data)
            time.sleep(0.3)

        mock_result = {
            "score": 60 + int(30 * (hash(code + agent_id) % 100) / 100),
            "conclusion": f"{agent_id}分析结论",
            "signals": [f"{agent_id}信号1", f"{agent_id}信号2"],
            "metrics": {f"{agent_id}_metric": 75},
            "recommendation": "中性偏多",
        }

        task_data = {
            "agents": {
                agent_id: {
                    "status": "completed",
                    "progress": 100,
                    "result": mock_result
                }
            }
        }
        _save_multi_agent_task_to_db(task_id, task_data)

    aggregated = {
        "code": code,
        "compositeScore": 68.5,
        "recommendation": "买入",
        "avgScore": 72.3,
        "signals": ["技术金叉", "资金流入", "业绩预增"],
        "agentResults": [
            {"name": "市场分析师", "role": "market", "score": 70, "conclusion": "偏多", "recommendation": "买入"},
        ],
        "generatedAt": datetime.now().isoformat(),
    }

    task_data = {
        "status": "completed",
        "aggregated_result": aggregated,
        "completed_at": datetime.now().isoformat()
    }
    _save_multi_agent_task_to_db(task_id, task_data)


@ai_advanced_bp.route("/multi-agent/<task_id>", methods=["GET"])
def get_multi_agent_progress(task_id: str):
    """获取多Agent分析进度"""
    task = _get_multi_agent_task_from_db(task_id)

    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status"),
        "code": task.get("code"),
        "agents": task.get("agents"),
        "aggregated_result": task.get("aggregated_result"),
    })


@ai_advanced_bp.route("/multi-agent/<task_id>/pause", methods=["POST"])
def pause_multi_agent(task_id: str):
    """暂停多Agent分析"""
    task = _get_multi_agent_task_from_db(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task_data = {"status": "paused"}
    _save_multi_agent_task_to_db(task_id, task_data)

    return jsonify({"success": True, "message": "任务已暂停"})


@ai_advanced_bp.route("/multi-agent/<task_id>/resume", methods=["POST"])
def resume_multi_agent(task_id: str):
    """恢复多Agent分析"""
    task = _get_multi_agent_task_from_db(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task_data = {"status": "running"}
    _save_multi_agent_task_to_db(task_id, task_data)

    return jsonify({"success": True, "message": "任务已恢复"})


@ai_advanced_bp.route("/multi-agent/<task_id>/stop", methods=["POST"])
def stop_multi_agent(task_id: str):
    """停止多Agent分析"""
    task = _get_multi_agent_task_from_db(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    task_data = {"status": "stopped"}
    _save_multi_agent_task_to_db(task_id, task_data)

    return jsonify({"success": True, "message": "任务已停止"})


@ai_advanced_bp.route("/multi-agent-tasks", methods=["GET"])
def list_multi_agent_tasks():
    """列出所有多Agent任务"""
    tasks = _get_multi_agent_tasks_from_db()
    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks
    })