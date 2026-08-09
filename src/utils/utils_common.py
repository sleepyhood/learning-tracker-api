# --- utils_common.py 같은 곳에 ---
from flask import Flask, request, render_template, redirect, url_for
import json
from collections import defaultdict
from flask import jsonify
import requests
from login import load_cookies, get_authenticated_session, is_cookie_valid
from datetime import datetime, timezone, timedelta
from pprint import pprint
from utils.streak_utils import generate_streak_data
from flask import session as fsession

import os
import re
from urllib.parse import quote
from utils.questions_crawler import do_crawling

from utils.summarizer import (
    summarize_progress,
    summarize_user_chapter_group,
    summarize_drilldown_progress,
)


from utils.questions_api import save_server_problems_json
from utils.legacy_map import build_legacy_map
from login import COOKIE_PATH

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

from pathlib import Path
import uuid

UTILS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = UTILS_DIR.parent.parent
META_DIR = PROJECT_ROOT / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

UUIDS_PATH = META_DIR / "uuids.json"
UUIDS_PATH.parent.mkdir(parents=True, exist_ok=True)

ADMIN_WHITELIST_PATH = META_DIR / "admin_whitelist.json"
ADMIN_WHITELIST_PATH.parent.mkdir(parents=True, exist_ok=True)
if not ADMIN_WHITELIST_PATH.exists():
    ADMIN_WHITELIST_PATH.write_text(
        json.dumps({"usernames": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_admin_whitelist() -> set[str]:
    try:
        data = json.loads(ADMIN_WHITELIST_PATH.read_text(encoding="utf-8"))
        names = data.get("usernames", [])
        return {str(x).strip() for x in names if str(x).strip()}
    except Exception:
        return set()


# --- 유틸들 ---


def get_api_session():
    cookies = load_cookies(COOKIE_PATH)
    if not cookies:  # ← 파일이 없거나 읽기 실패
        print(f"쿠키 없음")
        return None

    s = get_authenticated_session(cookies)
    if not s:  # ← cookie_dict None 방지
        print(f"누구세요?")
        return None

    if not is_cookie_valid(s):  # ← 무효 쿠키
        return None
    return s


def ensure_login_or_redirect():
    s = get_api_session()
    print(f"is_cookie_valid(s): {bool(s)}")
    if not s:
        return None, redirect("/login")
    return s, None


def fetch_profile(s, username=None, timeout=10):
    """username=None?? ? ???, ??? ?? ??? ???."""
    if username:
        res = s.get(
            f"{BASE_URL}/api/profile?username={quote(username)}", timeout=timeout
        )
    else:
        res = s.get(f"{BASE_URL}/api/profile", timeout=timeout)
    data = res.json()
    return data


def is_admin_profile(profile_json: dict) -> bool:
    payload = profile_json.get("data", {}) if profile_json else {}
    user_data = payload.get("user", {}) if payload else {}
    username = (user_data.get("username") or "").strip()
    admin_type = user_data.get("admin_type")
    _label, is_admin, _role_norm = normalize_role(admin_type)
    if is_admin:
        return True
    whitelist = load_admin_whitelist()
    return bool(username and username in whitelist)


def ensure_admin_or_redirect():
    s, redir = ensure_login_or_redirect()
    if redir:
        return None, redir
    try:
        prof = fetch_profile(s, username=None)
    except Exception:
        return None, ("forbidden", 403)
    if not is_admin_profile(prof):
        return None, ("forbidden", 403)
    return s, None


def ensure_admin_or_403():
    s = get_api_session()
    if not s:
        return None, (jsonify({"ok": False, "error": "unauthorized"}), 401)
    try:
        prof = fetch_profile(s, username=None)
    except Exception:
        return None, (jsonify({"ok": False, "error": "forbidden"}), 403)
    if not is_admin_profile(prof):
        return None, (jsonify({"ok": False, "error": "forbidden"}), 403)
    return s, None


def normalize_role(admin_type: str | None):
    """admin_type 문자열을 일관된 라벨/플래그로 변환"""
    t = (admin_type or "").strip().lower()
    print(f"[role] admin_type raw={admin_type!r} normalized={t!r}")
    if t in ("super admin", "superadmin", "super_admin", "super-admin", "owner", "root"):
        return ("총관리자", True, "superadmin")
    if t in ("admin", "teacher", "coach"):
        return ("관리자", True, "admin")
    return ("일반", False, "user")


def resolve_legacy_map_path():
    try:
        legacy_to_server_file = LEGACY_TO_SERVER_FILE
    except NameError:
        legacy_to_server_file = os.path.join(
            PROBLEM_DIR, "server_legacy_map_reverse.json"
        )
    return legacy_to_server_file if os.path.exists(legacy_to_server_file) else None


if not UUIDS_PATH.exists():
    UUIDS_PATH.write_text("{}", encoding="utf-8")


def resolve_uuid(student_id: str) -> str:
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    if student_id not in m:
        m[student_id] = str(uuid.uuid4())
        UUIDS_PATH.write_text(
            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return m[student_id]


def reverse_lookup(user_uuid: str) -> str | None:
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    for sid, u in m.items():
        if u == user_uuid:
            return sid
    return None


def user_doc_path_by_uuid(user_uuid: str) -> Path:
    return Path(USER_DATA_DIR) / f"{user_uuid}.json"


def load_user_doc_for(username: str) -> dict:
    """UUID 문서를 로드(없으면 초기 구조 생성)."""
    u = resolve_uuid(username)
    p = user_doc_path_by_uuid(u)
    if not p.exists():
        return {
            "user_uuid": u,
            "profile": {"student_id": username, "name": username},
            "oi_problems": {},
            "homework_logs": [],
        }
    return json.loads(p.read_text(encoding="utf-8"))


def save_user_doc(doc: dict):
    u = doc["user_uuid"]
    p = user_doc_path_by_uuid(u)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_user_problems(username: str, problems: dict):
    """
    듀얼 저장:
      - 문서(users_data/<uuid>.json): oi_problems 갱신(숙제로그/프로필 보존)
      - 캐시(users_data/<username>.json): 문제-only (기존 summarize_progress 호환)
    반환값은 '캐시 경로'(기존 호출부와 동일하게 사용되도록).
    """
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    # 1) 문서 업데이트 (UUID 파일)
    doc = load_user_doc_for(username)
    doc["profile"]["student_id"] = username
    # real_name/class_id 등은 가능하면 여기서 덮어쓰세요(상위 호출에서 넘길 때)
    doc["oi_problems"] = problems or {}
    save_user_doc(doc)

    # 2) 문제-only 캐시 (기존 summarize_progress가 읽는 파일)
    cache_filename = f"{sanitize_filename(username)}.json"
    cache_path = os.path.join(USER_DATA_DIR, cache_filename)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(problems or {}, f, ensure_ascii=False, indent=2)

    return cache_path


def fetch_submissions_window(s, username, myself: int, days=30, limit=100):
    """최근 N일 제출을 페이지네이션으로 모아 반환 (create_time이 cutoff 이전이면 중단)"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    results, page = [], 1
    while True:
        r = s.get(
            f"{BASE_URL}/api/submissions",
            params={
                "myself": myself,
                "starred": 0,
                "result": "",
                "username": username,
                "page": page,
                "limit": limit,
                "offset": (page - 1) * limit,
            },
            timeout=20,
        ).json()["data"]["results"]
        if not r:
            break
        r.sort(key=lambda x: x["create_time"], reverse=True)
        for rec in r:
            ts = datetime.fromisoformat(rec["create_time"].replace("Z", "+00:00"))
            if ts.replace(tzinfo=None) < cutoff:
                return results
            results.append(rec)
        page += 1
    return results


def filter_main_account_submissions(submissions, true_username):
    if not isinstance(submissions, (list, tuple)):
        return []
    return [rec for rec in submissions if isinstance(rec, dict) and (not rec.get("username") or rec.get("username") == true_username)]


def compute_primary_language(submissions, now=None):
    """하루/문제/언어 중복 제거 + 7/30/90일 가중치로 상위 언어 계산"""
    if not now:
        now = datetime.now(timezone.utc)
    seen = set()
    score = defaultdict(int)
    count90 = defaultdict(int)
    if not isinstance(submissions, (list, tuple)):
        return None, []

    for rec in submissions:
        if not isinstance(rec, dict) or not rec.get("create_time"):
            continue
        try:
            ts = datetime.fromisoformat(str(rec["create_time"]).replace("Z", "+00:00"))
        except Exception:
            continue
        day = ts.date()
        lang = rec.get("language") or "Unknown"
        pid = rec.get("problem")
        if isinstance(pid, dict):
            pid = pid.get("_id") or pid.get("id") or str(pid)
        else:
            pid = str(pid)
        key = (day, pid, lang)
        if key in seen:
            continue
        seen.add(key)
        delta = (now - ts).days
        w = 3 if delta <= 7 else 2 if delta <= 30 else 1
        score[lang] += w
        count90[lang] += 1
    if not score:
        return None, []
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], -count90[kv[0]], kv[0]))
    top_lang = ranked[0][0]
    top3 = [(lang, count90[lang]) for lang, _ in ranked[:3]]
    return top_lang, top3


def build_dashboard_viewmodel(*args, **kwargs):
    """
    지원 형태 1: build_dashboard_viewmodel(s, profile_json: dict, is_me: bool, days: int = 7, curr_key: str = 'prog1')
    지원 형태 2: build_dashboard_viewmodel(username_raw=..., user_uuid=..., profile=..., submissions=..., problems_dict=..., role_ctx=..., curr_key=...)
    """
    curr_key = kwargs.get("curr_key") or kwargs.get("curr") or "prog1"
    curriculum_file_map = {
        "prog1": "all_problems.json",
        "prog2": "prog2_problems.json",
        "block": "block_problems.json",
        "external": "external_problems.json",
    }
    target_filename = curriculum_file_map.get(curr_key, "all_problems.json")
    target_problem_file = os.path.join(PROBLEM_DIR, target_filename)
    if not os.path.exists(target_problem_file):
        target_problem_file = PROBLEM_FILE

    if len(args) >= 2 or "profile_json" in kwargs:
        s = args[0] if len(args) > 0 else kwargs.get("s")
        profile_json = args[1] if len(args) > 1 else kwargs.get("profile_json", {})
        is_me = args[2] if len(args) > 2 else kwargs.get("is_me", False)
        days = args[3] if len(args) > 3 else kwargs.get("days", 7)

        payload = profile_json.get("data", {})
        user_data = payload.get("user", {})
        username = user_data.get("username", "")

        role_label, is_admin, role_norm = normalize_role(user_data.get("admin_type"))
        if is_me:
            fsession["role"] = role_norm

        problems = payload.get("oi_problems_status", {}).get("problems", {})

        myself_flag = 1 if is_me else 0
        submissions = fetch_submissions_window(
            s, username, myself=myself_flag, days=max(days, 30), limit=100
        )
        filtered = filter_main_account_submissions(submissions, username)

        problems = _merge_submissions_list_into_problems(filtered, problems)
        user_path = cache_user_problems(username, problems)

        legacy_map = resolve_legacy_map_path()
        chapter_summary = summarize_progress(
            target_problem_file, user_path, legacy_map_file=legacy_map
        )
        drilldown_summary = summarize_drilldown_progress(
            target_problem_file, user_path, legacy_map_file=legacy_map
        )

        streak = generate_streak_data(filtered, days=days)
        top_lang, top3 = compute_primary_language(filtered)
        last_login_fmt = format_last_login(user_data.get("last_login"))
        avatar = payload.get("avatar") or "/public/avatar/default.png"
        avatar_path = f"{BASE_URL}{avatar}"

        return dict(
            username=username,
            real_name=user_data.get("realname") or username,
            last_login=last_login_fmt,
            accepted_number=payload.get("accepted_number"),
            submission_number=payload.get("submission_number"),
            total_score=payload.get("total_score"),
            progress_data=chapter_summary,
            drilldown_data=drilldown_summary,
            streak_data=streak,
            avatar_path=avatar_path,
            role_label=role_label,
            is_admin=is_admin,
            primary_lang=top_lang,
            primary_lang_top3=top3,
            current_curr=curr_key,
        )

    # 형태 2: kwargs 기반 호출 지원
    username = kwargs.get("username_raw") or kwargs.get("username", "")
    user_uuid = kwargs.get("user_uuid", "")
    profile = kwargs.get("profile", {})
    submissions = kwargs.get("submissions", [])
    days = kwargs.get("days", 7)

    filtered = filter_main_account_submissions(submissions, username)
    top_lang, top3 = compute_primary_language(filtered)
    last_login_fmt = format_last_login(profile.get("last_login", "")) if profile.get("last_login") else "-"
    role_label, is_admin, _ = normalize_role(profile.get("admin_type"))
    avatar = profile.get("avatar") or "/public/avatar/default.png"
    avatar_path = f"{BASE_URL}{avatar}" if not avatar.startswith("http") else avatar

    user_path = os.path.join(USER_DATA_DIR, f"{sanitize_filename(username)}.json")
    if not os.path.exists(user_path) and user_uuid:
        user_path = os.path.join(USER_DATA_DIR, f"{user_uuid}.json")

    legacy_map = resolve_legacy_map_path()
    solve_path = user_path if os.path.exists(user_path) else None
    chapter_summary = summarize_progress(
        target_problem_file, solve_path, legacy_map_file=legacy_map
    )
    drilldown_summary = summarize_drilldown_progress(
        target_problem_file, solve_path, legacy_map_file=legacy_map
    )
    streak = generate_streak_data(filtered, days=days)

    return dict(
        username=username,
        real_name=profile.get("name") or profile.get("realname") or username,
        last_login=last_login_fmt,
        accepted_number=profile.get("accepted_number", 0),
        submission_number=profile.get("submission_number", len(submissions)),
        total_score=profile.get("total_score", 0),
        progress_data=chapter_summary,
        drilldown_data=drilldown_summary,
        streak_data=streak,
        avatar_path=avatar_path,
        role_label=role_label,
        is_admin=is_admin,
        primary_lang=top_lang,
        primary_lang_top3=top3,
        current_curr=curr_key,
    )


#########


def ensure_problem_assets():
    os.makedirs(PROBLEM_DIR, exist_ok=True)
    need_crawl = not os.path.exists(PROBLEM_FILE)
    need_api = not os.path.exists(SERVER_DUMP_FILE)
    # ✅ 맵 파일 두 가지 다 검사
    need_maps = not (
        os.path.exists(SERVER_TO_LEGACY_FILE) and os.path.exists(LEGACY_TO_SERVER_FILE)
    )
    if need_crawl:
        do_crawling(output_dir=PROBLEM_DIR, filename="all_problems.json")

    if need_api:
        save_server_problems_json(out_path=SERVER_DUMP_FILE)

    if need_maps:
        # build_legacy_map가 server_legacy_map.json + server_legacy_map_reverse.json 둘 다 쓰게 구현되어 있어야 함
        build_legacy_map(
            PROBLEM_FILE,
            SERVER_DUMP_FILE,
            out_map_path=SERVER_TO_LEGACY_FILE,  # 서버→레거시
            out_unmatched_path=UNMATCHED_FILE,  # 미매핑
        )


# 몰?루
def sanitize_filename(name):
    # 파일명으로 부적절한 문자를 밑줄(_)로 대체
    return re.sub(r'[\\/:"*?<>|]+', "_", name)


def format_last_login(last_login_str):
    now = datetime.now(timezone.utc)
    last_login = datetime.fromisoformat(last_login_str.replace("Z", "+00:00"))
    delta = now - last_login

    if delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() // 60)
        return f"{minutes}분 전"
    elif delta < timedelta(hours=24):
        hours = int(delta.total_seconds() // 3600)
        return f"{hours}시간 전"
    elif delta < timedelta(days=7):
        days = delta.days
        return f"{days}일 전"
    else:
        return last_login.strftime("%Y년 %m월 %d일")


def get_progress(solved_list, problem_info):
    progress = defaultdict(int)
    for pid in solved_list:
        for prefix, info in problem_info.items():
            if pid.startswith(prefix):
                progress[info["title"]] += 1
                break
    return progress


def calculate_progress(solved_list, chapter_json):
    progress_data = []

    for group_id, info in chapter_json.items():
        total = info["total"]
        problem_names = info["problem_names"]
        title = info["title"]

        # 푼 문제 개수만 카운트
        solved = sum(1 for pid in problem_names if pid in solved_list)
        percent = round(solved / total * 100, 1) if total else 0

        progress_data.append(
            {
                "group_id": group_id,
                "title": title,
                "solved": solved,
                "total": total,
                "percent": percent,
            }
        )

    return progress_data


def role_ctx_from_session():
    """??? ??? role? ???? ????? ??"""
    r = (fsession.get("role") or "").lower()
    if not r:
        s = get_api_session()
        if s:
            try:
                prof = fetch_profile(s, username=None)
                user_data = (prof.get("data", {}) or {}).get("user", {}) or {}
                role_label, is_admin, role_norm = normalize_role(
                    user_data.get("admin_type")
                )
                fsession["role"] = role_norm
                return {"role_label": role_label, "is_admin": is_admin}
            except Exception:
                pass
        r = "user"
    if r in ("superadmin", "owner"):
        return {"role_label": "????", "is_admin": True}
    if r in ("admin", "teacher", "coach"):
        return {"role_label": "???", "is_admin": True}
    return {"role_label": "??", "is_admin": False}


def _merge_submissions_list_into_problems(submissions, problems: dict) -> dict:
    if not submissions:
        return problems
    merged = dict(problems)
    
    legacy_to_server = resolve_legacy_map_dict()
    server_to_legacy = {v: k for k, v in legacy_to_server.items()}

    for rec in submissions:
        pid = rec.get("problem")
        if isinstance(pid, dict):
            pid = pid.get("_id") or pid.get("id") or str(pid)
        pid = str(pid).strip()
        if not pid:
            continue

        if pid in legacy_to_server:
            legacy_code = pid
            server_id = legacy_to_server[pid]
        elif pid in server_to_legacy:
            server_id = pid
            legacy_code = server_to_legacy[pid]
        else:
            server_id = pid
            legacy_code = pid

        result = rec.get("result")
        score = rec.get("statistic_info", {}).get("score", 0)
        status = 0 if result == 0 else -1

        if server_id not in merged:
            merged[server_id] = {
                "_id": legacy_code,
                "score": score,
                "status": status
            }
        else:
            existing_status = merged[server_id].get("status")
            if status == 0 or (existing_status != 0 and status == -1):
                merged[server_id]["status"] = status
                merged[server_id]["score"] = max(merged[server_id].get("score", 0), score)
    return merged


def merge_submissions_into_problems(api_session, username: str, problems: dict) -> dict:
    try:
        submissions = fetch_submissions_window(
            api_session, username, myself=0, days=30, limit=100
        )
        problems = _merge_submissions_list_into_problems(submissions, problems)
    except Exception as e:
        print(f"[merge_submissions_into_problems] failed for {username}: {e}")
    return problems


def sync_user_problems_cache(
    api_session, username: str, timeout=10
) -> tuple[dict, str]:
    """
    프로필을 가져와 문제 상태를 캐시에 저장하고 (USER_DATA_DIR/<username>.json),
    (profile_json, user_path) 를 반환.
    """

    os.makedirs(USER_DATA_DIR, exist_ok=True)

    encoded_username = quote(username)
    prof = api_session.get(
        f"{BASE_URL}/api/profile?username={encoded_username}", timeout=timeout
    ).json()
    problems = prof.get("data", {}).get("oi_problems_status", {}).get("problems", {})

    # 최근 30일 제출 현황을 반영하여 실시간 동기화율 향상
    problems = merge_submissions_into_problems(api_session, username, problems)

    filename = f"{sanitize_filename(username)}.json"
    user_path = os.path.join(USER_DATA_DIR, filename)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

    return prof, user_path


def ensure_user_cache_or_404(user_id_or_uuid: str, api_session=None, max_age_seconds: int = 600) -> tuple[dict, bool]:
    """
    유저 캐시 데이터(USER_DATA_DIR/{uuid}.json)를 로드하고,
    캐시가 없거나 max_age_seconds 초 초과 시 API 세션을 통해 최신화한 뒤
    (data_dict, is_success) 튜플을 반환.
    """
    try:
        from utils.utils_user_doc import load_doc_by_any, is_doc_stale, pull_and_store_user, resolve_uuid

        user_uuid = resolve_uuid(user_id_or_uuid) if "-" not in str(user_id_or_uuid) else str(user_id_or_uuid)
        doc = load_doc_by_any(user_uuid)

        username = (doc.get("profile") or {}).get("student_id") or (doc.get("profile") or {}).get("username") or user_id_or_uuid
        ttl_ms = max_age_seconds * 1000

        if (is_doc_stale(doc, ttl_ms=ttl_ms) or not doc.get("profile")) and api_session and username:
            try:
                doc = pull_and_store_user(username)
            except Exception as e:
                print(f"[ensure_user_cache_or_404] Sync failed for {username}: {e}")

        if not doc:
            return {}, False

        doc.setdefault("profile", {"student_id": username, "name": username})
        doc.setdefault("submissions", doc.get("oi_problems") or [])
        doc.setdefault("problems_dict", doc.get("oi_problems") if isinstance(doc.get("oi_problems"), dict) else {})

        return doc, True
    except Exception as e:
        print(f"[ensure_user_cache_or_404] Exception for {user_id_or_uuid}: {e}")
        return {}, False


def resolve_legacy_map_dict():
    """레거시→서버ID 맵을 dict로 로드(없으면 빈 dict)"""
    from config import LEGACY_TO_SERVER_FILE, PROBLEM_DIR

    path = LEGACY_TO_SERVER_FILE or os.path.join(PROBLEM_DIR, "server_legacy_map_reverse.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def resolve_uuid(student_id: str) -> str:
    """레거시 student_id에 대응하는 UUID를 반환(없으면 생성)."""
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    if student_id not in m:
        m[student_id] = str(uuid.uuid4())
        UUIDS_PATH.write_text(
            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return m[student_id]
