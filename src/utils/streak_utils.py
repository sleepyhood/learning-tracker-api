# streak_utils.py
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
import json, os

from config import (
    PROBLEM_FILE,
)  # 필요 시 조정

# 문제 제목 매핑 (lazy load)
_problem_title_map = None


def _load_title_map():
    global _problem_title_map
    if _problem_title_map is None:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = {}
        for _, category_data in data.items():
            for _, chapter_data in category_data.items():
                for pid, title in chapter_data.get("problem_names", {}).items():
                    m[str(pid)] = title
        _problem_title_map = m
    return _problem_title_map


def generate_streak_data(submissions, days: int = 7):
    """
    submissions: /api/submissions 결과 리스트 (필터링 OK)
    days: 보여줄 일수 (기본 7, 30/90 등)
    """
    kst = ZoneInfo("Asia/Seoul")
    title_map = _load_title_map()

    # 문제별 '최초 정답'만 카운트 (기존 로직 유지)
    first_corrects = dict()  # problem_id(str) -> info

    for rec in submissions:
        if rec.get("result") != 0:
            continue

        pid = rec.get("problem")
        if isinstance(pid, dict):
            pid = pid.get("_id") or pid.get("id") or str(pid)
        pid = str(pid)

        dt_utc = datetime.fromisoformat(rec["create_time"].replace("Z", "+00:00"))
        dt_kst = dt_utc.astimezone(kst)
        date_str = dt_kst.strftime("%Y-%m-%d")

        if pid not in first_corrects:
            first_corrects[pid] = {
                "date": date_str,
                "time": dt_kst.strftime("%H:%M:%S"),
                "score": rec.get("statistic_info", {}).get("score", 0),
                "language": rec.get("language"),
                "problem": pid,
                "title": title_map.get(pid, pid),
                "server_sub_id": rec.get("id"),
            }

    # 날짜별 묶기
    by_date = defaultdict(list)
    for info in first_corrects.values():
        by_date[info["date"]].append(
            {
                "problem": info["problem"],
                "title": info["title"],
                "score": info["score"],
                "language": info["language"],
                "time": info["time"],
                "server_sub_id": info["server_sub_id"],
            }
        )

    # 연속 days일 생성
    today = datetime.now(tz=kst).date()
    streak_data = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        problems = by_date.get(day_key, [])
        streak_data.append(
            {
                "date": day.strftime("%m-%d"),
                "weekday": ["월", "화", "수", "목", "금", "토", "일"][day.weekday()],
                "count": len(problems),
                "details": problems,  # 각 문제의 server_sub_id는 여기에 있음
            }
        )
    return streak_data
