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
    KST,
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
from utils.legacy_map import build_legacy_map
from utils.questions_crawler import (
    do_crawling,
    chapter_name as crawler_chapter_name,
    resolve_chapter_index,
    chapter_count as crawler_chapter_count,
)
from utils.summarizer import summarize_progress, summarize_user_chapter_group
from utils.streak_utils import generate_streak_data
from utils.playwright_crawler import get_crawl_status

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/api/crawl_status")
def api_crawl_status():
    status = get_crawl_status()
    # If no in-memory crawl has run yet, enrich with metadata from saved JSON files
    if not status.get("last_crawled"):
        curr = request.args.get("curr", "prog1")
        filename = "prog2_problems.json" if curr == "prog2" else "all_problems.json"
        fpath = os.path.join(PROBLEM_DIR, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                status["last_crawled"] = saved.get("_last_updated", "")
                status["last_crawled_stats"] = saved.get("_stats", {})
            except Exception:
                pass
    return jsonify(status)



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
    try:
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
        curr_key = (
            payload.get("curr")
            or payload.get("curr_key")
            or request.form.get("curr")
            or request.args.get("curr")
            or request.args.get("curr_key")
            or "prog1"
        )
        chapter_token = str(chapter_token).strip()
        curr_key = str(curr_key).strip().lower()
        refresh_api = payload.get("refresh_api")
        show_browser_val = (
            payload.get("show_browser")
            or request.args.get("show_browser")
            or request.form.get("show_browser")
        )
        is_headless = not (str(show_browser_val).lower() in ("true", "1", "yes"))

        username_val = (
            payload.get("username")
            or request.args.get("username")
            or request.form.get("username")
            or ""
        )
        password_val = (
            payload.get("password")
            or request.args.get("password")
            or request.form.get("password")
            or ""
        )
        timeout_sec_val = (
            payload.get("timeout_sec")
            or request.args.get("timeout_sec")
            or request.form.get("timeout_sec")
            or 60
        )
        try:
            timeout_sec = int(timeout_sec_val)
        except Exception:
            timeout_sec = 60

        if curr_key == "prog2":
            output_filename = "prog2_problems.json"
            target_url = f"{BASE_URL}/p102"
        else:
            output_filename = "all_problems.json"
            target_url = f"{BASE_URL}/p101"

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
                filename=output_filename,
                chapter=chapter_value,
                url=target_url,
                headless=is_headless,
                username=username_val,
                password=password_val,
                timeout_sec=timeout_sec,
            )
            should_refresh_api = (
                bool(refresh_api) if refresh_api is not None else not os.path.exists(SERVER_DUMP_FILE)
            )
        else:
            problem_file_path = do_crawling(
                output_dir=PROBLEM_DIR,
                filename=output_filename,
                url=target_url,
                headless=is_headless,
                username=username_val,
                password=password_val,
                timeout_sec=timeout_sec,
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
            all_prob_path = os.path.join(PROBLEM_DIR, output_filename)
            serv_prob_path = os.path.join(PROBLEM_DIR, "server_problems.json")
            if os.path.exists(all_prob_path) and os.path.exists(serv_prob_path):
                map_stats = build_legacy_map(
                    all_prob_path,
                    serv_prob_path,
                    out_map_path=os.path.join(PROBLEM_DIR, "legacy_map.json"),
                    out_unmatched_path=os.path.join(PROBLEM_DIR, "legacy_unmatched.json"),
                )
                map_result = {"ok": True, "stats": map_stats}
        except Exception as e:
            map_result = {"ok": False, "error": str(e)}

        now_str = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S")

        # Read scraped_count from crawler status — used by frontend to detect 0-item failures
        try:
            from utils.playwright_crawler import get_crawl_status
            crawl_status = get_crawl_status()
            scraped_count = crawl_status.get("scraped_count", -1)
        except Exception:
            scraped_count = -1

        return jsonify(
            {
                "status": "success",
                "ok": True,
                "curr": curr_key,
                "last_updated": now_str,
                "scraped_count": scraped_count,
                "crawling": {
                    "file": problem_file_path,
                    "chapter": chapter_label,
                    "output_filename": output_filename,
                },
                "api_refresh": api_result,
                "legacy_map": map_result,
            }
        )

    except Exception as exc:
        import traceback
        err_msg = f"[update_problems] Exception: {exc}\n{traceback.format_exc()}"
        print(err_msg)
        return jsonify({"ok": False, "status": "error", "error": str(exc), "details": err_msg}), 500


@schedule_bp.route("/api/streak")
def api_streak():
    s, err = ensure_login_or_redirect()
    if err:
        return jsonify({"error": "Unauthorized"}), 401

    username = request.args.get("username", "").strip() or request.args.get("viewUsername", "").strip()
    days = request.args.get("days", "7")
    try:
        days = int(days)
    except ValueError:
        days = 7

    # username이 UUID인 경우 실제 username으로 역변환
    if not username or (len(username) == 36 and "-" in username):
        # UUID로 들어왔거나 비어있으면 doc에서 username 꺼내기
        uuid_key = username or ""
        try:
            from utils.utils_user_doc import load_doc_by_any
            doc = load_doc_by_any(uuid_key) if uuid_key else {}
            username = (doc.get("profile") or {}).get("student_id") or (doc.get("profile") or {}).get("username") or ""
        except Exception:
            pass

    if not username:
        try:
            me_json = fetch_profile(s, username=None)
            if isinstance(me_json, dict):
                username = me_json.get("data", {}).get("user", {}).get("username", "")
        except Exception:
            pass

    if not username:
        return jsonify({"error": "username parameter is required"}), 400

    # fetch_submissions_window: create_time이 포함된 실제 제출 로그 리스트 취득
    try:
        fetch_days = max(days, 30)  # 최소 30일치 가져와 streak 범위 확보
        submissions = fetch_submissions_window(s, username, myself=0, days=fetch_days, limit=200)
        filtered = filter_main_account_submissions(submissions, username)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch submissions for {username}: {e}"}), 500

    streak_info = generate_streak_data(filtered, days=days)
    return jsonify(streak_info)


@schedule_bp.route("/api/submission_code")
def api_submission_code():
    """DoingCoding 제출 상세 코드를 프록시하여 반환."""
    s, err = ensure_login_or_redirect()
    if err:
        return jsonify({"error": "Unauthorized"}), 401

    sub_id = request.args.get("id", "").strip()
    if not sub_id:
        return jsonify({"error": "id parameter is required"}), 400

    try:
        resp = s.get(f"{BASE_URL}/api/submission", params={"id": sub_id}, timeout=10)
        if not resp.ok:
            return jsonify({"error": f"upstream error {resp.status_code}"}), resp.status_code

        # DoingCoding이 HTML 에러 페이지를 돌려줄 경우 방어
        ct = resp.headers.get("content-type", "")
        if "application/json" not in ct:
            return jsonify({"error": f"upstream returned non-JSON ({ct[:40]}): {resp.text[:80]}"}), 502

        try:
            payload = resp.json()
        except Exception:
            return jsonify({"error": f"upstream response is not valid JSON: {resp.text[:80]}"}), 502

        upstream_error = payload.get("error")
        if upstream_error:
            return jsonify({"error": f"upstream error: {upstream_error}"}), 403

        data = payload.get("data") or {}
        code = data.get("code")
        if code is None:
            return jsonify({"error": "code not available (not shared or no permission)"}), 404
        return jsonify({
            "id": sub_id,
            "code": code,
            "language": data.get("language", ""),
            "result": data.get("result"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@schedule_bp.route("/proxy/user_rank")
def proxy_user_rank():
    s, err = ensure_admin_or_403()
    if err:
        return jsonify({"error": "Forbidden"}), 403

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
    curr_key = request.args.get("curr", "prog1")
    me_json = fetch_profile(s, username=None)
    vm = build_dashboard_viewmodel(s, me_json, is_me=True, days=days, curr_key=curr_key)
    vm["streak_days"] = days
    my_name = me_json.get("data", {}).get("user", {}).get("username") if isinstance(me_json, dict) else ""
    my_uuid = resolve_uuid(my_name) if my_name else ""
    role_ctx = role_ctx_from_session()
    return render_template(
        "index.html",
        **vm,
        view_mode="me",
        view_username=my_name,
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
    curr_key = request.args.get("curr", "prog1")
    vm = build_dashboard_viewmodel(s, other_json, is_me=False, days=days, curr_key=curr_key)
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
        "chapter_workspace.html",
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

    all_chapters = vm.get("progress_data", [])
    target_ch = next((c for c in all_chapters if c.get("chapter") == chapter), None)
    if not target_ch:
        ch_num = chapter.split(".")[0].strip()
        target_ch = next((c for c in all_chapters if str(c.get("chapter", "")).startswith(ch_num + ".")), None)

    chapter_name = target_ch.get("chapter", chapter) if target_ch else chapter
    groups_progress = target_ch.get("groups", []) if target_ch else []

    return render_template(
        "chapter_detail.html",
        username=username,
        user_uuid=u,
        chapter=chapter,
        chapter_name=chapter_name,
        progress_data=groups_progress,
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

    group_title = group_id
    problem_names = []
    try:
        from config import PROBLEM_FILE
        from urllib.parse import quote
        from utils.summarizer import summarize_user_chapter_group

        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            all_problems = json.load(f)

        real_chapter = chapter
        if real_chapter not in all_problems:
            ch_num = chapter.split(".")[0].strip()
            real_chapter = next((ch_k for ch_k in all_problems.keys() if ch_k.startswith(ch_num + ".")), chapter)

        group_res = summarize_user_chapter_group(
            data.get("problems_dict") or data,
            all_problems,
            real_chapter,
            group_id,
            legacy_map=resolve_legacy_map_dict()
        )
        group_title = group_res.get("group_title", group_id)
        problem_names = group_res.get("problem_names", [])
    except Exception as e:
        print(f"[user_chapter_group_view] Error: {e}")

    return render_template(
        "group_detail.html",
        username=username,
        user_uuid=u,
        chapter=chapter,
        group_id=group_id,
        group_title=group_title,
        problem_names=problem_names,
        chapter_url_html=f"http://edu.doingcoding.com/user/{username}/chapter/{quote(chapter)}",
        vm=vm,
        role_ctx=role_ctx,
    )
