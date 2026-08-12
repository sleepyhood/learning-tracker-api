import json
import os
import re
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
CUSTOM_METADATA_FILE = os.path.join(PROBLEM_DIR, "problem_custom_metadata.json")


def _load_problem_custom_metadata() -> dict:
    if os.path.exists(CUSTOM_METADATA_FILE):
        try:
            with open(CUSTOM_METADATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print("[custom_metadata] load error:", e)
    return {}


def _save_problem_custom_metadata(data: dict):
    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(CUSTOM_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _natural_sort_key(text: str):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text or '')]


def _make_canonical_key(major: str, sub: str, title: str) -> str:
    clean_t = re.sub(r'\[.*?\]', '', title or '').strip().lower()
    return f"{(major or '').strip()}:{(sub or '').strip()}:{clean_t}"


def _build_micro_registry(raw_json: dict) -> dict:
    registry = {}
    if not isinstance(raw_json, dict):
        return registry

    custom_meta = _load_problem_custom_metadata()

    # Pre-build Canonical Index for 2nd-stage matching if ID changed
    canonical_index = {}
    for c_id, c_val in custom_meta.items():
        if isinstance(c_val, dict):
            c_maj = c_val.get("major", "")
            c_sub = c_val.get("sub", "")
            c_title = c_val.get("title", "")
            if c_maj or c_sub or c_title:
                ck = _make_canonical_key(c_maj, c_sub, c_title)
                canonical_index[ck] = c_val

    dirty_custom_meta = False

    for key, value in raw_json.items():
        if not isinstance(value, dict):
            continue
        if "title" in value and ("major" in value or "concept" in value or "id" in value):
            prob_id = value.get("id") or key
            maj = value.get("major", "기타")
            sub_title = value.get("sub", "일반")
            prob_t = value.get("title", prob_id)
            concept = value.get("concept", "")
            
            c_entry = custom_meta.get(prob_id)
            if not c_entry:
                # 2nd Stage Fallback Matching via Canonical Key
                ck = _make_canonical_key(maj, sub_title, prob_t)
                c_entry = canonical_index.get(ck)
                if c_entry:
                    # Auto-link ID change: preserve metadata for newly updated ID
                    custom_meta[prob_id] = dict(c_entry)
                    custom_meta[prob_id]["id"] = prob_id
                    c_entry = custom_meta[prob_id]
                    dirty_custom_meta = True
            
            c_entry = c_entry or {}
            l_goal = c_entry.get("learning_goal") or value.get("learning_goal", "")
            
            sol_codes = c_entry.get("solution_codes") or value.get("solution_codes") or {}
            if not sol_codes and (c_entry.get("solution_code") or value.get("solution_code")):
                sol_codes = {"c": c_entry.get("solution_code") or value.get("solution_code")}

            registry[prob_id] = {
                "id": prob_id,
                "title": prob_t,
                "concept": c_entry.get("concept") or concept,
                "major": maj,
                "sub": sub_title,
                "learning_goal": l_goal,
                "solution_codes": sol_codes,
                "solution_code": sol_codes.get("c") or sol_codes.get("python") or c_entry.get("solution_code") or "",
                "tags": c_entry.get("tags") or value.get("tags") or []
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
                        
                        c_entry = custom_meta.get(prob_id)
                        if not c_entry:
                            ck = _make_canonical_key(major_ch, sub_title, prob_title)
                            c_entry = canonical_index.get(ck)
                            if c_entry:
                                custom_meta[prob_id] = dict(c_entry)
                                custom_meta[prob_id]["id"] = prob_id
                                c_entry = custom_meta[prob_id]
                                dirty_custom_meta = True

                        c_entry = c_entry or {}
                        l_goal = c_entry.get("learning_goal", "")

                        sol_codes = c_entry.get("solution_codes") or {}
                        if not sol_codes and c_entry.get("solution_code"):
                            sol_codes = {"c": c_entry.get("solution_code")}

                        registry[prob_id] = {
                            "id": prob_id,
                            "title": prob_title,
                            "concept": c_entry.get("concept") or concept,
                            "major": major_ch,
                            "sub": sub_title,
                            "learning_goal": l_goal,
                            "solution_codes": sol_codes,
                            "solution_code": sol_codes.get("c") or sol_codes.get("python") or c_entry.get("solution_code") or "",
                            "tags": c_entry.get("tags") or []
                        }

    if dirty_custom_meta:
        _save_problem_custom_metadata(custom_meta)

    # Apply Fallback Learning Goals if individual learning_goal is missing
    for prob_id, item in registry.items():
        if not item.get("learning_goal"):
            sub_t = item.get("sub")
            maj_t = item.get("major")
            if sub_t and sub_t != "일반":
                item["learning_goal_fallback"] = f"[{sub_t}] 단원 핵심 개념 및 알고리즘 풀이"
            elif maj_t and maj_t != "기타":
                item["learning_goal_fallback"] = f"[{maj_t}] 학습 문제 이해 및 구현"
            else:
                item["learning_goal_fallback"] = "코딩 문제 해결 및 로직 구현"

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
    workspace_data = _sync_workspace_students()
    raw_schedule = load_schedule()
    slots = raw_schedule.get("slots", [])
    
    # 1. Map slots by student uuid for legacy compatibility
    slot_labels_by_uuid = {}
    for slot in slots:
        label = slot.get("label", "")
        w = slot.get("weekday")
        for u_token in slot.get("students", []):
            if not u_token: continue
            if u_token not in slot_labels_by_uuid:
                slot_labels_by_uuid[u_token] = []
            if label and label not in slot_labels_by_uuid[u_token]:
                slot_labels_by_uuid[u_token].append(label)

    # 2. Name counts for Duplicate Name detection
    name_counts = {}
    for u, st in workspace_data.items():
        name = st.get("name", "").strip()
        if name:
            name_counts[name] = name_counts.get(name, 0) + 1

    name_indices = {}
    
    # Filter by weekday
    target_w = None
    if weekday_str != "all":
        try:
            target_w = int(weekday_str)
        except ValueError:
            target_w = None

    result_students = []
    
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")

    for u, st in workspace_data.items():
        st_name = st.get("name") or st.get("display_id") or "이름없음"
        
        # Determine dup_tag
        dup_tag = ""
        if name_counts.get(st_name, 0) > 1:
            idx = name_indices.get(st_name, 0) + 1
            name_indices[st_name] = idx
            dup_tag = f"#{idx}"

        st_weekdays = st.get("weekdays") or []
        legacy_labels = slot_labels_by_uuid.get(u, [])
        
        # Check weekday matching
        is_matched = True
        if target_w is not None:
            # Matched if in weekdays array OR in legacy slots for this weekday
            is_in_weekdays = target_w in st_weekdays
            is_in_legacy_slot = False
            for slot in slots:
                if slot.get("weekday") == target_w and u in slot.get("students", []):
                    is_in_legacy_slot = True
                    break
            is_matched = is_in_weekdays or is_in_legacy_slot

        if not is_matched:
            continue

        # Compute today's status badge stats
        solved_cnt = 0
        wrong_cnt = 0
        hw_cnt = 0
        try:
            doc = load_doc_by_any(u)
            logs = doc.get("homework_logs", [])
            if logs:
                latest = logs[-1]
                hw_cnt = len(latest.get("problems", []))
                for p in latest.get("problems", []):
                    st_val = p.get("status")
                    if st_val == "solved":
                        solved_cnt += 1
                    elif st_val == "wrong":
                        wrong_cnt += 1
        except Exception:
            pass

        combined_label = ", ".join(legacy_labels) if legacy_labels else ""
        
        result_students.append({
            "user_uuid": u,
            "display_id": st.get("display_id") or u,
            "name": st_name,
            "dup_tag": dup_tag,
            "birth_md": st.get("birth_md", ""),
            "weekdays": st_weekdays,
            "subjects": st.get("subjects", []),
            "slot_label": combined_label,
            "note": st.get("note", ""),
            "status": st.get("status", "active"),
            "accounts": st.get("accounts", []),
            "solved_count": solved_cnt,
            "wrong_count": wrong_cnt,
            "homework_count": hw_cnt
        })

    all_slots = [{"id": s.get("id"), "label": s.get("label"), "weekday": s.get("weekday")} for s in slots]
    return jsonify({"ok": True, "students": result_students, "all_slots": all_slots})


@workspace_bp.route("/api/workspace/register_student", methods=["POST"])
def api_workspace_register_student():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "").strip()
    birth_md = payload.get("birth_md", "").strip()
    slot_id = payload.get("slot_id")
    weekdays_input = payload.get("weekdays") or []
    subjects_input = payload.get("subjects") or []
    
    if not name:
        return jsonify({"ok": False, "error": "이름을 입력해주세요."}), 400
        
    display_id = f"{name}{birth_md}" if birth_md else name
    new_uuid = str(uuid4())
    
    workspace_data = _load_workspace_students()
    
    # Process weekdays
    weekdays_set = set()
    if isinstance(weekdays_input, list):
        for w in weekdays_input:
            try: weekdays_set.add(int(w))
            except ValueError: pass

    # If slot_id passed from legacy dropdown, find weekday
    if slot_id:
        raw = load_schedule()
        for slot in raw.get("slots", []):
            if slot.get("id") == slot_id:
                w = slot.get("weekday")
                if isinstance(w, int): weekdays_set.add(w)
                slot.setdefault("students", []).append(new_uuid)
                break
        save_schedule(raw)

    workspace_data[new_uuid] = {
        "user_uuid": new_uuid,
        "display_id": display_id,
        "name": name,
        "birth_md": birth_md,
        "weekdays": list(weekdays_set),
        "subjects": subjects_input if isinstance(subjects_input, list) else [],
        "accounts": [{"type": "academy", "label": "학원", "username": display_id}],
        "note": ""
    }
    _save_workspace_students(workspace_data)
        
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    m[display_id] = new_uuid
    m[new_uuid] = new_uuid
    UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        
    doc = load_doc_by_any(new_uuid)
    doc["profile"] = {"name": name, "student_id": display_id}
    save_doc_by_any(new_uuid, doc)
    
    return jsonify({"ok": True, "display_id": display_id, "user_uuid": new_uuid})


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


