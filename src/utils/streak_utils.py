from datetime import datetime, timedelta
from collections import defaultdict

from zoneinfo import ZoneInfo  # Python 3.9 이상

import json

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)  # 한 단계 위 폴더
PROBLEM_DIR = os.path.join(PARENT_DIR, "problems_data/all_problems.json")

with open(PROBLEM_DIR, "r", encoding="utf-8") as f:
    data = json.load(f)

# 문제 ID -> 제목 매핑 생성
problem_id_to_title = {}

for category, category_data in data.items():
    for chapter_id, chapter_data in category_data.items():
        for problem_id, title in chapter_data.get("problem_names", {}).items():
            problem_id_to_title[problem_id] = title


def group_submissions_by_date(submissions):
    date_problem_map = defaultdict(list)
    kst = ZoneInfo("Asia/Seoul")

    for rec in submissions:
        # UTC 기준 datetime 생성
        dt_utc = datetime.fromisoformat(rec["create_time"].replace("Z", "+00:00"))
        # 한국 시간으로 변환
        dt = dt_utc.astimezone(kst)
        date_str = dt.strftime("%Y-%m-%d")

        # 정확히 푼 문제만 포함
        if rec["result"] == 0:
            date_problem_map[date_str].append(
                {
                    "problem": rec["problem"],
                    "score": rec["statistic_info"]["score"],
                    "language": rec["language"],
                    "time": dt.strftime("%H:%M:%S"),
                }
            )

    return date_problem_map


def generate_streak_data(submissions):
    kst = ZoneInfo("Asia/Seoul")
    first_corrects = dict()  # 문제 ID → 최초 정답 날짜

    for rec in submissions:
        if rec["result"] != 0:
            continue  # 정답이 아닌 경우 무시

        pid = rec["problem"]
        server_sub_id = rec["id"]

        dt_utc = datetime.fromisoformat(rec["create_time"].replace("Z", "+00:00"))
        dt_kst = dt_utc.astimezone(kst)
        date_str = dt_kst.strftime("%Y-%m-%d")

        # 문제 제목 찾아 넣기
        title = problem_id_to_title.get(pid, pid)  # 없으면 ID를 대체 표시

        # 이미 기록된 문제면 무시 (최초 정답만 고려)
        if pid not in first_corrects:
            first_corrects[pid] = {
                "date": date_str,
                "time": dt_kst.strftime("%H:%M:%S"),
                "score": rec["statistic_info"].get("score", 0),
                "language": rec["language"],
                "problem": pid,
                "title": title,  # 제목 추가
                "server_sub_id": server_sub_id,  # 여기 추가
            }

    # 날짜별로 문제 묶기
    date_problem_map = defaultdict(list)
    for info in first_corrects.values():
        date_problem_map[info["date"]].append(
            {
                "problem": info["problem"],
                "title": info["title"],  # 제목 포함
                "score": info["score"],
                "language": info["language"],
                "time": info["time"],
                "server_sub_id": info[
                    "server_sub_id"
                ],  # rec["id"] → info["server_sub_id"]로 수정
            }
        )

    # 마지막 7일간의 스트릭 데이터 생성
    today = datetime.now(tz=kst).date()
    streak_data = []

    for i in range(6, -1, -1):  # 최근 7일
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        print_day = day.strftime("%m-%d")
        weekday = ["월", "화", "수", "목", "금", "토", "일"][day.weekday()]
        problems = date_problem_map.get(day_str, [])

        streak_data.append(
            {
                "date": print_day,
                "weekday": weekday,
                "count": len(problems),
                "details": problems,
                "server_sub_id": rec["id"],  # 여기에 id 추가
            }
        )

    return streak_data
