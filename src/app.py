from flask import Flask, request, render_template, redirect, url_for
import json
from collections import defaultdict
from flask import jsonify
import requests
from login import load_cookies, get_authenticated_session, is_cookie_valid
from datetime import datetime, timezone, timedelta
from pprint import pprint
from utils.streak_utils import generate_streak_data

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

from utils.user_crawler import crawl_user
import re
from urllib.parse import quote
from utils.questions_crawler import do_crawling

from utils.summarizer import (
    summarize_progress,
    summarize_user_chapter_group,
)  # 너가 사용하는 함수 경로에 따라 조정 필요


from utils.questions_api import save_server_problems_json
from utils.legacy_map import build_legacy_map

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")
COOKIE_PATH = os.path.join(BASE_DIR, "cookies.json")

PROBLEM_FILE = os.path.join(PROBLEM_DIR, "all_problems.json")
SERVER_DUMP_FILE = os.path.join(PROBLEM_DIR, "server_problems.json")

# ✅ 추천: 파일명 명확화
SERVER_TO_LEGACY_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map.json")
LEGACY_TO_SERVER_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map_reverse.json")
UNMATCHED_FILE = os.path.join(PROBLEM_DIR, "legacy_unmatched.json")

# app = Flask(__name__)
app = Flask(__name__, static_folder="static")

import os


USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")

COOKIE_PATH = os.path.join(BASE_DIR, "cookies.json")

BASE_URL = os.environ.get("API_BASE_URL")

login_user_type = "Regular User"  # 유저 로그인 타입은 전역변수로

if not BASE_URL:
    raise RuntimeError("환경 변수 API_BASE_URL이 설정되지 않았습니다.")


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


@app.route("/", methods=["GET", "POST"])
def index():

    ensure_problem_assets()

    global login_user_type
    # 쿠키 확인
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    if not is_cookie_valid(session):
        return redirect("/login")

    # 기본 유저명: 로그인한 유저명 or 입력받은 유저명
    username = ""

    # print(f"user_overview: {username}")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:

            # 다른 유저 조회 요청 시
            return redirect(
                url_for("user", username=username)
            )  # ✅ 이 부분에서 처리 위임
        else:
            return "유저명을 입력해주세요.", 400

    # 유저 정보 가져오기

    res = session.get(f"{BASE_URL}/api/profile")  # ✅ 현재 유저 정보
    data = json.loads(res.text)

    user_data = data["data"]["user"]
    username = user_data["username"]

    # pprint(data["data"]["oi_problems_status"])
    filename = f"{sanitize_filename(user_data['username'])}.json"

    user_path = os.path.join(USER_DATA_DIR, filename)

    os.makedirs(USER_DATA_DIR, exist_ok=True)

    payload = data.get("data", {})

    problems = payload.get("oi_problems_status", {}).get("problems", {})

    # 사용자 문제 상태 저장
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(
            data["data"]["oi_problems_status"]["problems"],
            f,
            ensure_ascii=False,
            indent=2,
        )

    lastLogin = format_last_login(user_data["last_login"])

    # ... (사용자 로그인/데이터 로드 등)

    # ✅ 레거시→서버ID 맵 파일 사용
    try:
        legacy_to_server_file = LEGACY_TO_SERVER_FILE
    except NameError:
        legacy_to_server_file = os.path.join(
            PROBLEM_DIR, "server_legacy_map_reverse.json"
        )
    legacy_map_arg = (
        legacy_to_server_file if os.path.exists(legacy_to_server_file) else None
    )

    all_chapter_data = summarize_progress(
        PROBLEM_FILE, user_path, legacy_map_file=legacy_map_arg
    )

    # print(f"progress_data: {progress_data}")
    # 제출 기록
    records = session.get(
        f"{BASE_URL}/api/submissions?myself=1&starred=0&result=&username={username}&page=1&limit=100&offset=0"
    )
    records = records.json()

    true_username = user_data["username"]
    # pprint(records["data"]["results"])
    raw_submissions = records["data"]["results"]
    # 메인 계정으로 푼 문제만 필터링
    filtered_submissions = [
        rec for rec in raw_submissions if rec.get("username") == true_username
    ]
    streak_data = generate_streak_data(filtered_submissions)

    # pprint(records["data"]["results"])
    # for rec in records["data"]["results"]:
    #     problem = rec["problem"]
    #     user = rec["username"]
    #     lang = rec["language"]
    #     result = rec["result"]
    #     score = rec["statistic_info"]["score"]
    #     # time_cost = rec["statistic_info"]["time_cost"]
    #     # memory_cost = rec["statistic_info"]["memory_cost"]
    #     # ISO 포맷 날짜를 사람이 읽기 편한 형태로 변경
    #     create_time = datetime.fromisoformat(
    #         rec["create_time"].replace("Z", "+00:00")
    #     ).strftime("%Y-%m-%d %H:%M:%S")

    #     print(
    #         f"{create_time} | 문제: {problem} | 사용자: {user} | 언어: {lang} | 결과: {result} | 점수: {score} "
    # )

    # 프로필 이미지 가져오기
    # 기본값은 /public/avatar/dafault.png
    avatar = data["data"].get("avatar") or "/public/avatar/default.png"

    avatar_path = f"{BASE_URL}{avatar}"
    # print(f"avatar_path: {avatar_path}")
    # print(f"user_data.get(): { user_data["admin_type"]}")
    login_user_type = user_data["admin_type"]
    return render_template(
        "index.html",
        username=username,
        last_login=lastLogin,
        accepted_number=data["data"]["accepted_number"],
        submission_number=data["data"]["submission_number"],
        total_score=data["data"]["total_score"],
        progress_data=all_chapter_data,
        streak_data=streak_data,  # 👈 스트릭 추가
        avatar_path=avatar_path,  # 프로필 이미지
        admin_type=login_user_type,  # ✅ 여기 추가
    )


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