@workspace_bp.route("/api/workspace/update_student_profile", methods=["POST"])
@workspace_bp.route("/api/workspace/update_student_accounts", methods=["POST"])
def api_workspace_update_student_profile():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    user_uuid = payload.get("user_uuid") or payload.get("display_id") or ""
    user_uuid = str(user_uuid).strip()
    
    if not user_uuid:
        return jsonify({"ok": False, "error": "user_uuid 또는 display_id가 필요합니다."}), 400
        
    workspace_data = _load_workspace_students()
    student = workspace_data.get(user_uuid)
    
    # Fallback lookup by display_id if user_uuid key was legacy
    if not student:
        for u, st in workspace_data.items():
            if st.get("display_id") == user_uuid or st.get("user_uuid") == user_uuid:
                student = st
                user_uuid = u
                break
                
    if not student:
        new_uuid = str(uuid4())
        student = {
            "user_uuid": new_uuid,
            "display_id": user_uuid,
            "name": payload.get("name", user_uuid).strip(),
            "birth_md": "",
            "weekdays": [],
            "subjects": [],
            "accounts": [],
            "note": ""
        }
        workspace_data[new_uuid] = student
        user_uuid = new_uuid

    if "name" in payload and payload["name"]:
        student["name"] = payload["name"].strip()
    if "birth_md" in payload:
        student["birth_md"] = str(payload["birth_md"]).strip()
    if "weekdays" in payload and isinstance(payload["weekdays"], list):
        try:
            student["weekdays"] = [int(w) for w in payload["weekdays"]]
        except ValueError:
            pass
    if "subjects" in payload and isinstance(payload["subjects"], list):
        student["subjects"] = [str(sb).strip() for sb in payload["subjects"] if sb]
    if "note" in payload and payload["note"] is not None:
        student["note"] = str(payload["note"]).strip()
    if "status" in payload and payload["status"]:
        status_val = str(payload["status"]).strip()
        if status_val in ["active", "paused", "inactive"]:
            student["status"] = status_val
    if "accounts" in payload:
        student["accounts"] = _normalize_accounts(payload["accounts"])
    
    _save_workspace_students(workspace_data)
    
    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    m[student["display_id"]] = user_uuid
    m[user_uuid] = user_uuid
    for acc in student.get("accounts", []):
        uname = acc.get("username")
        if uname:
            m[uname] = user_uuid
    UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"ok": True, "student": student})


