"""
routes/workspace/student_routes.py

학생(수강생) 관련 API 라우트.
비즈니스 로직은 services.workspace_student_service에 위임합니다.

엔드포인트 (7개):
  GET  /workspace                            - 워크스페이스 메인 페이지
  GET  /api/workspace/schedule_students      - 학생 목록 + 슬롯 조회
  POST /api/workspace/register_student       - 학생 신규 등록
  POST /api/workspace/update_student_profile - 학생 프로필/계정 업데이트
  POST /api/workspace/update_student_accounts - 학생 프로필/계정 업데이트 (alias)
  POST /api/workspace/delete_student         - 학생 삭제
  GET  /api/workspace/student_problems/<id>  - 학생 풀었던 문제 목록
"""

from flask import Blueprint, jsonify, render_template, request, redirect

from services.workspace_student_service import (
    delete_student,
    get_schedule_students,
    get_student_problems,
    register_student,
    update_student_profile,
)
from utils.utils_common import ensure_admin_or_403, ensure_admin_or_redirect

student_bp = Blueprint("workspace_student", __name__)


@student_bp.route("/workspace")
def workspace_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    return redirect("/")


@student_bp.route("/api/workspace/schedule_students")
def api_workspace_schedule_students():
    s, err = ensure_admin_or_403()
    if err:
        return err

    weekday_str = request.args.get("weekday", "all")
    result_students, all_slots = get_schedule_students(weekday_str)
    return jsonify({"ok": True, "students": result_students, "all_slots": all_slots})


@student_bp.route("/api/workspace/register_student", methods=["POST"])
def api_workspace_register_student():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    name = payload.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "이름을 입력해주세요."}), 400

    result = register_student(
        name=name,
        birth_md=payload.get("birth_md", "").strip(),
        slot_id=payload.get("slot_id"),
        weekdays_input=payload.get("weekdays") or [],
        subjects_input=payload.get("subjects") or [],
    )
    return jsonify({"ok": True, **result})


@student_bp.route("/api/workspace/update_student_profile", methods=["POST"])
@student_bp.route("/api/workspace/update_student_accounts", methods=["POST"])
def api_workspace_update_student_profile():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    user_uuid = (payload.get("user_uuid") or payload.get("display_id") or "").strip()
    if not user_uuid:
        return jsonify({"ok": False, "error": "user_uuid 또는 display_id가 필요합니다."}), 400

    student = update_student_profile(user_uuid, payload)
    return jsonify({"ok": True, "student": student})


@student_bp.route("/api/workspace/delete_student", methods=["POST"])
def api_workspace_delete_student():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    req_id = (payload.get("display_id") or payload.get("user_uuid") or "").strip()
    if not req_id:
        return jsonify({"ok": False, "error": "display_id 또는 user_uuid가 필요합니다."}), 400

    try:
        deleted = delete_student(req_id)
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404

    return jsonify({"ok": True, "deleted": deleted})


@student_bp.route("/api/workspace/student_problems/<display_id>")
def api_workspace_student_problems(display_id):
    s, err = ensure_admin_or_403()
    if err:
        return err

    try:
        problems = get_student_problems(display_id)
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404

    return jsonify({"ok": True, "problems": problems})
