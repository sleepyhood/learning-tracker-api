from flask import Flask, request, render_template, redirect, url_for
import json
from collections import defaultdict
from flask import jsonify
import requests
from login import load_cookies, get_authenticated_session
from datetime import datetime, timezone, timedelta

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


def is_cookie_valid():
    if not os.path.exists(COOKIE_PATH):
        return False
    try:
        with open(COOKIE_PATH, "r") as f:
            cookies = json.load(f)

        if "sessionid" not in cookies or not cookies["sessionid"]:
            return False

        if "timestamp" in cookies:
            ts = datetime.fromisoformat(cookies["timestamp"])
            now = datetime.now()

            # 조건 1: 12시간 이상 지남
            if now - ts > timedelta(hours=12):
                return False

            # 조건 2: 날짜가 바뀜 (예: 07/20 → 07/21)
            if now.date() != ts.date():
                return False

        return True
    except Exception as e:
        print("쿠키 유효성 검사 중 오류:", e)
        return False


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


@app.route("/", methods=["GET", "POST"])
def index():
    username = ""
    cookie_result = is_cookie_valid()
    print(f"cookie_result: {cookie_result}")
    if not cookie_result:
        return redirect("/login")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            return redirect(url_for("user_overview", username=username))

    print("유효한 쿠키. index에 접근 허용됨.")

    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    res = session.get(f"http://edu.doingcoding.com/api/profile?username={username}")
    # 프로필 JSON 파싱
    data = json.loads(res.text)
    print(data["data"]["user"])

    user_id = data["data"]["user"]["username"]
    filename = f"{user_id}.json"

    user_path = os.path.join(USER_DATA_DIR, filename)

    # 유저 디렉토리 없으면 생성
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(
            data["data"]["oi_problems_status"]["problems"],
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✅ 저장됨: {filename}")

    # print(f"나의 정보: {data}")

    # 제출 기록
    # res = session.get(
    #     f"http://edu.doingcoding.com/api/submissions?myself=1&starred=0&result=&username={username}&page=1&limit=100&offset=0"
    # )

    print("\n\n")

    print(f"해결: {data["data"]["accepted_number"]}")
    print(f"제출: {data["data"]["submission_number"]}")
    print(f"점수: {data["data"]["total_score"]}")

    lastLogin = format_last_login(data["data"]["user"]["last_login"])

    # 파일이 없으면 크롤링 실행
    PROBLEM_FILE = os.path.join(PROBLEM_DIR, filename)

    PROBLEM_FILE = "src\\problems_data\\all_problems.json"
    # SOLVED_FILE = "src\\problems_data\\" + filename
    SOLVED_FILE = os.path.join(USER_DATA_DIR, filename)

    if not os.path.exists(PROBLEM_FILE):
        print(f"{PROBLEM_FILE}이 존재하지 않아 크롤링을 시작합니다.")
        do_crawling()
        print("크롤링이 완료되었습니다.")

    progress_data = summarize_progress(PROBLEM_FILE, SOLVED_FILE)

    return render_template(
        "index.html",
        username=data["data"]["user"]["username"],
        last_login=lastLogin,
        accepted_number=data["data"]["accepted_number"],
        submission_number=data["data"]["submission_number"],
        total_score=data["data"]["total_score"],
        progress_data=progress_data,  # ✅ 여기에 추가!
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
            return redirect(url_for("index"))
        else:
            print("로그인 실패:", session_or_msg)
            return render_template("login.html", error="로그인에 실패했습니다.")

    return render_template("login.html")


@app.route("/api/overview/<username>", methods=["GET"])
def api_overview(username):
    user_path = os.path.join(USER_DATA_DIR, f"{username}.json")
    crawl_user(username)

    if not os.path.exists(user_path):
        return jsonify({"status": "error", "message": "사용자 데이터가 없습니다."}), 404

    with open(user_path, "r", encoding="utf-8") as f:
        solved_list = json.load(f)

    chapter_files = sorted(os.listdir(PROBLEM_DIR))
    progress_data = []

    for file in chapter_files:
        if file.endswith(".json"):
            chapter = file.replace(".json", "")
            problem_path = os.path.join(PROBLEM_DIR, file)
            with open(problem_path, "r", encoding="utf-8") as f:
                problem_info = json.load(f)

            total_problems = 0
            solved_problems = 0

            for group_id, info in problem_info.items():
                total = info.get("total", 0)
                total_problems += total

                problem_names = info.get("problem_names", {})
                solved = sum(1 for pid in problem_names if pid in solved_list)
                solved_problems += solved

            percent = (
                round(solved_problems / total_problems * 100, 1)
                if total_problems
                else 0
            )

            progress_data.append(
                {
                    "chapter": chapter,
                    "title": f"{chapter.upper()}",
                    "solved": solved_problems,
                    "total": total_problems,
                    "percent": percent,
                }
            )

    return jsonify(
        {"status": "ok", "username": username, "progress_data": progress_data}
    )


@app.route("/user/<username>/chapter/<chapter>")
def chapter_detail(username, chapter):
    user_path = os.path.join(USER_DATA_DIR, f"{username}.json")
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
    )


@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
    user_path = os.path.join(USER_DATA_DIR, f"{username}.json")
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

    return render_template(
        "group_detail.html",
        username=username,
        chapter=chapter,
        group_id=group_id,
        group_title=result["group_title"],
        problem_names=result["problem_names"],
    )


if __name__ == "__main__":
    app.run(debug=True)
