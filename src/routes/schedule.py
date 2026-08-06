import json
import os
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, Response

from config import (
    PROBLEM_DIR,
    SERVER_DUMP_FILE,
    SERVER_TO_LEGACY_FILE,
    LEGACY_TO_SERVER_FILE,
    UNMATCHED_FILE,
    BASE_URL,
    RELAX_HOST_RESTRICTION,
    SESSION_COOKIE_DOMAIN,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
)
from core.storage import (
    load_schedule,
    save_schedule,
    hydrate_slot_students,
    _load_workspace_students,
    UNCERTAIN_WEEKDAY,
    UNCERTAIN_WEEKDAY_LABEL,
    WEEKDAY_LABELS,
)
from utils.utils_common import (
    ensure_admin_or_403,
    ensure_admin_or_redirect,
    ensure_login_or_redirect,
    ensure_problem_assets,
    ensure_user_cache_or_404,
    build_dashboard_viewmodel,
    role_ctx_from_session,
    fetch_profile,
    fetch_submissions_window,
    filter_main_account_submissions,
    merge_submissions_into_problems,
    resolve_legacy_map_path,
    resolve_legacy_map_dict,
    resolve_uuid,
    sanitize_filename,
    sync_user_problems_cache,
)
from utils.questions_api import save_server_problems_json
from utils.questions_crawler import (
    do_crawling,
    chapter_name as crawler_chapter_name,
    resolve_chapter_index,
    chapter_count as crawler_chapter_count,
)
from utils.summarizer import summarize_progress, summarize_user_chapter_group
from utils.streak_utils import generate_streak_data

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/schedule")
def schedule_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    raw = load_schedule()
    slots_by_wday = {i: [] for i in range(7)}
    slots_by_wday[UNCERTAIN_WEEKDAY] = []

    for slot in raw.get("slots", []):
        try:
            w = int(slot.get("weekday", 0))
        except (ValueError, TypeError):
            w = UNCERTAIN_WEEKDAY
        if w not in slots_by_wday:
            slots_by_wday[w] = []
        slots_by_wday[w].append(slot)

    hydrated_by_wday = {}
    for w, slots in slots_by_wday.items():
        hydrated_by_wday[w] = hydrate_slot_students(slots)

    wday_columns = []
    for w in range(7):
        wday_columns.append(
            {
                "weekday": w,
                "label": WEEKDAY_LABELS[w],
                "slots": hydrated_by_wday.get(w, []),
            }
        )

    uncertain_column = {
        "weekday": UNCERTAIN_WEEKDAY,
        "label": UNCERTAIN_WEEKDAY_LABEL,
        "slots": hydrated_by_wday.get(UNCERTAIN_WEEKDAY, []),
    }

    return render_template(
        "schedule.html",
        wday_columns=wday_columns,
        uncertain_column=uncertain_column,
    )


@schedule_bp.route("/schedule/add_slot", methods=["POST"])
def schedule_add_slot():
    s, err = ensure_admin_or_403()
    if err:
        return err

    label = (request.form.get("label") or "").strip()
    weekday_raw = (request.form.get("weekday") or "0").strip()
    note = (request.form.get("note") or "").strip()

    if not label:
        return jsonify({"ok": False, "error": "슬롯 이름을 입력하세요."}), 400

    try:
        weekday = int(weekday_raw)
    except ValueError:
        weekday = UNCERTAIN_WEEKDAY

    data = load_schedule()
    slots = data.setdefault("slots", [])

    from uuid import uuid4
    new_slot = {
        "id": str(uuid4()),
        "label": label,
        "weekday": weekday,
        "note": note,
        "students": [],
    }

    slots.append(new_slot)
    save_schedule(data)
    return jsonify({"ok": True, "slot": new_slot})


@schedule_bp.route("/schedule/delete_slot", methods=["POST"])
def schedule_delete_slot():
    s, err = ensure_admin_or_403()
    if err:
        return err

    slot_id = (request.form.get("slot_id") or "").strip()
    if not slot_id:
        return jsonify({"ok": False, "error": "slot_id가 필요합니다."}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])
    new_slots = [s for s in slots if s.get("id") != slot_id]
    if len(new_slots) == len(slots):
        return jsonify({"ok": False, "error": "slot not found"}), 404

    data["slots"] = new_slots
    save_schedule(data)
    return jsonify({"ok": True})


