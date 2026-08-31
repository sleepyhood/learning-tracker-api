import json
import os
import re
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
    
    probs_dict = user_doc.get("problems_dict") or {}
    if isinstance(probs_dict, dict):
        for k, v in probs_dict.items():
            if isinstance(v, dict):
                code = v.get("_id") or v.get("legacy_code") or k
                st = v.get("status")
                score = str(v.get("score") if v.get("score") is not None else "0")
                if code:
                    if st in [0, "0", "PASSED", "solved", "passed", "AC", "ACCEPTED"] or score == "100":
                        res[str(code)] = "solved"
                    elif st in [-1, "-1", "WRONG", "wrong", "FAILED", "failed"]:
                        res[str(code)] = "wrong"

    logs = user_doc.get("homework_logs", [])
    if isinstance(logs, list):
        for log in logs:
            if not isinstance(log, dict):
                continue
            problems = log.get("problems", [])
            if not isinstance(problems, list):
                continue
            for p in problems:
                if not isinstance(p, dict):
                    continue
                lc = p.get("legacy_code") or p.get("code") or p.get("pid") or p.get("id")
                st = str(p.get("status") or "").lower()
                score = str(p.get("score") or "0")
                if lc and str(lc) not in res:
                    if st in ["solved", "passed", "0", "ac", "accepted"] or score == "100":
                        res[str(lc)] = "solved"
                    elif st in ["wrong", "failed", "-1"]:
                        res[str(lc)] = "wrong"
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

    # RDB Dual-Store 동기화 (삭제)
    try:
        from db.dual_store import USE_RDB_STORE
        if USE_RDB_STORE:
            from db.session import get_db_session
            from db.repo import delete_assignment_rdb
            with get_db_session() as session:
                delete_assignment_rdb(session, log_key)
                session.commit()
    except Exception as _rdb_err:
        print(f"[delete_homework_log] RDB delete warning: {_rdb_err}")

    return jsonify({"ok": True})