@app.route("/refresh_user/<username>")
def refresh_user(username):
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    encoded_username = quote(username)

    # 유저 목록?
    # users_rank = session.get(
    #     f"http://edu.doingcoding.com/api/user_rank?offset=0&limit=201&rule=ACM"
    # )
    # users_rank = users_rank.json()
    # usernames = [entry["user"]["username"] for entry in users_rank["data"]["results"]]

    # print(f"users_rank: {usernames}")

    try:
        res = session.get(f"{BASE_URL}/api/profile?username={encoded_username}")
        data = res.json()
        user_data = data["data"]["user"]
        # print(f"user_data: {user_data}")
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

    # 저장
    filename = f"{sanitize_filename(user_data['username'])}.json"
    user_path = os.path.join(USER_DATA_DIR, filename)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(
            data["data"]["oi_problems_status"]["problems"],
            f,
            ensure_ascii=False,
            indent=2,
        )

    return jsonify({"success": True, "updated_at": datetime.now().isoformat()})


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


@app.route("/user/<username>")
def user(username):
    global login_user_type

    print(f"user_overview: {username}")
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    try:
        # username에 특수문자 들어간 경우 예외 처리
        from urllib.parse import quote

        encoded_username = quote(username)
        print(f"encoded_username: {encoded_username}")
        res = session.get(f"{BASE_URL}/api/profile?username={encoded_username}")
        data = res.json()
        user_data = data["data"]["user"]
    except Exception as e:
        return f"❌ 사용자 정보를 불러오지 못했습니다: {e}", 500

    # filename = f"{user_data['username']}.json"
    filename = f"{sanitize_filename(user_data['username'])}.json"

    user_path = os.path.join(USER_DATA_DIR, filename)

    sample = data["data"]
    # print(f"{username}의 데이터: {sample}")
    # pprint(data["data"]["avatar"])

    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(
            data["data"]["oi_problems_status"]["problems"],
            f,
            ensure_ascii=False,
            indent=2,
        )

    ensure_problem_assets()

    # (권장) 최신 사용자 데이터로 갱신
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    if not is_cookie_valid(session):
        return redirect("/login")
    try:
        encoded_username = quote(username)
        res = session.get(
            f"{BASE_URL}/api/profile?username={encoded_username}", timeout=10
        )
        data = res.json()
        problems = (
            data.get("data", {}).get("oi_problems_status", {}).get("problems", {})
        )
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        with open(user_path, "w", encoding="utf-8") as f:
            json.dump(problems, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"프로필 갱신 실패, 캐시 사용: {e}")

    if not os.path.exists(user_path) or not os.path.exists(PROBLEM_FILE):
        return f"{username} 또는 문제 파일이 존재하지 않습니다."

    # progress_data = summarize_progress(PROBLEM_FILE, user_path)
    lastLogin = format_last_login(user_data["last_login"])

    # ... (사용자 로그인/데이터 로드 등)

    # 🔹 serverID 매칭을 적용해 집계

    # ✅ 레거시→서버ID 맵 파일 사용
    try:
        legacy_to_server_file = LEGACY_TO_SERVER_FILE
    except NameError:
        legacy_to_server_file = os.path.join(
            PROBLEM_DIR, "server_legacy_map_reverse.json"
        )
    legacy_map_arg = (
        legacy_to_server_file if os.path.exists(legacy_to_server_file) else None
    )

    all_chapter_data = summarize_progress(
        PROBLEM_FILE, user_path, legacy_map_file=legacy_map_arg
    )

    # 제출 기록
    records = session.get(
        f"{BASE_URL}/api/submissions?myself=0&starred=0&result=&username={user_data['username']}&page=1&limit=100&offset=0"
    )
    records = records.json()

    true_username = user_data["username"]
    # pprint(records["data"]["results"])
    raw_submissions = records["data"]["results"]
    # 메인 계정으로 푼 문제만 필터링
    filtered_submissions = [
        rec for rec in raw_submissions if rec.get("username") == true_username
    ]
    streak_data = generate_streak_data(filtered_submissions)

    # pprint(filtered_submissions[0])
    for rec in records["data"]["results"]:
        server_sub_id = rec["id"]
        problem = rec["problem"]
        user = rec["username"]
        lang = rec["language"]
        result = rec["result"]
        try:
            score = rec["statistic_info"]["score"]
        except Exception as e:
            print(f"score 없음: {e}")
        # time_cost = rec["statistic_info"]["time_cost"]
        # memory_cost = rec["statistic_info"]["memory_cost"]
        # ISO 포맷 날짜를 사람이 읽기 편한 형태로 변경
        create_time = datetime.fromisoformat(
            rec["create_time"].replace("Z", "+00:00")
        ).strftime("%Y-%m-%d %H:%M:%S")

        # print(
        #    f"{create_time} | 문제: {problem} | 사용자: {user} | 언어: {lang} | 결과: {result} | 점수: {score} "
        # )

    avatar = data["data"].get("avatar") or "/public/avatar/default.png"

    # print(f"user_data[]: {user_data["admin_type"]}")

    avatar_path = f"{BASE_URL}{avatar}"
    print(f"avatar_path: {avatar_path}")
    return render_template(
        "index.html",
        username=user_data["username"],
        last_login=lastLogin,
        accepted_number=data["data"]["accepted_number"],
        submission_number=data["data"]["submission_number"],
        total_score=data["data"]["total_score"],
        progress_data=all_chapter_data,
        streak_data=streak_data,
        avatar_path=avatar_path,  # 프로필 이미지
        admin_type=login_user_type,  # ✅ 여기 추가
    )


