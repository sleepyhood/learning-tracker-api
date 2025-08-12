# utils/problem_api.py
import json
import time
from typing import Dict, Any, List
import requests
import os

API_BASE = "http://edu.doingcoding.com/api/problem"
API_TIMEOUT = 10
API_PAGE_LIMIT = 100
API_SLEEP_SEC = 0.15  # 서버 배려용

# API 응답에서 보관할 최소 필드 (매핑/표시용으로 충분)
# - 반드시 필요한 식별자: _id(서버ID), id(정수ID)
# - 매칭/검증/필터용: title, tags, difficulty, total_score
# - 참고 메타: create_time, last_update_time, time_limit, memory_limit
KEEP_FIELDS = {
    "_id",
    "id",
    "title",
    "tags",
    "difficulty",
    "total_score",
    "create_time",
    "last_update_time",
    "time_limit",
    "memory_limit",
}


def _trim_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: item.get(k) for k in KEEP_FIELDS}


def fetch_all_problems(limit: int = API_PAGE_LIMIT) -> List[Dict[str, Any]]:
    page = 1
    results: List[Dict[str, Any]] = []

    while True:
        params = {
            "paging": "true",
            "offset": (page - 1) * limit,
            "limit": limit,
            "page": page,
        }
        r = requests.get(API_BASE, params=params, timeout=API_TIMEOUT)
        r.raise_for_status()

        payload = r.json() or {}
        batch = (payload.get("data") or {}).get("results") or []
        if not batch:
            break

        # 필요한 키만 추려서 누적
        results.extend(_trim_fields(x) for x in batch)

        page += 1
        if API_SLEEP_SEC:
            time.sleep(API_SLEEP_SEC)

    return results


def save_server_problems_json(out_path: str = "server_problems.json") -> str:
    data = fetch_all_problems()
    wrapped = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(data),
        "results": data,
    }

    # 현재 파일 기준 상위 폴더로 이동 후, problems_data 폴더 지정
    output_dir = os.path.join(os.path.dirname(__file__), "..", "problems_data")
    os.makedirs(output_dir, exist_ok=True)
    # save_path = os.path.join(output_dir, f"{i+1}. {difficultys_names[i]}.json")
    out_path = os.path.join(output_dir, out_path)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(wrapped, f, ensure_ascii=False, indent=2)
    return out_path
