import json
import os
from uuid import uuid4
from flask import Blueprint, request, jsonify, render_template

from config import PROBLEM_DIR, PROBLEM_FILE
from core.storage import (
    UUIDS_PATH,
    load_schedule,
    save_schedule,
    hydrate_slot_students,
    _load_workspace_students,
    _save_workspace_students,
    _sync_workspace_students,
    append_homework_log,
)
from utils.utils_common import ensure_admin_or_403, ensure_admin_or_redirect
from utils.utils_user_doc import load_doc_by_any, save_doc_by_any

workspace_bp = Blueprint("workspace", __name__)

CURRICULUM_CONFIG_FILE = os.path.join(PROBLEM_DIR, "curriculum_config.json")


def _build_micro_registry(raw_json: dict) -> dict:
    registry = {}
    if not isinstance(raw_json, dict):
        return registry
    for key, value in raw_json.items():
        if not isinstance(value, dict):
            continue
        if "title" in value and ("major" in value or "concept" in value or "id" in value):
            prob_id = value.get("id") or key
            registry[prob_id] = {
                "id": prob_id,
                "title": value.get("title", prob_id),
                "concept": value.get("concept", ""),
                "major": value.get("major", "기타"),
                "sub": value.get("sub", "일반")
            }
        else:
            major_ch = key
            for group_id, group_data in value.items():
                if not isinstance(group_data, dict):
                    continue
                sub_title = group_data.get("title", "")
                problem_names = group_data.get("problem_names", {})
                if isinstance(problem_names, dict):
                    for prob_id, prob_title in problem_names.items():
                        concept = ""
                        if "[" in prob_title and "]" in prob_title:
                            concept = prob_title.split("[")[1].split("]")[0]
                        registry[prob_id] = {
                            "id": prob_id,
                            "title": prob_title,
                            "concept": concept,
                            "major": major_ch,
                            "sub": sub_title
                        }
    return registry


