"""
routes/workspace/__init__.py

workspace Blueprint 통합 진입점.

app.py에서 기존에 사용하던:
    from routes.workspace import workspace_bp

구문이 변경 없이 동작하도록 하위 호환성을 보장합니다.
서브 블루프린트(student, catalog, crawler, ai)를 하나의 workspace_bp에 통합합니다.
"""

from flask import Blueprint

from .ai_routes import ai_bp
from .catalog_routes import catalog_bp
from .crawler_routes import crawler_bp
from .student_routes import student_bp

# app.py 하위 호환: `from routes.workspace import workspace_bp`
workspace_bp = Blueprint("workspace", __name__)

workspace_bp.register_blueprint(student_bp)
workspace_bp.register_blueprint(catalog_bp)
workspace_bp.register_blueprint(crawler_bp)
workspace_bp.register_blueprint(ai_bp)
