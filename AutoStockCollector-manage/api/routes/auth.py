"""
Authentication routes: register, login, profile
"""
import re
from flask import Blueprint, request, jsonify, g
from config.database import DatabaseConfig
from api.auth_utils import (
    hash_password, verify_password, create_token, login_required, admin_required,
)
from utils.logger import get_logger

logger = get_logger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fa5]{2,20}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请提供注册信息"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    email = (data.get("email") or "").strip()
    nickname = (data.get("nickname") or "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"}), 400

    if not _USERNAME_RE.match(username):
        return jsonify({"success": False, "error": "用户名需2-20位字符（字母/数字/中文/下划线）"}), 400

    if email and not _EMAIL_RE.match(email):
        return jsonify({"success": False, "error": "邮箱格式不正确"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "密码长度至少6位"}), 400

    db = DatabaseConfig.get_database()

    existing = db.users.find_one({"username": username})
    if existing:
        return jsonify({"success": False, "error": "用户名已存在"}), 409

    if email:
        existing_email = db.users.find_one({"email": email})
        if existing_email:
            return jsonify({"success": False, "error": "邮箱已被使用"}), 409

    from utils.helpers import beijing_now
    is_first = db.users.count_documents({}) == 0
    role = "admin" if is_first else "user"
    user_doc = {
        "username": username,
        "password": hash_password(password),
        "email": email,
        "nickname": nickname or username,
        "user_id": username,
        "role": role,
        "created_at": beijing_now(),
        "updated_at": beijing_now(),
    }
    db.users.insert_one(user_doc)

    token = create_token(username)
    nick = nickname or username
    msg = "注册成功，您是管理员" if is_first else "注册成功"
    return jsonify({
        "success": True,
        "data": {
            "token": token,
            "user": {
                "user_id": username,
                "username": username,
                "nickname": nick,
                "email": email,
                "role": role,
            },
        },
        "message": msg,
    })


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请提供登录信息"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"}), 400

    db = DatabaseConfig.get_database()
    user = db.users.find_one({"username": username})

    if not user:
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

    if not verify_password(password, user.get("password", "")):
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

    token = create_token(user["user_id"])
    return jsonify({
        "success": True,
        "data": {
            "token": token,
            "user": {
                "user_id": user["user_id"],
                "username": user["username"],
                "nickname": user.get("nickname", user["username"]),
                "email": user.get("email", ""),
                "role": user.get("role", "user"),
            },
        },
        "message": "登录成功",
    })


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_profile():
    return jsonify({
        "success": True,
        "data": g.current_user,
    })


@auth_bp.route("/me", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请提供更新信息"}), 400

    db = DatabaseConfig.get_database()
    update_fields = {}
    nickname = (data.get("nickname") or "").strip()
    if nickname:
        if len(nickname) < 2 or len(nickname) > 20:
            return jsonify({"success": False, "error": "昵称需2-20位字符"}), 400
        update_fields["nickname"] = nickname

    email = (data.get("email") or "").strip()
    if email:
        if not _EMAIL_RE.match(email):
            return jsonify({"success": False, "error": "邮箱格式不正确"}), 400
        existing = db.users.find_one({"email": email, "user_id": {"$ne": g.current_user["user_id"]}})
        if existing:
            return jsonify({"success": False, "error": "邮箱已被使用"}), 409
        update_fields["email"] = email

    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    if old_password and new_password:
        user = db.users.find_one({"user_id": g.current_user["user_id"]})
        if not verify_password(old_password, user.get("password", "")):
            return jsonify({"success": False, "error": "原密码不正确"}), 400
        if len(new_password) < 6:
            return jsonify({"success": False, "error": "新密码长度至少6位"}), 400
        update_fields["password"] = hash_password(new_password)

    if not update_fields:
        return jsonify({"success": False, "error": "没有需要更新的字段"}), 400

    from utils.helpers import beijing_now
    update_fields["updated_at"] = beijing_now()
    db.users.update_one({"user_id": g.current_user["user_id"]}, {"$set": update_fields})

    updated = db.users.find_one({"user_id": g.current_user["user_id"]}, {"password": 0})
    updated.pop("_id", None)
    return jsonify({"success": True, "data": updated, "message": "更新成功"})


# ===== Admin endpoints =====


@auth_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    db = DatabaseConfig.get_database()
    users = list(db.users.find({}, {"password": 0}).sort("created_at", -1))
    for u in users:
        u.pop("_id", None)
    return jsonify({"success": True, "count": len(users), "data": users})


@auth_bp.route("/users/<user_id>/role", methods=["PUT"])
@admin_required
def update_user_role(user_id):
    data = request.get_json()
    role = data.get("role") if data else None
    if role not in ("user", "admin"):
        return jsonify({"success": False, "error": "角色必须是 user 或 admin"}), 400
    db = DatabaseConfig.get_database()
    if user_id == g.current_user["user_id"]:
        return jsonify({"success": False, "error": "不能修改自己的角色"}), 400
    result = db.users.update_one({"user_id": user_id}, {"$set": {"role": role}})
    if result.matched_count == 0:
        return jsonify({"success": False, "error": "用户不存在"}), 404
    return jsonify({"success": True, "message": f"用户 {user_id} 角色已设为 {role}"})


@auth_bp.route("/users/<user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    if user_id == g.current_user["user_id"]:
        return jsonify({"success": False, "error": "不能删除自己"}), 400
    db = DatabaseConfig.get_database()
    result = db.users.delete_one({"user_id": user_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "用户不存在"}), 404
    return jsonify({"success": True, "message": f"用户 {user_id} 已删除"})
