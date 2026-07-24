from flask import Flask, request, render_template, redirect, url_for
import json
import ipaddress

from flask import jsonify
import requests
from login import load_cookies, get_authenticated_session, is_cookie_valid, clear_active_session
from datetime import datetime, timezone, timedelta
from pprint import pprint
from utils.streak_utils import generate_streak_data
from pathlib import Path

from flask_cors import CORS

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os
from uuid import uuid4


from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import webbrowser
from utils.questions_crawler import (
    do_crawling,
    chapter_name as crawler_chapter_name,
    resolve_chapter_index,
    chapter_count as crawler_chapter_count,
)

from utils.summarizer import (
    summarize_progress,
    summarize_user_chapter_group,
)  # 너가 사용하는 함수 경로에 따라 조정 필요


from utils.questions_api import save_server_problems_json
from utils.legacy_map import build_legacy_map
from utils.utils_common import (
    ensure_login_or_redirect,
    ensure_admin_or_403,
    ensure_admin_or_redirect,
    fetch_profile,
    fetch_submissions_window,
    filter_main_account_submissions,
    sanitize_filename,
    ensure_problem_assets,
    build_dashboard_viewmodel,
    role_ctx_from_session,
    sync_user_problems_cache,
    ensure_user_cache_or_404,
    resolve_legacy_map_path,
    resolve_legacy_map_dict,
    resolve_uuid,
    merge_submissions_into_problems,
)


from config import (
    USER_DATA_DIR,
    PROBLEM_DIR,
    BASE_URL,
    PROBLEM_FILE,
    SERVER_DUMP_FILE,
    SERVER_TO_LEGACY_FILE,
    LEGACY_TO_SERVER_FILE,
    UNMATCHED_FILE,
    USER_DATA_DIR,
    COOKIE_PATH,
    ADMIN_DOMAIN,
    STUDENT_DOMAIN,
    SESSION_COOKIE_DOMAIN,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    CORS_ALLOWED_ORIGINS,
)  # 필요 시 조정


from config import RELAX_HOST_RESTRICTION

#########

from utils.utils_user_doc import (
    load_doc_by_any,
    save_doc_by_any,
    _user_doc_path_by_uuid,
)
import uuid

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
META_DIR = PROJECT_ROOT / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

# UUID 레지스트리(레거시ID ↔ UUID 매핑) 파일 경로
UUIDS_PATH = META_DIR / "uuids.json"
UUIDS_PATH.parent.mkdir(parents=True, exist_ok=True)
if not UUIDS_PATH.exists():
    UUIDS_PATH.write_text("{}", encoding="utf-8")

KST = timezone(timedelta(hours=9))

# homework_latest_batch에서 학생별 submissions 조회 결과를 짧게 캐시
TODAY_ACTIVITY_CACHE: dict[str, dict] = {}
TODAY_ACTIVITY_CACHE_LOCK = threading.Lock()
TODAY_ACTIVITY_CACHE_MAX = 5000




# ===== 요일별 스케줄 저장용 =====
SCHEDULE_PATH = META_DIR / "schedule.json"
SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]
UNCERTAIN_WEEKDAY = -1
UNCERTAIN_WEEKDAY_LABEL = "일정 불확실"


def load_schedule() -> dict:
    """요일별 수업 스케줄 JSON 로드."""
    try:
        if SCHEDULE_PATH.exists():
            return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print("[schedule] load error:", e)
    return {"slots": []}


def save_schedule(data: dict) -> dict:
    """스케줄 JSON 저장."""
    try:
        SCHEDULE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("[schedule] save error:", e)
    return data


def hydrate_slot_students(slots):
    """
    슬롯에 들어있는 students 리스트( uuid 또는 student_id )를
    화면에서 쓰기 좋은 dict 리스트로 변환.
    """
    hydrated = []
    for slot in slots:
        students_detail = []
        notes = slot.get("student_notes") or {}
        for token in slot.get("students", []):
            # token: user_uuid 또는 student_id
            try:
                doc = load_doc_by_any(token)
            except Exception:
                doc = {}

            profile = doc.get("profile") or {}
            student_id = (
                profile.get("student_id")
                or reverse_lookup(token)
                or str(token)
            )
            name = profile.get("name") or student_id
            user_uuid = doc.get("user_uuid") or resolve_uuid(student_id)
            note = ""
            if isinstance(notes, dict):
                note = (
                    notes.get(user_uuid)
                    or notes.get(student_id)
                    or notes.get(str(token))
                    or ""
                )

            students_detail.append(
                {
                    "user_uuid": user_uuid,
                    "student_id": student_id,
                    "name": name,
                    "note": str(note or "").strip(),
                }
            )

        merged = dict(slot)
        merged["students_detail"] = students_detail
        hydrated.append(merged)

    return hydrated

# app.py 어딘가(라우트 위) 유틸 함수로 추가


def reverse_lookup(user_uuid: str) -> str | None:
    """UUID에서 레거시 student_id를 찾아 반환."""
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    for sid, u in m.items():
        if u == user_uuid:
            return sid
    return None


# def _user_file_path(student_id: str) -> Path:
#     safe = sanitize_filename(student_id)
#     return Path(USER_DATA_DIR) / f"{safe}.json"


# def _load_user_doc(student_id: str) -> dict:
#     """기존 파일이 배열형(oi_problems만 저장)이어도 dict 구조로 승격."""
#     p = _user_file_path(student_id)
#     if not p.exists():
#         return {
#             "profile": {"student_id": student_id},
#             "oi_problems": [],
#             "homework_logs": [],
#         }
#     raw = json.loads(p.read_text(encoding="utf-8"))
#     if isinstance(raw, list):
#         # 과거 포맷: 문제배열만 저장하던 파일
#         return {
#             "profile": {"student_id": student_id},
#             "oi_problems": raw,
#             "homework_logs": [],
#         }
#     # dict 보장 + 기본키 보강
#     raw.setdefault("profile", {"student_id": student_id})
#     raw.setdefault("oi_problems", raw.get("problems", []))
#     raw.setdefault("homework_logs", [])
#     return raw


# def _save_user_doc(student_id: str, doc: dict):
#     p = _user_file_path(resolve_uuid(student_id))
#     print(f"p: {p}")
#     p.parent.mkdir(parents=True, exist_ok=True)
#     p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


# 기존: def append_homework_log(student_id: str, payload: dict) -> dict:
def append_homework_log(user_uuid: str, payload: dict) -> dict:
    doc = load_doc_by_any(user_uuid)
    doc.setdefault("user_uuid", user_uuid)

    payload = payload or {}
    payload.setdefault("channel", "kakao")
    payload.setdefault("message", "")
    payload.setdefault("title", "")
    payload.setdefault("url", "")
    payload.setdefault("problems", [])

    from uuid import uuid4

    log = dict(payload)
    log["id"] = log.get("id") or str(uuid4())
    log["log_id"] = log.get("log_id") or log["id"]

    # 문제 매핑
    log["problems"] = []
    with open(LEGACY_TO_SERVER_FILE, encoding="utf-8") as f:
        legacy_to_server = json.load(f)

    for ent in list(payload["problems"]):
        if isinstance(ent, dict):
            legacy_code = ent.get("legacy_code") or ent.get("code") or ""
            title = ent.get("title") or ent.get("title_at_issue") or ""
        else:
            legacy_code = str(ent)
            title = ""
        log["problems"].append(
            {
                "legacy_code": legacy_code,
                "server_problem_id": legacy_to_server.get(legacy_code),
                "title": title,
            }
        )

    log.setdefault("ts", datetime.now(tz=KST).isoformat())

    # 최신이 위로 보이고 싶으면 insert(0), 기본은 append
    doc.setdefault("homework_logs", []).append(log)

    path = save_doc_by_any(user_uuid, doc)  # ✅ 여기서 딱 한 번 저장
    print(f"[HW] saved -> {path}, logs={len(doc['homework_logs'])}")
    return doc


#########


# app = Flask(__name__)
app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)  # ✅ 여기에 바로 설정

if SESSION_COOKIE_DOMAIN:
    app.config["SESSION_COOKIE_DOMAIN"] = SESSION_COOKIE_DOMAIN
app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE

cors_origins = CORS_ALLOWED_ORIGINS or []
if not cors_origins and ADMIN_DOMAIN:
    cors_origins.append(f"https://{ADMIN_DOMAIN}")
if not cors_origins and STUDENT_DOMAIN:
    cors_origins.append(f"https://{STUDENT_DOMAIN}")

