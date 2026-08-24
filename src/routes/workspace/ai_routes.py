"""
routes/workspace/ai_routes.py

AI 프롬프트 생성, Gemini 피드백 생성, 숙제 이력 저장 API 라우트.
비즈니스 로직은 services.ai_prompt_service / services.gemini_service /
services.workspace_student_service에 위임합니다.

엔드포인트 (3개):
  POST /api/workspace/generate_ai_prompt    - AI 학부모 문자 초안 프롬프트 생성 (기존)
  POST /api/workspace/generate_ai_feedback  - Gemini API로 완성된 피드백 직접 생성 (신규)
  POST /api/workspace/save_homework_log     - 학생 숙제 이력 저장
"""

from flask import Blueprint, jsonify, request

from services.ai_prompt_service import generate_ai_prompt
from services.gemini_service import GeminiAPIError, GeminiConfigError, generate_feedback
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


@ai_bp.route("/api/workspace/generate_ai_feedback", methods=["POST"])
def api_workspace_generate_ai_feedback():
    """
    POST /api/workspace/generate_ai_feedback

    프론트엔드에서 조립한 프롬프트 텍스트를 받아 Gemini API를 호출,
    완성된 학부모 알림장 피드백 문자를 반환합니다.

    Request Body:
      { "prompt": "<완전한 프롬프트 문자열>" }

    Response:
      성공: { "ok": true,  "feedback": "안녕하세요 두잉창의코딩학원입니다. ..." }
      실패: { "ok": false, "error": "...", "code": "NO_KEY" | "API_ERROR" }
    """
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt 필드가 비어 있습니다.", "code": "EMPTY_PROMPT"}), 400

    try:
        feedback = generate_feedback(prompt)
    except GeminiConfigError as e:
        return jsonify({"ok": False, "error": str(e), "code": "NO_KEY"}), 503
    except GeminiAPIError as e:
        return jsonify({"ok": False, "error": str(e), "code": "API_ERROR"}), 502

    return jsonify({"ok": True, "feedback": feedback})


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
