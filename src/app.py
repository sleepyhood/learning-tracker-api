from flask import Flask, request, render_template, redirect, url_for
import json

from flask import jsonify
import requests
from login import load_cookies, get_authenticated_session, is_cookie_valid
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
from utils.questions_crawler import do_crawling

from utils.summarizer import (
    summarize_progress,
    summarize_user_chapter_group,
)  # 너가 사용하는 함수 경로에 따라 조정 필요


from utils.questions_api import save_server_problems_json
from utils.legacy_map import build_legacy_map
from utils.utils_common import (
    ensure_login_or_redirect,
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
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# --- imports 상단 ---
from flask import session as fsession
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
import os, json
from collections import defaultdict


# 문제 목록 강제 업데이트 기능
@app.route("/update_problems", methods=["POST"])
def update_problems():
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
    }
    doc["user_uuid"] = resolve_uuid(student_id)
    doc["oi_problems"] = problems
    doc.setdefault("homework_logs", doc.get("homework_logs", []))
    doc["updated_at"] = datetime.now(tz=KST).isoformat()

    save_doc_by_any(student_id, doc)
    return doc


@app.route("/api/students/<user_uuid>/refresh", methods=["POST"])
def refresh_by_uuid(user_uuid):
    try:
        cookies = load_cookies(COOKIE_PATH)
        session = get_authenticated_session(cookies)

        base = load_doc_by_any(user_uuid)
        username = (base.get("profile") or {}).get("student_id") or (
            base.get("profile") or {}
        ).get("name")
        if not username:
            username = reverse_lookup(user_uuid)
            if not username:
                return (
                    jsonify({"success": False, "error": "username not resolvable"}),
                    400,
                )
            base.setdefault("profile", {})
            base["profile"]["student_id"] = username
            base["profile"].setdefault("name", username)

        # 원격 데이터
        res = session.get(f"{BASE_URL}/api/profile?username={quote(username)}")
        data = res.json()
        user_data = data["data"]["user"]
        problems = data["data"]["oi_problems_status"]["problems"]

        # ✅ 저장 직전 다시 읽어 'homework_logs' 보존
        current = load_doc_by_any(user_uuid)
        current["profile"] = {
            "student_id": user_data["username"],
            "name": user_data.get("realname") or user_data.get("username"),
            "class_id": user_data.get("class_id"),
        }
        current["oi_problems"] = problems
        current["updated_at"] = datetime.now(tz=KST).isoformat()
        # current["homework_logs"] 는 그대로 두기!

        save_doc_by_any(user_uuid, current)
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
    doc = load_doc_by_any(user_uuid)
    return jsonify(compute_homework_status(doc))


# DELETE /api/students/<id_or_uuid>/homework_logs/<log_key>
# log_key: 로그의 uuid id 또는 index(0-based)
@app.delete("/api/students/<id_or_uuid>/homework_logs/<log_key>")
def api_delete_homework_log(id_or_uuid, log_key):
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
    print(f"doc: {doc["homework_logs"]}")
    save_doc_by_any(u, doc)
    # print(f"logs: {logs}")
    return jsonify({"ok": True, "count": len(logs)})


@app.route("/api/students/<id_or_uuid>/homework_logs", methods=["POST", "OPTIONS"])
def api_save_homework_log(id_or_uuid):
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


@app.get("/api/students/<user_uuid>/homework_latest")
def homework_latest(user_uuid):
    doc = load_doc_by_any(user_uuid)
    logs = doc.get("homework_logs", [])
    if not logs:
        return jsonify({"ok": True, "log": None})

    # 가장 최신: ts 기준(없으면 배열 마지막)
    def ts_val(x):
        return x.get("ts") or ""

    latest_log = max(logs, key=ts_val) if any(x.get("ts") for x in logs) else logs[-1]
    key = latest_log.get("log_id") or latest_log.get("ts")

    # 상태/카운트 계산은 기존 compute_homework_status를 재사용
    status = compute_homework_status(doc)
    item = next((it for it in status["items"] if it["key"] == key), None)

    # 결합 응답 (뷰에서 쓰는 필드만)
    return jsonify(
        {
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
                    else {"total": 0, "passed": 0, "wrong": 0, "pending": 0}
                ),
                "problem_status": item["problems"] if item else [],
            },
        }
    )


# ✅ 뷰어: UUID로 학생 숙제로그 열람 (템플릿: templates/homework_view.html 필요)
@app.get("/students/<user_uuid>/homework")
def view_homework_logs(user_uuid):
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
    role_ctx = role_ctx_from_session()
    # print(f"result: {result}")
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


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
