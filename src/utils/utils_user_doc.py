# utils_user_doc.py (예시)
import os, json
from uuid import UUID

from utils.utils_common import (
    ensure_login_or_redirect,
    fetch_profile,
    fetch_submissions_window,
    filter_main_account_submissions,
    sanitize_filename,
    ensure_problem_assets,
    build_dashboard_viewmodel,
    role_ctx_from_session,
    sync_user_problems_cache,
    ensure_user_cache_or_404,
    resolve_legacy_map_path,
    resolve_legacy_map_dict,
    resolve_uuid,
)

from config import (

    USER_DATA_DIR,

)  # 필요 시 조정



def _user_doc_path_by_uuid(u: str) -> str:
        
    return os.path.join(USER_DATA_DIR, f"{u}.json")


def _ensure_uuid(id_or_uuid: str) -> str:
    if not id_or_uuid:
        return ""
    val = str(id_or_uuid).strip()
    # 1. 36자리 uuid 포맷이면 그대로 반환
    if "-" in val and len(val) == 36:
        return val
    # 2. workspace_students 매핑 검색 (portal_student_id, name, display_id, accounts)
    try:
        from services.workspace_student_service import find_student_by_any
        u, _ = find_student_by_any(val)
        if u:
            return u
    except Exception:
        pass
    # 3. uuids.json fallback
    return resolve_uuid(val)


def load_doc_by_any(id_or_uuid: str) -> dict:
    u = _ensure_uuid(id_or_uuid)
    print(f"id_or_uuid: {id_or_uuid}")
    p = _user_doc_path_by_uuid(u)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"user_uuid": u, "homework_logs": []}


def save_doc_by_any(id_or_uuid: str, doc: dict) -> str:
    u = _ensure_uuid(id_or_uuid)
    doc.setdefault("user_uuid", u)
    p = _user_doc_path_by_uuid(u)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)  # 원자적 저장
    return p


def pull_and_store_user(username: str):
    from urllib.parse import quote
    from datetime import datetime
    from config import COOKIE_PATH, BASE_URL
    from login import load_cookies, get_authenticated_session
    from core.storage import KST
    from utils.utils_common import merge_submissions_into_problems

    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)
    encoded_username = quote(username)

    res = session.get(f"{BASE_URL}/api/profile?username={encoded_username}")
    data = res.json()
    user_data = data["data"]["user"]
    problems = data["data"]["oi_problems_status"]["problems"]
    problems = merge_submissions_into_problems(session, username, problems)

    student_id = user_data["username"]
    doc = load_doc_by_any(student_id)
    doc["profile"] = {
        "student_id": student_id,
        "name": user_data.get("realname") or user_data.get("username"),
        "class_id": user_data.get("class_id"),
        "last_login": user_data.get("last_login"),
    }
    doc["user_uuid"] = resolve_uuid(student_id)
    doc["oi_problems"] = problems
    doc.setdefault("homework_logs", doc.get("homework_logs", []))
    doc["updated_at"] = datetime.now(tz=KST).isoformat()

    save_doc_by_any(student_id, doc)
    return doc


def _parse_iso_datetime(value: str | None):
    from datetime import datetime
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_doc_stale(doc: dict, ttl_ms: int = 60_000) -> bool:
    from datetime import datetime
    from core.storage import KST
    if ttl_ms < 0:
        ttl_ms = 0
    parsed = _parse_iso_datetime((doc or {}).get("updated_at"))
    if not parsed:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    age_ms = (datetime.now(tz=KST) - parsed.astimezone(KST)).total_seconds() * 1000
    return age_ms > ttl_ms


def refresh_user_doc_by_uuid(user_uuid: str) -> dict:
    from config import COOKIE_PATH
    from login import load_cookies, get_authenticated_session
    cookies = load_cookies(COOKIE_PATH)
    session = get_authenticated_session(cookies)

    base = load_doc_by_any(user_uuid)
    username = (base.get("profile") or {}).get("student_id") or (
        base.get("profile") or {}
    ).get("username")
    if not username:
        return base

    return pull_and_store_user(username)

    return p