@app.route("/user/<username>/chapter/<chapter>")
def chapter_detail(username, chapter):
    global login_user_type

    safe_name = sanitize_filename(username)
    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")

    # (권장) 리소스 보장
    ensure_problem_assets()

    # (권장) 최신 사용자 데이터로 갱신
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    if not is_cookie_valid(session):
        return redirect("/login")
    try:
        encoded_username = quote(username)
        res = session.get(
            f"{BASE_URL}/api/profile?username={encoded_username}", timeout=10
        )
        data = res.json()
        problems = (
            data.get("data", {}).get("oi_problems_status", {}).get("problems", {})
        )
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        with open(user_path, "w", encoding="utf-8") as f:
            json.dump(problems, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"프로필 갱신 실패, 캐시 사용: {e}")

    if not os.path.exists(user_path) or not os.path.exists(PROBLEM_FILE):
        return f"{username} 또는 문제 파일이 존재하지 않습니다."

    # ✅ 레거시→서버ID 맵 파일 사용
    try:
        legacy_to_server_file = LEGACY_TO_SERVER_FILE
    except NameError:
        legacy_to_server_file = os.path.join(
            PROBLEM_DIR, "server_legacy_map_reverse.json"
        )
    legacy_map_arg = (
        legacy_to_server_file if os.path.exists(legacy_to_server_file) else None
    )

    all_chapter_data = summarize_progress(
        PROBLEM_FILE, user_path, legacy_map_file=legacy_map_arg
    )

    matched = next(
        (item for item in all_chapter_data if item["chapter"] == chapter), None
    )
    if matched is None:
        return f"'{chapter}' 챕터를 찾을 수 없습니다."

    return render_template(
        "chapter_detail.html",
        username=username,
        chapter=chapter,
        chapter_name=chapter + " 단원",
        progress_data=matched["groups"],
        admin_type=login_user_type,
    )