if not cors_origins:
    cors_origins.extend(["http://localhost:5000", "http://127.0.0.1:5000"])

CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

CHAPTER_WORKSPACE_BETA_ENABLED = (
    os.environ.get("CHAPTER_WORKSPACE_BETA_ENABLED", "0").strip().lower()
    in ("1", "true", "yes", "on")
)
CHAPTER_WORKSPACE_BETA_USERS = {
    x.strip()
    for x in os.environ.get("CHAPTER_WORKSPACE_BETA_USERS", "").split(",")
    if x.strip()
}
CHAPTER_WORKSPACE_DEFAULT_ENABLED = (
    os.environ.get("CHAPTER_WORKSPACE_DEFAULT_ENABLED", "0").strip().lower()
    in ("1", "true", "yes", "on")
)
CHAPTER_WORKSPACE_DEFAULT_USERS = {
    x.strip()
    for x in os.environ.get("CHAPTER_WORKSPACE_DEFAULT_USERS", "").split(",")
    if x.strip()
}
CHAPTER_WORKSPACE_EVENTS_PATH = META_DIR / "chapter_workspace_events.jsonl"
CHAPTER_WORKSPACE_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- imports 상단 ---
from flask import session as fsession
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
import os, json
from collections import defaultdict

ADMIN_ONLY_PREFIXES = (
    "/schedule",
    "/api/schedule",
    "/update_problems",
    "/api/students",
    "/students",
    "/refresh_user",
    "/proxy/user_rank",
)

STUDENT_ONLY_PREFIXES = (
    "/user",
    "/api/streak",
)


def _is_localhost(host: str) -> bool:
    return host in ("localhost", "127.0.0.1")


def _is_private_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private)


def _is_admin_route(path: str) -> bool:
    return path in ADMIN_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in ADMIN_ONLY_PREFIXES
    )


def _is_student_route(path: str) -> bool:
    return path in STUDENT_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in STUDENT_ONLY_PREFIXES
    )


def _workspace_beta_enabled_for(username: str) -> bool:
    if CHAPTER_WORKSPACE_BETA_ENABLED:
        return True
    return bool(username and username in CHAPTER_WORKSPACE_BETA_USERS)


def _workspace_default_enabled_for(username: str) -> bool:
    if CHAPTER_WORKSPACE_DEFAULT_ENABLED:
        return True
    return bool(username and username in CHAPTER_WORKSPACE_DEFAULT_USERS)


def _workspace_route_enabled_for(username: str) -> bool:
    return _workspace_default_enabled_for(username) or _workspace_beta_enabled_for(username)


def _append_workspace_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with CHAPTER_WORKSPACE_EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_workspace_events(limit_days: int = 14) -> list[dict]:
    if limit_days <= 0:
        limit_days = 1
    cutoff = datetime.now(tz=KST) - timedelta(days=limit_days)
    events: list[dict] = []
    if not CHAPTER_WORKSPACE_EVENTS_PATH.exists():
        return events

    with CHAPTER_WORKSPACE_EVENTS_PATH.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso_datetime(ev.get("ts"))
            if not ts:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=KST)
            ts = ts.astimezone(KST)
            if ts < cutoff:
                continue
            ev["_ts"] = ts
            ev["_date"] = ts.date().isoformat()
            events.append(ev)
    return events


def _build_workspace_event_summary(events: list[dict]) -> dict:
    daily: dict[str, dict] = {}
    sessions_with_group_switch = set()
    sessions_with_save_success = set()
    group_switch_by_group: dict[str, int] = {}
    save_success_by_group: dict[str, int] = {}
    totals = {
        "workspace_load_succeeded": 0,
        "workspace_load_failed": 0,
        "workspace_save_succeeded": 0,
        "workspace_save_failed": 0,
        "workspace_copy_selected": 0,
        "group_switch": 0,
    }

    for ev in events:
        name = ev.get("event_name") or ""
        date_key = ev.get("_date")
        group_id = (ev.get("group") or "").strip() or "(none)"
        session_id = (ev.get("session_id") or "").strip()

        if date_key not in daily:
            daily[date_key] = {
                "date": date_key,
                "workspace_load_succeeded": 0,
                "workspace_load_failed": 0,
                "workspace_save_succeeded": 0,
                "workspace_save_failed": 0,
                "workspace_copy_selected": 0,
                "group_switch": 0,
            }

        if name in totals:
            totals[name] += 1
            daily[date_key][name] += 1

        if name == "group_switch":
            group_switch_by_group[group_id] = group_switch_by_group.get(group_id, 0) + 1
            if session_id:
                sessions_with_group_switch.add(session_id)
        elif name == "workspace_save_succeeded":
            save_success_by_group[group_id] = save_success_by_group.get(group_id, 0) + 1
            if session_id:
                sessions_with_save_success.add(session_id)

    daily_rows = []
    for _, row in sorted(daily.items(), key=lambda kv: kv[0]):
        save_attempts = row["workspace_save_succeeded"] + row["workspace_save_failed"]
        row["save_attempts"] = save_attempts
        row["save_failure_rate"] = round(
            (row["workspace_save_failed"] / save_attempts) * 100, 2
        ) if save_attempts else 0.0
        daily_rows.append(row)

    total_save_attempts = totals["workspace_save_succeeded"] + totals["workspace_save_failed"]
    total_save_failure_rate = round(
        (totals["workspace_save_failed"] / total_save_attempts) * 100, 2
    ) if total_save_attempts else 0.0

    conversion_den = len(sessions_with_group_switch)
    conversion_num = len(sessions_with_group_switch & sessions_with_save_success)
    conversion_rate = round((conversion_num / conversion_den) * 100, 2) if conversion_den else 0.0

    group_rows = []
    for group_id in sorted(set(group_switch_by_group.keys()) | set(save_success_by_group.keys())):
        switches = group_switch_by_group.get(group_id, 0)
        saves = save_success_by_group.get(group_id, 0)
        group_rows.append(
            {
                "group": group_id,
                "group_switch": switches,
                "workspace_save_succeeded": saves,
                "save_per_switch": round((saves / switches) * 100, 2) if switches else 0.0,
            }
        )

    return {
        "totals": {
            **totals,
            "save_attempts": total_save_attempts,
            "save_failure_rate": total_save_failure_rate,
        },
        "funnel": {
            "group_switch_sessions": conversion_den,
            "save_success_sessions_after_switch": conversion_num,
            "group_switch_to_save_conversion_rate": conversion_rate,
        },
        "daily": daily_rows,
        "groups": group_rows,
    }


def _status_label_from_raw(raw_status):
    if raw_status == 0:
        return "solved"
    if raw_status == -1:
        return "wrong"
    if raw_status is not None:
        return "partial"
    return "unsolved"


def _group_status_from_homework_status(raw_status: str | None) -> str | None:
    if raw_status == "passed":
        return "solved"
    if raw_status in ("wrong", "partial", "pending"):
        return raw_status
    return None


def _latest_homework_status_map(doc: dict) -> dict[str, str]:
    latest = build_homework_latest_payload(doc).get("log") or {}
    status_map: dict[str, str] = {}
    for item in latest.get("problem_status") or []:
        legacy_code = str(item.get("legacy_code") or "").strip()
        normalized = _group_status_from_homework_status(item.get("status"))
        if legacy_code and normalized:
            status_map[legacy_code] = normalized
    return status_map


def _build_user_status_map(user_data: dict) -> dict:
    user_status_map = {}
    for record_key, rec in (user_data or {}).items():
        sid = str(record_key).strip()
        if not sid or not isinstance(rec, dict):
            continue
        user_status_map[sid] = rec.get("status")
    return user_status_map


def _build_group_problem_items(group_data: dict, user_status_map: dict, legacy_map: dict) -> list[dict]:
    problems = []
    for legacy_code, title in (group_data.get("problem_names") or {}).items():
        sid = legacy_map.get(legacy_code, legacy_code)
        raw_status = user_status_map.get(sid)
        status = _status_label_from_raw(raw_status)
        problems.append(
            {
                "problem_id": legacy_code,
                "legacy_code": legacy_code,
                "title": title,
                "status": status,
                "link": f"http://edu.doingcoding.com/problem/{legacy_code}",
            }
        )
    return problems


def _overlay_homework_statuses(problem_items: list[dict], homework_status_map: dict[str, str]) -> list[dict]:
    if not homework_status_map:
        return problem_items

    merged = []
    for item in problem_items:
        patched = dict(item)
        hw_status = homework_status_map.get(item.get("legacy_code"))
        if hw_status:
            patched["status"] = hw_status
        merged.append(patched)
    return merged


