import json
import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, render_template

from core.storage import (
    load_seating_layout,
    save_seating_layout,
    load_seating_sessions,
    save_seating_sessions,
    _load_workspace_students,
    _sync_workspace_students,
    DEFAULT_SEATING_LAYOUT,
    KST,
)
from utils.utils_common import ensure_admin_or_403, ensure_admin_or_redirect

seating_bp = Blueprint("seating", __name__)


@seating_bp.route("/seating")
def seating_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    return render_template("seating_map.html")


def _time_to_mins(time_str: str) -> int:
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 14 * 60


@seating_bp.route("/api/seating", methods=["GET"])
def api_get_seating():
    s, err = ensure_admin_or_403()
    if err:
        return err
    target_date = request.args.get("date") or datetime.now(tz=KST).strftime("%Y-%m-%d")
    layout = load_seating_layout()
    sessions = load_seating_sessions()
    
    # Always trigger real-time student sync
    try:
        _sync_workspace_students()
    except Exception:
        pass
    workspace_students = _load_workspace_students()
    
    if isinstance(workspace_students, dict):
        students_list = list(workspace_students.values())
    elif isinstance(workspace_students, list):
        students_list = workspace_students
    else:
        students_list = []

    raw_date_sessions = sessions.get("dates", {}).get(target_date, {})
    date_sessions = {}
    for seat, item in raw_date_sessions.items():
        if isinstance(item, list):
            date_sessions[seat] = item
        elif isinstance(item, dict):
            date_sessions[seat] = [item]

    return jsonify({
        "status": "success",
        "date": target_date,
        "layout": layout,
        "sessions": date_sessions,
        "students": students_list,
    })


@seating_bp.route("/api/seating/layout", methods=["POST"])
def api_save_layout():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", 8)
    cols = payload.get("cols", 7)
    cells = payload.get("cells", [])

    if not isinstance(rows, int) or rows < 1 or rows > 20:
        return jsonify({"status": "error", "message": "Rows must be between 1 and 20"}), 400
    if not isinstance(cols, int) or cols < 1 or cols > 20:
        return jsonify({"status": "error", "message": "Cols must be between 1 and 20"}), 400

    layout_data = {
        "rows": rows,
        "cols": cols,
        "cells": cells,
        "updated_at": datetime.now(tz=KST).isoformat()
    }
    save_seating_layout(layout_data)
    return jsonify({"status": "success", "layout": layout_data})


@seating_bp.route("/api/seating/layout/reset", methods=["POST"])
def api_reset_layout():
    s, err = ensure_admin_or_403()
    if err:
        return err
    save_seating_layout(DEFAULT_SEATING_LAYOUT)
    return jsonify({"status": "success", "layout": DEFAULT_SEATING_LAYOUT})


