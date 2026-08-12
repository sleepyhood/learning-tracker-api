"""
routes/workspace/ai_routes.py

AI 프롬프트 생성 및 숙제 이력 저장 API 라우트.
비즈니스 로직은 services.ai_prompt_service / services.workspace_student_service에 위임합니다.

엔드포인트 (2개):
  POST /api/workspace/generate_ai_prompt - AI 학부모 문자 초안 프롬프트 생성
  POST /api/workspace/save_homework_log  - 학생 숙제 이력 저장
"""

from flask import Blueprint, jsonify, request

from services.ai_prompt_service import generate_ai_prompt
from services.workspace_student_service import save_homework_log
from utils.utils_common import ensure_admin_or_403

ai_bp = Blueprint("workspace_ai", __name__)


@ai_bp.route("/api/workspace/generate_ai_prompt", methods=["POST"])
def api_workspace_generate_ai_prompt():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")

    try:
        prompt = generate_ai_prompt(display_id)
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404

    return jsonify({"ok": True, "prompt": prompt})


@ai_bp.route("/api/workspace/save_homework_log", methods=["POST"])
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