def _build_group_counts(problem_items: list[dict]) -> dict:
    counts = {"total": len(problem_items), "solved": 0, "partial": 0, "wrong": 0, "unsolved": 0}
    for p in problem_items:
        st = p.get("status") or "unsolved"
        if st not in counts:
            st = "unsolved"
        counts[st] += 1
    return counts


def _build_chapter_workspace_payload(s, username: str, chapter: str, selected_group: str | None = None):
    ensure_problem_assets()

    safe_name = sanitize_filename(username)
    fallback_user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    user_path = fallback_user_path
    try:
        _, user_path = sync_user_problems_cache(s, username)
    except Exception as e:
        print(f"[chapter_workspace] sync failed, fallback cache: {e}")

    missing = ensure_user_cache_or_404(user_path, PROBLEM_FILE, username)
    if missing:
        raise FileNotFoundError(str(missing))

    with open(user_path, encoding="utf-8") as f:
        user_data = json.load(f)
    with open(PROBLEM_FILE, encoding="utf-8") as f:
        all_problems = json.load(f)

    legacy_to_server = resolve_legacy_map_dict()
    user_status_map = _build_user_status_map(user_data)

    chapter_groups = (all_problems or {}).get(chapter)
    if not chapter_groups:
        raise KeyError(f"'{chapter}' 챕터를 찾을 수 없습니다.")

    group_ids = list(chapter_groups.keys())
    if not group_ids:
        raise KeyError(f"'{chapter}' 챕터에 그룹이 없습니다.")

    if selected_group not in chapter_groups:
        selected_group = group_ids[0]

    subchapters = []
    chapter_status_map = {}
    for gid, gdata in chapter_groups.items():
        problem_items = _build_group_problem_items(gdata, user_status_map, legacy_to_server)
        counts = _build_group_counts(problem_items)
        chapter_id = gdata.get("chapter_id")
        title = gdata.get("title", "")
        tag = quote(str(title).replace(".", ""))
        chapter_url = f"{BASE_URL}/{chapter_id}?tag={tag}" if chapter_id else ""
        subchapters.append(
            {
                "group_id": gid,
                "title": title,
                "counts": counts,
                "chapter_url": chapter_url,
                "legacy_group_url": f"/user/{quote(username)}/chapter/{quote(chapter)}/group/{quote(gid)}",
            }
        )
        for item in problem_items:
            chapter_status_map[item["problem_id"]] = item["status"]

    selected_group_data = chapter_groups[selected_group]
    selected_problems = _build_group_problem_items(
        selected_group_data,
        user_status_map,
        legacy_to_server,
    )

    user_uuid = resolve_uuid(username)
    doc = load_doc_by_any(user_uuid)
    latest_homework = build_homework_latest_payload(doc).get("log")

    return {
        "ok": True,
        "user": username,
        "user_uuid": user_uuid,
        "chapter": chapter,
        "subchapters": subchapters,
        "selected_group": selected_group,
        "problems": selected_problems,
        "status_map": chapter_status_map,
        "latest_homework": latest_homework,
    }


@app.before_request
def enforce_subdomain_access():
    if not ADMIN_DOMAIN and not STUDENT_DOMAIN:
        return None

    host = (request.host or "").split(":")[0].lower()
    if _is_localhost(host):
        return None
    if RELAX_HOST_RESTRICTION and _is_private_host(host):
        return None

    path = request.path or "/"
    is_admin_route = _is_admin_route(path)
    is_student_route = _is_student_route(path)

    allowed_hosts = {h for h in (ADMIN_DOMAIN, STUDENT_DOMAIN) if h}
    if allowed_hosts and host not in allowed_hosts:
        return ("forbidden", 403)

    if STUDENT_DOMAIN and host == STUDENT_DOMAIN and is_admin_route:
        return ("forbidden", 403)

    if ADMIN_DOMAIN and host == ADMIN_DOMAIN and is_student_route:
        return ("forbidden", 403)

    if ADMIN_DOMAIN and host == ADMIN_DOMAIN:
        return None

    if STUDENT_DOMAIN and host == STUDENT_DOMAIN:
        return None

    return None


# 문제 목록 강제 업데이트 기능
@app.context_processor
def inject_host_access_notice():
    return {
        "relax_host_restriction": RELAX_HOST_RESTRICTION,
        "host_access_notice": "호스트 제한이 임시 해제되어 있습니다. 내부 네트워크에서 직접 접속이 가능합니다.",
    }


@app.after_request
def add_host_access_notice_header(response):
    if RELAX_HOST_RESTRICTION:
        response.headers["X-Host-Restriction-Relaxed"] = "1"
    return response


@app.route("/update_problems", methods=["POST"])
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

    if should_refresh_api:
        save_server_problems_json(out_path=SERVER_DUMP_FILE)

    build_legacy_map(
        problem_file_path,
        SERVER_DUMP_FILE,
        out_map_path=SERVER_TO_LEGACY_FILE,
        out_unmatched_path=UNMATCHED_FILE,
    )

    return jsonify(
        {
            "ok": True,
            "message": (
                f"{chapter_label} 문제 목록을 갱신했습니다. "
                f"({'크롤링 + API + 매핑' if should_refresh_api else '크롤링 + 매핑'})"
                if chapter_label
                else f"전체 문제 목록을 갱신했습니다. "
                f"({'크롤링 + API + 매핑' if should_refresh_api else '크롤링 + 매핑'})"
            ),
            "chapter": chapter_label,
            "api_refreshed": should_refresh_api,
            "problem_file": problem_file_path,
            "api_dump": SERVER_DUMP_FILE,
            "server_to_legacy": SERVER_TO_LEGACY_FILE,
            "legacy_to_server": LEGACY_TO_SERVER_FILE,
            "unmatched": UNMATCHED_FILE,
            "time": datetime.now().isoformat(),
        }
    )


# ✅ AJAX: streak만 교체
@app.route("/api/streak")
def api_streak():

    streak_username = request.args.get("viewUsername")
    view_mode = request.args.get("viewMode")  # "me" or "user"

    print(f"streak_username: {streak_username}")
    print(f"view_mode: {view_mode}")

    days = int(request.args.get("days", 7))

    s, redir = ensure_login_or_redirect()
    if redir:
        return jsonify({"error": "unauthorized"}), 401

    try:
        if view_mode == "user":
            if not streak_username:
                return jsonify({"error": "username required for view=user"}), 400
            prof = fetch_profile(s, username=streak_username)
            is_me = False
        else:
            prof = fetch_profile(s, username=None)
            is_me = True

        payload = prof.get("data", {})
        user_data = payload.get("user", {})
        uname = user_data.get("username")
        print(f"api_streak의 prof: {prof}")

        submissions = fetch_submissions_window(
            s, uname, myself=(1 if is_me else 0), days=max(days, 7), limit=100
        )
        filtered = filter_main_account_submissions(submissions, uname)
        streak = generate_streak_data(filtered, days=days)
        print(f"streak: {streak}")
        return jsonify({"streak_data": streak})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 유저 목록
@app.route("/proxy/user_rank")
def proxy_user_rank():
    s, err = ensure_admin_or_403()
    if err:
        return err
    url = f"{BASE_URL}/api/user_rank?offset=0&limit=100&rule=ACM"
    all_users = []
    offset = 0
    limit = 100
    # users_rank = session.get(
    #     f"http://edu.doingcoding.com/api/user_rank?offset=0&limit=201&rule=ACM"
    # )
    # users_rank = users_rank.json()
    # usernames = [entry["user"]["username"] for entry in users_rank["data"]["results"]]
    while True:
        res = requests.get(f"{url}&offset={offset}&limit={limit}")
        data = res.json()
        # results = data.get("data", {}).get("results", [])
        if not data or "data" not in data:
            break
        # 유저명만 추출
        results = data["data"].get("results", [])
        usernames = [entry["user"]["username"] for entry in results]
        all_users.extend(usernames)
        if len(usernames) < limit:
            break
        offset += limit

    return jsonify({"usernames": all_users})


