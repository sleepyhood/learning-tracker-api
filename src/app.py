import os
import sys
import json
import ipaddress
import threading
import webbrowser
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from config import (
    ADMIN_DOMAIN,
    STUDENT_DOMAIN,
    SESSION_COOKIE_DOMAIN,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    CORS_ALLOWED_ORIGINS,
    RELAX_HOST_RESTRICTION,
)
from core.storage import META_DIR, KST
from utils.utils_user_doc import _parse_iso_datetime






# app = Flask(__name__)
app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)  # ✅ 여기에 바로 설정
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

if SESSION_COOKIE_DOMAIN:
    app.config["SESSION_COOKIE_DOMAIN"] = SESSION_COOKIE_DOMAIN
app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE

cors_origins = CORS_ALLOWED_ORIGINS or []
if not cors_origins and ADMIN_DOMAIN:
    cors_origins.append(f"https://{ADMIN_DOMAIN}")
if not cors_origins and STUDENT_DOMAIN:
    cors_origins.append(f"https://{STUDENT_DOMAIN}")

if not cors_origins:
    cors_origins.extend(["http://localhost:5000", "http://127.0.0.1:5000"])

CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

# Register Blueprints (Phase 2, 3 & 4)
from routes.workspace import workspace_bp
from routes.auth import auth_bp
from routes.schedule import schedule_bp
from routes.students import students_bp
from routes.seating import seating_bp

app.register_blueprint(workspace_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(students_bp)
app.register_blueprint(seating_bp)

app.add_url_rule("/students/<user_uuid>/homework", endpoint="view_homework_logs", view_func=app.view_functions["students.view_homework_logs"])

# Initialize RDB store & Background Worker
try:
    from db.session import init_db
    from workers.background_sync import start_background_sync_worker
    init_db()
    start_background_sync_worker(app)
except Exception as _e:
    print(f"[AppInit] DB/Worker init error: {_e}")


CHAPTER_WORKSPACE_BETA_ENABLED = (
    os.environ.get("CHAPTER_WORKSPACE_BETA_ENABLED", "0").strip().lower()
    in ("1", "true", "yes", "on")
)
CHAPTER_WORKSPACE_BETA_USERS = {
    x.strip()
    for x in os.environ.get("CHAPTER_WORKSPACE_BETA_USERS", "").split(",")
    if x.strip()
}
CHAPTER_WORKSPACE_DEFAULT_ENABLED = (
    os.environ.get("CHAPTER_WORKSPACE_DEFAULT_ENABLED", "0").strip().lower()
    in ("1", "true", "yes", "on")
)
CHAPTER_WORKSPACE_DEFAULT_USERS = {
    x.strip()
    for x in os.environ.get("CHAPTER_WORKSPACE_DEFAULT_USERS", "").split(",")
    if x.strip()
}
CHAPTER_WORKSPACE_EVENTS_PATH = META_DIR / "chapter_workspace_events.jsonl"
CHAPTER_WORKSPACE_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- imports 상단 ---
from flask import session as fsession
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
import os, json
from collections import defaultdict

ADMIN_ONLY_PREFIXES = (
    "/schedule",
    "/api/schedule",
    "/seating",
    "/api/seating",
    "/update_problems",
    "/api/students",
    "/students",
    "/refresh_user",
    "/proxy/user_rank",
)

STUDENT_ONLY_PREFIXES = (
    "/user",
    "/api/streak",
)


def _is_localhost(host: str) -> bool:
    return host in ("localhost", "127.0.0.1")


def _is_private_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private)


def _is_admin_route(path: str) -> bool:
    return path in ADMIN_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in ADMIN_ONLY_PREFIXES
    )


def _is_student_route(path: str) -> bool:
    return path in STUDENT_ONLY_PREFIXES or any(
        path.startswith(p + "/") for p in STUDENT_ONLY_PREFIXES
    )


def _workspace_beta_enabled_for(username: str) -> bool:
    if CHAPTER_WORKSPACE_BETA_ENABLED:
        return True
    return bool(username and username in CHAPTER_WORKSPACE_BETA_USERS)


def _workspace_default_enabled_for(username: str) -> bool:
    if CHAPTER_WORKSPACE_DEFAULT_ENABLED:
        return True
    return bool(username and username in CHAPTER_WORKSPACE_DEFAULT_USERS)


def _workspace_route_enabled_for(username: str) -> bool:
    return _workspace_default_enabled_for(username) or _workspace_beta_enabled_for(username)


def _append_workspace_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with CHAPTER_WORKSPACE_EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_workspace_events(limit_days: int = 14) -> list[dict]:
    if limit_days <= 0:
        limit_days = 1
    cutoff = datetime.now(tz=KST) - timedelta(days=limit_days)
    events: list[dict] = []
    if not CHAPTER_WORKSPACE_EVENTS_PATH.exists():
        return events

    with CHAPTER_WORKSPACE_EVENTS_PATH.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso_datetime(ev.get("ts"))
            if not ts:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=KST)
            ts = ts.astimezone(KST)
            if ts < cutoff:
                continue
            ev["_ts"] = ts
            ev["_date"] = ts.date().isoformat()
            events.append(ev)
    return events


