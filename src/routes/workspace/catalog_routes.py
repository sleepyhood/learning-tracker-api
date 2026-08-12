"""
routes/workspace/catalog_routes.py

문제 카탈로그 및 커리큘럼 관련 API 라우트.
비즈니스 로직은 services.problem_catalog_service에 위임합니다.

엔드포인트 (6개):
  GET/POST /api/workspace/curriculums          - 커리큘럼 목록 조회/URL 업데이트
  POST     /api/workspace/batch_add_problems   - 문제 텍스트 파싱 & 일괄 추가
  GET      /api/workspace/search_problems      - 문제 검색 및 필터링
  POST     /api/workspace/update_problem_metadata - 문제 메타데이터 업데이트
  GET      /api/workspace/export_problem_metadata - 문제 메타데이터 Export
  POST     /api/workspace/import_problem_metadata - 문제 메타데이터 Import
"""

from flask import Blueprint, jsonify, request

from core.storage import _load_workspace_students
from services.problem_catalog_service import (
    batch_add_problems,
    export_problem_metadata,
    import_problem_metadata,
    load_curriculum_configs,
    load_registry_for_curriculum,
    save_curriculum_configs,
    search_problems_in_registry,
    update_problem_metadata,
)
from services.workspace_student_service import get_student_solved_sets
from utils.utils_common import ensure_admin_or_403

catalog_bp = Blueprint("workspace_catalog", __name__)


@catalog_bp.route("/api/workspace/curriculums", methods=["GET", "POST"])
def api_workspace_curriculums():
    s, err = ensure_admin_or_403()
    if err:
        return err

    if request.method == "GET":
        configs = load_curriculum_configs()
        return jsonify({"ok": True, "curriculums": configs})

    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    url = payload.get("url")
    if not key or url is None:
        return jsonify({"ok": False, "error": "key and url required"}), 400

    configs = load_curriculum_configs()
    target = next((c for c in configs if c.get("key") == key), None)
    if not target:
        return jsonify({"ok": False, "error": f"Curriculum key {key} not found"}), 404

    target["url"] = url.strip()
    save_curriculum_configs(configs)
    return jsonify({"ok": True, "curriculums": configs})


@catalog_bp.route("/api/workspace/batch_add_problems", methods=["POST"])
def api_workspace_batch_add_problems():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    major = payload.get("major", "").strip()
    sub = payload.get("sub", "").strip()
    raw_text = payload.get("raw_text", "").strip()

    if not key or not major or not sub or not raw_text:
        return jsonify({"ok": False, "error": "과정 키, 대단원, 소단원, 텍스트 입력이 모두 필요합니다."}), 400

    configs = load_curriculum_configs()
    if not any(c.get("key") == key for c in configs):
        return jsonify({"ok": False, "error": f"Invalid key: {key}"}), 404

    try:
        added_count, total_count = batch_add_problems(key, major, sub, raw_text, configs)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404

    return jsonify({"ok": True, "added_count": added_count, "total_count": total_count})


@catalog_bp.route("/api/workspace/search_problems")
def api_workspace_search_problems():
    s, err = ensure_admin_or_403()
    if err:
        return err

    q = request.args.get("q", "").strip().lower()
    curr_key = (request.args.get("curriculum") or request.args.get("curr") or "prog1").strip()
    chapter_filter = request.args.get("chapter", "all").strip()
    sub_filter = request.args.get("sub", "all").strip()
    display_id = request.args.get("display_id", "").strip()
    limit = int(request.args.get("limit", 80))

    configs = load_curriculum_configs()
    target_config = next((c for c in configs if c.get("key") == curr_key), None)
    registry = load_registry_for_curriculum(curr_key, configs)

    solved_set: set = set()
    wrong_set: set = set()
    if display_id:
        workspace_data = _load_workspace_students()
        solved_set, wrong_set = get_student_solved_sets(display_id, workspace_data)

    results, formatted_tree = search_problems_in_registry(
        registry=registry,
        q=q,
        chapter_filter=chapter_filter,
        sub_filter=sub_filter,
        solved_set=solved_set,
        wrong_set=wrong_set,
        curr_key=curr_key,
        target_config=target_config,
        limit=limit,
    )

    return jsonify({
        "ok": True,
        "problems": results,
        "tree": formatted_tree,
        "total_count": len(registry),
    })


@catalog_bp.route("/api/workspace/update_problem_metadata", methods=["POST"])
def api_workspace_update_problem_metadata():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}

    items_to_update = []
    if "prob_id" in payload or "id" in payload:
        items_to_update.append(payload)
    elif "problems" in payload and isinstance(payload["problems"], list):
        items_to_update = payload["problems"]

    if not items_to_update:
        return jsonify({"ok": False, "error": "prob_id 또는 problems 배열이 필요합니다."}), 400

    from services.problem_catalog_service import load_problem_custom_metadata
    updated_count = update_problem_metadata(items_to_update)
    total = len(load_problem_custom_metadata())
    return jsonify({"ok": True, "updated_count": updated_count, "total_custom_count": total})


@catalog_bp.route("/api/workspace/export_problem_metadata")
def api_workspace_export_problem_metadata():
    s, err = ensure_admin_or_403()
    if err:
        return err

    curr_key = (request.args.get("curriculum") or request.args.get("curr") or "prog1").strip()
    major_filter = request.args.get("major", "all").strip()
    sub_filter = request.args.get("sub", "all").strip()

    configs = load_curriculum_configs()
    registry = load_registry_for_curriculum(curr_key, configs)
    export_list, formatted_tree = export_problem_metadata(registry, major_filter, sub_filter)

    return jsonify({
        "ok": True,
        "problems": export_list,
        "tree": formatted_tree,
        "total_count": len(export_list),
        "curriculum_key": curr_key,
    })


@catalog_bp.route("/api/workspace/import_problem_metadata", methods=["POST"])
def api_workspace_import_problem_metadata():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    raw_text = payload.get("raw_text", "").strip()
    problems_arr = payload.get("problems") or []

    from services.problem_catalog_service import load_problem_custom_metadata
    updated_count = import_problem_metadata(raw_text, problems_arr)
    total = len(load_problem_custom_metadata())
    return jsonify({"ok": True, "updated_count": updated_count, "total_custom_count": total})