@schedule_bp.route("/update_problems", methods=["POST"])
def update_problems():
    s, err = ensure_admin_or_403()
    if err:
        return err
    os.makedirs(PROBLEM_DIR, exist_ok=True)

    payload = request.get_json(silent=True) or {}
    chapter_token = (
        payload.get("chapter")
        or request.form.get("chapter")
        or request.args.get("chapter")
        or ""
    )
    chapter_token = str(chapter_token).strip()
    refresh_api = payload.get("refresh_api")

    chapter_label = None
    if chapter_token and chapter_token.lower() != "all":
        try:
            chapter_index = resolve_chapter_index(chapter_token)
        except ValueError as e:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": str(e),
                        "valid_range": f"1-{crawler_chapter_count()}",
                    }
                ),
                400,
            )
        chapter_value = chapter_index + 1
        chapter_label = crawler_chapter_name(chapter_index)
        problem_file_path = do_crawling(
            output_dir=PROBLEM_DIR,
            filename="all_problems.json",
            chapter=chapter_value,
        )
        should_refresh_api = (
            bool(refresh_api) if refresh_api is not None else not os.path.exists(SERVER_DUMP_FILE)
        )
    else:
        problem_file_path = do_crawling(
            output_dir=PROBLEM_DIR, filename="all_problems.json"
        )
        should_refresh_api = True if refresh_api is None else bool(refresh_api)

    api_result = None
    if should_refresh_api:
        try:
            api_result = save_server_problems_json(PROBLEM_DIR, BASE_URL)
        except Exception as e:
            api_result = {"ok": False, "error": str(e)}

    map_result = None
    try:
        all_prob_path = os.path.join(PROBLEM_DIR, "all_problems.json")
        serv_prob_path = os.path.join(PROBLEM_DIR, "server_problems.json")
        if os.path.exists(all_prob_path) and os.path.exists(serv_prob_path):
            map_stats = build_legacy_map(
                all_problems_path=all_prob_path,
                server_problems_path=serv_prob_path,
                out_dir=PROBLEM_DIR,
            )
            map_result = {"ok": True, "stats": map_stats}
        else:
            map_result = {"ok": False, "error": "매핑에 필요한 JSON 파일이 부족합니다."}
    except Exception as e:
        map_result = {"ok": False, "error": str(e)}

    return jsonify(
        {
            "ok": True,
            "chapter_token": chapter_token or "ALL",
            "chapter_label": chapter_label,
            "problem_file": problem_file_path,
            "api_result": api_result,
            "map_result": map_result,
        }
    )


@schedule_bp.route("/api/streak")
def api_streak():
    s, err = ensure_admin_or_403()
    if err:
        return err

    username = request.args.get("username", "").strip()
    days = request.args.get("days", "365")
    try:
        days = int(days)
    except ValueError:
        days = 365

    if not username:
        return jsonify({"error": "username parameter is required"}), 400

    u = resolve_uuid(username)
    data, ok = ensure_user_cache_or_404(u, s, max_age_seconds=600)
    if not ok:
        return jsonify({"error": f"Failed to fetch user data for {username}"}), 500

    submissions = data.get("submissions", [])
    streak_info = generate_streak_data(submissions, days=days)
    return jsonify(streak_info)