@seating_bp.route("/api/seating/session", methods=["POST"])
def api_save_session():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    target_date = payload.get("date") or datetime.now(tz=KST).strftime("%Y-%m-%d")
    seat_label = payload.get("seat_label") or payload.get("cell_id")

    if not seat_label:
        return jsonify({"status": "error", "message": "seat_label parameter missing"}), 400

    sessions = load_seating_sessions()
    sessions.setdefault("dates", {})
    sessions["dates"].setdefault(target_date, {})

    raw_seat_entry = sessions["dates"][target_date].get(seat_label, [])
    if isinstance(raw_seat_entry, dict):
        seat_sessions = [raw_seat_entry]
    elif isinstance(raw_seat_entry, list):
        seat_sessions = list(raw_seat_entry)
    else:
        seat_sessions = []

    action = payload.get("action", "assign")

    # Action 1: Clear all sessions on this seat
    if action == "clear":
        if seat_label in sessions["dates"][target_date]:
            del sessions["dates"][target_date][seat_label]
        save_seating_sessions(sessions)
        return jsonify({"status": "success", "action": "clear", "seat_label": seat_label})

    # Action 2: Delete specific session by ID
    session_id = payload.get("session_id")
    if action == "delete":
        if session_id:
            seat_sessions = [s for s in seat_sessions if s.get("id") != session_id]
            if seat_sessions:
                sessions["dates"][target_date][seat_label] = seat_sessions
            else:
                if seat_label in sessions["dates"][target_date]:
                    del sessions["dates"][target_date][seat_label]
            save_seating_sessions(sessions)
        return jsonify({"status": "success", "action": "delete", "seat_label": seat_label})

    # Action 3: Assign / Edit session
    student_type = payload.get("student_type", "auto")
    student_id = payload.get("student_id", "")
    student_name = payload.get("student_name", "")
    start_time = payload.get("start_time", "14:00")
    duration_hours = float(payload.get("duration_hours", 1.5))
    help_status = payload.get("help_status", "normal")
    memo = payload.get("memo", "")

    from uuid import uuid4
    if not session_id:
        session_id = f"sess_{uuid4().hex[:8]}"

    # Time overlap conflict check
    new_start_m = _time_to_mins(start_time)
    new_end_m = new_start_m + int(duration_hours * 60)

    conflicts = []
    for existing in seat_sessions:
        if existing.get("id") == session_id:
            continue
        ex_start_m = _time_to_mins(existing.get("start_time", "14:00"))
        ex_dur = float(existing.get("duration_hours", 1.5))
        ex_end_m = ex_start_m + int(ex_dur * 60)

        # Overlap check
        if new_start_m < ex_end_m and ex_start_m < new_end_m:
            conflicts.append(existing)

    has_conflict = len(conflicts) > 0
    conflict_messages = []
    if has_conflict:
        for c_entry in conflicts:
            c_name = c_entry.get("student_name", "다른 수강생")
            c_start = c_entry.get("start_time", "")
            c_dur = c_entry.get("duration_hours", 1.5)
            conflict_messages.append(f"[{c_start} ({c_dur}시간)] {c_name}")

    entry = {
        "id": session_id,
        "seat_label": seat_label,
        "student_type": student_type,
        "student_id": student_id,
        "student_name": student_name,
        "start_time": start_time,
        "duration_hours": duration_hours,
        "help_status": help_status,
        "memo": memo,
        "has_conflict": has_conflict,
        "conflict_message": ", ".join(conflict_messages) if conflict_messages else "",
        "updated_at": datetime.now(tz=KST).isoformat()
    }

    # Update or append in seat_sessions list
    updated = False
    for idx, s in enumerate(seat_sessions):
        if s.get("id") == session_id:
            seat_sessions[idx] = entry
            updated = True
            break
    if not updated:
        seat_sessions.append(entry)

    sessions["dates"][target_date][seat_label] = seat_sessions
    save_seating_sessions(sessions)

    return jsonify({
        "status": "success",
        "entry": entry,
        "has_conflict": has_conflict,
        "conflict_message": entry["conflict_message"],
        "seat_sessions": seat_sessions
    })


@seating_bp.route("/api/seating/import", methods=["POST"])
def api_import_seating():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    target_date = payload.get("date") or datetime.now(tz=KST).strftime("%Y-%m-%d")

    imported_layout = payload.get("layout")
    imported_sessions = payload.get("sessions")

    if imported_layout and isinstance(imported_layout, dict) and "cells" in imported_layout:
        save_seating_layout(imported_layout)

    if imported_sessions and isinstance(imported_sessions, dict):
        all_sessions = load_seating_sessions()
        all_sessions.setdefault("dates", {})
        all_sessions["dates"][target_date] = imported_sessions
        save_seating_sessions(all_sessions)

    cur_layout = load_seating_layout()
    cur_sessions = load_seating_sessions().get("dates", {}).get(target_date, {})

    return jsonify({
        "status": "success",
        "date": target_date,
        "layout": cur_layout,
        "sessions": cur_sessions
    })