# --- 공통 pull & merge 로직으로 분리 ---
def pull_and_store_user(username: str):
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    encoded_username = quote(username)

    res = session.get(f"{BASE_URL}/api/profile?username={encoded_username}")
    data = res.json()
    user_data = data["data"]["user"]
    problems = data["data"]["oi_problems_status"]["problems"]
    problems = merge_submissions_into_problems(session, username, problems)

    student_id = user_data["username"]
    doc = load_doc_by_any(student_id)  # student_id나 uuid로 찾아오는 헬퍼
    doc["profile"] = {
        "student_id": student_id,
        "name": user_data.get("realname") or user_data.get("username"),
        "class_id": user_data.get("class_id"),
        "last_login": user_data.get("last_login"),
    }
    doc["user_uuid"] = resolve_uuid(student_id)
    doc["oi_problems"] = problems
    doc.setdefault("homework_logs", doc.get("homework_logs", []))
    doc["updated_at"] = datetime.now(tz=KST).isoformat()

    save_doc_by_any(student_id, doc)
    return doc


def _parse_iso_datetime(value: str | None):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_doc_stale(doc: dict, ttl_ms: int = 60_000) -> bool:
    if ttl_ms < 0:
        ttl_ms = 0
    parsed = _parse_iso_datetime((doc or {}).get("updated_at"))
    if not parsed:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    age_ms = (datetime.now(tz=KST) - parsed.astimezone(KST)).total_seconds() * 1000
    return age_ms > ttl_ms


def refresh_user_doc_by_uuid(user_uuid: str) -> dict:
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    base = load_doc_by_any(user_uuid)
    username = (base.get("profile") or {}).get("student_id") or (
        base.get("profile") or {}
    ).get("name")
    if not username:
        username = reverse_lookup(user_uuid)
        if not username:
            raise ValueError("username not resolvable")
        base.setdefault("profile", {})
        base["profile"]["student_id"] = username
        base["profile"].setdefault("name", username)

    # 원격 데이터
    res = session.get(f"{BASE_URL}/api/profile?username={quote(username)}")
    data = res.json()
    user_data = data["data"]["user"]
    problems = data["data"]["oi_problems_status"]["problems"]
    problems = merge_submissions_into_problems(session, username, problems)

    # 저장 직전 다시 읽어 homework_logs 보존
    current = load_doc_by_any(user_uuid)
    current["profile"] = {
        "student_id": user_data["username"],
        "name": user_data.get("realname") or user_data.get("username"),
        "class_id": user_data.get("class_id"),
        "last_login": user_data.get("last_login"),
    }
    current["oi_problems"] = problems
    current["updated_at"] = datetime.now(tz=KST).isoformat()

    save_doc_by_any(user_uuid, current)
    return current