def _load_curriculum_configs() -> list:
    if os.path.exists(CURRICULUM_CONFIG_FILE):
        try:
            with open(CURRICULUM_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return [
        {"key": "prog1", "name": "💻 프로그래밍 I (기초/기본)", "url": "http://edu.doingcoding.com/p101", "file": "all_problems.json"},
        {"key": "prog2", "name": "💻 프로그래밍 II (심화)", "url": "http://edu.doingcoding.com/p102", "file": "prog2_problems.json"},
        {"key": "block", "name": "🧩 블록코딩 활동", "url": "", "file": "block_problems.json"},
        {"key": "external", "name": "📘 외부 교재 / 자격증", "url": "", "file": "external_problems.json"}
    ]


def _save_curriculum_configs(configs: list):
    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(CURRICULUM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


@workspace_bp.route("/workspace")
def workspace_page():
    s, err = ensure_admin_or_redirect()
    if err:
        return err
    return render_template("workspace_2pane.html")


@workspace_bp.route("/api/workspace/schedule_students")
def api_workspace_schedule_students():
    s, err = ensure_admin_or_403()
    if err: return err
    
    weekday_str = request.args.get("weekday", "all")
    
    raw = load_schedule()
    slots = raw.get("slots", [])
    
    if weekday_str != "all":
        try:
            target_w = int(weekday_str)
            slots = [slot for slot in slots if slot.get("weekday") == target_w]
        except ValueError:
            pass
            
    hydrated_slots = hydrate_slot_students(slots)
    workspace_data = _sync_workspace_students()
    
    result_students = []
    seen_uuids = set()
    
    for slot in hydrated_slots:
        slot_label = slot.get("label", "")
        for st in slot.get("students_detail", []):
            u = st.get("user_uuid")
            if not u: continue
            
            display_id = u
            st_name = st.get("name", "이름없음")
            
            found = False
            for w_did, w_obj in workspace_data.items():
                if w_obj.get("user_uuid") == u:
                    display_id = w_did
                    st_name = w_obj.get("name") or st_name
                    found = True
                    break
            
            if not found:
                display_id = st.get("student_id") or st_name
                workspace_data[display_id] = {
                    "display_id": display_id,
                    "name": st_name,
                    "birth_md": "",
                    "accounts": [st.get("student_id")],
                    "user_uuid": u
                }
                _save_workspace_students(workspace_data)
            
            if u not in seen_uuids:
                seen_uuids.add(u)
                result_students.append({
                    "user_uuid": u,
                    "display_id": display_id,
                    "name": st_name,
                    "slot_label": slot_label,
                    "note": st.get("note", ""),
                    "slot_id": slot.get("id"),
                    "accounts": workspace_data[display_id].get("accounts", [])
                })
            else:
                for rs in result_students:
                    if rs["user_uuid"] == u:
                        if slot_label and slot_label not in rs["slot_label"]:
                            rs["slot_label"] += f", {slot_label}"
                        if st.get("note") and st.get("note") not in rs["note"]:
                            rs["note"] += f" | {st.get('note')}"
    
    all_slots = [{"id": s.get("id"), "label": s.get("label"), "weekday": s.get("weekday")} for s in raw.get("slots", [])]
    return jsonify({"ok": True, "students": result_students, "all_slots": all_slots})


@workspace_bp.route("/api/workspace/register_student", methods=["POST"])
def api_workspace_register_student():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "").strip()
    birth_md = payload.get("birth_md", "").strip()
    slot_id = payload.get("slot_id")
    
    if not name or not slot_id:
        return jsonify({"ok": False, "error": "이름과 요일 슬롯을 선택해주세요."}), 400
        
    display_id = f"{name}{birth_md}"
    new_uuid = str(uuid4())
    
    workspace_data = _load_workspace_students()
    if display_id in workspace_data:
        new_uuid = workspace_data[display_id].get("user_uuid", new_uuid)
    else:
        workspace_data[display_id] = {
            "display_id": display_id,
            "name": name,
            "birth_md": birth_md,
            "accounts": [],
            "user_uuid": new_uuid
        }
        _save_workspace_students(workspace_data)
        
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    if display_id not in m:
        m[display_id] = new_uuid
        UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        
    doc = load_doc_by_any(new_uuid)
    doc["profile"] = {"name": name, "student_id": display_id}
    save_doc_by_any(new_uuid, doc)
    
    raw = load_schedule()
    for slot in raw.get("slots", []):
        if slot.get("id") == slot_id:
            students = slot.setdefault("students", [])
            if new_uuid not in students:
                students.append(new_uuid)
            break
    
    save_schedule(raw)
    return jsonify({"ok": True, "display_id": display_id})


def _normalize_accounts(raw_accounts):
    normalized = []
    if not isinstance(raw_accounts, list):
        return normalized
    for acc in raw_accounts:
        if isinstance(acc, dict):
            username = str(acc.get("username", "")).strip()
            if username:
                acc_type = acc.get("type", "academy")
                labels = {"academy": "학원", "scratch": "스크래치", "goorm": "구름", "etc": "기타"}
                label = acc.get("label") or labels.get(acc_type, "학원")
                normalized.append({
                    "type": acc_type,
                    "label": label,
                    "username": username
                })
        elif isinstance(acc, str) and acc.strip():
            normalized.append({
                "type": "academy",
                "label": "학원",
                "username": acc.strip()
            })
    return normalized


@workspace_bp.route("/api/workspace/update_student_accounts", methods=["POST"])
def api_workspace_update_student_accounts():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id", "").strip()
    accounts = payload.get("accounts", [])
    name = payload.get("name", "").strip()
    note = payload.get("note", "").strip()
    
    if not display_id:
        return jsonify({"ok": False, "error": "display_id가 필요합니다."}), 400
        
    workspace_data = _load_workspace_students()
    student = workspace_data.get(display_id)
    if not student:
        new_uuid = str(uuid4())
        student = {
            "display_id": display_id,
            "name": name or display_id,
            "birth_md": "",
            "accounts": [],
            "user_uuid": new_uuid
        }
        workspace_data[display_id] = student

    if name:
        student["name"] = name
    if note is not None:
        student["note"] = note
    
    norm_accs = _normalize_accounts(accounts)
    student["accounts"] = norm_accs
    
    _save_workspace_students(workspace_data)
    
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    u = student.get("user_uuid")
    if u and display_id not in m:
        m[display_id] = u
    for acc in norm_accs:
        uname = acc.get("username")
        if uname and uname not in m and u:
            m[uname] = u
    UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


    return jsonify({"ok": True, "student": student})


@workspace_bp.route("/api/workspace/delete_student", methods=["POST"])
def api_workspace_delete_student():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id", "").strip()
    
    if not display_id:
        return jsonify({"ok": False, "error": "display_id가 필요합니다."}), 400
        
    workspace_data = _load_workspace_students()
    student = workspace_data.get(display_id)
    target_uuid = student.get("user_uuid") if student else None
    
    if display_id in workspace_data:
        del workspace_data[display_id]
        _save_workspace_students(workspace_data)
        
    raw = load_schedule()
    for slot in raw.get("slots", []):
        students = slot.get("students", [])
        if target_uuid and target_uuid in students:
            slot["students"] = [st for st in students if st != target_uuid]
        elif display_id in students:
            slot["students"] = [st for st in students if st != display_id]
    save_schedule(raw)
    
    return jsonify({"ok": True, "deleted": display_id})


@workspace_bp.route("/api/workspace/generate_ai_prompt", methods=["POST"])
def api_workspace_generate_ai_prompt():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    
    workspace_data = _load_workspace_students()
    student = workspace_data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
        
    u = student.get("user_uuid") or display_id
    doc = load_doc_by_any(u)
    
    name = student.get("name", display_id)
    
    logs = doc.get("homework_logs", [])
    recent_hw = logs[-1] if logs else {}
    hw_list = recent_hw.get("problems", [])
    hw_titles = [f"[{p.get('legacy_code')}] {p.get('title')}" for p in hw_list]
    hw_text = "\n".join(hw_titles) if hw_titles else "숙제 없음"
    
    prompt = f"""다음은 {name} 학생의 오늘 학습 내용 및 숙제입니다. 학부모님께 보낼 피드백 문자를 친절하고 전문적인 어조로 작성해주세요.

[학생 이름] {name}
[오늘 부여된 숙제]
{hw_text}

[요청 사항]
- 숙제를 열심히 할 수 있도록 격려하는 멘트 포함
- 3~4문장으로 간결하게 작성
"""
    return jsonify({"ok": True, "prompt": prompt})


@workspace_bp.route("/api/workspace/student_problems/<display_id>")
def api_workspace_student_problems(display_id):
    s, err = ensure_admin_or_403()
    if err:
        return err
    data = _load_workspace_students()
    student = data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
    
    lookup_keys = set()
    u = student.get("user_uuid")
    if u: lookup_keys.add(u)
    lookup_keys.add(display_id)
    for acc in student.get("accounts", []):
        if acc: lookup_keys.add(str(acc).strip())
        
    problems = []
    seen_docs = set()
    
    for key in lookup_keys:
        try:
            doc = load_doc_by_any(key)
            doc_id = id(doc)
            if doc_id in seen_docs: continue
            seen_docs.add(doc_id)
            
            logs = doc.get("homework_logs", [])
            for log in logs:
                for p in log.get("problems", []):
                    problems.append({
                        "legacy_code": p.get("legacy_code"),
                        "title": p.get("title", "알 수 없는 문제"),
                        "status": "solved" if p.get("status") == "solved" else "partial"
                    })
        except Exception:
            pass
            
    seen = set()
    uniq_problems = []
    for p in problems:
        code = p.get("legacy_code")
        if code and code not in seen:
            seen.add(code)
            uniq_problems.append(p)

    return jsonify({"ok": True, "problems": uniq_problems})


@workspace_bp.route("/api/workspace/curriculums", methods=["GET", "POST"])
def api_workspace_curriculums():
    s, err = ensure_admin_or_403()
    if err: return err

    if request.method == "GET":
        configs = _load_curriculum_configs()
        return jsonify({"ok": True, "curriculums": configs})
    
    elif request.method == "POST":
        payload = request.get_json(force=True) or {}
        key = payload.get("key")
        url = payload.get("url")
        if not key or url is None:
            return jsonify({"ok": False, "error": "key and url required"}), 400
            
        configs = _load_curriculum_configs()
        target = None
        for c in configs:
            if c.get("key") == key:
                target = c
                break
        if not target:
            return jsonify({"ok": False, "error": f"Curriculum key {key} not found"}), 404
            
        target["url"] = url.strip()
        _save_curriculum_configs(configs)
        return jsonify({"ok": True, "curriculums": configs})


@workspace_bp.route("/api/workspace/crawl_status")
def api_workspace_crawl_status():
    s, err = ensure_admin_or_403()
    if err: return err
    
    status_file = os.path.join(PROBLEM_DIR, "crawl_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, encoding="utf-8") as f:
                return jsonify({"ok": True, "status": json.load(f)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, "status": {"is_running": False, "message": "대기 중"}})


@workspace_bp.route("/api/workspace/trigger_crawl", methods=["POST"])
def api_workspace_trigger_crawl():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    if not key:
        return jsonify({"ok": False, "error": "key is required"}), 400

    configs = _load_curriculum_configs()
    target = next((c for c in configs if c.get("key") == key), None)
    if not target:
        return jsonify({"ok": False, "error": f"Invalid key: {key}"}), 404
        
    url = target.get("url")
    if not url:
        return jsonify({"ok": False, "error": "URL이 설정되지 않았습니다."}), 400

    target_file = os.path.join(PROBLEM_DIR, target.get("file", f"{key}_problems.json"))
    status_file = os.path.join(PROBLEM_DIR, "crawl_status.json")

    def run_crawler_bg():
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump({"is_running": True, "key": key, "message": f"'{target.get('name')}' 문제 목록을 크롤링 중입니다..."}, f, ensure_ascii=False)
            
            import sys
            import subprocess
            cmd = [sys.executable, "-m", "utils.questions_crawler", "--url", url, "--output", target_file]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump({"is_running": False, "key": key, "message": "크롤링 완료!", "success": True}, f, ensure_ascii=False)
            else:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump({"is_running": False, "key": key, "message": f"크롤링 실패: {res.stderr[:200]}", "success": False}, f, ensure_ascii=False)
        except Exception as e:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump({"is_running": False, "key": key, "message": f"오류 발생: {str(e)}", "success": False}, f, ensure_ascii=False)

    import threading
    t = threading.Thread(target=run_crawler_bg, daemon=True)
    t.start()

    return jsonify({"ok": True, "message": "크롤링이 백그라운드에서 시작되었습니다."})


@workspace_bp.route("/api/workspace/batch_add_problems", methods=["POST"])
def api_workspace_batch_add_problems():
    s, err = ensure_admin_or_403()
    if err: return err

    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    major = payload.get("major", "").strip()
    sub = payload.get("sub", "").strip()
    raw_text = payload.get("raw_text", "").strip()

    if not key or not major or not sub or not raw_text:
        return jsonify({"ok": False, "error": "과정 키, 대단원, 소단원, 텍스트 입력이 모두 필요합니다."}), 400

    configs = _load_curriculum_configs()
    target = next((c for c in configs if c.get("key") == key), None)
    if not target:
        return jsonify({"ok": False, "error": f"Invalid key: {key}"}), 404

    target_file = os.path.join(PROBLEM_DIR, target.get("file", f"{key}_problems.json"))
    
    current_data = {}
    if os.path.exists(target_file):
        try:
            with open(target_file, encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            current_data = {}

    lines = raw_text.splitlines()
    added_count = 0
    
    for line in lines:
        line = line.strip()
        if not line: continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            prob_id, prob_title = parts[0].strip(), parts[1].strip()
        else:
            prob_id = parts[0].strip()
            prob_title = prob_id
            
        concept = ""
        if "[" in prob_title and "]" in prob_title:
            concept = prob_title.split("[")[1].split("]")[0]
            
        current_data[prob_id] = {
            "id": prob_id,
            "title": prob_title,
            "concept": concept,
            "major": major,
            "sub": sub
        }
        added_count += 1

    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True, "added_count": added_count, "total_count": len(current_data)})


@workspace_bp.route("/api/workspace/search_problems")
def api_workspace_search_problems():
    s, err = ensure_admin_or_403()
    if err: return err

    q = request.args.get("q", "").strip().lower()
    curr_key = (request.args.get("curriculum") or request.args.get("curr") or "prog1").strip()
    chapter_filter = request.args.get("chapter", "all").strip()
    sub_filter = request.args.get("sub", "all").strip()
    display_id = request.args.get("display_id", "").strip()
    limit = int(request.args.get("limit", 80))

    configs = _load_curriculum_configs()
    target_config = next((c for c in configs if c.get("key") == curr_key), None)
    
    registry = {}
    if target_config:
        target_file = os.path.join(PROBLEM_DIR, target_config.get("file", f"{curr_key}_problems.json"))
        if os.path.exists(target_file):
            try:
                with open(target_file, encoding="utf-8") as f:
                    raw_json = json.load(f)
                    registry = _build_micro_registry(raw_json)
            except Exception as e:
                print(f"[search_problems] error loading {target_file}:", e)

    solved_set = set()
    wrong_set = set()
    
    if display_id:
        workspace_data = _load_workspace_students()
        student = workspace_data.get(display_id)
        if student:
            lookup_keys = set()
            u = student.get("user_uuid")
            if u: lookup_keys.add(u)
            lookup_keys.add(display_id)
            for acc in student.get("accounts", []):
                if acc: lookup_keys.add(str(acc).strip())
                
            for key in lookup_keys:
                try:
                    doc = load_doc_by_any(key)
                    for log in doc.get("homework_logs", []):
                        for p in log.get("problems", []):
                            code = p.get("legacy_code")
                            if code:
                                status = p.get("status", "solved")
                                if status == "solved":
                                    solved_set.add(code)
                                else:
                                    wrong_set.add(code)
                except Exception:
                    pass

    chapters_tree = {}
    for p_id, item in registry.items():
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")
        if maj not in chapters_tree:
            chapters_tree[maj] = set()
        chapters_tree[maj].add(sub_title)
        
    formatted_tree = {m: sorted(list(subs)) for m, subs in chapters_tree.items()}

    results = []
    for p_id, item in registry.items():
        title = item.get("title", "")
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")
        concept = item.get("concept", "")

        if chapter_filter != "all" and maj != chapter_filter:
            continue
        if sub_filter != "all" and sub_title != sub_filter:
            continue

        if q and q != "all":
            match_q = (q in p_id.lower()) or (q in title.lower()) or (q in maj.lower()) or (q in sub_title.lower()) or (q in concept.lower())
            if not match_q:
                continue

        status = "normal"
        if p_id in solved_set:
            status = "solved"
        elif p_id in wrong_set:
            status = "wrong"

        results.append({
            "legacy_code": p_id,
            "title": title,
            "concept": concept,
            "major": maj,
            "sub": sub_title,
            "status": status
        })
        
        if len(results) >= limit:
            break

    return jsonify({
        "ok": True,
        "problems": results,
        "tree": formatted_tree,
        "total_count": len(registry)
    })


@workspace_bp.route("/api/workspace/save_homework_log", methods=["POST"])
def api_workspace_save_homework_log():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    problems = payload.get("problems", [])
    
    data = _load_workspace_students()
    student = data.get(display_id)
    if not student:
        return jsonify({"ok": False, "error": "Student not found"}), 404
        
    u = student.get("user_uuid") or display_id
    append_homework_log(u, {"problems": problems})
    return jsonify({"ok": True})
