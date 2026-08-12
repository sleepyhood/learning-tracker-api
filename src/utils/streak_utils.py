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

    # 1. 제출 기록 시간순(오래된 순) 정렬
    parsed_subs = []
    for rec in submissions:
        if not isinstance(rec, dict):
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
        parsed_subs.append((dt_kst, pid, rec))

    parsed_subs.sort(key=lambda x: x[0])

    # 2. Phase 2 & 3: 시도 횟수, 1-Try AC 및 AI 복사 의심 탐지
    problem_attempt_counts = defaultdict(int)
    prev_sub_time = None
    prev_sub_pid = None
    prev_sub_was_ac = False

    processed_details = {}

    for dt_kst, pid, rec in parsed_subs:
        rec_id = rec.get("id") or id(rec)
        problem_attempt_counts[pid] += 1
        attempt_number = problem_attempt_counts[pid]

        stat_info = rec.get("statistic_info") or {}
        score = stat_info.get("score", 0)
        res_code = rec.get("result")
        is_ac = (res_code == 0 or score >= 90)
        is_first_try_ac = (attempt_number == 1 and is_ac)

        # AI 의심 탐지 로직 (Phase 3)
        is_ai_suspected = False
        ai_suspicion_reasons = []

        if prev_sub_time is not None:
            delta_sec = (dt_kst - prev_sub_time).total_seconds()

            # 규칙 1: 이전 100점 성공 후 다음 100점 성공까지 30초 미만 (연속 통과)
            if is_ac and prev_sub_was_ac and delta_sec < 30:
                is_ai_suspected = True
                ai_suspicion_reasons.append(f"이전 문제 통과 후 {int(delta_sec)}초 만에 100점 성공 (복사 제출 의심)")

            # 규칙 2: 20초 미만 초고속 1-Try 통과
            if is_first_try_ac and delta_sec < 20:
                is_ai_suspected = True
                ai_suspicion_reasons.append(f"이전 제출 후 {int(delta_sec)}초 만에 1-Try 통과 (입력 속도 미달)")

            # 규칙 3: 30초 미만 간격으로 서로 다른 문제 제출 순서 꼬임
            if not is_ac and not prev_sub_was_ac and pid != prev_sub_pid and delta_sec < 30:
                is_ai_suspected = True
                ai_suspicion_reasons.append(f"{int(delta_sec)}초 간격으로 서로 다른 문제 연속 실패 (복사 순서 꼬임)")

        prev_sub_time = dt_kst
        prev_sub_pid = pid
        prev_sub_was_ac = is_ac

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
            problem_url = f"{BASE_URL}/problem/{quote(pid)}"

        processed_details[rec_id] = {
            "problem": pid,
            "title": title_map.get(pid, pid),
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "score": score,
            "result": res_code,
            "language": rec.get("language"),
            "date": dt_kst.strftime("%Y-%m-%d"),
            "time": dt_kst.strftime("%H:%M:%S"),
            "server_sub_id": rec.get("id"),
            "show_link": rec.get("show_link", True),
            "problem_url": problem_url,
            "chapter_url": chapter_url,
            # Phase 2
            "attempt_number": attempt_number,
            "is_first_try_ac": is_first_try_ac,
            # Phase 3
            "is_ai_suspected": is_ai_suspected,
            "ai_suspicion_reason": " · ".join(ai_suspicion_reasons) if ai_suspicion_reasons else "",
        }

    # 날짜별 그룹화
    by_date = defaultdict(list)
    for dt_kst, pid, rec in parsed_subs:
        rec_id = rec.get("id") or id(rec)
        date_str = dt_kst.strftime("%Y-%m-%d")
        if rec_id in processed_details:
            by_date[date_str].append(processed_details[rec_id])

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