def _build_workspace_event_summary(events: list[dict]) -> dict:
    daily: dict[str, dict] = {}
    sessions_with_group_switch = set()
    sessions_with_save_success = set()
    group_switch_by_group: dict[str, int] = {}
    save_success_by_group: dict[str, int] = {}
    totals = {
        "workspace_load_succeeded": 0,
        "workspace_load_failed": 0,
        "workspace_save_succeeded": 0,
        "workspace_save_failed": 0,
        "workspace_copy_selected": 0,
        "group_switch": 0,
    }

    for ev in events:
        name = ev.get("event_name") or ""
        date_key = ev.get("_date")
        group_id = (ev.get("group") or "").strip() or "(none)"
        session_id = (ev.get("session_id") or "").strip()

        if date_key not in daily:
            daily[date_key] = {
                "date": date_key,
                "workspace_load_succeeded": 0,
                "workspace_load_failed": 0,
                "workspace_save_succeeded": 0,
                "workspace_save_failed": 0,
                "workspace_copy_selected": 0,
                "group_switch": 0,
            }

        if name in totals:
            totals[name] += 1
            daily[date_key][name] += 1

        if name == "group_switch":
            group_switch_by_group[group_id] = group_switch_by_group.get(group_id, 0) + 1
            if session_id:
                sessions_with_group_switch.add(session_id)
        elif name == "workspace_save_succeeded":
            save_success_by_group[group_id] = save_success_by_group.get(group_id, 0) + 1
            if session_id:
                sessions_with_save_success.add(session_id)

    daily_rows = []
    for _, row in sorted(daily.items(), key=lambda kv: kv[0]):
        save_attempts = row["workspace_save_succeeded"] + row["workspace_save_failed"]
        row["save_attempts"] = save_attempts
        row["save_failure_rate"] = round(
            (row["workspace_save_failed"] / save_attempts) * 100, 2
        ) if save_attempts else 0.0
        daily_rows.append(row)

    total_save_attempts = totals["workspace_save_succeeded"] + totals["workspace_save_failed"]
    total_save_failure_rate = round(
        (totals["workspace_save_failed"] / total_save_attempts) * 100, 2
    ) if total_save_attempts else 0.0

    conversion_den = len(sessions_with_group_switch)
    conversion_num = len(sessions_with_group_switch & sessions_with_save_success)
    conversion_rate = round((conversion_num / conversion_den) * 100, 2) if conversion_den else 0.0

    group_rows = []
    for group_id in sorted(set(group_switch_by_group.keys()) | set(save_success_by_group.keys())):
        switches = group_switch_by_group.get(group_id, 0)
        saves = save_success_by_group.get(group_id, 0)
        group_rows.append(
            {
                "group": group_id,
                "group_switch": switches,
                "workspace_save_succeeded": saves,
                "save_per_switch": round((saves / switches) * 100, 2) if switches else 0.0,
            }
        )

    return {
        "totals": {
            **totals,
            "save_attempts": total_save_attempts,
            "save_failure_rate": total_save_failure_rate,
        },
        "funnel": {
            "group_switch_sessions": conversion_den,
            "save_success_sessions_after_switch": conversion_num,
            "group_switch_to_save_conversion_rate": conversion_rate,
        },
        "daily": daily_rows,
        "groups": group_rows,
    }





@app.before_request
def enforce_subdomain_access():
    if not ADMIN_DOMAIN and not STUDENT_DOMAIN:
        return None

    host = (request.host or "").split(":")[0].lower()
    if _is_localhost(host):
        return None
    if RELAX_HOST_RESTRICTION and _is_private_host(host):
        return None

    path = request.path or "/"
    is_admin_route = _is_admin_route(path)
    is_student_route = _is_student_route(path)

    allowed_hosts = {h for h in (ADMIN_DOMAIN, STUDENT_DOMAIN) if h}
    if allowed_hosts and host not in allowed_hosts:
        return ("forbidden", 403)

    if STUDENT_DOMAIN and host == STUDENT_DOMAIN and is_admin_route:
        return ("forbidden", 403)

    if ADMIN_DOMAIN and host == ADMIN_DOMAIN and is_student_route:
        return ("forbidden", 403)

    if ADMIN_DOMAIN and host == ADMIN_DOMAIN:
        return None

    if STUDENT_DOMAIN and host == STUDENT_DOMAIN:
        return None

    return None



# --- Server Entrypoint Starter ---





if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    open_browser = os.environ.get("FLASK_OPEN_BROWSER", "1").lower() in ("1", "true", "yes")

    # Werkzeug reloader parent process should not open a duplicate browser tab.
    should_open_browser = open_browser and (not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true")
    if should_open_browser:
        browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
        threading.Timer(0.7, lambda: webbrowser.open(f"http://{browser_host}:{port}")).start()

    app.run(host=host, port=port, debug=debug)
