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


import re

def _parse_account_name_birth(account_str: str) -> tuple[str, str, bool]:
    """
    Parses account string into (parsed_name, birth_md, is_standard).
    Supports Korean (2~4 chars) and English (2~15 chars) followed by 4-digit birthday.
    Examples:
      '홍길동0101' -> ('홍길동', '0101', True)
      'leo0719' -> ('leo', '0719', True)
      'david1225' -> ('david', '1225', True)
      'coding_king' -> ('coding_king', '', False)
    """
    if not account_str:
        return ("", "", False)
    s = str(account_str).strip()
    m = re.match(r'^([가-힣]{2,4}|[a-zA-Z]{2,15})(\d{4})$', s)
    if m:
        return (m.group(1), m.group(2), True)
    return (s, "", False)


def _load_workspace_students():
    if not WORKSPACE_STUDENTS_PATH.exists():
        return {}
    try:
        raw_data = json.loads(WORKSPACE_STUDENTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            return {}
        
        # Migration check: if keys are display_id, convert primary key to user_uuid
        migrated = {}
        need_save = False
        for k, v in raw_data.items():
            if not isinstance(v, dict):
                continue
            u = v.get("user_uuid")
            if not u:
                from uuid import uuid4
                u = str(uuid4())
                v["user_uuid"] = u
                need_save = True
            
            # Ensure standard fields
            disp = v.get("display_id") or v.get("name") or k
            name_val = v.get("name")
            p_name, p_birth, is_std = _parse_account_name_birth(disp)
            
            if not name_val or (is_std and name_val == disp):
                name_val = p_name or disp
                v["name"] = name_val
                need_save = True

            if is_std and p_birth and not v.get("birth_md"):
                v["birth_md"] = p_birth
                need_save = True

            v.setdefault("display_id", disp)
            v.setdefault("name", name_val)
            v.setdefault("birth_md", p_birth if is_std else "")
            v.setdefault("weekdays", [])
            v.setdefault("subjects", [])
            
            # Normalize accounts to clean list of strings
            raw_accs = v.get("accounts", [])
            norm_accs = []
            if isinstance(raw_accs, list):
                for acc in raw_accs:
                    if isinstance(acc, dict) and acc.get("username"):
                        norm_accs.append(acc["username"].strip())
                    elif isinstance(acc, str) and acc.strip():
                        norm_accs.append(acc.strip())
            if disp and disp not in norm_accs:
                norm_accs.insert(0, disp)
            v["accounts"] = norm_accs

            v.setdefault("note", "")
            v.setdefault("status", "active")

            # If key is not uuid, set key to uuid
            migrated[u] = v
            if k != u:
                need_save = True

        if need_save and migrated:
            _save_workspace_students(migrated)
        return migrated
    except Exception as e:
        print("[workspace_students] load error:", e)
        return {}


def _save_workspace_students(data):
    WORKSPACE_STUDENTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_workspace_students():
    data = _load_workspace_students()
    try:
        uuids = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
        changed = False
        uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        
        for sid, u in uuids.items():
            if uuid_pattern.match(sid):
                continue
            if u not in data:
                p_name, p_birth, is_std = _parse_account_name_birth(sid)
                data[u] = {
                    "user_uuid": u,
                    "display_id": sid,
                    "name": p_name or sid,
                    "birth_md": p_birth,
                    "weekdays": [],
                    "subjects": [],
                    "accounts": [sid],
                    "note": "",
                    "status": "active"
                }
                changed = True
            else:
                # Ensure sid is in student's accounts
                accs = data[u].setdefault("accounts", [])
                if sid not in accs:
                    accs.append(sid)
                    changed = True
        if changed:
            _save_workspace_students(data)
    except Exception as e:
        print("[workspace_students] sync error:", e)
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
            legacy_code = ent.get("legacy_code") or ent.get("code") or ent.get("pid") or ""
            title = ent.get("title") or ent.get("title_at_issue") or ""
            server_id = ent.get("server_problem_id") or legacy_to_server.get(legacy_code) or None
        else:
            legacy_code = str(ent)
            title = ""
            server_id = legacy_to_server.get(legacy_code) or None

        prob_entry = {
            "legacy_code": legacy_code,
            "title": title,
        }
        # server_problem_id는 실제 값이 있을 때만 저장 (None 제거)
        if server_id:
            prob_entry["server_problem_id"] = server_id
        log["problems"].append(prob_entry)

    now_iso = datetime.now(tz=KST).isoformat()
    log.setdefault("ts", now_iso)
    log.setdefault("created_at", now_iso)  # homework_logs 정렬 기준으로 활용
    doc.setdefault("homework_logs", []).append(log)

    path = save_doc_by_any(user_uuid, doc)
    print(f"[HW] saved -> {path}, logs={len(doc['homework_logs'])}")
    return doc


SEATING_LAYOUT_PATH = META_DIR / "seating_layout.json"
SEATING_SESSIONS_PATH = META_DIR / "seating_sessions.json"

DEFAULT_SEATING_LAYOUT = {
    "rows": 8,
    "cols": 7,
    "cells": [
        {"r": 0, "c": 0, "type": "monitor", "label": "선생님 모니터 1"},
        {"r": 0, "c": 1, "type": "aisle", "label": ""},
        {"r": 0, "c": 2, "type": "aisle", "label": ""},
        {"r": 0, "c": 3, "type": "aisle", "label": ""},
        {"r": 0, "c": 4, "type": "aisle", "label": ""},
        {"r": 0, "c": 5, "type": "aisle", "label": ""},
        {"r": 0, "c": 6, "type": "door", "label": "출입문 1"},
        {"r": 1, "c": 0, "type": "seat", "label": "STD31"},
        {"r": 1, "c": 1, "type": "aisle", "label": "통로/의자"},
        {"r": 1, "c": 2, "type": "aisle", "label": ""},
        {"r": 1, "c": 3, "type": "aisle", "label": ""},
        {"r": 1, "c": 4, "type": "aisle", "label": ""},
        {"r": 1, "c": 5, "type": "seat", "label": "STD12"},
        {"r": 1, "c": 6, "type": "aisle", "label": ""},
        {"r": 2, "c": 0, "type": "seat", "label": "STD30"},
        {"r": 2, "c": 1, "type": "aisle", "label": "통로/의자"},
        {"r": 2, "c": 2, "type": "aisle", "label": ""},
        {"r": 2, "c": 3, "type": "aisle", "label": ""},
        {"r": 2, "c": 4, "type": "aisle", "label": ""},
        {"r": 2, "c": 5, "type": "seat", "label": "STD11"},
        {"r": 2, "c": 6, "type": "aisle", "label": ""},
        {"r": 3, "c": 0, "type": "seat", "label": "STD29"},
        {"r": 3, "c": 1, "type": "aisle", "label": "통로/의자"},
        {"r": 3, "c": 2, "type": "aisle", "label": ""},
        {"r": 3, "c": 3, "type": "aisle", "label": ""},
        {"r": 3, "c": 4, "type": "aisle", "label": ""},
        {"r": 3, "c": 5, "type": "seat", "label": "STD10"},
        {"r": 3, "c": 6, "type": "door", "label": "출입문 2"},
        {"r": 4, "c": 0, "type": "seat", "label": "STD28"},
        {"r": 4, "c": 1, "type": "aisle", "label": ""},
        {"r": 4, "c": 2, "type": "aisle", "label": ""},
        {"r": 4, "c": 3, "type": "aisle", "label": ""},
        {"r": 4, "c": 4, "type": "aisle", "label": ""},
        {"r": 4, "c": 5, "type": "aisle", "label": ""},
        {"r": 4, "c": 6, "type": "aisle", "label": ""},
        {"r": 5, "c": 0, "type": "seat", "label": "STD13"},
        {"r": 5, "c": 1, "type": "seat", "label": "STD14"},
        {"r": 5, "c": 2, "type": "seat", "label": "STD15"},
        {"r": 5, "c": 3, "type": "seat", "label": "STD16"},
        {"r": 5, "c": 4, "type": "aisle", "label": ""},
        {"r": 5, "c": 5, "type": "aisle", "label": ""},
        {"r": 5, "c": 6, "type": "aisle", "label": ""},
        {"r": 6, "c": 0, "type": "aisle", "label": "통로/의자"},
        {"r": 6, "c": 1, "type": "aisle", "label": "통로/의자"},
        {"r": 6, "c": 2, "type": "aisle", "label": "통로/의자"},
        {"r": 6, "c": 3, "type": "aisle", "label": "통로/의자"},
        {"r": 6, "c": 4, "type": "aisle", "label": ""},
        {"r": 6, "c": 5, "type": "aisle", "label": ""},
        {"r": 6, "c": 6, "type": "monitor", "label": "선생님 모니터 2"},
        {"r": 7, "c": 0, "type": "seat", "label": "STD20"},
        {"r": 7, "c": 1, "type": "seat", "label": "STD19"},
        {"r": 7, "c": 2, "type": "seat", "label": "STD18"},
        {"r": 7, "c": 3, "type": "seat", "label": "STD17"},
        {"r": 7, "c": 4, "type": "aisle", "label": ""},
        {"r": 7, "c": 5, "type": "aisle", "label": ""},
        {"r": 7, "c": 6, "type": "aisle", "label": ""},
    ]
}


def load_seating_layout() -> dict:
    """좌석 레이아웃 배치 데이터 로드"""
    try:
        if SEATING_LAYOUT_PATH.exists():
            data = json.loads(SEATING_LAYOUT_PATH.read_text(encoding="utf-8"))
            if data and "cells" in data:
                return data
    except Exception as e:
        print("[seating] layout load error:", e)
    return DEFAULT_SEATING_LAYOUT


def save_seating_layout(layout: dict) -> dict:
    """좌석 레이아웃 배치 데이터 저장"""
    try:
        SEATING_LAYOUT_PATH.write_text(
            json.dumps(layout, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print("[seating] layout save error:", e)
    return layout


def load_seating_sessions() -> dict:
    """좌석 수강생 배정 및 체류 세션 로드 {"dates": {"2026-08-14": {"STD31": {...}}}}"""
    try:
        if SEATING_SESSIONS_PATH.exists():
            return json.loads(SEATING_SESSIONS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print("[seating] sessions load error:", e)
    return {"dates": {}}


def save_seating_sessions(sessions: dict) -> dict:
    """좌석 수강생 배정 및 체류 세션 저장"""
    try:
        SEATING_SESSIONS_PATH.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print("[seating] sessions save error:", e)
    return sessions

