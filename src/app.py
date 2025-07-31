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

load_dotenv()

# USERNAME = os.getenv("USERNAME")
# PASSWORD = os.getenv("PASSWORD")

# app = Flask(__name__)
app = Flask(__name__, static_folder="static")

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")

COOKIE_PATH = "cookies.json"

BASE_URL = "http://edu.doingcoding.com"

login_user_type = "Regular User"  # 유저 로그인 타입은 전역변수로


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
    # 무조건 새로 크롤링
    do_crawling()
    return jsonify(
        {"message": "문제 목록이 갱신되었습니다.", "time": datetime.now().isoformat()}
    )


@app.route("/", methods=["GET", "POST"])
def index():
    global login_user_type
    # 쿠키 확인
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    if not is_cookie_valid(session):
        return redirect("/login")

    # 기본 유저명: 로그인한 유저명 or 입력받은 유저명
    username = ""

    print(f"user_overview: {username}")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:

            # 다른 유저 조회 요청 시
            return redirect(
                url_for("user_overview", username=username)
            )  # ✅ 이 부분에서 처리 위임
        else:
            return "유저명을 입력해주세요.", 400

    # POST가 아닌 경우: 로그인한 유저 기준으로 기본 데이터 보여주기
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    # 유저 정보 가져오기
    res = session.get("http://edu.doingcoding.com/api/profile")  # ✅ 현재 유저 정보
    data = json.loads(res.text)

    user_data = data["data"]["user"]
    username = user_data["username"]

    # pprint(data["data"]["oi_problems_status"])
    filename = f"{sanitize_filename(user_data['username'])}.json"

    user_path = os.path.join(USER_DATA_DIR, filename)

    os.makedirs(USER_DATA_DIR, exist_ok=True)

    # 사용자 문제 상태 저장
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(
            data["data"]["oi_problems_status"]["problems"],
            f,
            ensure_ascii=False,
            indent=2,
        )

    PROBLEM_FILE = os.path.join(PROBLEM_DIR, "all_problems.json")
    if not os.path.exists(PROBLEM_FILE):
        do_crawling()

    lastLogin = format_last_login(user_data["last_login"])
    progress_data = summarize_progress(PROBLEM_FILE, user_path)

    # 제출 기록
    records = session.get(
        f"http://edu.doingcoding.com/api/submissions?myself=1&starred=0&result=&username={username}&page=1&limit=100&offset=0"
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
    avatar = "/public/avatar/dafault.png"

    if avatar != data["data"].get("avatar", None):
        avatar = data["data"].get("avatar", None)

    avatar_path = f"http://edu.doingcoding.com{avatar}"
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
        progress_data=progress_data,
        streak_data=streak_data,  # 👈 스트릭 추가
        avatar_path=avatar_path,  # 프로필 이미지
        admin_type=login_user_type,  # ✅ 여기 추가
    )


@app.route("/refresh_user/<username>")
def refresh_user(username):
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    encoded_username = quote(username)

    try:
        res = session.get(
            f"http://edu.doingcoding.com/api/profile?username={encoded_username}"
        )
        data = res.json()
        user_data = data["data"]["user"]
        print(f"user_data: {user_data}")
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
            print("로그인 실패:", session_or_msg)
            return render_template("login.html", error="로그인에 실패했습니다.")

    return render_template("login.html")


@app.route("/user_overview/<username>")
def user_overview(username):
    global login_user_type

    print(f"user_overview: {username}")
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    try:
        # username에 특수문자 들어간 경우 예외 처리
        from urllib.parse import quote

        encoded_username = quote(username)
        print(f"encoded_username: {encoded_username}")
        res = session.get(
            f"http://edu.doingcoding.com/api/profile?username={encoded_username}"
        )
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

    PROBLEM_FILE = os.path.join(PROBLEM_DIR, "all_problems.json")
    if not os.path.exists(PROBLEM_FILE):
        do_crawling()

    progress_data = summarize_progress(PROBLEM_FILE, user_path)
    lastLogin = format_last_login(user_data["last_login"])

    # 제출 기록
    records = session.get(
        f"http://edu.doingcoding.com/api/submissions?myself=0&starred=0&result=&username={user_data['username']}&page=1&limit=100&offset=0"
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

    avatar = "/public/avatar/dafault.png"

    if avatar != data["data"].get("avatar", None):
        avatar = data["data"].get("avatar", None)

    print(f"user_data[]: {user_data["admin_type"]}")

    avatar_path = f"http://edu.doingcoding.com{avatar}"
    print(f"avatar_path: {avatar_path}")
    return render_template(
        "index.html",
        username=user_data["username"],
        last_login=lastLogin,
        accepted_number=data["data"]["accepted_number"],
        submission_number=data["data"]["submission_number"],
        total_score=data["data"]["total_score"],
        progress_data=progress_data,
        streak_data=streak_data,
        avatar_path=avatar_path,  # 프로필 이미지
        admin_type=login_user_type,  # ✅ 여기 추가
    )


@app.route("/user/<username>/chapter/<chapter>")
def chapter_detail(username, chapter):
    global login_user_type

    print(f"username: {username}")
    safe_name = sanitize_filename(username)
    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    problem_path = os.path.join(PROBLEM_DIR, "all_problems.json")

    if not os.path.exists(user_path) or not os.path.exists(problem_path):
        return f"{username} 또는 문제 파일이 존재하지 않습니다."

    # with open(problem_path, "r", encoding="utf-8") as f:
    #     all_problems = json.load(f)
    # with open(user_path, "r", encoding="utf-8") as f:
    #     user_data = json.load(f)

    all_chapter_data = summarize_progress(problem_path, user_path)
    print(all_chapter_data)

    # 해당 챕터의 문제만 필터링
    # ✅ 요기 부분만 이렇게 고쳐주세요
    matched = next(
        (item for item in all_chapter_data if item["chapter"] == chapter), None
    )
    # print(matched)

    if matched is None:
        return f"'{chapter}' 챕터를 찾을 수 없습니다."

    return render_template(
        "chapter_detail.html",
        username=username,
        chapter=chapter,
        chapter_name=chapter + " 단원",
        progress_data=matched["groups"],  # 👈 그룹 리스트만 넘김!
        admin_type=login_user_type,  # ✅ 여기 추가
    )


@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
    global login_user_type

    safe_name = sanitize_filename(username)

    user_path = os.path.join(USER_DATA_DIR, f"{safe_name}.json")
    problem_path = os.path.join(PROBLEM_DIR, "all_problems.json")

    try:
        with open(user_path, encoding="utf-8") as f:
            user_data = json.load(f)
        with open(problem_path, encoding="utf-8") as f:
            all_problems = json.load(f)

        result = summarize_user_chapter_group(
            user_data, all_problems, chapter, group_id
        )

    except FileNotFoundError as e:
        return str(e)
    except KeyError as e:
        return f"데이터 오류: {e}"

    pprint(f"index.py\tgroup_id: {group_id}")

    problem_chapter_id = result["problem_chapter_id"]  # url에 사용할 데이터
    title_url = str(result["group_title"]).replace(".", "")
    title_url = quote(title_url)
    chapter_url = BASE_URL + f"/{problem_chapter_id}?tag=" + title_url
    # url에는 .이 없어야함

    return render_template(
        "group_detail.html",
        username=username,
        chapter=chapter,
        group_id=group_id,
        group_title=result["group_title"],
        problem_names=result["problem_names"],
        admin_type=login_user_type,  # ✅ 여기 추가
        chapter_url_html=chapter_url,
    )


if __name__ == "__main__":
    app.run(debug=True)
