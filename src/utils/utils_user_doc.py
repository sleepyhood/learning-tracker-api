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


USER_DATA_DIR = os.path.abspath(os.getenv("USER_DATA_DIR", "./users_data"))


def _user_doc_path_by_uuid(u: str) -> str:
    return os.path.join(USER_DATA_DIR, f"{u}.json")


def _ensure_uuid(id_or_uuid: str) -> str:
    # uuid 포맷이면 그대로, 아니면 sid->uuid 변환
    if "-" in id_or_uuid:
        return id_or_uuid
    return resolve_uuid(id_or_uuid)  # 반드시 uuid 반환


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
