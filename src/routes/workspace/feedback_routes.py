"""
routes/workspace/feedback_routes.py

숙제 및 알림장 이력 저장 API 라우트.
비즈니스 로직은 services.workspace_student_service에 위임합니다.

엔드포인트:
  POST /api/workspace/save_homework_log          - 학생 숙제 및 알림장 이력 저장
  GET  /api/public/student-today-summary         - 구글 문서 사이드바(OJ 탭) 전용: 당일 학생 요약 조회
"""

from flask import Blueprint, jsonify, request

from services.workspace_student_service import save_homework_log, get_student_today_summary
from utils.utils_common import ensure_admin_or_403

feedback_bp = Blueprint("workspace_feedback", __name__)


@feedback_bp.route("/api/workspace/save_homework_log", methods=["POST"])
def api_workspace_save_homework_log():
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    user_uuid = payload.get("user_uuid")
    problems = payload.get("problems", [])

    log_payload = {
        "problems": problems,
        "title": payload.get("title", ""),
        "comment": payload.get("comment", ""),
        "teacher_memo": payload.get("teacher_memo", ""),
        "message": payload.get("message", ""),
        "mode": payload.get("mode", "homework" if len(problems) > 0 else "comment"),
    }

    try:
        save_homework_log(display_id, user_uuid, log_payload)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"저장 실패: {e}"}), 500

    return jsonify({"ok": True})


@feedback_bp.route("/api/public/student-today-summary", methods=["GET"])
def api_public_student_today_summary():
    """
    구글 문서 사이드바(OJ 피드백 탭) 전용 당일 학생 요약 조회 API.

    Query Parameters (최소 하나 필수):
        display_id   - 학원 내부 계정 ID (e.g. 'hong123')
        user_uuid    - 내부 UUID (e.g. '3a6d3624-...')
        portal_id    - 학원 포탈 학생 번호 (e.g. '104')
        date         - 조회 날짜 'YYYY-MM-DD' (생략 시 오늘 KST)

    Response:
        {
            "ok": true,
            "student_name": "홍길동",
            "display_id": "hong123",
            "user_uuid": "3a6d3624-...",
            "portal_id": "104",
            "date": "2026-08-29",
            "solved_problems":   [{code, title, result, language, date}, ...],
            "wrong_problems":    [{code, title, result, language, date}, ...],
            "homework_problems": [{legacy_code, title, server_problem_id}, ...],
            "teacher_memo": "오답 디버깅 스스로 완료함",
            "mode": "homework"
        }
    """
    display_id = request.args.get("display_id", "").strip() or None
    user_uuid  = request.args.get("user_uuid",  "").strip() or None
    portal_id  = request.args.get("portal_id",  "").strip() or None
    name       = request.args.get("name",       "").strip() or None
    date_str   = request.args.get("date",        "").strip() or None

    if not any([display_id, user_uuid, portal_id, name]):
        return jsonify({"ok": False, "error": "display_id, user_uuid, portal_id, name 중 하나 이상 필요합니다."}), 400

    try:
        result = get_student_today_summary(
            display_id=display_id,
            user_uuid=user_uuid,
            portal_id=portal_id,
            name=name,
            date_str=date_str,
        )
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": f"조회 실패: {e}"}), 500

    return jsonify(result)


@feedback_bp.route("/api/public/search-accounts", methods=["GET"])
def api_public_search_accounts():
    """
    구글 문서 사이드바 계정 검색용:
    1,040명 학생 목록에서 실시간 자동완성 검색 결과를 반환합니다.
    Query Parameter: q (검색어)
    """
    from services.workspace_student_service import search_public_student_accounts
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ok": True, "results": []})

    results = search_public_student_accounts(q, limit=10)
    return jsonify({"ok": True, "results": results})


@feedback_bp.route("/api/public/update-student-mapping", methods=["POST"])
def api_public_update_student_mapping():
    """
    구글 문서 사이드바에서 학생의 매핑 계정을 변경했을 때 영구 저장합니다.
    Body JSON: { portal_id: "151", oj_display_id: "이서율08123", student_name: "이서율" }
    """
    from services.workspace_student_service import update_portal_student_mapping
    payload = request.get_json(force=True) or {}
    portal_id = str(payload.get("portal_id", "")).strip()
    oj_display_id = str(payload.get("oj_display_id", "")).strip()
    student_name = payload.get("student_name")

    if not portal_id or not oj_display_id:
        return jsonify({"ok": False, "error": "portal_id와 oj_display_id가 필요합니다."}), 400

    try:
        res = update_portal_student_mapping(portal_id, oj_display_id, student_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