@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
    global login_user_type

    safe_name = sanitize_filename(username)
    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    problem_path = os.path.join(PROBLEM_DIR, "all_problems.json")

    # 0) 문제 리소스 보장(없으면 생성)
    ensure_problem_assets()  # ← index/user 라우트와 동일하게 공통 함수로

    # 1) 최신 사용자 데이터로 갱신
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    if not is_cookie_valid(session):
        return redirect("/login")

    encoded_username = quote(username)
    try:
        res = session.get(
            f"{BASE_URL}/api/profile?username={encoded_username}", timeout=10
        )
        data = res.json()
        # 최신 프로필로 user_path 갱신
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        with open(user_path, "w", encoding="utf-8") as f:
            json.dump(
                data["data"]["oi_problems_status"]["problems"],
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        # 서버 실패 시엔 캐시 사용(파일 없으면 에러 반환)
        print(f"프로필 갱신 실패, 캐시 사용: {e}")

    try:
        with open(user_path, encoding="utf-8") as f:
            user_data = json.load(f)
        with open(problem_path, encoding="utf-8") as f:
            all_problems = json.load(f)

        try:
            with open(LEGACY_TO_SERVER_FILE, encoding="utf-8") as f:
                legacy_to_server = json.load(f)
        except FileNotFoundError:
            legacy_to_server = {}

        result = summarize_user_chapter_group(
            user_data,
            all_problems,
            chapter,
            group_id,
            legacy_map=legacy_to_server,  # ✅ 레거시→서버 맵
        )

    except FileNotFoundError as e:
        return str(e)
    except KeyError as e:
        return f"데이터 오류: {e}"

    title_url = quote(str(result["group_title"]).replace(".", ""))
    chapter_url = f"{BASE_URL}/{result['problem_chapter_id']}?tag={title_url}"

    return render_template(
        "group_detail.html",
        username=username,
        chapter=chapter,
        group_id=group_id,
        group_title=result["group_title"],
        problem_names=result["problem_names"],
        admin_type=login_user_type,
        chapter_url_html=chapter_url,
    )


if __name__ == "__main__":
    app.run(debug=True)
