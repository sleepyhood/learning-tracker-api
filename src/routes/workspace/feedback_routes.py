"""
routes/workspace/feedback_routes.py

숙제 및 알림장 이력 저장 API 라우트.
비즈니스 로직은 services.workspace_student_service에 위임합니다.

엔드포인트:
  POST /api/workspace/save_homework_log - 학생 숙제 및 알림장 이력 저장
"""

from flask import Blueprint, jsonify, request

from services.workspace_student_service import save_homework_log
from utils.utils_common import ensure_admin_or_403

feedback_bp = Blueprint("workspace_feedback", __name__)


@feedback_bp.route("/api/workspace/save_homework_log", methods=["POST"])
def api_workspace_save_homework_log():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    user_uuid = payload.get("user_uuid")
    problems = payload.get("problems", [])

    log_payload = {
        "problems": problems,
        "title": payload.get("title", ""),
        "comment": payload.get("comment", ""),
        "message": payload.get("message", ""),
        "mode": payload.get("mode", "homework" if len(problems) > 0 else "comment"),
    }

    try:
        save_homework_log(display_id, user_uuid, log_payload)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({"ok": True})