@schedule_bp.route("/proxy/user_rank")
def proxy_user_rank():
    s, err = ensure_admin_or_403()
    if err:
        return err

    page = request.args.get("page", "1")
    url = f"{BASE_URL}/user_rank?page={page}"
    try:
        resp = s.get(url, timeout=10)
        return Response(
            resp.content, status=resp.status_code, content_type=resp.headers.get("content-type")
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@schedule_bp.route("/", methods=["GET", "POST"])
def index():
    ensure_problem_assets()

    if request.method == "POST":
        query = request.form.get("username", "").strip()
        if query:
            return redirect(f"/user/{query}")
        return redirect("/")

    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    days = int(request.args.get("days", 7))
    me_json = fetch_profile(s, username=None)
    vm = build_dashboard_viewmodel(s, me_json, is_me=True, days=days)
    vm["streak_days"] = days
    my_name = me_json.get("data", {}).get("user", {}).get("username") if isinstance(me_json, dict) else ""
    my_uuid = resolve_uuid(my_name) if my_name else ""
    role_ctx = role_ctx_from_session()
    return render_template(
        "index.html",
        **vm,
        view_mode="me",
        view_username="",
        user_uuid=my_uuid,
        viewer_is_admin=role_ctx.get("is_admin", False),
    )



@schedule_bp.route("/user/<username>")
def user_dashboard(username):
    ensure_problem_assets()

    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    try:
        other_json = fetch_profile(s, username=username)
    except Exception as e:
        return f"❌ 사용자 정보를 불러오지 못했습니다: {e}", 500

    days = int(request.args.get("days", 7))
    vm = build_dashboard_viewmodel(s, other_json, is_me=False, days=days)
    vm["streak_days"] = days

    other_name = other_json.get("data", {}).get("user", {}).get("username") if isinstance(other_json, dict) else username
    other_uuid = resolve_uuid(other_name)

    role_ctx = role_ctx_from_session()
    return render_template(
        "index.html",
        **vm,
        view_mode="user",
        view_username=username,
        user_uuid=other_uuid,
        viewer_is_admin=role_ctx.get("is_admin", False),
    )



@schedule_bp.route("/user/<username>/chapter/<chapter>/workspace")
def user_chapter_workspace(username, chapter):
    ensure_problem_assets()

    s, err = ensure_login_or_redirect()
    if err:
        return err

    u = resolve_uuid(username)
    data, ok = ensure_user_cache_or_404(u, s, max_age_seconds=600)
    if not ok:
        return render_template("error.html", message=f"[{username}] 유저 정보를 불러올 수 없습니다."), 404

    role_ctx = role_ctx_from_session()

    vm = build_dashboard_viewmodel(
        username_raw=username,
        user_uuid=u,
        profile=data.get("profile", {}),
        submissions=data.get("submissions", []),
        problems_dict=data.get("problems_dict", {}),
        role_ctx=role_ctx,
    )
    return render_template(
        "user_chapter_workspace.html",
        username=username,
        user_uuid=u,
        chapter=chapter,
        vm=vm,
        role_ctx=role_ctx,
    )


@schedule_bp.route("/user/<username>/chapter/<chapter>")
def user_chapter_view(username, chapter):
    ensure_problem_assets()

    s, err = ensure_login_or_redirect()
    if err:
        return err

    u = resolve_uuid(username)
    data, ok = ensure_user_cache_or_404(u, s, max_age_seconds=600)
    if not ok:
        return render_template("error.html", message=f"[{username}] 유저 정보를 불러올 수 없습니다."), 404

    role_ctx = role_ctx_from_session()

    vm = build_dashboard_viewmodel(
        username_raw=username,
        user_uuid=u,
        profile=data.get("profile", {}),
        submissions=data.get("submissions", []),
        problems_dict=data.get("problems_dict", {}),
        role_ctx=role_ctx,
    )
    return render_template(
        "user_chapter_view.html",
        username=username,
        user_uuid=u,
        chapter=chapter,
        vm=vm,
        role_ctx=role_ctx,
    )


@schedule_bp.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def user_chapter_group_view(username, chapter, group_id):
    ensure_problem_assets()

    s, err = ensure_login_or_redirect()
    if err:
        return err

    u = resolve_uuid(username)
    data, ok = ensure_user_cache_or_404(u, s, max_age_seconds=600)
    if not ok:
        return render_template("error.html", message=f"[{username}] 유저 정보를 불러올 수 없습니다."), 404

    role_ctx = role_ctx_from_session()

    vm = build_dashboard_viewmodel(
        username_raw=username,
        user_uuid=u,
        profile=data.get("profile", {}),
        submissions=data.get("submissions", []),
        problems_dict=data.get("problems_dict", {}),
        role_ctx=role_ctx,
    )
    return render_template(
        "user_chapter_group_view.html",
        username=username,
        user_uuid=u,
        chapter=chapter,
        group_id=group_id,
        vm=vm,
        role_ctx=role_ctx,
    )