def _enrich_log_problem_status(doc: dict, log: dict) -> dict:
    if not log or not isinstance(log, dict):
        return log
    
    from utils.utils_common import resolve_legacy_map_dict
    legacy_to_server = resolve_legacy_map_dict()
    server_to_legacy = {v: k for k, v in legacy_to_server.items()}

    oi_probs = doc.get("oi_problems") or {}
    oi_dict = {}
    if isinstance(oi_probs, dict):
        oi_dict = oi_probs
    elif isinstance(oi_probs, list):
        for item in oi_probs:
            if isinstance(item, dict):
                code = item.get("legacy_code") or item.get("code") or item.get("pid") or item.get("id")
                if code:
                    oi_dict[str(code)] = item

    solved_set = set()
    wrong_set = set()
    submission_map = {}

    def register_code(code_str, is_passed, is_wrong, entry):
        if not code_str:
            return
        c_str = str(code_str).strip()
        c_norm = re.sub(r'[^a-zA-Z0-9]', '', c_str).lower()
        
        codes_to_register = {c_str, c_str.lower(), c_norm}
        if c_str in legacy_to_server:
            srv = legacy_to_server[c_str]
            codes_to_register.update({srv, srv.lower(), re.sub(r'[^a-zA-Z0-9]', '', srv).lower()})
        if c_str in server_to_legacy:
            leg = server_to_legacy[c_str]
            codes_to_register.update({leg, leg.lower(), re.sub(r'[^a-zA-Z0-9]', '', leg).lower()})

        for k in codes_to_register:
            submission_map[k] = entry
            if is_passed:
                solved_set.add(k)
            elif is_wrong:
                wrong_set.add(k)

    # 1. doc 내부 problems_dict 및 oi_problems 파싱
    problems_dict = doc.get("problems_dict") or {}
    if not isinstance(problems_dict, dict):
        problems_dict = {}

    oi_probs = doc.get("oi_problems") or {}
    if isinstance(oi_probs, dict):
        for k, v in oi_probs.items():
            if k not in problems_dict:
                problems_dict[k] = v
    elif isinstance(oi_probs, list):
        for item in oi_probs:
            if isinstance(item, dict):
                code = item.get("legacy_code") or item.get("code") or item.get("pid") or item.get("id")
                if code:
                    problems_dict[str(code)] = item

    # 2. {username}.json 및 {uuid}.json 외부 파일 통합 파싱
    prof = doc.get("profile") or {}
    username = prof.get("username") or prof.get("student_id")
    user_uuid_key = doc.get("user_uuid") or doc.get("uuid")
    
    for candidate in filter(None, [username, user_uuid_key]):
        user_prob_file = os.path.join(USER_DATA_DIR, f"{candidate}.json")
        if os.path.exists(user_prob_file):
            try:
                with open(user_prob_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                if isinstance(file_data, dict):
                    # UUID 문서인 경우 oi_problems / problems_dict 추출
                    target_dict = file_data
                    if "user_uuid" in file_data or "homework_logs" in file_data:
                        target_dict = file_data.get("oi_problems") or file_data.get("problems_dict") or {}
                        if isinstance(target_dict, list):
                            target_dict = {str(item.get("code") or item.get("legacy_code")): item for item in target_dict if isinstance(item, dict)}

                    if isinstance(target_dict, dict):
                        for k, v in target_dict.items():
                            if k not in problems_dict:
                                problems_dict[k] = v
            except Exception:
                pass

    for k, v in problems_dict.items():
        if isinstance(v, dict):
            code = v.get("_id") or v.get("legacy_code") or k
            raw_st = v.get("status")
            score_val = str(v.get("score") if v.get("score") is not None else "0")
            
            is_passed = (raw_st == 0 or raw_st == "0" or score_val == "100")
            is_wrong = (raw_st == -1 or raw_st == "-1") and not is_passed
            
            entry = {"score": score_val, "status": "PASSED" if is_passed else ("WRONG" if is_wrong else str(raw_st))}
            register_code(code, is_passed, is_wrong, entry)
            if k != code:
                register_code(k, is_passed, is_wrong, entry)

    def add_to_maps(raw_code, info_dict):
        if not raw_code:
            return
        raw_res = info_dict.get("result")
        raw_st = info_dict.get("status")
        status = str(raw_st if raw_st is not None else raw_res if raw_res is not None else "").upper()
        
        stat_info = info_dict.get("statistic_info")
        score = "0"
        if isinstance(stat_info, dict) and "score" in stat_info:
            score = str(stat_info.get("score") or "0")
        elif "score" in info_dict:
            score = str(info_dict.get("score") or "0")

        is_passed = (
            status in ["0", "PASSED", "SOLVED", "CORRECT", "AC", "ACCEPTED"] or 
            raw_res == 0 or raw_st == 0 or score == "100"
        )
        is_wrong = (status in ["WRONG", "FAILED"] or raw_res in [-1, 1, 2, 3, 4, 5]) and not is_passed
        
        entry = {"score": score, "status": "PASSED" if is_passed else status}
        register_code(raw_code, is_passed, is_wrong, entry)

    for code, info in oi_dict.items():
        if isinstance(info, dict):
            add_to_maps(code, info)

    for sub in doc.get("submissions", []) or []:
        if isinstance(sub, dict):
            code = sub.get("legacy_code") or sub.get("problem_id") or sub.get("code") or sub.get("problem")
            if isinstance(code, dict):
                code = code.get("_id") or code.get("id")
            if code:
                add_to_maps(code, sub)

    for sp in doc.get("solved_problems", []) or []:
        register_code(sp, is_passed=True, is_wrong=False, entry={"score": "100", "status": "PASSED"})

    enriched_problems = []
    counts = {"total": 0, "passed": 0, "wrong": 0, "partial": 0, "pending": 0}
    
    problems = log.get("problems", [])
    counts["total"] = len(problems)

    for p in problems:
        if isinstance(p, dict):
            # server_problem_id도 추출해 병행 검사
            p_server_id = str(p.get("server_problem_id") or "").strip()
            p_code = str(p.get("legacy_code") or p.get("code") or p.get("pid") or p.get("problem_id") or p.get("id") or p.get("_id") or "").strip()
            p_title = p.get("title") or ""
        else:
            p_code = str(p).strip()
            p_title = ""

        p_norm = re.sub(r'[^a-zA-Z0-9]', '', p_code).lower()
        # server_problem_id 기반 추가 조회 키 생성
        p_server_norm = re.sub(r'[^a-zA-Z0-9]', '', p_server_id).lower() if p_server_id else ""
        # legacy_code -> server_id 변환 키 및 역방향도 조회
        p_mapped_server = legacy_to_server.get(p_code, "")
        p_mapped_legacy = server_to_legacy.get(p_code, "")

        def _find_in_map(m):
            for key in filter(None, [p_code, p_code.lower(), p_norm, p_server_id, p_server_id.lower() if p_server_id else "", p_server_norm, p_mapped_server, p_mapped_legacy]):
                if key and key in m:
                    return m[key]
            return None

        sub_info = _find_in_map(submission_map) or {}
        score = sub_info.get("score")
        sub_status = sub_info.get("status", "")

        def _in_set(s):
            return any(k in s for k in filter(None, [p_code, p_code.lower(), p_norm, p_server_id, p_server_norm, p_mapped_server, p_mapped_legacy]))

        status = "pending"
        if (_in_set(solved_set) or score == "100" or sub_status in ["PASSED", "SOLVED", "CORRECT"]):
            status = "passed"
            counts["passed"] += 1
        elif score and score != "0":
            status = "partial"
            counts["partial"] += 1
        elif (_in_set(wrong_set) or sub_status in ["WRONG", "FAILED"]):
            status = "wrong"
            counts["wrong"] += 1
        else:
            counts["pending"] += 1

        enriched_p = dict(p) if isinstance(p, dict) else {}
        enriched_p["legacy_code"] = p_code
        enriched_p["title"] = p_title
        if p_server_id:
            enriched_p["server_problem_id"] = p_server_id
        enriched_p["status"] = status
        enriched_p["score"] = score if (score is not None and score != "") else ("100" if status == "passed" else "0")
        enriched_problems.append(enriched_p)

    enriched_log = dict(log)
    enriched_log["problems"] = enriched_problems
    enriched_log["counts"] = counts
    return enriched_log


@students_bp.route("/api/students/<id_or_uuid>/homework_logs", methods=["GET", "POST", "OPTIONS"])
def api_student_homework_logs(id_or_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if request.method == "GET":
        from utils.utils_common import ensure_user_cache_or_404
        doc, _ = ensure_user_cache_or_404(id_or_uuid)
        if not doc:
            from utils.utils_user_doc import load_doc_by_any
            doc = load_doc_by_any(id_or_uuid) or {}

        prof = doc.get("profile") or {}
        st_id = prof.get("student_id") or prof.get("username") or id_or_uuid
        st_name = prof.get("name") or st_id

        if st_id and st_id != id_or_uuid:
            from config import USER_DATA_DIR
            import os as _os
            cache_path = _os.path.join(USER_DATA_DIR, f"{st_id}.json")
            if _os.path.exists(cache_path):
                try:
                    import json as _json
                    cache_data = _json.load(open(cache_path, encoding="utf-8"))
                    if isinstance(cache_data, dict):
                        oi = doc.get("oi_problems")
                        if not oi:
                            doc["oi_problems"] = cache_data
                        elif isinstance(oi, dict):
                            for k, v in cache_data.items():
                                if k not in oi:
                                    oi[k] = v
                except Exception as _e:
                    print(f"[hw_logs] cache merge failed: {_e}")

        logs = doc.get("homework_logs", [])
        try:
            logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
        except Exception:
            pass
        enriched_logs = [_enrich_log_problem_status(doc, l) for l in logs]

        return jsonify({
            "ok": True, 
            "homework_logs": enriched_logs, 
            "logs": enriched_logs,
            "student_id": st_id,
            "student_name": st_name
        })

    payload = request.get_json(force=True) or {}
    updated_doc = append_homework_log(id_or_uuid, payload)
    logs = updated_doc.get("homework_logs", [])
    try:
        logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
    except Exception:
        pass
    enriched_logs = [_enrich_log_problem_status(updated_doc, l) for l in logs]
    return jsonify({"ok": True, "homework_logs": enriched_logs, "logs": enriched_logs})


@students_bp.get("/api/students/<user_uuid>/homework_latest")
def api_student_homework_latest(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    from db.dual_store import USE_RDB_STORE
    if USE_RDB_STORE:
        try:
            from db.session import get_db_session
            from db.repo import get_latest_assignment_for_user
            with get_db_session() as session:
                rdb_res = get_latest_assignment_for_user(session, user_uuid)
                if rdb_res and rdb_res.get("ok") and rdb_res.get("log"):
                    return jsonify({
                        "ok": True,
                        "homework": rdb_res["log"],
                        "log": rdb_res["log"],
                        "student_id": user_uuid,
                        "student_name": rdb_res.get("student_name") or user_uuid,
                    })
        except Exception as e:
            print(f"[api_student_homework_latest] RDB lookup fallback: {e}")

    from utils.utils_user_doc import load_doc_by_any
    from utils.utils_common import ensure_user_cache_or_404

    # 1) UUID 문서 로드 (homework_logs + profile + oi_problems)
    doc, _ = ensure_user_cache_or_404(user_uuid)
    if not doc:
        doc = load_doc_by_any(user_uuid) or {}

    # 2) username 캐시 파일({username}.json)의 풀이 데이터를 oi_problems에 병합
    prof = doc.get("profile") or {}
    st_id = prof.get("student_id") or prof.get("username") or user_uuid
    st_name = prof.get("name") or st_id

    if st_id and st_id != user_uuid:
        from config import USER_DATA_DIR
        import os as _os
        cache_path = _os.path.join(USER_DATA_DIR, f"{st_id}.json")
        if _os.path.exists(cache_path):
            try:
                import json as _json
                cache_data = _json.load(open(cache_path, encoding="utf-8"))
                if isinstance(cache_data, dict):
                    oi = doc.get("oi_problems")
                    if not oi:
                        doc["oi_problems"] = cache_data
                    elif isinstance(oi, dict):
                        for k, v in cache_data.items():
                            if k not in oi:
                                oi[k] = v
            except Exception as _e:
                print(f"[hw_latest] cache merge failed: {_e}")

    logs = doc.get("homework_logs", [])
    try:
        logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
    except Exception:
        pass
    recent = logs[0] if logs else {}
    enriched_recent = _enrich_log_problem_status(doc, recent)

    return jsonify({
        "ok": True,
        "homework": enriched_recent,
        "log": enriched_recent,
        "student_id": st_id,
        "student_name": st_name
    })


@students_bp.post("/api/students/homework_latest_batch")
def api_students_homework_latest_batch():
    s, err = ensure_admin_or_403()
    if err:
        return err

    payload = request.get_json(force=True) or {}
    uuids = payload.get("user_uuids", [])
    result = {}

    from db.dual_store import USE_RDB_STORE
    if USE_RDB_STORE:
        try:
            from db.session import get_db_session
            from db.repo import get_latest_assignment_for_user
            with get_db_session() as session:
                for u in uuids:
                    rdb_res = get_latest_assignment_for_user(session, u)
                    if rdb_res and rdb_res.get("log"):
                        result[u] = rdb_res["log"]
                    else:
                        # RDB에 없으면 JSON fallback
                        try:
                            from utils.utils_user_doc import load_doc_by_any
                            doc = load_doc_by_any(u)
                            logs = doc.get("homework_logs", []) if doc else []
                            logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
                            recent = logs[0] if logs else {}
                            result[u] = _enrich_log_problem_status(doc, recent) if recent else {}
                        except Exception:
                            result[u] = {}
                return jsonify({"ok": True, "batch": result})
        except Exception as e:
            print(f"[api_students_homework_latest_batch] RDB batch fallback: {e}")

    from utils.utils_user_doc import load_doc_by_any
    for u in uuids:
        try:
            doc = load_doc_by_any(u)
            logs = doc.get("homework_logs", []) if doc else []
            logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
            recent = logs[0] if logs else {}
            result[u] = _enrich_log_problem_status(doc, recent) if recent else {}
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


CHOSEONG_LIST = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ',
    'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
]


def _get_choseong(text: str) -> str:
    if not text:
        return ""
    res = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            idx = (code - 0xAC00) // 588
            res.append(CHOSEONG_LIST[idx])
        else:
            res.append(char.lower())
    return "".join(res)


def _is_pure_choseong(text: str) -> bool:
    if not text:
        return False
    clean = text.replace(" ", "")
    return bool(clean) and all(ch in CHOSEONG_LIST for ch in clean)


def _calculate_student_score(name: str, display_id: str, username: str, accounts: list, q: str, is_chos: bool) -> int:
    name_lower = (name or "").lower()
    disp_lower = (display_id or "").lower()
    uname_lower = (username or "").lower()
    accs_lower = [str(a).lower() for a in accounts if a]
    q_lower = (q or "").lower()

    if is_chos:
        name_chos = _get_choseong(name)
        disp_chos = _get_choseong(display_id)
        if name_chos == q:
            return 300
        if name_chos.startswith(q):
            return 200
        if q in name_chos:
            return 100
        if disp_chos.startswith(q):
            return 80
        if q in disp_chos:
            return 50
        for acc in accs_lower:
            acc_chos = _get_choseong(acc)
            if acc_chos.startswith(q):
                return 70
            if q in acc_chos:
                return 40
        return 0

    # Direct Text search
    if name_lower == q_lower:
        return 1000
    if name_lower.startswith(q_lower):
        return 850
    if disp_lower.startswith(q_lower) or uname_lower.startswith(q_lower):
        return 750
    if any(acc.startswith(q_lower) for acc in accs_lower):
        return 700
    if q_lower in name_lower:
        return 600
    if q_lower in disp_lower or q_lower in uname_lower:
        return 400
    if any(q_lower in acc for acc in accs_lower):
        return 300
    return 0


def _format_activity_time(dt_obj, now=None) -> tuple[str, bool]:
    from datetime import datetime, timezone, timedelta
    if not dt_obj:
        return ("", False)
    if now is None:
        now = datetime.now(timezone.utc)
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    
    delta = now - dt_obj
    is_recent_active = delta < timedelta(days=3)

    if delta < timedelta(hours=1):
        minutes = max(1, int(delta.total_seconds() // 60))
        return (f"{minutes}분 전", True)
    elif delta < timedelta(hours=24):
        hours = int(delta.total_seconds() // 3600)
        return (f"{hours}시간 전", True)
    elif delta < timedelta(days=2):
        return ("어제", True)
    elif delta < timedelta(days=7):
        return (f"{delta.days}일 전", is_recent_active)
    elif delta < timedelta(days=30):
        return (f"{delta.days}일 전", False)
    elif now.year == dt_obj.year:
        return (f"{dt_obj.month}월 {dt_obj.day}일", False)
    else:
        return (f"{dt_obj.year}.{dt_obj.month}.{dt_obj.day}", False)


def _resolve_accounts_last_login_from_st(st_info: dict) -> dict:
    """
    workspace_students.json의 st_info를 받아 accounts_last_login 캐시를 우선 사용하고,
    캐시가 없는 계정만 로컬 JSON doc에서 보완하여 반환.
    """
    from utils.utils_user_doc import load_doc_by_any
    from datetime import datetime, timezone

    accounts = st_info.get("accounts", [])
    cached = st_info.get("accounts_last_login") or {}

    result = {}
    best_acc = None
    best_dt = None
    now = datetime.now(timezone.utc)

    for acc in accounts:
        acc_str = str(acc).strip()
        if not acc_str:
            continue

        candidates = []

        # 1. accounts_last_login 캐시 우선 확인 (학생 페이지 조회 시 포털 데이터에서 저장됨)
        cached_iso = cached.get(acc_str) or ""
        if cached_iso and isinstance(cached_iso, str):
            try:
                candidates.append(datetime.fromisoformat(cached_iso.replace("Z", "+00:00")))
            except Exception:
                pass

        # 2. 로컬 JSON doc 보완 (homework_logs 등)
        try:
            doc = load_doc_by_any(acc_str)
            if isinstance(doc, dict):
                prof = doc.get("profile", {})
                if isinstance(prof, dict) and prof.get("last_login"):
                    try:
                        candidates.append(datetime.fromisoformat(str(prof["last_login"]).replace("Z", "+00:00")))
                    except Exception:
                        pass

                for hw in doc.get("homework_logs", []):
                    if isinstance(hw, dict):
                        for k in ("created_at", "ts"):
                            if hw.get(k):
                                try:
                                    candidates.append(datetime.fromisoformat(str(hw[k]).replace("Z", "+00:00")))
                                except Exception:
                                    pass
        except Exception:
            pass

        acc_best_dt = None
        for dt in candidates:
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if acc_best_dt is None or dt > acc_best_dt:
                    acc_best_dt = dt

        rel_time, is_recent_time = _format_activity_time(acc_best_dt, now)
        raw_iso = acc_best_dt.isoformat() if acc_best_dt else ""

        result[acc_str] = {
            "last_login": raw_iso,
            "relative_time": rel_time,
            "is_recent_time": is_recent_time,
            "is_most_recent": False
        }

        if acc_best_dt:
            if best_dt is None or acc_best_dt > best_dt:
                best_dt = acc_best_dt
                best_acc = acc_str

    has_multiple_accounts = len([a for a in accounts if a]) > 1
    if best_acc and best_acc in result and best_dt is not None:
        if result[best_acc]["is_recent_time"] or has_multiple_accounts:
            result[best_acc]["is_most_recent"] = True

    return result


@students_bp.route("/api/students/search_suggestions", methods=["GET"])
def api_student_search_suggestions():
    q = (request.args.get("q") or "").strip()
    try:
        _sync_workspace_students()
    except Exception:
        pass
    ws_students = _load_workspace_students()
    scored_suggestions = []
    seen = set()

    is_choseong_query = _is_pure_choseong(q) if q else False

    for st_uuid, st_info in ws_students.items():
        display_id = (st_info.get("display_id") or "").strip()
        name = (st_info.get("name") or "").strip()
        username = (st_info.get("username") or "").strip()
        accounts = st_info.get("accounts", [])
        if not isinstance(accounts, list):
            accounts = [display_id] if display_id else []

        if not display_id and not name and not username and not accounts:
            continue
        
        score = 0
        if q:
            score = _calculate_student_score(name, display_id, username, accounts, q, is_choseong_query)
            if score <= 0:
                continue

        key = (display_id.lower(), name.lower(), username.lower())
        if key in seen:
            continue
        seen.add(key)
        
        student_name = name or display_id or username
        account_logins = _resolve_accounts_last_login_from_st(st_info)
        scored_suggestions.append((
            score,
            len(student_name),
            student_name,
            {
                "user_uuid": st_uuid,
                "display_id": display_id or username or name,
                "name": student_name,
                "username": username,
                "accounts": accounts,
                "account_logins": account_logins,
                "birth_md": st_info.get("birth_md", "")
            }
        ))

    # If query is provided, sort by score desc, then name length asc, then alphabetical
    if q:
        scored_suggestions.sort(key=lambda item: (-item[0], item[1], item[2]))

    suggestions = [item[3] for item in scored_suggestions]

    # On-demand live lookup if query has few matches
    if q and len(suggestions) < 3 and len(q) >= 2:
        try:
            from utils.utils_common import get_api_session, BASE_URL, resolve_uuid, format_last_login
            from utils.utils_user_doc import pull_and_store_user
            from core.storage import _parse_account_name_birth
            from urllib.parse import quote

            s = get_api_session()
            if s:
                encoded_q = quote(q)
                resp = s.get(f"{BASE_URL}/api/profile?username={encoded_q}", timeout=5)
                if resp.status_code == 200:
                    res_json = resp.json()
                    p_data = res_json.get("data", {}) if isinstance(res_json, dict) else {}
                    if isinstance(p_data, dict):
                        user_obj = p_data.get("user", {})
                        if isinstance(user_obj, dict):
                            found_uname = (user_obj.get("username") or "").strip()
                            if found_uname:
                                pull_and_store_user(found_uname)
                                found_name = user_obj.get("realname") or user_obj.get("username")
                                u_resolved = resolve_uuid(found_uname)
                                p_name, p_birth, _ = _parse_account_name_birth(found_uname)
                                
                                key = (found_uname.lower(), (found_name or "").lower(), found_uname.lower())
                                if key not in seen:
                                    seen.add(key)
                                    u_login = user_obj.get("last_login") or ""
                                    u_rel_time = format_last_login(u_login) if u_login else ""
                                    suggestions.insert(0, {
                                        "user_uuid": u_resolved,
                                        "display_id": found_uname,
                                        "name": found_name or p_name or found_uname,
                                        "username": found_uname,
                                        "accounts": [found_uname],
                                        "account_logins": {
                                            found_uname: {
                                                "last_login": u_login,
                                                "relative_time": u_rel_time,
                                                "is_most_recent": True
                                            }
                                        },
                                        "birth_md": p_birth
                                    })
        except Exception as e:
            print(f"[search_suggestions] on-demand lookup exception for {q}: {e}")

    return jsonify({"ok": True, "suggestions": suggestions})


@students_bp.route("/api/students/sync_all", methods=["POST"])
def api_students_sync_all():
    s, err = ensure_admin_or_403()
    if err:
        return err
    try:
        from services.workspace_student_service import sync_all_doingcoding_students
        res = sync_all_doingcoding_students(api_session=s)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



@students_bp.route("/api/students/mapping", methods=["GET"])
def api_get_students_mapping():
    try:
        _sync_workspace_students()
    except Exception:
        pass
    ws_students = _load_workspace_students()
    
    # Calculate unlinked accounts from uuids.json
    from core.storage import UUIDS_PATH, _save_workspace_students
    all_assigned_accounts = set()
    students_list = []
    
    for u, data in ws_students.items():
        disp = data.get("display_id") or ""
        name = data.get("name") or ""
        accs = data.get("accounts") or []
        if isinstance(accs, list):
            for a in accs:
                if a: all_assigned_accounts.add(str(a).strip().lower())
        if disp:
            all_assigned_accounts.add(disp.strip().lower())

        students_list.append({
            "user_uuid": u,
            "name": name,
            "display_id": disp,
            "birth_md": data.get("birth_md", ""),
            "accounts": accs if isinstance(accs, list) else ([disp] if disp else []),
            "status": data.get("status", "active")
        })

    # Sort students alphabetically by name
    students_list.sort(key=lambda s: s.get("name") or s.get("display_id") or "")

    unlinked_accounts = []
    try:
        if UUIDS_PATH.exists():
            uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
            for raw_acc in uuids_map.keys():
                if raw_acc.strip().lower() not in all_assigned_accounts:
                    unlinked_accounts.append(raw_acc.strip())
    except Exception as e:
        print("[api_get_students_mapping] unlinked accounts error:", e)

    # Candidate pool for smart suggestions: unlinked accounts + other single-account cards
    from services.workspace_student_service import find_suggested_subaccounts
    candidate_pool = list(unlinked_accounts)
    for st in students_list:
        st_accs = st.get("accounts", [])
        if len(st_accs) <= 1:
            disp = st.get("display_id")
            if disp and disp not in candidate_pool:
                candidate_pool.append(disp)

    # Calculate suggested accounts for each student
    for st in students_list:
        st["suggested_accounts"] = find_suggested_subaccounts(st, candidate_pool, max_suggestions=4)

    return jsonify({
        "ok": True,
        "students": students_list,
        "unlinked_accounts": sorted(unlinked_accounts)
    })


@students_bp.route("/api/students/mapping/link_subaccount", methods=["POST"])
def api_link_subaccount():
    payload = request.get_json(force=True, silent=True) or {}
    user_uuid = (payload.get("user_uuid") or "").strip()
    account_to_link = (payload.get("account") or "").strip()
    
    if not user_uuid or not account_to_link:
        return jsonify({"ok": False, "error": "user_uuid and account are required"}), 400

    ws_students = _load_workspace_students()
    if user_uuid not in ws_students:
        return jsonify({"ok": False, "error": "student not found"}), 404

    target = ws_students[user_uuid]
    accs = target.setdefault("accounts", [])
    if account_to_link not in accs:
        accs.append(account_to_link)

    # If account_to_link was previously its own standalone card, automatically remove it
    cards_to_remove = []
    for other_uuid, other_st in ws_students.items():
        if other_uuid != user_uuid:
            other_accs = other_st.get("accounts", [])
            other_disp = other_st.get("display_id", "")
            if (other_disp == account_to_link and len(other_accs) <= 1) or (other_accs == [account_to_link]):
                cards_to_remove.append(other_uuid)

    for r_uuid in cards_to_remove:
        del ws_students[r_uuid]

    from core.storage import _save_workspace_students, UUIDS_PATH
    _save_workspace_students(ws_students)

    # Sync uuids.json
    try:
        if UUIDS_PATH.exists():
            uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
            uuids_map[account_to_link] = user_uuid
            UUIDS_PATH.write_text(json.dumps(uuids_map, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("[api_link_subaccount] UUID sync error:", e)

    return jsonify({
        "ok": True,
        "student": target,
        "removed_card_uuids": cards_to_remove
    })


@students_bp.route("/api/students/mapping", methods=["POST"])
def api_update_student_mapping():
    payload = request.get_json(force=True, silent=True) or {}
    user_uuid = (payload.get("user_uuid") or "").strip()
    if not user_uuid:
        return jsonify({"ok": False, "error": "user_uuid is required"}), 400

    ws_students = _load_workspace_students()
    if user_uuid not in ws_students:
        return jsonify({"ok": False, "error": "student not found"}), 404

    target = ws_students[user_uuid]
    
    if "name" in payload:
        target["name"] = str(payload["name"]).strip()
    if "display_id" in payload and payload["display_id"]:
        target["display_id"] = str(payload["display_id"]).strip()
    if "birth_md" in payload:
        target["birth_md"] = str(payload["birth_md"]).strip()
    if "status" in payload:
        target["status"] = str(payload["status"]).strip()
    if "accounts" in payload and isinstance(payload["accounts"], list):
        # Normalize and remove duplicates while preserving order
        clean_accs = []
        for acc in payload["accounts"]:
            s_acc = str(acc).strip()
            if s_acc and s_acc not in clean_accs:
                clean_accs.append(s_acc)
        target["accounts"] = clean_accs
        if clean_accs and not target.get("display_id"):
            target["display_id"] = clean_accs[0]

        # Auto-remove standalone cards that have been merged into this student
        cards_to_remove = []
        for other_uuid, other_st in ws_students.items():
            if other_uuid != user_uuid:
                other_accs = other_st.get("accounts", [])
                other_disp = other_st.get("display_id", "")
                if (other_disp in clean_accs and len(other_accs) <= 1) or (len(other_accs) == 1 and other_accs[0] in clean_accs):
                    cards_to_remove.append(other_uuid)

        for r_uuid in cards_to_remove:
            del ws_students[r_uuid]

        # Update uuids.json mapping for all associated accounts
        try:
            from core.storage import UUIDS_PATH
            if UUIDS_PATH.exists():
                uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
                for acc in clean_accs:
                    uuids_map[acc] = user_uuid
                UUIDS_PATH.write_text(json.dumps(uuids_map, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print("[api_update_student_mapping] UUID mapping update error:", e)

    from core.storage import _save_workspace_students
    _save_workspace_students(ws_students)
    return jsonify({"ok": True, "student": target})


@students_bp.route("/api/students/mapping/new", methods=["POST"])
def api_create_student_mapping():
    payload = request.get_json(force=True, silent=True) or {}
    name = (payload.get("name") or "").strip()
    initial_account = (payload.get("display_id") or payload.get("account") or "").strip()
    
    from core.storage import _parse_account_name_birth, _save_workspace_students, UUIDS_PATH
    from uuid import uuid4

    p_name, p_birth, _ = _parse_account_name_birth(initial_account)
    final_name = name or p_name or initial_account or "신규 수강생"
    new_uuid = str(uuid4())

    ws_students = _load_workspace_students()
    accounts_list = [initial_account] if initial_account else []

    ws_students[new_uuid] = {
        "user_uuid": new_uuid,
        "name": final_name,
        "display_id": initial_account or final_name,
        "birth_md": payload.get("birth_md") or p_birth,
        "weekdays": [],
        "subjects": [],
        "accounts": accounts_list,
        "note": "",
        "status": "active"
    }

    _save_workspace_students(ws_students)

    # Sync uuids.json if initial_account provided
    if initial_account:
        try:
            if UUIDS_PATH.exists():
                uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
                uuids_map[initial_account] = new_uuid
                UUIDS_PATH.write_text(json.dumps(uuids_map, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return jsonify({"ok": True, "student": ws_students[new_uuid]})


@students_bp.route("/api/students/mapping/delete", methods=["POST"])
def api_delete_student_mapping():
    payload = request.get_json(force=True, silent=True) or {}
    user_uuid = (payload.get("user_uuid") or "").strip()
    if not user_uuid:
        return jsonify({"ok": False, "error": "user_uuid is required"}), 400

    ws_students = _load_workspace_students()
    if user_uuid in ws_students:
        target = ws_students[user_uuid]
        del ws_students[user_uuid]
        from core.storage import _save_workspace_students, UUIDS_PATH
        _save_workspace_students(ws_students)

        # Cleanup uuids.json for deleted student
        try:
            if UUIDS_PATH.exists():
                uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
                for acc in target.get("accounts", []):
                    if acc in uuids_map and uuids_map[acc] == user_uuid:
                        del uuids_map[acc]
                if user_uuid in uuids_map:
                    del uuids_map[user_uuid]
                UUIDS_PATH.write_text(json.dumps(uuids_map, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print("[api_delete_student_mapping] uuids cleanup error:", e)

        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "student not found"}), 404


@students_bp.get("/api/students/<user_uuid>/recommendations")
def api_student_recommendations(user_uuid):
    s, err = ensure_admin_or_403()
    if err:
        return err

    from db.dual_store import USE_RDB_STORE
    if USE_RDB_STORE:
        try:
            from db.session import get_db_session
            from db.repo import analyze_user_weakness, get_recommended_problems
            with get_db_session() as session:
                weak_groups = analyze_user_weakness(session, user_uuid)
                recommendations = get_recommended_problems(session, user_uuid, limit=3)
                return jsonify({
                    "ok": True,
                    "weak_groups": weak_groups,
                    "recommendations": recommendations,
                    "user_uuid": user_uuid,
                })
        except Exception as e:
            print(f"[api_student_recommendations] RDB lookup fallback: {e}")

    # RDB 미구축 시 JSON Fallback
    from utils.utils_user_doc import load_doc_by_any
    doc = load_doc_by_any(user_uuid) or {}
    hw_map = _latest_homework_status_map(doc)

    wrong_codes = [code for code, status in hw_map.items() if status == "wrong"]
    recs = []
    for code in wrong_codes[:3]:
        recs.append({
            "problem_id": None,
            "legacy_code": code,
            "server_problem_id": code,
            "title": f"오답 문항 ({code})",
            "tier": 1,
            "reason": "오답 재도전 (JSON)",
            "difficulty": 1,
        })

    return jsonify({
        "ok": True,
        "weak_groups": [],
        "recommendations": recs,
        "user_uuid": user_uuid,
    })


