import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Application Directory & File Paths
APP_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = APP_DIR.parent
META_DIR = PROJECT_ROOT / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

UUIDS_PATH = META_DIR / "uuids.json"
UUIDS_PATH.parent.mkdir(parents=True, exist_ok=True)
if not UUIDS_PATH.exists():
    UUIDS_PATH.write_text("{}", encoding="utf-8")

SCHEDULE_PATH = META_DIR / "schedule.json"
SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)

WORKSPACE_STUDENTS_PATH = META_DIR / "workspace_students.json"

KST = timezone(timedelta(hours=9))

UNCERTAIN_WEEKDAY = 99
UNCERTAIN_WEEKDAY_LABEL = "일정 불확실"
WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]

# --- Schedule I/O Functions ---

def load_schedule() -> dict:
    """요일별 수업 스케줄 JSON 로드."""
    try:
        if SCHEDULE_PATH.exists():
            return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print("[schedule] load error:", e)
    return {"slots": []}


def save_schedule(data: dict) -> dict:
    """스케줄 JSON 저장."""
    try:
        SCHEDULE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("[schedule] save error:", e)
    return data


def reverse_lookup(user_uuid: str) -> str | None:
    """UUID에서 레거시 student_id를 찾아 반환."""
    try:
        m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
        for sid, u in m.items():
            if u == user_uuid:
                return sid
    except Exception:
        pass
    return None


def hydrate_slot_students(slots):
    """
    슬롯에 들어있는 students 리스트( uuid 또는 student_id )를
    화면에서 쓰기 좋은 dict 리스트로 변환.
    """
    from utils.utils_user_doc import load_doc_by_any
    from utils.utils_common import resolve_uuid

    hydrated = []
    for slot in slots:
        students_detail = []
        notes = slot.get("student_notes") or {}
        for token in slot.get("students", []):
            try:
                doc = load_doc_by_any(token)
            except Exception:
                doc = {}

            profile = doc.get("profile") or {}
            student_id = (
                profile.get("student_id")
                or reverse_lookup(token)
                or str(token)
            )
            name = profile.get("name") or student_id
            user_uuid = doc.get("user_uuid") or resolve_uuid(student_id)
            note = ""
            if isinstance(notes, dict):
                note = (
                    notes.get(user_uuid)
                    or notes.get(student_id)
                    or notes.get(str(token))
                    or ""
                )

            students_detail.append(
                {
                    "user_uuid": user_uuid,
                    "student_id": student_id,
                    "name": name,
                    "note": str(note or "").strip(),
                }
            )

        merged = dict(slot)
        merged["students_detail"] = students_detail
        hydrated.append(merged)

    return hydrated


# --- Workspace Students Storage Functions ---

def _load_workspace_students():
    if not WORKSPACE_STUDENTS_PATH.exists():
        return {}
    try:
        return json.loads(WORKSPACE_STUDENTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_workspace_students(data):
    WORKSPACE_STUDENTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_workspace_students():
    data = _load_workspace_students()
    try:
        uuids = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
        for sid, u in uuids.items():
            display_id = sid
            if display_id not in data:
                data[display_id] = {
                    "display_id": display_id,
                    "name": sid,
                    "birth_md": "",
                    "accounts": [sid],
                    "user_uuid": u
                }
        _save_workspace_students(data)
    except Exception:
        pass
    return data


def append_homework_log(user_uuid: str, payload: dict) -> dict:
    from utils.utils_user_doc import load_doc_by_any, save_doc_by_any
    from config import LEGACY_TO_SERVER_FILE
    from uuid import uuid4

    doc = load_doc_by_any(user_uuid)
    doc.setdefault("user_uuid", user_uuid)

    payload = payload or {}
    payload.setdefault("channel", "kakao")
    payload.setdefault("message", "")
    payload.setdefault("title", "")
    payload.setdefault("url", "")
    payload.setdefault("problems", [])

    log = dict(payload)
    log["id"] = log.get("id") or str(uuid4())
    log["log_id"] = log.get("log_id") or log["id"]

    log["problems"] = []
    legacy_to_server = {}
    if os.path.exists(LEGACY_TO_SERVER_FILE):
        try:
            with open(LEGACY_TO_SERVER_FILE, encoding="utf-8") as f:
                legacy_to_server = json.load(f)
        except Exception:
            pass

    for ent in list(payload["problems"]):
        if isinstance(ent, dict):
            legacy_code = ent.get("legacy_code") or ent.get("code") or ""
            title = ent.get("title") or ent.get("title_at_issue") or ""
        else:
            legacy_code = str(ent)
            title = ""
        log["problems"].append(
            {
                "legacy_code": legacy_code,
                "server_problem_id": legacy_to_server.get(legacy_code),
                "title": title,
            }
        )

    log.setdefault("ts", datetime.now(tz=KST).isoformat())
    doc.setdefault("homework_logs", []).append(log)

    path = save_doc_by_any(user_uuid, doc)
    print(f"[HW] saved -> {path}, logs={len(doc['homework_logs'])}")
    return doc
