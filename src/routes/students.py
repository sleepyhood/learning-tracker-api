import json
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template

from config import (
    PROBLEM_DIR,
    PROBLEM_FILE,
    USER_DATA_DIR,
    LEGACY_TO_SERVER_FILE,
)
CHAPTER_WORKSPACE_EVENTS_FILE = os.path.join(PROBLEM_DIR, "chapter_workspace_events.json")
from core.storage import (
    load_schedule,
    save_schedule,
    hydrate_slot_students,
    append_homework_log,
    _load_workspace_students,
    UNCERTAIN_WEEKDAY,
    UNCERTAIN_WEEKDAY_LABEL,
    WEEKDAY_LABELS,
)
from utils.utils_common import (
    ensure_admin_or_403,
    ensure_admin_or_redirect,
    ensure_login_or_redirect,
    ensure_user_cache_or_404,
    resolve_uuid,
    sanitize_filename,
    sync_user_problems_cache,
)
from utils.utils_user_doc import load_doc_by_any, save_doc_by_any

students_bp = Blueprint("students", __name__)


def _workspace_beta_enabled_for(username: str) -> bool:
    return True


def _workspace_default_enabled_for(username: str) -> bool:
    return True


def _latest_homework_status_map(user_doc: dict) -> dict:
    res = {}
    if not isinstance(user_doc, dict):
        return res
    logs = user_doc.get("homework_logs", [])
    if not isinstance(logs, list):
        return res
    for log in logs:
        if not isinstance(log, dict):
            continue
        problems = log.get("problems", [])
        if not isinstance(problems, list):
            continue
        for p in problems:
            if not isinstance(p, dict):
                continue
            lc = p.get("legacy_code")
            st = p.get("status")
            if lc and st:
                res[str(lc)] = "solved" if st == "solved" else "wrong"
    return res


