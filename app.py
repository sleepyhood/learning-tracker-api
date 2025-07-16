from flask import Flask, request, render_template, redirect, url_for
import json
from collections import defaultdict
from flask import jsonify

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

from utils.user_crawler import crawl_user

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

app = Flask(__name__)

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "students_data")


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
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            return redirect(url_for("user_overview", username=username))
    return render_template("index.html", username="", progress_data=[])


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
