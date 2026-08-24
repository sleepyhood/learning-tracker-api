"""
services/workspace_student_service.py

학생(수강생) 관련 순수 비즈니스 로직 계층.
HTTP 요청/응답에 의존하지 않으며, 라우트 핸들러에서 호출됩니다.

담당 기능:
  - 학생 목록 조회 및 스케줄 매핑 연산
  - 학생 계정 정보 정규화 (_normalize_accounts)
  - 학생 프로필/계정 업데이트
  - 학생 삭제 (workspace + uuids + schedule 동기화)
  - 학생 숙제 이력 조회 (student_problems)
"""

import json
from uuid import uuid4

from core.storage import (
    UUIDS_PATH,
    load_schedule,
    save_schedule,
    _load_workspace_students,
    _save_workspace_students,
    _sync_workspace_students,
    append_homework_log,
)
from utils.utils_user_doc import load_doc_by_any, save_doc_by_any


# ─────────────────────────────────────────
# 학생 목록 조회 (스케줄 매핑 포함)
# ─────────────────────────────────────────

def get_schedule_students(weekday_str: str) -> tuple[list, list]:
    """
    workspace_students.json과 schedule.json을 결합하여
    학생 목록과 슬롯 목록을 반환합니다.

    Args:
        weekday_str: 'all' 또는 요일 숫자 문자열 (e.g. '1')

    Returns:
        (result_students, all_slots)
    """
    from datetime import datetime

    workspace_data = _sync_workspace_students()
    raw_schedule = load_schedule()
    slots = raw_schedule.get("slots", [])

    # 슬롯별 uuid → 레이블 매핑
    slot_labels_by_uuid: dict[str, list] = {}
    for slot in slots:
        label = slot.get("label", "")
        for u_token in slot.get("students", []):
            if not u_token:
                continue
            if u_token not in slot_labels_by_uuid:
                slot_labels_by_uuid[u_token] = []
            if label and label not in slot_labels_by_uuid[u_token]:
                slot_labels_by_uuid[u_token].append(label)

    # 이름 중복 카운트
    name_counts: dict[str, int] = {}
    for u, st in workspace_data.items():
        name = st.get("name", "").strip()
        if name:
            name_counts[name] = name_counts.get(name, 0) + 1

    name_indices: dict[str, int] = {}

    # 요일 필터
    target_w = None
    if weekday_str != "all":
        try:
            target_w = int(weekday_str)
        except ValueError:
            target_w = None

    result_students = []

    for u, st in workspace_data.items():
        st_name = st.get("name") or st.get("display_id") or "이름없음"

        dup_tag = ""
        if name_counts.get(st_name, 0) > 1:
            idx = name_indices.get(st_name, 0) + 1
            name_indices[st_name] = idx
            dup_tag = f"#{idx}"

        st_weekdays = st.get("weekdays") or []
        legacy_labels = slot_labels_by_uuid.get(u, [])

        is_matched = True
        if target_w is not None:
            is_in_weekdays = target_w in st_weekdays
            is_in_legacy_slot = any(
                slot.get("weekday") == target_w and u in slot.get("students", [])
                for slot in slots
            )
            is_matched = is_in_weekdays or is_in_legacy_slot

        if not is_matched:
            continue

        # 오늘 숙제 현황 집계
        solved_cnt = wrong_cnt = hw_cnt = 0
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
            "homework_count": hw_cnt,
        })

    all_slots = [
        {"id": s.get("id"), "label": s.get("label"), "weekday": s.get("weekday")}
        for s in slots
    ]
    return result_students, all_slots


# ─────────────────────────────────────────
# 학생 등록
# ─────────────────────────────────────────

def register_student(
    name: str,
    birth_md: str,
    slot_id: str | None,
    weekdays_input: list,
    subjects_input: list,
) -> dict:
    """
    신규 학생을 등록하고 workspace/uuids/doc에 반영합니다.

    Returns:
        {"display_id": ..., "user_uuid": ...}
    """
    display_id = f"{name}{birth_md}" if birth_md else name
    new_uuid = str(uuid4())

    workspace_data = _load_workspace_students()

    weekdays_set: set[int] = set()
    if isinstance(weekdays_input, list):
        for w in weekdays_input:
            try:
                weekdays_set.add(int(w))
            except ValueError:
                pass

    if slot_id:
        raw = load_schedule()
        for slot in raw.get("slots", []):
            if slot.get("id") == slot_id:
                w = slot.get("weekday")
                if isinstance(w, int):
                    weekdays_set.add(w)
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
        "note": "",
    }
    _save_workspace_students(workspace_data)

    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    m[display_id] = new_uuid
    m[new_uuid] = new_uuid
    UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    doc = load_doc_by_any(new_uuid)
    doc["profile"] = {"name": name, "student_id": display_id}
    save_doc_by_any(new_uuid, doc)

    return {"display_id": display_id, "user_uuid": new_uuid}


