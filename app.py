from flask import Flask, request, render_template, redirect, url_for
import json
from collections import defaultdict
from flask import jsonify
from datetime import datetime, timedelta
import requests
from login import load_cookies, get_authenticated_session

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

from utils.user_crawler import crawl_user
import re

load_dotenv()

# USERNAME = os.getenv("USERNAME")
# PASSWORD = os.getenv("PASSWORD")

# app = Flask(__name__)
app = Flask(__name__, static_folder="static")

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "students_data")

COOKIE_PATH = "cookies.json"

BASE_URL = "http://edu.doingcoding.com"


def is_cookie_valid():
    if not os.path.exists(COOKIE_PATH):
        return False
    try:
        with open(COOKIE_PATH, "r") as f:
            cookies = json.load(f)

        if "timestamp" in cookies:
            ts = datetime.fromisoformat(cookies["timestamp"])
            if datetime.now() - ts > timedelta(hours=12):
                return False

        return "sessionid" in cookies and cookies["sessionid"]
    except:
        return False


def extract_level(name):
    # Lv 또는 SLv 다음 숫자 추출
    match = re.match(r"(S?Lv)\s*(\d+)", name)
    if match:
        prefix = match.group(1)
        level_num = int(match.group(2))
        # Lv는 SLv보다 우선 (숫자가 같으면 Lv 먼저)
        priority = 0 if prefix == "Lv" else 1  # Lv=0, SLv=1
        return (level_num, priority)
    else:
        # 매칭 안되면 최하위 처리
        return (float("inf"), float("inf"))


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
    if not is_cookie_valid():
        return redirect("/login")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            return redirect(url_for("user_overview", username=username))

    print("유효한 쿠키. index에 접근 허용됨.")

    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    res = session.get(f"http://edu.doingcoding.com/api/profile?username={username}")

    # # JSON 파싱
    data = json.loads(res.text)
    print(data)

    ###################
    print()

    res = session.get(
        f"http://edu.doingcoding.com/api/submissions?myself=1&starred=0&result=&username={username}&page=1&limit=100&offset=0"
    )

    # # JSON 파싱
    data = json.loads(res.text)
    print(data)

    return render_template("index.html", username="", progress_data=[])


@app.route("/api/problems", methods=["GET"])
def get_problem_list():
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    try:
        chapter = "LV1 출력"
        res1 = session.get(
            f"http://edu.doingcoding.com/api/problem?paging=true&offset=0&limit=100&tag=Lv1+%EC%B6%9C%EB%A0%A5&page=1"
        )
        print(res1.json())

        with open("student_data.json", "w", encoding="utf-8") as f:
            json.dump(res1.json(), f, ensure_ascii=False, indent=2)

        res = session.get(
            f"http://edu.doingcoding.com/api/problem/tags"
            # f"http://edu.doingcoding.com/api/problem?paging=true&offset=0&limit=100&tag=Lv1+%EC%B6%9C%EB%A0%A5&page=1"
        )  # ← 실제 API 엔드포인트에 맞게 변경
        problem_data = res.json()

        filtered = [
            problem
            for problem in problem_data["data"]
            if problem["name"].startswith("Lv") or problem["name"].startswith("SLv")
        ]

        sorted_problems = sorted(filtered, key=lambda p: extract_level(p["name"]))

        for p in sorted_problems:
            print(f"{p['name']} (id: {p['id']})")

        return jsonify({"success": True, "problems": res1.json()})

    except Exception as e:
        print("문제 목록 API 호출 실패:", e)
        return jsonify({"success": False, "error": str(e)})


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
    problem_path = os.path.join(PROBLEM_DIR, f"{chapter}.json")

    if not os.path.exists(user_path) or not os.path.exists(problem_path):
        return f"{username} 또는 {chapter} 파일이 존재하지 않습니다."

    with open(user_path, "r", encoding="utf-8") as f:
        solved_list = json.load(f)

    with open(problem_path, "r", encoding="utf-8") as f:
        problem_info = json.load(f)

    progress_data = []

    for group_id, info in problem_info.items():
        title = info["title"]
        total = info["total"]
        problem_names = info["problem_names"]
        solved = sum(1 for pid in problem_names if pid in solved_list)
        percent = round(solved / total * 100, 1) if total else 0

        progress_data.append(
            {
                "group_id": group_id,  # 추가
                "title": title,
                "solved": solved,
                "total": total,
                "percent": percent,
            }
        )

    return render_template(
        "chapter_detail.html",
        username=username,
        chapter=chapter,
        chapter_name=chapter + " (" + str(len(progress_data)) + "개 단원)",
        progress_data=progress_data,
    )


# 07 12 추가
# 각 파트별 어떤 문제를 풀었는지 확인용
@app.route("/user/<username>/chapter/<chapter>/group/<group_id>")
def group_detail(username, chapter, group_id):
    user_path = os.path.join(USER_DATA_DIR, f"{username}.json")
    problem_path = os.path.join(PROBLEM_DIR, f"{chapter}.json")

    if not os.path.exists(user_path) or not os.path.exists(problem_path):
        return f"{username} 또는 {chapter} 파일이 존재하지 않습니다."

    with open(user_path, "r", encoding="utf-8") as f:
        solved_list = json.load(f)

    with open(problem_path, "r", encoding="utf-8") as f:
        problem_info = json.load(f)

    # 단원(group_id) 정보 가져오기
    if group_id not in problem_info:
        return f"{group_id} 단원이 존재하지 않습니다."

    group = problem_info[group_id]
    title = group["title"]
    problem_names = group["problem_names"]

    return render_template(
        "group_detail.html",
        username=username,
        chapter=chapter,
        group_id=group_id,
        group_title=title,
        problem_names=problem_names,
        solved_problems=solved_list,
    )


if __name__ == "__main__":
    app.run(debug=True)
