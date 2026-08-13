"""
src/db/session.py
DB 엔진 생성 및 세션 팩토리.
- 기본: SQLite (meta/tracker.db) with WAL 모드
- PostgreSQL 전환: 환경변수 DATABASE_URL만 변경
- 롤백 스위치: USE_RDB_STORE=false 시 RDB 비활성화
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
META_DIR = PROJECT_ROOT / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

# 듀얼 스토어 스위치: USE_RDB_STORE=false 이면 RDB 완전 비활성화 (JSON fallback 유지)
USE_RDB_STORE = os.environ.get("USE_RDB_STORE", "true").strip().lower() in ("1", "true", "yes", "on")

_DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{META_DIR / 'tracker.db'}"

_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        kwargs = {}
        if _DATABASE_URL.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        _engine = create_engine(_DATABASE_URL, **kwargs)
        # SQLite WAL 모드 활성화 (동시 쓰기 락 방지)
        if _DATABASE_URL.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_wal_mode(dbapi_conn, _):
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
                dbapi_conn.execute("PRAGMA synchronous=NORMAL")
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


@contextmanager
def get_db_session() -> Session:
    """DB 세션 컨텍스트 매니저 - with get_db_session() as session: 형태로 사용"""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """앱 시작 시 테이블 생성 (Alembic 미사용 시 폴백)"""
    if not USE_RDB_STORE:
        return
    from db.base import Base
    import db.models  # noqa: F401 - 모델 등록
    Base.metadata.create_all(get_engine())