@app.route("/api/students/<user_uuid>/refresh", methods=["POST"])
def refresh_by_uuid(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err
    try:
        current = refresh_user_doc_by_uuid(user_uuid)
        return jsonify(
            {
                "success": True,
                "updated_at": current["updated_at"],
                "user_uuid": current["user_uuid"],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 기존 라우트는 공통 함수를 호출하도록
@app.route("/refresh_user/<username>")
def refresh_user(username):
    s, err = ensure_admin_or_403()
    if err:
        return err
    try:
        doc = pull_and_store_user(username)
        return jsonify(
            {   
                "success": True,
                "updated_at": doc["updated_at"],
                "user_uuid": doc["user_uuid"],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def compute_homework_status(doc: dict):
    oi = doc.get(
        "oi_problems", {}
    )  # {"27": {"_id":"P101v0101","score":100,"status":0}, ...}

    # 조회 인덱스
    by_legacy = {}
    by_numeric_key = {}
    for k, v in oi.items():
        if isinstance(v, dict):
            by_numeric_key[str(k)] = v
            if v.get("_id"):
                by_legacy[v["_id"]] = v

    def is_pass(p):  # 서비스 룰에 맞게 통일
        return (p.get("score", 0) >= 100) or (p.get("status") == 0)

    def is_attempted(p):
        return (p.get("score", 0) == 0) or (p.get("status") in (-1))

    def is_partial(p):
        return (p.get("score", 0) > 0) or (p.get("status") in (8, 4))

    items = []
    for hw in doc.get("homework_logs", []):
        log_id = hw.get("log_id") or hw.get("ts")  # 안정 키
        counts = {"total": 0, "passed": 0, "wrong": 0, "partial": 0, "pending": 0}
        probs = []

        for prob in hw.get("problems", []):
            counts["total"] += 1
            p = None
            code = prob.get("legacy_code")
            if code:
                p = by_legacy.get(code)
            if not p and prob.get("server_problem_id"):
                p = by_numeric_key.get(str(prob["server_problem_id"]))

            if p:
                # print(f"p: {p}")
                if is_pass(p):
                    status = "passed"
                    counts["passed"] += 1
                elif is_partial(p):
                    status = "partial"
                    counts["partial"] += 1
                elif is_attempted(p):
                    status = "wrong"
                    counts["wrong"] += 1
                else:
                    status = "pending"
                    counts["pending"] += 1
            else:
                status = "pending"
                counts["pending"] += 1

            probs.append(
                {
                    "legacy_code": prob.get("legacy_code"),
                    "server_problem_id": prob.get("server_problem_id"),
                    "status": status,
                }
            )

        items.append({"key": log_id, "counts": counts, "problems": probs})

    return {"ok": True, "items": items, "updated_at": doc.get("updated_at")}


@app.route("/api/students/<user_uuid>/homework_status")
def homework_status(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err
    doc = load_doc_by_any(user_uuid)
    return jsonify(compute_homework_status(doc))


# DELETE /api/students/<id_or_uuid>/homework_logs/<log_key>
# log_key: 로그의 uuid id 또는 index(0-based)
@app.delete("/api/students/<id_or_uuid>/homework_logs/<log_key>")
def api_delete_homework_log(id_or_uuid, log_key):
    s, err = ensure_admin_or_403()
    if err:
        return err
    u = id_or_uuid if "-" in id_or_uuid else resolve_uuid(id_or_uuid)
    if not u:
        return jsonify({"ok": False, "error": "unknown user"}), 404

    doc = load_doc_by_any(u)  # 반드시 uuid.json을 여는 함수
    logs = doc.get("homework_logs", [])
    print(f"logs: {logs}")
    removed = None
    # 1) id로 삭제
    for i, x in enumerate(logs):
        if str(x.get("id", "")) == log_key:
            removed = logs.pop(i)
            break

    # 2) index로 삭제(뷰가 역순 렌더라는 가정하에 보정)
    if removed is None:
        try:
            idx_view = int(log_key)
            idx_real = len(logs) - 1 - idx_view  # !!! 역순 보정
            if 0 <= idx_real < len(logs):
                removed = logs.pop(idx_real)
        except ValueError:
            pass

    if removed is None:
        return jsonify({"ok": False, "error": "log not found"}), 404
    # print(f"doc: {doc["homework_logs"]}")
    save_doc_by_any(u, doc)
    # print(f"logs: {logs}")
    return jsonify({"ok": True, "count": len(logs)})


@app.route("/api/students/<id_or_uuid>/homework_logs", methods=["POST", "OPTIONS"])
def api_save_homework_log(id_or_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err
    if request.method == "OPTIONS":
        return ("", 204)

    # ✅ 경로 값을 uuid로 정규화(끝까지 이 값만 사용)
    u = id_or_uuid if "-" in id_or_uuid else resolve_uuid(id_or_uuid)

    payload = request.get_json(force=True) or {}
    doc = append_homework_log(u, payload)  # ✅ uuid 기반 함수 호출

    # 디버깅: 실제 저장된 파일의 로그 개수 확인
    print(f"[HW] logs now: {len(doc.get('homework_logs', []))} for {u}")
    return jsonify(
        {
            "ok": True,
            "user_uuid": doc.get("user_uuid"),
            "count": len(doc.get("homework_logs", [])),
            # 필요하면 방금 추가된 log_id/id를 내려 프런트에서 data-log-id로 심어도 좋음
        }
    )


def _today_activity_from_doc(doc: dict) -> dict:
    today = datetime.now(tz=KST).date()
    profile = (doc or {}).get("profile") or {}
    last_login_raw = profile.get("last_login")
    last_login_dt = _parse_iso_datetime(last_login_raw)
    if last_login_dt and last_login_dt.tzinfo is None:
        last_login_dt = last_login_dt.replace(tzinfo=timezone.utc)
    has_login_today = (
        bool(last_login_dt) and last_login_dt.astimezone(KST).date() == today
    )
    return {
        "has_login_today": has_login_today,
        "has_submission_today": False,
        "submission_count_today": 0,
    }


def _fetch_today_activity_for_student(session: requests.Session | None, username: str) -> dict:
    activity = {
        "has_login_today": False,
        "has_submission_today": False,
        "submission_count_today": 0,
    }
    if not session or not username:
        return activity

    today = datetime.now(tz=KST).date()
    page = 1
    limit = 100
    max_pages = 3

    while page <= max_pages:
        res = session.get(
            f"{BASE_URL}/api/submissions",
            params={
                "myself": 0,
                "starred": 0,
                "result": "",
                "username": username,
                "page": page,
                "limit": limit,
                "offset": (page - 1) * limit,
            },
            timeout=10,
        )
        if res.status_code != 200:
            break

        payload = res.json() or {}
        results = (payload.get("data") or {}).get("results") or []
        if not results:
            break

        saw_older = False
        for rec in results:
            ts_raw = rec.get("create_time")
            if not ts_raw:
                continue
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone(KST)
            except ValueError:
                continue
            day = dt.date()
            if day == today:
                activity["submission_count_today"] += 1
            elif day < today:
                saw_older = True

        if saw_older:
            break
        page += 1

    activity["has_submission_today"] = activity["submission_count_today"] > 0
    return activity


def _get_cached_today_activity(username: str, ttl_ms: int) -> dict | None:
    if not username:
        return None
    now_ms = int(time.time() * 1000)
    with TODAY_ACTIVITY_CACHE_LOCK:
        entry = TODAY_ACTIVITY_CACHE.get(username)
        if not entry:
            return None
        if now_ms - int(entry.get("fetched_at_ms", 0)) > max(0, ttl_ms):
            TODAY_ACTIVITY_CACHE.pop(username, None)
            return None
        data = entry.get("data")
        return dict(data) if isinstance(data, dict) else None


def _set_cached_today_activity(username: str, activity: dict):
    if not username or not isinstance(activity, dict):
        return
    now_ms = int(time.time() * 1000)
    with TODAY_ACTIVITY_CACHE_LOCK:
        if len(TODAY_ACTIVITY_CACHE) >= TODAY_ACTIVITY_CACHE_MAX:
            # 가장 단순한 메모리 상한 보호: 오래된 항목 일부 제거
            keys = list(TODAY_ACTIVITY_CACHE.keys())[: max(1, TODAY_ACTIVITY_CACHE_MAX // 10)]
            for k in keys:
                TODAY_ACTIVITY_CACHE.pop(k, None)
        TODAY_ACTIVITY_CACHE[username] = {
            "fetched_at_ms": now_ms,
            "data": {
                "has_login_today": bool(activity.get("has_login_today", False)),
                "has_submission_today": bool(activity.get("has_submission_today", False)),
                "submission_count_today": int(activity.get("submission_count_today", 0)),
            },
        }


def build_homework_latest_payload(doc: dict, today_activity: dict | None = None) -> dict:
    logs = doc.get("homework_logs", [])
    if not logs:
        return {"ok": True, "updated_at": doc.get("updated_at"), "log": None}

    # 가장 최신: ts 기준(없으면 배열 마지막)
    def ts_val(x):
        return x.get("ts") or ""

    latest_log = max(logs, key=ts_val) if any(x.get("ts") for x in logs) else logs[-1]
    key = latest_log.get("log_id") or latest_log.get("ts")

    # 상태/카운트 계산은 기존 compute_homework_status를 재사용
    status = compute_homework_status(doc)
    item = next((it for it in status["items"] if it["key"] == key), None)

    # 오늘 숙제 여부 / 완료 여부 플래그 계산
    today = datetime.now(tz=KST).date()

    ts_raw = latest_log.get("ts")
    given_date = None
    if ts_raw:
        try:
            ts_dt = datetime.fromisoformat(ts_raw)
            given_date = ts_dt.astimezone(KST).date()
        except ValueError:
            given_date = None

    counts = (
        item["counts"]
        if item
        else {
            "total": 0,
            "passed": 0,
            "wrong": 0,
            "partial": 0,
            "pending": 0,
        }
    )

    total = counts.get("total") or 0
    passed = counts.get("passed") or 0
    wrong = counts.get("wrong") or 0
    pending = counts.get("pending") or 0

    feedback_given_today = False
    for x in logs:
        x_title = x.get("title") or ""
        x_ts = x.get("ts") or ""
        if "피드백" in x_title and x_ts:
            try:
                x_dt = datetime.fromisoformat(x_ts)
                if x_dt.astimezone(KST).date() == today:
                    feedback_given_today = True
                    break
            except ValueError:
                pass

    flags = {
        "is_given_today": bool(given_date and given_date == today),
        "all_passed": total > 0 and passed == total,
        "has_any": total > 0,
        "has_unresolved": (wrong + pending) > 0,
        "feedback_given_today": feedback_given_today,
    }

    return {
        "ok": True,
        "updated_at": status.get("updated_at"),
        "log": {
            "key": key,
            "id": latest_log.get("id"),
            "title": latest_log.get("title"),
            "url": latest_log.get("url"),
            "due_at": latest_log.get("due_at"),
            "ts": latest_log.get("ts"),
            "channel": latest_log.get("channel"),
            "problems": latest_log.get("problems", []),
            "counts": (
                item["counts"]
                if item
                else {"total": 0, "passed": 0, "wrong": 0, "partial": 0, "pending": 0}
            ),
            "problem_status": item["problems"] if item else [],
            "flags": flags,
            "today_activity": today_activity or _today_activity_from_doc(doc),
        },
    }


@app.get("/api/students/<user_uuid>/homework_latest")
def homework_latest(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err
    doc = load_doc_by_any(user_uuid)
    return jsonify(build_homework_latest_payload(doc))


@app.post("/api/students/homework_latest_batch")
def homework_latest_batch():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    raw_uuids = payload.get("user_uuids") or []
    if not isinstance(raw_uuids, list):
        return jsonify({"ok": False, "error": "user_uuids must be an array"}), 400

    refresh_stale = bool(payload.get("refresh_stale", True))
    try:
        ttl_ms = int(payload.get("ttl_ms", 60_000))
    except (TypeError, ValueError):
        ttl_ms = 60_000

    try:
        max_workers = int(payload.get("max_workers", 6))
    except (TypeError, ValueError):
        max_workers = 6
    max_workers = max(1, min(max_workers, 12))
    include_today_activity = bool(payload.get("include_today_activity", True))
    try:
        today_activity_ttl_ms = int(payload.get("today_activity_ttl_ms", 120_000))
    except (TypeError, ValueError):
        today_activity_ttl_ms = 120_000
    today_activity_ttl_ms = max(0, min(today_activity_ttl_ms, 600_000))

    user_uuids = []
    seen = set()
    for token in raw_uuids:
        raw = str(token or "").strip()
        if not raw:
            continue
        user_uuid = raw if "-" in raw else resolve_uuid(raw)
        if not user_uuid or user_uuid in seen:
            continue
        seen.add(user_uuid)
        user_uuids.append(user_uuid)

    cookie_dict = load_cookies(COOKIE_PATH)
    activity_session_local = threading.local()

    def get_activity_session():
        if not cookie_dict:
            return None
        s = getattr(activity_session_local, "session", None)
        if s is None:
            s = get_authenticated_session(cookie_dict)
            activity_session_local.session = s
        return s

    def process_user(user_uuid: str):
        doc = load_doc_by_any(user_uuid)
        if refresh_stale and is_doc_stale(doc, ttl_ms=ttl_ms):
            doc = refresh_user_doc_by_uuid(user_uuid)
        profile = doc.get("profile") or {}
        username = profile.get("student_id") or profile.get("name")

        activity = _today_activity_from_doc(doc)
        if include_today_activity:
            cached = _get_cached_today_activity(username, today_activity_ttl_ms)
            if cached:
                cached["has_login_today"] = activity["has_login_today"]
                activity = cached
            else:
                try:
                    session = get_activity_session()
                    fetched = _fetch_today_activity_for_student(session, username)
                    fetched["has_login_today"] = activity["has_login_today"]
                    activity = fetched
                    _set_cached_today_activity(username, fetched)
                except Exception:
                    pass

        return build_homework_latest_payload(doc, today_activity=activity)

    items = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(user_uuids) or 1)) as pool:
        future_map = {pool.submit(process_user, user_uuid): user_uuid for user_uuid in user_uuids}
        for future in as_completed(future_map):
            user_uuid = future_map[future]
            try:
                items[user_uuid] = future.result()
            except Exception as e:
                items[user_uuid] = {
                    "ok": False,
                    "error": str(e),
                    "updated_at": None,
                    "log": None,
                }

    return jsonify({"ok": True, "items": items})


# ✅ 뷰어: UUID로 학생 숙제로그 열람 (템플릿: templates/homework_view.html 필요)
@app.get("/students/<user_uuid>/homework")
def view_homework_logs(user_uuid):
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    sid = reverse_lookup(user_uuid)
    if not sid:
        return "학생을 찾을 수 없습니다.", 404
    doc = load_doc_by_any(user_uuid)
    logs = list(reversed(doc.get("homework_logs", [])))
    student = doc.get("profile", {})
    # 예: 간단 템플릿으로 렌더 (표/리스트)
    return render_template(
        "homework_view.html",
        student=student,
        logs=logs,
        user_uuid=user_uuid,
        is_admin=True,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        from login import do_login  # 쿠키 발급 로직 따로 작성

        success, session_or_msg = do_login(username, password)

        if success:
            # 로그인 성공 시 index 페이지로 리디렉션
            # return redirect(url_for("index"))
            return redirect("/")  # ✅ 이 리다이렉트가 핵심!
        else:
            print("로그인 실패!:", session_or_msg)
            return render_template("login.html", error="로그인에 실패했습니다.")

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    try:
        fsession.clear()
    except Exception:
        pass

    try:
        removed = clear_active_session()
        print(f"[logout] removed cookies: {removed}")
    except Exception as e:
        print("[logout] cookie removal failed:", e)

    return redirect("/login")


@app.route("/", methods=["GET", "POST"])
def index():
    ensure_problem_assets()

    # 검색 제출 시 -> /user/<username>로 위임
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            return "유저명을 입력해주세요.", 400
        return redirect(url_for("user", username=username))

    # 내 대시보드
    s, redir = ensure_login_or_redirect()
    print(f"s: {s}\nredir:{redir}")
    if redir:
        return redir

    # 기본 7일, 쿼리스트링으로 초기값 변경 가능 (?days=30)
    days = int(request.args.get("days", 7))
    me_json = fetch_profile(s, username=None)
    print(f"app.py-me_json: {me_json.get('data').get('user').get('username')}")
    vm = build_dashboard_viewmodel(s, me_json, is_me=True, days=days)
    vm["streak_days"] = days
    my_name = me_json.get("data").get("user").get("username")
    my_uuid = resolve_uuid(my_name)
    role_ctx = role_ctx_from_session()
    return render_template(
        "index.html",
        **vm,
        view_mode="me",
        view_username="",
        user_uuid=my_uuid,  # uuid 필드
        viewer_is_admin=role_ctx["is_admin"],
        # 공통 데이터 주입
    )


@app.route("/user/<username>")
def user(username):
    ensure_problem_assets()

    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    try:
        other_json = fetch_profile(s, username=username)  # 타인 프로필
    except Exception as e:
        return f"❌ 사용자 정보를 불러오지 못했습니다: {e}", 500

    days = int(request.args.get("days", 7))
    other_json = fetch_profile(s, username=username)
    print(f"other_json: {other_json}")
    vm = build_dashboard_viewmodel(s, other_json, is_me=False, days=days)
    vm["streak_days"] = days

    other_name = other_json.get("data").get("user").get("username")
    other_uuid = resolve_uuid(other_name)

    role_ctx = role_ctx_from_session()
    return render_template(
        "index.html",
        **vm,
        view_mode="user",
        view_username=username,
        user_uuid=other_uuid,  # uuid 필드
        viewer_is_admin=role_ctx["is_admin"],
    )


from flask import render_template, redirect
from urllib.parse import quote


@app.route("/user/<username>/chapter/<chapter>/workspace")
def chapter_workspace_page(username, chapter):
    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    selected_group = (request.args.get("group") or "").strip()
    selected_filter = (request.args.get("filter") or "all").strip() or "all"
    role_ctx = role_ctx_from_session()

    return render_template(
        "chapter_workspace.html",
        username=username,
        chapter=chapter,
        selected_group=selected_group,
        selected_filter=selected_filter,
        user_uuid=resolve_uuid(username),
        workspace_beta_enabled=_workspace_beta_enabled_for(username),
        workspace_default_enabled=_workspace_default_enabled_for(username),
        **role_ctx,
    )


@app.get("/api/chapter_workspace")
def api_chapter_workspace():
    s, redir = ensure_login_or_redirect()
    if redir:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    username = (request.args.get("user") or "").strip()
    chapter = (request.args.get("chapter") or "").strip()
    selected_group = (request.args.get("group") or "").strip() or None

    if not username or not chapter:
        return jsonify({"ok": False, "error": "user and chapter are required"}), 400

    try:
        payload = _build_chapter_workspace_payload(s, username, chapter, selected_group)
        return jsonify(payload)
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/chapter_workspace/group/<group_id>")
def api_chapter_workspace_group(group_id):
    s, redir = ensure_login_or_redirect()
    if redir:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    username = (request.args.get("user") or "").strip()
    chapter = (request.args.get("chapter") or "").strip()
    if not username or not chapter:
        return jsonify({"ok": False, "error": "user and chapter are required"}), 400

    try:
        payload = _build_chapter_workspace_payload(s, username, chapter, selected_group=group_id)
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except KeyError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify(
        {
            "ok": True,
            "user": payload.get("user"),
            "user_uuid": payload.get("user_uuid"),
            "chapter": payload.get("chapter"),
            "selected_group": payload.get("selected_group"),
            "problems": payload.get("problems"),
            "status_map": payload.get("status_map"),
            "latest_homework": payload.get("latest_homework"),
        }
    )


@app.post("/api/chapter_workspace/events")
def api_chapter_workspace_events():
    s, redir = ensure_login_or_redirect()
    if redir:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    payload = request.get_json(force=True) or {}
    event_name = (payload.get("event_name") or "").strip()
    username = (payload.get("user") or "").strip()
    chapter = (payload.get("chapter") or "").strip()
    group_id = (payload.get("group") or "").strip()
    session_id = (payload.get("session_id") or "").strip()
    detail = payload.get("detail")

    if not event_name:
        return jsonify({"ok": False, "error": "event_name required"}), 400

    event = {
        "ts": datetime.now(tz=KST).isoformat(),
        "event_name": event_name,
        "user": username,
        "chapter": chapter,
        "group": group_id,
        "session_id": session_id,
        "detail": detail if isinstance(detail, dict) else {},
        "ip": request.remote_addr,
        "ua": request.headers.get("User-Agent", ""),
    }
    try:
        _append_workspace_event(event)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


@app.get("/api/chapter_workspace/events_summary")
def api_chapter_workspace_events_summary():
    s, err = ensure_admin_or_403()
    if err:
        return err

    try:
        days = int(request.args.get("days", 14))
    except (TypeError, ValueError):
        days = 14
    days = max(1, min(days, 90))

    filter_user = (request.args.get("user") or "").strip()
    filter_chapter = (request.args.get("chapter") or "").strip()
    filter_group = (request.args.get("group") or "").strip()

    events = _read_workspace_events(limit_days=days)
    if filter_user:
        events = [e for e in events if (e.get("user") or "") == filter_user]
    if filter_chapter:
        events = [e for e in events if (e.get("chapter") or "") == filter_chapter]
    if filter_group:
        events = [e for e in events if (e.get("group") or "") == filter_group]

    summary = _build_workspace_event_summary(events)
    return jsonify(
        {
            "ok": True,
            "filters": {
                "days": days,
                "user": filter_user,
                "chapter": filter_chapter,
                "group": filter_group,
            },
            "event_count": len(events),
            **summary,
        }
    )


@app.route("/user/<username>/chapter/<chapter>")
def chapter_detail(username, chapter):
    if _workspace_default_enabled_for(username) and request.args.get("legacy") != "1":
        return redirect(f"/user/{quote(username)}/chapter/{quote(chapter)}/workspace")

    ensure_problem_assets()

    # 로그인/세션 보장
    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    # 최신 사용자 문제 캐시 동기화 (실패해도 캐시 사용)
    safe_name = sanitize_filename(username)
    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    try:
        _, user_path = sync_user_problems_cache(s, username)
    except Exception as e:
        print(f"[chapter_detail] 프로필 갱신 실패, 캐시 사용: {e}")

    # 리소스 존재 확인
    missing = ensure_user_cache_or_404(user_path, PROBLEM_FILE, username)
    if missing:
        return missing

    # 레거시 맵 경로/요약
    legacy_map_path = resolve_legacy_map_path()
    chapter_summary = summarize_progress(
        PROBLEM_FILE, user_path, legacy_map_file=legacy_map_path
    )

    matched = next(
        (item for item in chapter_summary if item["chapter"] == chapter), None
    )
    if matched is None:
        return f"'{chapter}' 챕터를 찾을 수 없습니다.", 404

    # 세션 role→템플릿 컨텍스트

    role_ctx = role_ctx_from_session()
    return render_template(
        "chapter_detail.html",
        username=username,
        chapter=chapter,
        chapter_name=f"{chapter} 단원",
        progress_data=matched["groups"],
        workspace_beta_enabled=_workspace_beta_enabled_for(username),
        workspace_default_enabled=_workspace_default_enabled_for(username),
        **role_ctx,  # role_label, is_admin
    )


@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
    if _workspace_route_enabled_for(username) and request.args.get("legacy") != "1":
        return redirect(
            f"/user/{quote(username)}/chapter/{quote(chapter)}/workspace?group={quote(group_id)}"
        )

    ensure_problem_assets()

    # 로그인/세션 보장
    s, redir = ensure_login_or_redirect()
    if redir:
        return redir

    # 최신 사용자 문제 캐시 동기화 (실패 시 캐시 사용)
    safe_name = sanitize_filename(username)
    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    try:
        _, user_path = sync_user_problems_cache(s, username)
    except Exception as e:
        print(f"[group_detail] 프로필 갱신 실패, 캐시 사용: {e}")

    # 리소스 존재 확인
    missing = ensure_user_cache_or_404(user_path, PROBLEM_FILE, username)
    if missing:
        return missing

    # 데이터 로드
    try:
        with open(user_path, encoding="utf-8") as f:
            user_data = json.load(f)
        with open(PROBLEM_FILE, encoding="utf-8") as f:
            all_problems = json.load(f)
        legacy_to_server = resolve_legacy_map_dict()
        user_doc = load_doc_by_any(username)
    except FileNotFoundError as e:
        return str(e), 404
    except json.JSONDecodeError as e:
        return f"데이터 파싱 오류: {e}", 500

        # ✅ UUID 준비: 파일에 없더라도 매핑 생성해서 확보
    try:
        user_uuid = user_data.get("user_uuid")
    except AttributeError:
        user_uuid = None
    if not user_uuid:
        user_uuid = resolve_uuid(username)

    # 그룹 요약
    try:
        result = summarize_user_chapter_group(
            user_data,
            all_problems,
            chapter,
            group_id,
            legacy_map=legacy_to_server,
        )
    except KeyError as e:
        return f"데이터 오류: {e}", 400

    result["problem_names"] = _overlay_homework_statuses(
        result["problem_names"],
        _latest_homework_status_map(user_doc),
    )

    # 외부 링크용 URL 생성
    title_url = quote(str(result["group_title"]).replace(".", ""))
    chapter_url = f"{BASE_URL}/{result['problem_chapter_id']}?tag={title_url}"

    # 세션 role→템플릿 컨텍스트
    # print(f"result: {result}")
    role_ctx = role_ctx_from_session()
    print(f"[group_detail] role_ctx={role_ctx}")
    return render_template(
        "group_detail.html",
        username=username,
        chapter=chapter,
        group_id=group_id,
        group_title=result["group_title"],
        problem_names=result["problem_names"],
        chapter_url_html=chapter_url,
        user_uuid=user_uuid,  # ✅ 추가
        **role_ctx,  # role_label, is_admin
    )

@app.get("/api/schedule")
def api_schedule_get():
    s, err = ensure_admin_or_403()
    if err:
        return err

    raw = load_schedule()
    slots = hydrate_slot_students(raw.get("slots", []))
    return jsonify({"ok": True, "slots": slots})

@app.post("/api/schedule/slots")
def api_schedule_create_slot():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    weekday = payload.get("weekday")
    label = (payload.get("label") or "").strip()

    if weekday is None or not label:
        return jsonify({"ok": False, "error": "weekday and label required"}), 400

    try:
        weekday = int(weekday)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid weekday"}), 400

    if not (-1 <= weekday <= 6):
        return jsonify({"ok": False, "error": "weekday must be -1~6"}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])

    new_slot = {
        "id": str(uuid4()),
        "weekday": weekday,
        "label": label,    # 예: "16:00 C언어반"
        "order": payload.get("order") or 0,
        "students": [],    # user_uuid 리스트
    }
    slots.append(new_slot)
    save_schedule(data)

    hydrated = hydrate_slot_students([new_slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@app.post("/api/schedule/slots/<slot_id>/students")
def api_schedule_add_student(slot_id):
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    student_id = (payload.get("student_id") or "").strip()
    if not student_id:
        return jsonify({"ok": False, "error": "student_id required"}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    # 프로필 동기화(있으면) - doingcoding API에서 끌어오는 기존 함수 활용
    try:
        doc = pull_and_store_user(student_id)
        user_uuid = doc.get("user_uuid") or resolve_uuid(student_id)
    except Exception as e:
        print("[schedule] pull_and_store_user failed:", e)
        user_uuid = resolve_uuid(student_id)

    slot.setdefault("students", [])
    if user_uuid not in slot["students"]:
        slot["students"].append(user_uuid)
        save_schedule(data)

    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})

@app.delete("/api/schedule/slots/<slot_id>/students/<user_token>")
def api_schedule_remove_student(slot_id, user_token):
    s, err = ensure_admin_or_403()
    if err:
        return err

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    students = slot.setdefault("students", [])

    # user_token은 uuid 또는 student_id 둘 다 허용
    target_uuid = user_token
    if "-" not in user_token:  # 단순 student_id 추정
        target_uuid = resolve_uuid(user_token)

    before = len(students)
    students[:] = [u for u in students if u != target_uuid]
    if len(students) == before:
        return jsonify({"ok": False, "error": "student not in slot"}), 404

    notes = slot.get("student_notes")
    if isinstance(notes, dict):
        notes.pop(target_uuid, None)
        notes.pop(user_token, None)

    save_schedule(data)
    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@app.patch("/api/schedule/slots/<slot_id>/students/<user_token>/note")
def api_schedule_update_student_note(slot_id, user_token):
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    note = str(payload.get("note") or "").strip()
    if len(note) > 80:
        return jsonify({"ok": False, "error": "note too long"}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    students = slot.setdefault("students", [])
    target_uuid = user_token
    if "-" not in user_token:
        target_uuid = resolve_uuid(user_token)

    if not target_uuid or target_uuid not in students:
        return jsonify({"ok": False, "error": "student not in slot"}), 404

    notes = slot.setdefault("student_notes", {})
    if note:
        notes[target_uuid] = note
    else:
        notes.pop(target_uuid, None)
        notes.pop(user_token, None)

    save_schedule(data)
    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})

@app.delete("/api/schedule/slots/<slot_id>")
def api_schedule_delete_slot(slot_id):
    s, err = ensure_admin_or_403()
    if err:
        return err

    data = load_schedule()
    slots = data.setdefault("slots", [])
    new_slots = [s for s in slots if s.get("id") != slot_id]
    if len(new_slots) == len(slots):
        return jsonify({"ok": False, "error": "slot not found"}), 404

    data["slots"] = new_slots
    save_schedule(data)
    return jsonify({"ok": True})

# --- 2-Pane Dual Workspace Routes ---

WORKSPACE_STUDENTS_PATH = META_DIR / "workspace_students.json"

def _load_workspace_students():
    if not WORKSPACE_STUDENTS_PATH.exists():
        return {}
    try:
        return json.loads(WORKSPACE_STUDENTS_PATH.read_text(encoding="utf-8"))
    except:
        return {}

def _save_workspace_students(data):
    WORKSPACE_STUDENTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _sync_workspace_students():
    # Sync with uuids.json if needed
    data = _load_workspace_students()
    try:
        uuids = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
        for sid, u in uuids.items():
            # Basic display ID generation: Name + (No birthdate for now)
            # Actually, just use sid as display_id for auto-imported ones
            display_id = sid
            if display_id not in data:
                data[display_id] = {
                    "display_id": display_id,
                    "name": sid,
                    "birth_md": "",
                    "accounts": [sid], # Map to this sid
                    "user_uuid": u # Primary UUID
                }
        _save_workspace_students(data)
    except:
        pass
    return data

@app.route("/workspace")
def workspace_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    return render_template("workspace_2pane.html")


@app.route("/api/workspace/schedule_students")
def api_workspace_schedule_students():
    s, err = ensure_admin_or_403()
    if err: return err
    
    weekday_str = request.args.get("weekday", "all")
    
    raw = load_schedule()
    slots = raw.get("slots", [])
    
    if weekday_str != "all":
        try:
            target_w = int(weekday_str)
            slots = [slot for slot in slots if slot.get("weekday") == target_w]
        except ValueError:
            pass
            
    hydrated_slots = hydrate_slot_students(slots)
    workspace_data = _sync_workspace_students()
    
    result_students = []
    seen_uuids = set()
    
    for slot in hydrated_slots:
        slot_label = slot.get("label", "")
        for st in slot.get("students_detail", []):
            u = st.get("user_uuid")
            if not u: continue
            
            display_id = u
            st_name = st.get("name", "이름없음")
            
            found = False
            for w_did, w_obj in workspace_data.items():
                if w_obj.get("user_uuid") == u:
                    display_id = w_did
                    st_name = w_obj.get("name") or st_name
                    found = True
                    break
            
            if not found:
                display_id = st.get("student_id") or st_name
                workspace_data[display_id] = {
                    "display_id": display_id,
                    "name": st_name,
                    "birth_md": "",
                    "accounts": [st.get("student_id")],
                    "user_uuid": u
                }
                _save_workspace_students(workspace_data)
            
            if u not in seen_uuids:
                seen_uuids.add(u)
                result_students.append({
                    "user_uuid": u,
                    "display_id": display_id,
                    "name": st_name,
                    "slot_label": slot_label,
                    "note": st.get("note", ""),
                    "slot_id": slot.get("id"),
                    "accounts": workspace_data[display_id].get("accounts", [])
                })
            else:
                for rs in result_students:
                    if rs["user_uuid"] == u:
                        if slot_label and slot_label not in rs["slot_label"]:
                            rs["slot_label"] += f", {slot_label}"
                        if st.get("note") and st.get("note") not in rs["note"]:
                            rs["note"] += f" | {st.get('note')}"
    
    # Also fetch full raw slots for dropdowns
    all_slots = [{"id": s.get("id"), "label": s.get("label"), "weekday": s.get("weekday")} for s in raw.get("slots", [])]
    return jsonify({"ok": True, "students": result_students, "all_slots": all_slots})


@app.route("/api/workspace/register_student", methods=["POST"])
def api_workspace_register_student():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "").strip()
    birth_md = payload.get("birth_md", "").strip()
    slot_id = payload.get("slot_id")
    
    if not name or not slot_id:
        return jsonify({"ok": False, "error": "이름과 요일 슬롯을 선택해주세요."}), 400
        
    display_id = f"{name}{birth_md}"
    
    from uuid import uuid4
    new_uuid = str(uuid4())
    
    workspace_data = _load_workspace_students()
    if display_id in workspace_data:
        new_uuid = workspace_data[display_id].get("user_uuid", new_uuid)
    else:
        workspace_data[display_id] = {
            "display_id": display_id,
            "name": name,
            "birth_md": birth_md,
            "accounts": [],
            "user_uuid": new_uuid
        }
        _save_workspace_students(workspace_data)
        
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    if display_id not in m:
        m[display_id] = new_uuid
        UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        
    doc = load_doc_by_any(new_uuid)
    doc["profile"] = {"name": name, "student_id": display_id}
    save_doc_by_any(new_uuid, doc)
    
    raw = load_schedule()
    for slot in raw.get("slots", []):
        if slot.get("id") == slot_id:
            students = slot.setdefault("students", [])
            if new_uuid not in students:
                students.append(new_uuid)
            break
    
    save_schedule(raw)
    return jsonify({"ok": True, "display_id": display_id})


@app.route("/api/workspace/generate_ai_prompt", methods=["POST"])
def api_workspace_generate_ai_prompt():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    
    workspace_data = _load_workspace_students()
    student = workspace_data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
        
    u = student.get("user_uuid") or display_id
    doc = load_doc_by_any(u)
    
    name = student.get("name", display_id)
    
    logs = doc.get("homework_logs", [])
    recent_hw = logs[-1] if logs else {}
    hw_list = recent_hw.get("problems", [])
    hw_titles = [f"[{p.get('legacy_code')}] {p.get('title')}" for p in hw_list]
    hw_text = "\n".join(hw_titles) if hw_titles else "숙제 없음"
    
    prompt = f"""다음은 {name} 학생의 오늘 학습 내용 및 숙제입니다. 학부모님께 보낼 피드백 문자를 친절하고 전문적인 어조로 작성해주세요.

[학생 이름] {name}
[오늘 부여된 숙제]
{hw_text}

[요청 사항]
- 숙제를 열심히 할 수 있도록 격려하는 멘트 포함
- 3~4문장으로 간결하게 작성
"""
    return jsonify({"ok": True, "prompt": prompt})


@app.route("/api/workspace/student_problems/<display_id>")
def api_workspace_student_problems(display_id):
    s, err = ensure_admin_or_403()
    if err:
        return err
    data = _load_workspace_students()
    student = data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
    
    # In v4, we can look up the user doc using user_uuid
    u = student.get("user_uuid") or display_id
    doc = load_doc_by_any(u)
    
    problems = []
    
    # We'll return recent homework logs as problems for now
    logs = doc.get("homework_logs", [])
    for log in logs:
        for p in log.get("problems", []):
            problems.append({
                "legacy_code": p.get("legacy_code"),
                "title": p.get("title", "알 수 없는 문제"),
                "status": "partial" # default
            })
            
    # Deduplicate
    seen = set()
    uniq_problems = []
    for p in problems:
        if p["legacy_code"] not in seen:
            seen.add(p["legacy_code"])
            uniq_problems.append(p)

    return jsonify({"ok": True, "problems": uniq_problems})

@app.route("/api/workspace/save_homework_log", methods=["POST"])
def api_workspace_save_homework_log():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    problems = payload.get("problems", [])
    
    data = _load_workspace_students()
    student = data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
        
    u = student.get("user_uuid") or display_id
    
    append_homework_log(u, {"problems": problems})
    
    return jsonify({"ok": True})


@app.route("/schedule")
def schedule_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    """
    요일별 학생 배치를 한눈에 보는 관리자 전용 페이지.
    """
    # 로그인 필수
    raw = load_schedule()
    slots_by_wday = {i: [] for i in range(7)}
    slots_by_wday[UNCERTAIN_WEEKDAY] = []

    for slot in raw.get("slots", []):
        try:
            w = int(slot.get("weekday", 0))
        except (TypeError, ValueError):
            w = 0
        if w not in slots_by_wday:
            w = UNCERTAIN_WEEKDAY
        slots_by_wday[w].append(slot)

    # order → label 순으로 정렬
    for w in slots_by_wday:
        slots_by_wday[w].sort(
            key=lambda s: (int(s.get("order", 0) or 0), str(s.get("label", "")))
        )

    hydrated_by_wday = {
        w: hydrate_slot_students(slots) for w, slots in slots_by_wday.items()
    }

    today_w = datetime.now(tz=KST).weekday()  # 월=0
    # 화면 표시 요일: 화~토 + 일정 불확실
    display_weekdays = [1, 2, 3, 4, 5, UNCERTAIN_WEEKDAY]
    weekday_label_map = {i: f"{WEEKDAY_LABELS[i]}요일" for i in range(7)}
    weekday_label_map[UNCERTAIN_WEEKDAY] = UNCERTAIN_WEEKDAY_LABEL

    role_ctx = {"role_label": "Admin", "is_admin": True}
    return render_template(
        "schedule.html",
        weekday_labels=WEEKDAY_LABELS,
        slots_by_wday=hydrated_by_wday,
        display_weekdays=display_weekdays,
        weekday_label_map=weekday_label_map,
        uncertain_weekday=UNCERTAIN_WEEKDAY,
        today_w=today_w,
        **role_ctx,
    )


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    open_browser = os.environ.get("FLASK_OPEN_BROWSER", "1").lower() in ("1", "true", "yes")

    # Werkzeug reloader parent process should not open a duplicate browser tab.
    should_open_browser = open_browser and (not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true")
    if should_open_browser:
        browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
        threading.Timer(0.7, lambda: webbrowser.open(f"http://{browser_host}:{port}")).start()

    app.run(host=host, port=port, debug=debug)
