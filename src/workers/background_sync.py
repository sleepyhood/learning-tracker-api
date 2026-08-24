import os
import sys
import time
import queue
import threading
from datetime import datetime, timezone

_sync_queue = queue.Queue()
_worker_thread = None
_lock = threading.Lock()
_started = False


def _is_main_flask_process() -> bool:
    werkzeug_val = os.environ.get('WERKZEUG_RUN_MAIN')
    if werkzeug_val is None:
        return True
    return werkzeug_val.lower() == 'true'


def enqueue_user_sync(user_identifier: str):
    if user_identifier:
        _sync_queue.put(str(user_identifier).strip())


def _worker_loop():
    print('BackgroundSyncWorker: Background sync thread started')
    last_periodic_run = 0
    last_student_sync = 0
    PERIODIC_INTERVAL_SEC = 300
    STUDENT_SYNC_INTERVAL_SEC = 3600  # 1시간마다 전체 학생 최신화

    # 서버 시작 후 3초 뒤 초기 1회 웜업 동기화
    time.sleep(3)
    _sync_doingcoding_students_job()
    last_student_sync = time.time()

    while True:
        try:
            try:
                user_id = _sync_queue.get(timeout=5)
                if user_id:
                    _perform_single_user_sync(user_id)
                    _sync_queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            if now - last_periodic_run >= PERIODIC_INTERVAL_SEC:
                last_periodic_run = now
                _perform_periodic_sync_all()

            if now - last_student_sync >= STUDENT_SYNC_INTERVAL_SEC:
                last_student_sync = now
                _sync_doingcoding_students_job()

        except Exception as e:
            print('BackgroundSyncWorker: Loop error:', e)
            time.sleep(5)


def _sync_doingcoding_students_job():
    try:
        from services.workspace_student_service import sync_all_doingcoding_students
        print('BackgroundSyncWorker: Syncing all DoingCoding students...')
        res = sync_all_doingcoding_students()
        print('BackgroundSyncWorker: Student sync result:', res)
    except Exception as e:
        print('BackgroundSyncWorker: Student sync error:', e)


def _perform_single_user_sync(user_identifier: str):
    try:
        print('BackgroundSyncWorker: Syncing user:', user_identifier)
        from db.dual_store import USE_RDB_STORE
        if USE_RDB_STORE:
            from db.session import get_db_session
            from db.repo import resolve_user_any
            with get_db_session() as session:
                user = resolve_user_any(session, user_identifier)
                if user:
                    user.updated_at = datetime.now(timezone.utc)
                    session.commit()
        print('BackgroundSyncWorker: Sync finished:', user_identifier)
    except Exception as e:
        print('BackgroundSyncWorker: Sync failed for', user_identifier, 'error:', e)


def _perform_periodic_sync_all():
    try:
        print('BackgroundSyncWorker: Periodic full sync started')
        from db.dual_store import USE_RDB_STORE
        if not USE_RDB_STORE:
            return
        from db.session import get_db_session
        from db.models import User
        from sqlalchemy import select
        with get_db_session() as session:
            users = session.scalars(select(User)).all()
            print('BackgroundSyncWorker: Sync target users count:', len(users))
        print('BackgroundSyncWorker: Periodic full sync done')
    except Exception as e:
        print('BackgroundSyncWorker: Periodic sync failed:', e)


def start_background_sync_worker(app=None):
    global _worker_thread, _started
    with _lock:
        if _started:
            return
        if not _is_main_flask_process():
            print('BackgroundSyncWorker: Reloader parent process - skipping worker start')
            return

        _started = True
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name='BackgroundSyncWorkerThread')
        _worker_thread.start()
        print('BackgroundSyncWorker: Daemon thread running')
