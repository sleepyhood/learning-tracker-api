from datetime import datetime, timedelta
from collections import defaultdict

from zoneinfo import ZoneInfo  # Python 3.9 이상


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
    grouped = group_submissions_by_date(submissions)

    kst = ZoneInfo("Asia/Seoul")
    today = datetime.now(tz=kst).date()
    streak_data = []

    for i in range(6, -1, -1):  # 7일 전 ~ 오늘까지
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        weekday = ["월", "화", "수", "목", "금", "토", "일"][day.weekday()]
        count = len(grouped.get(day_str, []))

        streak_data.append(
            {
                "date": day_str,
                "weekday": weekday,
                "count": count,
                "details": grouped.get(day_str, []),
            }
        )

    return streak_data
