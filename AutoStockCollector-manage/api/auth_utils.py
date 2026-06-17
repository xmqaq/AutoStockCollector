"""
JWT authentication utilities
"""
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable

import os
import jwt
from flask import request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from config.database import DatabaseConfig

JWT_SECRET = os.getenv("JWT_SECRET", "stock-collector-jwt-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)


def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _resolve_user() -> Optional[dict]:
    """Extract and validate current user from Authorization header. Returns user dict or None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if payload is None:
        return None
    db = DatabaseConfig.get_database()
    user = db.users.find_one({"user_id": payload["user_id"]}, {"password": 0})
    if user is None:
        return None
    user.pop("_id", None)
    return user


def login_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated(*args, **kwargs):
        user = _resolve_user()
        if user is None:
            return jsonify({"success": False, "error": "未提供认证令牌或令牌无效"}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated(*args, **kwargs):
        user = _resolve_user()
        if user is None:
            return jsonify({"success": False, "error": "未提供认证令牌或令牌无效"}), 401
        if user.get("role") != "admin":
            return jsonify({"success": False, "error": "需要管理员权限"}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated
