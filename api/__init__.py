"""
API模块初始化
"""
from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.settings.Settings")

    CORS(app)

    from api.routes import register_routes
    register_routes(app)

    return app


__all__ = ["create_app"]