# ─────────────────────────────────────────
# 계정 정보 정규화
# ─────────────────────────────────────────

def normalize_accounts(raw_accounts) -> list:
    """계정 목록을 표준 형식({type, label, username})으로 정규화합니다."""
    normalized = []
    if not isinstance(raw_accounts, list):
        return normalized
    labels = {"academy": "학원", "scratch": "스크래치", "goorm": "구름", "etc": "기타"}
    for acc in raw_accounts:
        if isinstance(acc, dict):
            username = str(acc.get("username", "")).strip()
            if username:
                acc_type = acc.get("type", "academy")
                label = acc.get("label") or labels.get(acc_type, "학원")
                normalized.append({"type": acc_type, "label": label, "username": username})
        elif isinstance(acc, str) and acc.strip():
            normalized.append({"type": "academy", "label": "학원", "username": acc.strip()})
    return normalized


# ─────────────────────────────────────────
# 학생 프로필/계정 업데이트
# ─────────────────────────────────────────

def update_student_profile(user_uuid_or_display: str, payload: dict) -> dict:
    """
    학생 프로필 및 계정 정보를 업데이트합니다.
    user_uuid_or_display에 uuid 또는 display_id를 전달할 수 있습니다.

    Returns:
        업데이트된 student dict
    """
    workspace_data = _load_workspace_students()
    student = workspace_data.get(user_uuid_or_display)
    user_uuid = user_uuid_or_display

    if not student:
        for u, st in workspace_data.items():
            if st.get("display_id") == user_uuid_or_display or st.get("user_uuid") == user_uuid_or_display:
                student = st
                user_uuid = u
                break

    if not student:
        new_uuid = str(uuid4())
        student = {
            "user_uuid": new_uuid,
            "display_id": user_uuid_or_display,
            "name": payload.get("name", user_uuid_or_display).strip(),
            "birth_md": "",
            "weekdays": [],
            "subjects": [],
            "accounts": [],
            "note": "",
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
        student["accounts"] = normalize_accounts(payload["accounts"])

    _save_workspace_students(workspace_data)

    m = json.loads(UUIDS_PATH.read_text(encoding="utf-8")) if UUIDS_PATH.exists() else {}
    m[student["display_id"]] = user_uuid
    m[user_uuid] = user_uuid
    for acc in student.get("accounts", []):
        uname = acc.get("username")
        if uname:
            m[uname] = user_uuid
    UUIDS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    return student


# ─────────────────────────────────────────
# 학생 삭제
# ─────────────────────────────────────────

def delete_student(req_id: str) -> str:
    """
    학생을 workspace/uuids/schedule에서 모두 삭제합니다.

    Returns:
        삭제된 학생의 display_id 또는 uuid

    Raises:
        KeyError: 학생을 찾을 수 없을 때
    """
    workspace_data = _load_workspace_students()

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
        raise KeyError("수강생을 찾을 수 없습니다.")

    target_uuid = student.get("user_uuid") if student else target_key
    display_id = student.get("display_id") if student else req_id
    student_name = student.get("name") if student else req_id

    ids_to_remove = set(filter(None, [req_id, target_key, target_uuid, display_id, student_name]))
    if student and isinstance(student.get("accounts"), list):
        for acc in student["accounts"]:
            if isinstance(acc, dict) and acc.get("username"):
                ids_to_remove.add(acc["username"])

    keys_to_del = [
        k for k, v in workspace_data.items()
        if k in ids_to_remove or (isinstance(v, dict) and v.get("user_uuid") in ids_to_remove)
    ]
    for k in keys_to_del:
        del workspace_data[k]
    _save_workspace_students(workspace_data)

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

    raw = load_schedule()
    for slot in raw.get("slots", []):
        students = slot.get("students", [])
        slot["students"] = [st for st in students if st not in ids_to_remove]
    save_schedule(raw)

    return display_id or target_uuid


# ─────────────────────────────────────────
# 학생 풀었던 문제 목록 조회
# ─────────────────────────────────────────

def get_student_problems(display_id: str) -> list:
    """
    학생 식별자로 학생의 숙제 이력에서 고유 문제 목록을 추출합니다.

    Returns:
        [{legacy_code, title, status}, ...] (중복 제거)

    Raises:
        KeyError: 학생을 찾을 수 없을 때
    """
    data = _load_workspace_students()
    student = data.get(display_id)
    if not student:
        raise KeyError("Student not found")

    lookup_keys = set()
    u = student.get("user_uuid")
    if u:
        lookup_keys.add(u)
    lookup_keys.add(display_id)
    for acc in student.get("accounts", []):
        if acc:
            lookup_keys.add(str(acc).strip())

    problems = []
    seen_docs: set[int] = set()

    for key in lookup_keys:
        try:
            doc = load_doc_by_any(key)
            doc_id = id(doc)
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            for log in doc.get("homework_logs", []):
                for p in log.get("problems", []):
                    problems.append({
                        "legacy_code": p.get("legacy_code"),
                        "title": p.get("title", "알 수 없는 문제"),
                        "status": "solved" if p.get("status") == "solved" else "partial",
                    })
        except Exception:
            pass

    seen: set[str] = set()
    uniq_problems = []
    for p in problems:
        code = p.get("legacy_code")
        if code and code not in seen:
            seen.add(code)
            uniq_problems.append(p)

    return uniq_problems


# ─────────────────────────────────────────
# 학생 문제 이력에서 solved/wrong set 수집
# ─────────────────────────────────────────

def get_student_solved_sets(display_id: str, workspace_data: dict) -> tuple[set, set]:
    """
    특정 학생의 숙제 이력 전체에서 solved/wrong 문제 코드 집합을 반환합니다.

    Returns:
        (solved_set, wrong_set)
    """
    student = workspace_data.get(display_id)
    if not student:
        return set(), set()

    lookup_keys = set()
    u = student.get("user_uuid")
    if u:
        lookup_keys.add(u)
    lookup_keys.add(display_id)
    for acc in student.get("accounts", []):
        if acc:
            lookup_keys.add(str(acc).strip())

    solved_set: set[str] = set()
    wrong_set: set[str] = set()

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

    return solved_set, wrong_set


# ─────────────────────────────────────────
# 숙제 이력 저장
# ─────────────────────────────────────────

def save_homework_log(display_id: str | None, user_uuid: str | None, log_payload: dict):
    """
    학생 uuid를 resolve하고 숙제 이력을 append합니다.

    Raises:
        ValueError: user_uuid/display_id 모두 없을 때
    """
    if not user_uuid and display_id:
        data = _load_workspace_students()
        student = data.get(display_id)
        if student:
            user_uuid = student.get("user_uuid") or display_id
        else:
            for u, st in data.items():
                if st.get("display_id") == display_id:
                    user_uuid = u
                    break
        if not user_uuid:
            try:
                from utils.utils_common import resolve_uuid
                user_uuid = resolve_uuid(display_id)
            except Exception:
                user_uuid = display_id

    if not user_uuid:
        raise ValueError("Target user_uuid or display_id is required")

    append_homework_log(user_uuid, log_payload)


# ─────────────────────────────────────────
# 두잉코딩 전체 학생 계정 자동 동기화
# ─────────────────────────────────────────

def sync_all_doingcoding_students(api_session=None, limit: int = 200) -> dict:
    """
    두잉코딩 /api/user_rank 를 순회하여 전체 학생 계정을 조회하고,
    uuids.json 및 workspace_students.json에 자동 등록/동기화합니다.
    """
    import re
    from utils.utils_common import get_api_session, BASE_URL
    from core.storage import _parse_account_name_birth
    
    session = api_session or get_api_session()
    if not session:
        print("[sync_all_doingcoding_students] No valid API session")
        return {"ok": False, "error": "No valid session"}

    workspace_data = _load_workspace_students()
    
    try:
        uuids_map = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
    except Exception:
        uuids_map = {}

    import time
    offset = 0
    total_fetched = 0
    new_added = 0
    
    while True:
        url = f"{BASE_URL}/api/user_rank?limit={limit}&offset={offset}"
        resp = None
        for retry in range(3):
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 200:
                    break
                time.sleep(1)
            except Exception as req_err:
                print(f"[sync_all_doingcoding_students] Retry {retry+1}/3 failed for offset {offset}: {req_err}")
                time.sleep(1.5)

        if not resp or resp.status_code != 200:
            print(f"[sync_all_doingcoding_students] Error or failed to fetch at offset {offset}")
            break

        try:
            res_json = resp.json()
            if res_json.get("error"):
                print(f"[sync_all_doingcoding_students] API error: {res_json.get('error')}")
                break
            
            data_obj = res_json.get("data", {})
            results = data_obj.get("results", [])
            total = data_obj.get("total", 0)
            
            if not results:
                break
                
            for item in results:
                user_info = item.get("user", {})
                username = (user_info.get("username") or "").strip()
                if not username:
                    continue
                
                real_name = (item.get("real_name") or "").strip()
                total_fetched += 1
                
                # UUID 발급/조회
                if username in uuids_map:
                    u = uuids_map[username]
                else:
                    u = str(uuid4())
                    uuids_map[username] = u
                    new_added += 1
                
                p_name, p_birth, is_std = _parse_account_name_birth(username)
                final_name = real_name or p_name or username
                
                if u not in workspace_data:
                    workspace_data[u] = {
                        "user_uuid": u,
                        "display_id": username,
                        "name": final_name,
                        "birth_md": p_birth,
                        "weekdays": [],
                        "subjects": [],
                        "accounts": [username],
                        "note": "",
                        "status": "active"
                    }
                else:
                    st = workspace_data[u]
                    st.setdefault("display_id", username)
                    if real_name:
                        st["name"] = real_name
                    elif not st.get("name") or st.get("name") == username:
                        st["name"] = final_name
                    if p_birth and not st.get("birth_md"):
                        st["birth_md"] = p_birth
                    accs = st.setdefault("accounts", [])
                    if username not in accs:
                        accs.append(username)

            offset += len(results)
            if offset >= total or len(results) < limit:
                break

            time.sleep(0.15)
                
        except Exception as e:
            print(f"[sync_all_doingcoding_students] Exception at offset {offset}: {e}")
            break

    # Clean UUIDs map (remove keys that are UUIDs themselves)
    uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    cleaned_uuids = {}
    for k, v in uuids_map.items():
        if uuid_pattern.match(k):
            continue
        cleaned_uuids[k] = v

    try:
        UUIDS_PATH.write_text(json.dumps(cleaned_uuids, ensure_ascii=False, indent=2), encoding="utf-8")
        _save_workspace_students(workspace_data)
    except Exception as e:
        print(f"[sync_all_doingcoding_students] Save error: {e}")

    print(f"[sync_all_doingcoding_students] Complete! Fetched: {total_fetched}, New: {new_added}, Total registered: {len(workspace_data)}")
    return {
        "ok": True,
        "total_fetched": total_fetched,
        "new_added": new_added,
        "total_students": len(workspace_data)
    }


# ─────────────────────────────────────────
# 스마트 유사 계정(부계정) 추천 알고리즘
# ─────────────────────────────────────────

def find_suggested_subaccounts(student: dict, candidate_accounts: list[str], max_suggestions: int = 4) -> list[str]:
    """
    주어진 학생의 이름, 생년월일, 대표 아이디를 기반으로
    후보 계정 목록에서 높은 확률로 동일 인물인 유사 계정을 자동 추천합니다.
    """
    import re
    from core.storage import _parse_account_name_birth

    if not isinstance(student, dict):
        return []

    name = (student.get("name") or "").strip()
    birth_md = (student.get("birth_md") or "").strip()
    display_id = (student.get("display_id") or "").strip()
    
    current_accs = {str(a).strip().lower() for a in student.get("accounts", []) if a}
    if display_id:
        current_accs.add(display_id.lower())

    if not name or name == display_id:
        p_name, p_birth, _ = _parse_account_name_birth(display_id)
        name = p_name or name
        if not birth_md:
            birth_md = p_birth

    if not name or len(name) < 2:
        return []

    name_lower = name.lower()
    reverse_pattern = f"{birth_md}{name_lower}" if birth_md else ""

    suggestions = []
    seen = set()

    for cand in candidate_accounts:
        if not cand:
            continue
        c_str = str(cand).strip()
        c_lower = c_str.lower()

        if c_lower in current_accs or c_lower in seen:
            continue

        c_name, c_birth, is_std = _parse_account_name_birth(c_str)
        c_name_lower = c_name.lower()

        is_match = False
        priority = 0

        # 1. 역순 패턴 완전 일치 (예: 강동현1103 ↔ 1103강동현)
        if reverse_pattern and c_lower == reverse_pattern:
            is_match = True
            priority = 100
        # 2. 동일 실명 + 표준 ID 패턴 (예: 강동현1103 ↔ 강동현1105)
        elif is_std and c_name_lower == name_lower:
            is_match = True
            priority = 90 if (birth_md and c_birth == birth_md) else 75
        # 3. 동일 실명으로 시작하거나 끝나는 변형 (예: 신승현1222_2, 강동현_sub)
        elif c_lower.startswith(name_lower) or c_lower.endswith(name_lower):
            is_match = True
            priority = 80
        # 4. 생년월일 접두 + 이름 포함 (예: 1103_강동현)
        elif birth_md and c_lower.startswith(birth_md) and name_lower in c_lower:
            is_match = True
            priority = 85

        if is_match:
            seen.add(c_lower)
            suggestions.append((priority, c_str))

    suggestions.sort(key=lambda x: -x[0])
    return [item[1] for item in suggestions[:max_suggestions]]