@workspace_bp.route("/api/workspace/delete_student", methods=["POST"])
def api_workspace_delete_student():
    s, err = ensure_admin_or_403()
    if err: return err
    
    payload = request.get_json(force=True) or {}
    req_id = (payload.get("display_id") or payload.get("user_uuid") or "").strip()
    
    if not req_id:
        return jsonify({"ok": False, "error": "display_id 또는 user_uuid가 필요합니다."}), 400
        
    workspace_data = _load_workspace_students()
    
    # 1. 수강생 및 target_uuid/key 찾기
    target_key = None
    student = None
    
    if req_id in workspace_data:
        target_key = req_id
        student = workspace_data[req_id]
    else:
        for k, v in workspace_data.items():
            if isinstance(v, dict):
                if v.get("user_uuid") == req_id or v.get("display_id") == req_id or v.get("name") == req_id:
                    target_key = k
                    student = v
                    break
                    
    if not student and not target_key:
        return jsonify({"ok": False, "error": "수강생을 찾을 수 없습니다."}), 404
        
    target_uuid = student.get("user_uuid") if student else target_key
    display_id = student.get("display_id") if student else req_id
    student_name = student.get("name") if student else req_id
    
    # 지울 식별자 집합 수집
    ids_to_remove = set(filter(None, [req_id, target_key, target_uuid, display_id, student_name]))
    if student and isinstance(student.get("accounts"), list):
        for acc in student["accounts"]:
            if isinstance(acc, dict) and acc.get("username"):
                ids_to_remove.add(acc["username"])
                
    # 2. workspace_students.json에서 삭제
    keys_to_del = [k for k, v in workspace_data.items() if k in ids_to_remove or (isinstance(v, dict) and v.get("user_uuid") in ids_to_remove)]
    for k in keys_to_del:
        del workspace_data[k]
    _save_workspace_students(workspace_data)
    
    # 3. uuids.json (UUIDS_PATH) 매핑 삭제 (자동 동기화 시 부활 방지)
    if UUIDS_PATH.exists():
        try:
            m = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
            keys_in_uuids = [k for k, v in m.items() if k in ids_to_remove or v in ids_to_remove]
            if keys_in_uuids:
                for k in keys_in_uuids:
                    del m[k]
                UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print("[delete_student] uuids cleanup error:", e)
            
    # 4. schedule.json (시간표 슬롯)에서 수강생 제거
    raw = load_schedule()
    for slot in raw.get("slots", []):
        students = slot.get("students", [])
        slot["students"] = [st for st in students if st not in ids_to_remove]
    save_schedule(raw)
    
    return jsonify({"ok": True, "deleted": display_id or target_uuid})


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
    
    custom_meta = _load_problem_custom_metadata()
    
    logs = doc.get("homework_logs", [])
    recent_hw = logs[-1] if logs else {}
    hw_list = recent_hw.get("problems", [])
    
    hw_details = []
    for p in hw_list:
        code = p.get("legacy_code") or ""
        title = p.get("title") or ""
        c_entry = custom_meta.get(code, {})
        l_goal = c_entry.get("learning_goal") or p.get("learning_goal") or ""
        goal_str = f" (학습목표: {l_goal})" if l_goal else ""
        hw_details.append(f"- [{code}] {title}{goal_str}")
        
    hw_text = "\n".join(hw_details) if hw_details else "지정된 숙제 없음"
    
    prompt = f"""다음은 {name} 학생의 오늘 학습 내용 및 부여된 숙제입니다. 학부모님께 보낼 수업 피드백 문자를 친절하고 전문적인 어조로 작성해주세요.

[학생 이름] {name}
[오늘 부여된 숙제 및 학습목표]
{hw_text}

[작성 가이드라인]
- 학생이 오늘 배운 핵심 학습목표와 문제해결 과정을 자연스럽게 칭찬하고 격려하는 멘트를 포함해주세요.
- 학부모님이 직관적으로 이해하기 쉽도록 3~4문장으로 간결하고 명확하게 작성해주세요.
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
        
    formatted_tree = {m: sorted(list(subs), key=_natural_sort_key) for m, subs in chapters_tree.items()}

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

        # Determine chapter_code
        ch_code = item.get("chapter_code") or item.get("chapter_id")
        if not ch_code and target_config and target_config.get("url"):
            url_str = target_config.get("url", "")
            match = re.search(r'doingcoding\.com/([^/?#]+)', url_str)
            if match:
                ch_code = match.group(1)
        if not ch_code:
            ch_code = "p101" if curr_key == "prog1" else ("p102" if curr_key == "prog2" else curr_key)

        results.append({
            "legacy_code": p_id,
            "title": title,
            "concept": concept,
            "major": maj,
            "sub": sub_title,
            "group_title": sub_title,
            "chapter_code": ch_code,
            "curriculum": curr_key,
            "learning_goal": item.get("learning_goal", ""),
            "learning_goal_fallback": item.get("learning_goal_fallback", ""),
            "tags": item.get("tags", []),
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


@workspace_bp.route("/api/workspace/update_problem_metadata", methods=["POST"])
def api_workspace_update_problem_metadata():
    s, err = ensure_admin_or_403()
    if err: return err

    payload = request.get_json(force=True) or {}
    custom_meta = _load_problem_custom_metadata()

    items_to_update = []
    if "prob_id" in payload or "id" in payload:
        items_to_update.append(payload)
    elif "problems" in payload and isinstance(payload["problems"], list):
        items_to_update = payload["problems"]

    if not items_to_update:
        return jsonify({"ok": False, "error": "prob_id 또는 problems 배열이 필요합니다."}), 400

    updated_count = 0
    for item in items_to_update:
        pid = str(item.get("prob_id") or item.get("id") or "").strip()
        if not pid: continue

        entry = custom_meta.setdefault(pid, {})
        entry["id"] = pid
        if "learning_goal" in item:
            entry["learning_goal"] = str(item["learning_goal"]).strip()
        if "concept" in item:
            entry["concept"] = str(item["concept"]).strip()
        if "tags" in item and isinstance(item["tags"], list):
            entry["tags"] = [str(t).strip() for t in item["tags"] if t]
        
        # Process solution_codes (dict) or solution_code (str)
        if "solution_codes" in item and isinstance(item["solution_codes"], dict):
            entry_sol = entry.setdefault("solution_codes", {})
            for lang_k, code_v in item["solution_codes"].items():
                if code_v is not None:
                    entry_sol[str(lang_k).lower().strip()] = str(code_v).strip()
        elif "solution_code" in item and item["solution_code"] is not None:
            code_str = str(item["solution_code"]).strip()
            lang_key = str(item.get("lang") or "c").lower().strip()
            entry_sol = entry.setdefault("solution_codes", {})
            entry_sol[lang_key] = code_str
            entry["solution_code"] = code_str

        updated_count += 1

    _save_problem_custom_metadata(custom_meta)
    return jsonify({"ok": True, "updated_count": updated_count, "total_custom_count": len(custom_meta)})


@workspace_bp.route("/api/workspace/export_problem_metadata")
def api_workspace_export_problem_metadata():
    s, err = ensure_admin_or_403()
    if err: return err

    curr_key = (request.args.get("curriculum") or request.args.get("curr") or "prog1").strip()
    major_filter = request.args.get("major", "all").strip()
    sub_filter = request.args.get("sub", "all").strip()

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
            except Exception:
                pass

    chapters_tree = {}
    export_list = []

    for pid, item in registry.items():
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")

        if maj not in chapters_tree:
            chapters_tree[maj] = set()
        chapters_tree[maj].add(sub_title)

        if major_filter != "all" and maj != major_filter:
            continue
        if sub_filter != "all" and sub_title != sub_filter:
            continue

        sol_codes = item.get("solution_codes") or {}
        export_list.append({
            "id": pid,
            "title": item.get("title", ""),
            "major": maj,
            "sub": sub_title,
            "concept": item.get("concept", ""),
            "learning_goal": item.get("learning_goal", ""),
            "learning_goal_fallback": item.get("learning_goal_fallback", ""),
            "solution_codes": sol_codes,
            "solution_code": item.get("solution_code", "")
        })

    formatted_tree = {m: sorted(list(subs), key=_natural_sort_key) for m, subs in chapters_tree.items()}

    return jsonify({
        "ok": True,
        "problems": export_list,
        "tree": formatted_tree,
        "total_count": len(export_list),
        "curriculum_key": curr_key
    })


@workspace_bp.route("/api/workspace/import_problem_metadata", methods=["POST"])
def api_workspace_import_problem_metadata():
    s, err = ensure_admin_or_403()
    if err: return err

    payload = request.get_json(force=True) or {}
    raw_text = payload.get("raw_text", "").strip()
    problems_arr = payload.get("problems") or []

    custom_meta = _load_problem_custom_metadata()
    updated_count = 0

    if raw_text:
        lines = raw_text.splitlines()
        for line in lines:
            line = line.strip()
            if not line: continue
            parts = line.split("\t")
            if len(parts) >= 2:
                pid = parts[0].strip()
                l_goal = parts[1].strip()
                concept = parts[2].strip() if len(parts) >= 3 else ""
                sol_c = parts[3].strip() if len(parts) >= 4 else ""
                sol_py = parts[4].strip() if len(parts) >= 5 else ""
                
                entry = custom_meta.setdefault(pid, {})
                entry["id"] = pid
                entry["learning_goal"] = l_goal
                if concept: entry["concept"] = concept
                if sol_c or sol_py:
                    entry_sol = entry.setdefault("solution_codes", {})
                    if sol_c: entry_sol["c"] = sol_c
                    if sol_py: entry_sol["python"] = sol_py
                updated_count += 1

    for item in problems_arr:
        if isinstance(item, dict):
            pid = str(item.get("id") or item.get("prob_id") or "").strip()
            if not pid: continue
            l_goal = str(item.get("learning_goal") or "").strip()
            concept = str(item.get("concept") or "").strip()
            sol_codes = item.get("solution_codes")
            
            entry = custom_meta.setdefault(pid, {})
            entry["id"] = pid
            if l_goal: entry["learning_goal"] = l_goal
            if concept: entry["concept"] = concept
            if isinstance(sol_codes, dict):
                entry["solution_codes"] = sol_codes
            elif item.get("solution_code"):
                entry.setdefault("solution_codes", {})["c"] = str(item["solution_code"]).strip()
            updated_count += 1

    _save_problem_custom_metadata(custom_meta)
    return jsonify({"ok": True, "updated_count": updated_count, "total_custom_count": len(custom_meta)})


@workspace_bp.route("/api/workspace/save_homework_log", methods=["POST"])
def api_workspace_save_homework_log():
    s, err = ensure_admin_or_403()
    if err:
        return err
    payload = request.get_json(force=True) or {}
    display_id = payload.get("display_id")
    user_uuid = payload.get("user_uuid")
    problems = payload.get("problems", [])

    if not user_uuid and display_id:
        data = _load_workspace_students()
        # 1차: display_id를 uuid 키로 직접 조회 (이전 uuid 기반 데이터 호환)
        student = data.get(display_id)
        if student:
            user_uuid = student.get("user_uuid") or display_id
        else:
            # 2차: display_id 필드 값으로 전체 순회 (계정명 기반 검색)
            for u, st in data.items():
                if st.get("display_id") == display_id:
                    user_uuid = u
                    break
        # 3차: resolve_uuid 최후 수단 (uuids.json 조회 또는 신규 생성)
        if not user_uuid:
            try:
                from utils.utils_common import resolve_uuid
                user_uuid = resolve_uuid(display_id)
            except Exception:
                user_uuid = display_id

    if not user_uuid:
        return jsonify({"ok": False, "error": "Target user_uuid or display_id is required"}), 400

    log_payload = {
        "problems": problems,
        "title": payload.get("title", ""),
        "comment": payload.get("comment", ""),
        "message": payload.get("message", ""),
        "mode": payload.get("mode", "homework" if len(problems) > 0 else "comment")
    }
    append_homework_log(user_uuid, log_payload)
    return jsonify({"ok": True})
