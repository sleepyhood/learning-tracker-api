from flask import Flask, request, render_template, redirect, url_for
import json

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
from utils.questions_crawler import do_crawling

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


#########

from utils.utils_user_doc import (
    load_doc_by_any,
    save_doc_by_any,
    _user_doc_path_by_uuid,
)
import uuid

# UUID 레지스트리(레거시ID ↔ UUID 매핑) 파일 경로
UUIDS_PATH = Path("meta/uuids.json")
UUIDS_PATH.parent.mkdir(parents=True, exist_ok=True)
if not UUIDS_PATH.exists():
    UUIDS_PATH.write_text("{}", encoding="utf-8")

KST = timezone(timedelta(hours=9))

# homework_latest_batch에서 학생별 submissions 조회 결과를 짧게 캐시
TODAY_ACTIVITY_CACHE: dict[str, dict] = {}
TODAY_ACTIVITY_CACHE_LOCK = threading.Lock()
TODAY_ACTIVITY_CACHE_MAX = 5000




# ===== 요일별 스케줄 저장용 =====
SCHEDULE_PATH = Path("meta/schedule.json")
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

            students_detail.append(
                {
                    "user_uuid": user_uuid,
                    "student_id": student_id,
                    "name": name,
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


def _is_admin_route(path: str) -> bool:
    return path in ADMIN_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in ADMIN_ONLY_PREFIXES
    )


def _is_student_route(path: str) -> bool:
    return path in STUDENT_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in STUDENT_ONLY_PREFIXES
    )


@app.before_request
def enforce_subdomain_access():
    if not ADMIN_DOMAIN and not STUDENT_DOMAIN:
        return None

    host = (request.host or "").split(":")[0].lower()
    if _is_localhost(host):
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
@app.route("/update_problems", methods=["POST"])
def update_problems():
    s, err = ensure_admin_or_403()
    if err:
        return err
    os.makedirs(PROBLEM_DIR, exist_ok=True)

    problem_file_path = do_crawling(
        output_dir=PROBLEM_DIR, filename="all_problems.json"
    )

    save_server_problems_json(out_path=SERVER_DUMP_FILE)

    build_legacy_map(
        problem_file_path,
        SERVER_DUMP_FILE,
        out_map_path=SERVER_TO_LEGACY_FILE,
        out_unmatched_path=UNMATCHED_FILE,
    )

    return jsonify(
        {
            "message": "문제 목록이 갱신되었습니다. (크롤링 + API + 매핑)",
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

    flags = {
        "is_given_today": bool(given_date and given_date == today),
        "all_passed": total > 0 and passed == total,
        "has_any": total > 0,
        "has_unresolved": (wrong + pending) > 0,
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
    return render_template(
        "index.html",
        **vm,
        view_mode="me",
        view_username="",
        user_uuid=my_uuid,  # uuid 필드
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

    return render_template(
        "index.html",
        **vm,
        view_mode="user",
        view_username=username,
        user_uuid=other_uuid,  # uuid 필드
    )


from flask import render_template, redirect
from urllib.parse import quote


@app.route("/user/<username>/chapter/<chapter>")
def chapter_detail(username, chapter):
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
        **role_ctx,  # role_label, is_admin
    )


@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
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
    app.run(debug=True)
