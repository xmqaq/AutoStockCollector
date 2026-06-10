"""
待办事项 CRUD 接口
支持：分页查询（page/pageSize/category）、新增（记录提交IP）、编辑、删除（含批量）
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from utils.helpers import beijing_now
from typing import Optional
import uuid

todo_bp = Blueprint("todo", __name__, url_prefix="/api/v1/todo")

_VALID_CATEGORIES = ("todo", "plan", "suggestion")
_MAX_PAGE_SIZE = 100


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _serialize(doc: dict) -> Optional[dict]:
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@todo_bp.route("", methods=["GET"])
def list_todos():
    """分页获取待办事项，支持 category 过滤"""
    db = _get_db()
    col = db["todo"]

    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(_MAX_PAGE_SIZE, max(1, int(request.args.get("pageSize", 20))))
    except (TypeError, ValueError):
        page, page_size = 1, 20

    category = request.args.get("category", "all")
    query = {} if category not in _VALID_CATEGORIES else {"category": category}

    filtered_total = col.count_documents(query)
    global_total = filtered_total if not query else col.count_documents({})
    global_done = col.count_documents({"done": True})

    skip = (page - 1) * page_size
    docs = list(col.find(query, sort=[("updatedAt", -1)], skip=skip, limit=page_size))
    items = [_serialize(d) for d in docs if d]

    return jsonify({
        "success": True,
        "data": items,
        "pagination": {"page": page, "pageSize": page_size, "total": filtered_total},
        "stats": {
            "total": global_total,
            "done": global_done,
            "pending": global_total - global_done,
        },
    })


@todo_bp.route("", methods=["POST"])
def create_todo():
    """新增待办事项，记录提交人 IP"""
    db = _get_db()
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400

    category = body.get("category", "todo")
    if category not in _VALID_CATEGORIES:
        category = "todo"

    now = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    doc = {
        "id": str(uuid.uuid4()),
        "text": text,
        "category": category,
        "done": False,
        "submitterIp": _get_client_ip(),
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
    if "category" in body and body["category"] in _VALID_CATEGORIES:
        updates["category"] = body["category"]
    if "done" in body:
        updates["done"] = bool(body["done"])

    if not updates:
        return jsonify({"success": False, "error": "no fields to update"}), 400

    updates["updatedAt"] = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
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
