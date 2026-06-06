"""
待办事项 CRUD 接口
支持：查询列表、新增、编辑内容/分类/状态、删除（含批量）
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Optional
import uuid

todo_bp = Blueprint("todo", __name__, url_prefix="/api/v1/todo")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _serialize(doc: dict) -> Optional[dict]:
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


@todo_bp.route("", methods=["GET"])
def list_todos():
    """获取全部待办事项，按 updatedAt 降序"""
    db = _get_db()
    docs = list(db["todo"].find(sort=[("updatedAt", -1)]))
    items = [_serialize(d) for d in docs if d]
    return jsonify({"success": True, "count": len(items), "data": items})


@todo_bp.route("", methods=["POST"])
def create_todo():
    """新增待办事项"""
    db = _get_db()
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400

    category = body.get("category", "todo")
    if category not in ("todo", "plan", "suggestion"):
        category = "todo"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = {
        "id": str(uuid.uuid4()),
        "text": text,
        "category": category,
        "done": False,
        "createdAt": now,
        "updatedAt": now,
    }
    db["todo"].insert_one(doc.copy())
    return jsonify({"success": True, "data": _serialize(doc)}), 201


@todo_bp.route("/<todo_id>", methods=["PUT"])
def update_todo(todo_id: str):
    """更新待办事项（text / category / done）"""
    body = request.get_json() or {}
    db = _get_db()

    existing = db["todo"].find_one({"id": todo_id})
    if not existing:
        return jsonify({"success": False, "error": "not found"}), 404

    updates = {}
    if "text" in body:
        text = (body["text"] or "").strip()
        if text:
            updates["text"] = text
    if "category" in body and body["category"] in ("todo", "plan", "suggestion"):
        updates["category"] = body["category"]
    if "done" in body:
        updates["done"] = bool(body["done"])

    if not updates:
        return jsonify({"success": False, "error": "no fields to update"}), 400

    updates["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db["todo"].update_one({"id": todo_id}, {"$set": updates})

    doc = db["todo"].find_one({"id": todo_id})
    return jsonify({"success": True, "data": _serialize(doc)})


@todo_bp.route("/<todo_id>", methods=["DELETE"])
def delete_todo(todo_id: str):
    """删除单条待办"""
    db = _get_db()
    result = db["todo"].delete_one({"id": todo_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "not found"}), 404
    return jsonify({"success": True, "deleted": todo_id})


@todo_bp.route("/batch", methods=["DELETE"])
def batch_delete_todos():
    """批量删除（POST JSON body: {"ids": ["id1", "id2"]}）"""
    body = request.get_json() or {}
    ids = body.get("ids", [])
    if not ids:
        return jsonify({"success": False, "error": "ids required"}), 400
    db = _get_db()
    result = db["todo"].delete_many({"id": {"$in": ids}})
    return jsonify({"success": True, "deleted_count": result.deleted_count})
