"""
src/db/dual_store.py
듀얼 스토어 어댑터 (위험요소 #5: 롤백 스위치)

USE_RDB_STORE=true  -> DB에서 최신 숙제/유저 조회
USE_RDB_STORE=false -> 기존 JSON 파일 경로 사용 (완전 원복)
"""
import os
from typing import Optional

USE_RDB_STORE = os.environ.get("USE_RDB_STORE", "true").strip().lower() in ("1", "true", "yes", "on")


def get_homework_latest(internal_user_id: str, json_fallback_fn) -> dict:
    """
    USE_RDB_STORE 플래그에 따라 DB 또는 JSON 경로로 숙제 최신 데이터를 반환.

    Args:
        internal_user_id: u_<uuid_hex> 형태의 내부 유저 ID
        json_fallback_fn: 기존 JSON 기반 숙제 로드 함수 (callable)
    """
    if USE_RDB_STORE:
        try:
            from db.session import get_db_session
            from db.repo import get_latest_assignment_for_user
            with get_db_session() as session:
                result = get_latest_assignment_for_user(session, internal_user_id)
                if result is not None:
                    return result
                # DB에 데이터 없으면 JSON fallback
        except Exception as e:
            print(f"[DualStore] DB 조회 실패, JSON fallback 사용: {e}")
    return json_fallback_fn()


def resolve_user_internal_id(id_or_uuid: str) -> str:
    """
    기존 UUID(하이픈 포함) 또는 student_id를 internal_user_id(u_<hex>) 형태로 변환.
    위험요소 #2 (하위 호환성) 대응.
    """
    if USE_RDB_STORE:
        try:
            from db.session import get_db_session
            from db.repo import resolve_user_any
            with get_db_session() as session:
                user = resolve_user_any(session, id_or_uuid)
                if user:
                    return user.internal_user_id
        except Exception:
            pass
    # fallback: 기존 UUID 그대로 반환
    return id_or_uuid
