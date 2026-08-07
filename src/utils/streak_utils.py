# streak_utils.py
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
from urllib.parse import quote
import json, os

from config import (
    PROBLEM_FILE,
    BASE_URL,
)  # 필요 시 조정

# 문제 제목 매핑 (lazy load)
_problem_title_map = None
_problem_meta_map = None


def _load_title_map():
    global _problem_title_map
    if _problem_title_map is None:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = {}
        if isinstance(data, dict) and data.get("_schema_version") == 2:
            for pid, p_info in data.get("problems", {}).items():
                m[str(pid)] = p_info.get("title", "")
        else:
            for _, category_data in data.items():
                if isinstance(category_data, dict):
                    for _, chapter_data in category_data.items():
                        if isinstance(chapter_data, dict):
                            for pid, title in chapter_data.get("problem_names", {}).items():
                                m[str(pid)] = title
        _problem_title_map = m
    return _problem_title_map


def _load_problem_meta_map():
    global _problem_meta_map
    if _problem_meta_map is None:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = {}
        if isinstance(data, dict) and data.get("_schema_version") == 2:
            groups = data.get("groups", {})
            for pid, p_info in data.get("problems", {}).items():
                gid = p_info.get("group_id")
                g_info = groups.get(gid, {})
                m[str(pid)] = {
                    "chapter_id": g_info.get("chapter_code"),
                    "chapter_title": g_info.get("title"),
                }
        else:
            for _, category_data in data.items():
                if isinstance(category_data, dict):
                    for _, chapter_data in category_data.items():
                        if isinstance(chapter_data, dict):
                            chapter_id = chapter_data.get("chapter_id")
                            chapter_title = chapter_data.get("title")
                            for pid in chapter_data.get("problem_names", {}).keys():
                                m[str(pid)] = {
                                    "chapter_id": chapter_id,
                                    "chapter_title": chapter_title,
                                }
        _problem_meta_map = m
    return _problem_meta_map


def generate_streak_data(submissions, days: int = 7):
    """
    submissions: /api/submissions 결과 리스트 (필터링 OK)
    days: 보여줄 일수 (기본 7, 30/90 등)
    """
    kst = ZoneInfo("Asia/Seoul")
    title_map = _load_title_map()
    problem_meta_map = _load_problem_meta_map()
    first_corrects = dict()  # problem_id(str) -> info

    for rec in submissions:
        if not isinstance(rec, dict):
            continue
        if rec.get("result") != 0:
            continue

        pid = rec.get("problem")
        if isinstance(pid, dict):
            pid = pid.get("_id") or pid.get("id") or str(pid)
        pid = str(pid)

        create_time_raw = rec.get("create_time")
        if not create_time_raw or not isinstance(create_time_raw, str):
            continue

        try:
            dt_utc = datetime.fromisoformat(create_time_raw.replace("Z", "+00:00"))
        except Exception:
            continue
        dt_kst = dt_utc.astimezone(kst)
        date_str = dt_kst.strftime("%Y-%m-%d")

        if pid not in first_corrects:
            meta = problem_meta_map.get(pid, {})
            chapter_id = meta.get("chapter_id")
            chapter_title = meta.get("chapter_title")
            chapter_url = None
            if chapter_id:
                tag = quote(str(chapter_title or "").replace(".", ""))
                chapter_url = f"{BASE_URL}/{chapter_id}"
                if tag:
                    chapter_url = f"{chapter_url}?tag={tag}"

            problem_url = None
            if pid:
                # 실 문제 페이지 링크(환경별 라우팅 차이 가능성을 고려한 best-effort)
                problem_url = f"{BASE_URL}/problem/{quote(pid)}"

            first_corrects[pid] = {
                "date": date_str,
                "time": dt_kst.strftime("%H:%M:%S"),
                "score": rec.get("statistic_info", {}).get("score", 0),
                "language": rec.get("language"),
                "problem": pid,
                "title": title_map.get(pid, pid),
                "server_sub_id": rec.get("id"),
                "show_link": rec.get("show_link", True),
                "problem_url": problem_url,
                "chapter_url": chapter_url,
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
                "show_link": info.get("show_link", True),
                "problem_url": info.get("problem_url"),
                "chapter_url": info.get("chapter_url"),
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
                "details": problems,
            }
        )
    return streak_data