@students_bp.route("/api/students/<user_uuid>/refresh", methods=["POST"])
def api_student_refresh(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    doc = load_doc_by_any(user_uuid)
    profile = doc.get("profile") or {}
    username = profile.get("student_id") or profile.get("username") or user_uuid

    try:
        updated_doc, user_path = sync_user_problems_cache(s, username)
        return jsonify({"ok": True, "updated_at": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@students_bp.route("/refresh_user/<username>")
def refresh_user(username):
    s, err = ensure_admin_or_403()
    if err:
        return err

    try:
        updated_doc, user_path = sync_user_problems_cache(s, username)
        return jsonify({"ok": True, "success": True, "message": f"{username} 프로필 갱신 완료"})
    except Exception as e:
        return jsonify({"ok": False, "success": False, "error": str(e)}), 500


@students_bp.route("/api/students/<user_uuid>/homework_status")
def api_student_homework_status(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    doc = load_doc_by_any(user_uuid)
    hw_map = _latest_homework_status_map(doc)
    return jsonify({"ok": True, "homework_status": hw_map, "updated_at": doc.get("updated_at")})


@students_bp.delete("/api/students/<id_or_uuid>/homework_logs/<log_key>")
def api_student_delete_homework_log(id_or_uuid, log_key):
    s, err = ensure_admin_or_403()
    if err:
        return err

    doc = load_doc_by_any(id_or_uuid)
    logs = doc.get("homework_logs", [])
    filtered = [l for l in logs if str(l.get("id")) != str(log_key) and str(l.get("log_id")) != str(log_key)]
    if len(filtered) == len(logs):
        return jsonify({"ok": False, "error": "Log not found"}), 404

    doc["homework_logs"] = filtered
    save_doc_by_any(id_or_uuid, doc)
    return jsonify({"ok": True})


@students_bp.route("/api/students/<id_or_uuid>/homework_logs", methods=["POST", "OPTIONS"])
def api_student_homework_logs(id_or_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    payload = request.get_json(force=True) or {}
    updated_doc = append_homework_log(id_or_uuid, payload)
    return jsonify({"ok": True, "homework_logs": updated_doc.get("homework_logs", [])})


@students_bp.get("/api/students/<user_uuid>/homework_latest")
def api_student_homework_latest(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    doc = load_doc_by_any(user_uuid)
    logs = doc.get("homework_logs", [])
    recent = logs[-1] if logs else {}
    return jsonify({"ok": True, "homework": recent, "log": recent})


@students_bp.post("/api/students/homework_latest_batch")
def api_students_homework_latest_batch():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    uuids = payload.get("user_uuids", [])
    result = {}
    for u in uuids:
        try:
            doc = load_doc_by_any(u)
            logs = doc.get("homework_logs", [])
            result[u] = logs[-1] if logs else {}
        except Exception:
            result[u] = {}

    return jsonify({"ok": True, "batch": result})


@students_bp.get("/students/<user_uuid>/homework", endpoint="view_homework_logs")
def view_homework_logs(user_uuid):
    s, err = ensure_admin_or_redirect()
    if err:
        return err

    doc = load_doc_by_any(user_uuid)
    profile = doc.get("profile", {})
    logs = doc.get("homework_logs", [])
    # 파일 자체가 없는 경우: profile도 비어있고 homework_logs도 없음
    doc_missing = not logs and not profile

    return render_template(
        "homework_view.html",
        student=profile,
        logs=logs,
        user_uuid=user_uuid,
        is_admin=True,
        doc_missing=doc_missing,
    )


@students_bp.get("/api/chapter_workspace")
def api_chapter_workspace_get():
    s, err = ensure_admin_or_403()
    if err:
        return err

    username = request.args.get("username", "").strip()
    chapter = request.args.get("chapter", "").strip()
    if not username or not chapter:
        return jsonify({"ok": False, "error": "username and chapter are required"}), 400

    u = resolve_uuid(username)
    user_doc = load_doc_by_any(u)
    if not user_doc:
        return jsonify({"ok": False, "error": "User not found"}), 404

    return jsonify({
        "ok": True,
        "username": username,
        "chapter": chapter,
        "workspace_beta": _workspace_beta_enabled_for(username),
    })


@students_bp.get("/api/schedule")
def api_schedule_get():
    s, err = ensure_admin_or_403()
    if err:
        return err

    raw = load_schedule()
    slots = hydrate_slot_students(raw.get("slots", []))
    return jsonify({"ok": True, "slots": slots})


@students_bp.post("/api/schedule/slots")
def api_schedule_create_slot():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    label = str(payload.get("label") or "").strip()
    weekday = payload.get("weekday", 0)

    if not label:
        return jsonify({"ok": False, "error": "label is required"}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])
    
    from uuid import uuid4
    new_slot = {
        "id": str(uuid4()),
        "label": label,
        "weekday": weekday,
        "students": [],
        "student_notes": {}
    }
    slots.append(new_slot)
    save_schedule(data)
    
    hydrated = hydrate_slot_students([new_slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@students_bp.post("/api/schedule/slots/<slot_id>/students")
def api_schedule_add_student_to_slot(slot_id):
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    user_token = str(payload.get("user_token") or "").strip()
    if not user_token:
        return jsonify({"ok": False, "error": "user_token is required"}), 400

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    target_uuid = user_token if "-" in user_token else resolve_uuid(user_token)
    students = slot.setdefault("students", [])
    if target_uuid not in students:
        students.append(target_uuid)

    save_schedule(data)
    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@students_bp.delete("/api/schedule/slots/<slot_id>/students/<user_token>")
def api_schedule_remove_student_from_slot(slot_id, user_token):
    s, err = ensure_admin_or_403()
    if err:
        return err

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    target_uuid = user_token if "-" in user_token else resolve_uuid(user_token)
    students = slot.setdefault("students", [])
    slot["students"] = [st for st in students if st != target_uuid and st != user_token]

    save_schedule(data)
    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@students_bp.patch("/api/schedule/slots/<slot_id>/students/<user_token>/note")
def api_schedule_update_student_note(slot_id, user_token):
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    note = str(payload.get("note") or "").strip()

    data = load_schedule()
    slots = data.setdefault("slots", [])
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        return jsonify({"ok": False, "error": "slot not found"}), 404

    target_uuid = user_token if "-" in user_token else resolve_uuid(user_token)
    notes = slot.setdefault("student_notes", {})
    if note:
        notes[target_uuid] = note
    else:
        notes.pop(target_uuid, None)

    save_schedule(data)
    hydrated = hydrate_slot_students([slot])[0]
    return jsonify({"ok": True, "slot": hydrated})


@students_bp.delete("/api/schedule/slots/<slot_id>")
def api_schedule_delete_slot(slot_id):
    s, err = ensure_admin_or_403()
    if err:
        return err

    data = load_schedule()
    slots = data.setdefault("slots", [])
    new_slots = [s for s in slots if s.get("id") != slot_id]
    if len(new_slots) == len(slots):
        return jsonify({"ok": False, "error": "slot not found"}), 404

    data["slots"] = new_slots
    save_schedule(data)
    return jsonify({"ok": True})
