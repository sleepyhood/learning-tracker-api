"""
routes/workspace/crawler_routes.py

크롤러 트리거 및 상태 조회 API 라우트.
비즈니스 로직은 services.crawler_service에 위임합니다.

엔드포인트 (2개):
  GET  /api/workspace/crawl_status   - 크롤링 현재 상태 조회
  POST /api/workspace/trigger_crawl  - 백그라운드 크롤링 시작
"""

import os

from flask import Blueprint, jsonify, request

from config import PROBLEM_DIR
from services.crawler_service import get_crawl_status, trigger_crawl
from services.problem_catalog_service import load_curriculum_configs
from utils.utils_common import ensure_admin_or_403

crawler_bp = Blueprint("workspace_crawler", __name__)


@crawler_bp.route("/api/workspace/crawl_status")
def api_workspace_crawl_status():
    s, err = ensure_admin_or_403()
    if err:
        return err

    try:
        status = get_crawl_status()
        return jsonify({"ok": True, "status": status})
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@crawler_bp.route("/api/workspace/trigger_crawl", methods=["POST"])
def api_workspace_trigger_crawl():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    if not key:
        return jsonify({"ok": False, "error": "key is required"}), 400

    configs = load_curriculum_configs()
    target = next((c for c in configs if c.get("key") == key), None)
    if not target:
        return jsonify({"ok": False, "error": f"Invalid key: {key}"}), 404

    url = target.get("url")
    if not url:
        return jsonify({"ok": False, "error": "URL이 설정되지 않았습니다."}), 400

    target_file = os.path.join(PROBLEM_DIR, target.get("file", f"{key}_problems.json"))
    trigger_crawl(key, target, target_file)

    return jsonify({"ok": True, "message": "크롤링이 백그라운드에서 시작되었습니다."})
