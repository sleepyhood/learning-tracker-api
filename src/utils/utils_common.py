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

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

import re
from urllib.parse import quote
from utils.questions_crawler import do_crawling

from utils.summarizer import (
    summarize_progress,
    summarize_user_chapter_group,
)  # 너가 사용하는 함수 경로에 따라 조정 필요


from utils.questions_api import save_server_problems_json
from utils.legacy_map import build_legacy_map
from login import COOKIE_PATH

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")

PROBLEM_FILE = os.path.join(PROBLEM_DIR, "all_problems.json")
SERVER_DUMP_FILE = os.path.join(PROBLEM_DIR, "server_problems.json")

# ✅ 추천: 파일명 명확화
SERVER_TO_LEGACY_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map.json")
LEGACY_TO_SERVER_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map_reverse.json")
UNMATCHED_FILE = os.path.join(PROBLEM_DIR, "legacy_unmatched.json")

# app = Flask(__name__)


USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")

BASE_URL = os.environ.get("API_BASE_URL")

if not BASE_URL:
    raise RuntimeError("환경 변수 API_BASE_URL이 설정되지 않았습니다.")


#########


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
    """username=None이면 내 프로필, 아니면 해당 유저 프로필"""
    if username:
        res = s.get(
            f"{BASE_URL}/api/profile?username={quote(username)}", timeout=timeout
        )
    else:
        res = s.get(f"{BASE_URL}/api/profile", timeout=timeout)
    data = res.json()
    return data


def normalize_role(admin_type: str | None):
    """admin_type 문자열을 일관된 라벨/플래그로 변환"""
    t = (admin_type or "").strip().lower()
    if t in ("super admin", "superadmin", "owner"):
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


def cache_user_problems(username: str, problems: dict):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    filename = f"{sanitize_filename(username)}.json"
    user_path = os.path.join(USER_DATA_DIR, filename)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)
    return user_path


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
    return [rec for rec in submissions if rec.get("username") == true_username]


def compute_primary_language(submissions, now=None):
    """하루/문제/언어 중복 제거 + 7/30/90일 가중치로 상위 언어 계산"""
    if not now:
        now = datetime.now(timezone.utc)
    seen = set()
    score = defaultdict(int)
    count90 = defaultdict(int)
    for rec in submissions:
        ts = datetime.fromisoformat(rec["create_time"].replace("Z", "+00:00"))
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


# ... build_dashboard_viewmodel 에 days 파라미터 전달
def build_dashboard_viewmodel(s, profile_json: dict, is_me: bool, days: int = 7):
    payload = profile_json.get("data", {})
    user_data = payload.get("user", {})
    username = user_data.get("username", "")

    role_label, is_admin, role_norm = normalize_role(user_data.get("admin_type"))
    if is_me:
        fsession["role"] = role_norm

    problems = payload.get("oi_problems_status", {}).get("problems", {})
    user_path = cache_user_problems(username, problems)

    legacy_map = resolve_legacy_map_path()
    chapter_summary = summarize_progress(
        PROBLEM_FILE, user_path, legacy_map_file=legacy_map
    )

    myself_flag = 1 if is_me else 0
    submissions = fetch_submissions_window(
        s, username, myself=myself_flag, days=max(days, 7), limit=100
    )
    filtered = filter_main_account_submissions(submissions, username)

    # ✅ days 반영
    streak = generate_streak_data(filtered, days=days)

    top_lang, top3 = compute_primary_language(filtered)
    last_login_fmt = format_last_login(user_data.get("last_login"))
    avatar = payload.get("avatar") or "/public/avatar/default.png"
    avatar_path = f"{BASE_URL}{avatar}"

    return dict(
        username=username,
        last_login=last_login_fmt,
        accepted_number=payload.get("accepted_number"),
        submission_number=payload.get("submission_number"),
        total_score=payload.get("total_score"),
        progress_data=chapter_summary,
        streak_data=streak,
        avatar_path=avatar_path,
        role_label=role_label,
        is_admin=is_admin,
        primary_lang=top_lang,
        primary_lang_top3=top3,
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
    """세션에 저장된 정규화 role → 템플릿용 컨텍스트로 변환"""
    r = (fsession.get("role") or "user").lower()
    if r in ("superadmin", "owner"):
        return {"role_label": "총관리자", "is_admin": True}
    if r in ("admin", "teacher", "coach"):
        return {"role_label": "관리자", "is_admin": True}
    return {"role_label": "일반", "is_admin": False}


def sync_user_problems_cache(
    api_session, username: str, timeout=10
) -> tuple[dict, str]:
    """
    프로필을 가져와 문제 상태를 캐시에 저장하고 (USER_DATA_DIR/<username>.json),
    (profile_json, user_path) 를 반환.
    """
    from app import USER_DATA_DIR, PROBLEM_DIR, BASE_URL  # 필요 시 조정

    os.makedirs(USER_DATA_DIR, exist_ok=True)

    encoded_username = quote(username)
    prof = api_session.get(
        f"{BASE_URL}/api/profile?username={encoded_username}", timeout=timeout
    ).json()
    problems = prof.get("data", {}).get("oi_problems_status", {}).get("problems", {})

    filename = f"{sanitize_filename(username)}.json"
    user_path = os.path.join(USER_DATA_DIR, filename)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

    return prof, user_path


def ensure_user_cache_or_404(user_path: str, problem_file: str, username: str):
    if not os.path.exists(user_path) or not os.path.exists(problem_file):
        return f"{username} 또는 문제 파일이 존재하지 않습니다."
    return None


def resolve_legacy_map_dict():
    """레거시→서버ID 맵을 dict로 로드(없으면 빈 dict)"""
    try:
        from app import LEGACY_TO_SERVER_FILE

        path = LEGACY_TO_SERVER_FILE
    except NameError:
        from app import PROBLEM_DIR

        path = os.path.join(PROBLEM_DIR, "server_legacy_map_reverse.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}
