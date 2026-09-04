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

# ─────────────────────────────────────────
# 당일 학생 요약 (구글 문서 사이드바 OJ 탭 전용)
# ─────────────────────────────────────────

def get_student_today_summary(
    display_id: str | None = None,
    user_uuid: str | None = None,
    portal_id: str | None = None,
    name: str | None = None,
    date_str: str | None = None,
) -> dict:
    """
    구글 문서 사이드바(OJ 피드백 탭)가 단일 GET 요청으로 학생의 당일 요약을
    가져갈 수 있도록 조회합니다.

    탐색 우선순위:
        1. user_uuid
        2. portal_id (meta/portal_mapping.json 및 workspace_students.json 탐색)
        3. display_id (workspace_students.json 및 uuids.json 탐색)
        4. name (실명 정확 일치 / 접두사 / 부분 일치 스마트 탐색 및 1회 자동 매핑 저장)

    Returns:
        {
            "ok": True,
            "student_name": str,
            "display_id": str,
            "user_uuid": str,
            "portal_id": str,
            "date": str,                   # 'YYYY-MM-DD'
            "solved_problems": [...],      # 오늘 정답 처리된 OJ 제출 기록
            "wrong_problems": [...],       # 오늘 오답/부분 점수 OJ 제출 기록
            "homework_problems": [...],    # 오늘 지정된 숙제 문항 목록
            "teacher_memo": str,
            "mode": str,                   # 'homework' | 'review' | 'comment'
        }

    Raises:
        KeyError: 학생을 찾을 수 없을 때
    """
    from datetime import datetime, timezone, timedelta
    from core.storage import META_DIR

    KST = timezone(timedelta(hours=9))
    today = date_str or datetime.now(tz=KST).strftime("%Y-%m-%d")

    workspace_data = _load_workspace_students()

    # ─── portal_mapping.json 로드 ──────────────────────────────────────────
    portal_mapping_file = META_DIR / "portal_mapping.json"
    portal_mappings = {}
    if portal_mapping_file.exists():
        try:
            m_data = json.loads(portal_mapping_file.read_text(encoding="utf-8"))
            portal_mappings = m_data.get("mappings", {})
        except Exception:
            pass

    # ─── 학생 resolve ───────────────────────────────────────────────────────
    student_entry: dict | None = None
    resolved_uuid: str | None = None
    resolved_display_id: str | None = None

    # 1순위: user_uuid 직접 매핑
    if user_uuid:
        for u, st in workspace_data.items():
            if u == user_uuid or st.get("user_uuid") == user_uuid:
                student_entry = st
                resolved_uuid = u
                resolved_display_id = st.get("display_id") or u
                break

    # 2순위: portal_id로 portal_mapping.json 조회
    if not student_entry and portal_id:
        pid_str = str(portal_id).strip()
        saved_map = portal_mappings.get(pid_str)
        if saved_map:
            target_uuid = saved_map.get("oj_uuid")
            if target_uuid and target_uuid in workspace_data:
                student_entry = workspace_data[target_uuid]
                resolved_uuid = target_uuid
                resolved_display_id = student_entry.get("display_id") or saved_map.get("oj_display_id") or target_uuid

    # 3순위: workspace_students.json 내 portal_id 필드 매핑
    if not student_entry and portal_id:
        pid_str = str(portal_id).strip()
        for u, st in workspace_data.items():
            if str(st.get("portal_id", "")).strip() == pid_str:
                student_entry = st
                resolved_uuid = u
                resolved_display_id = st.get("display_id") or u
                break

    # 4순위: display_id 매핑
    if not student_entry and display_id:
        for u, st in workspace_data.items():
            if st.get("display_id") == display_id or u == display_id:
                student_entry = st
                resolved_uuid = u
                resolved_display_id = st.get("display_id") or u
                break

    # 5순위: name (실명) 기반 스마트 매칭 (예: '서율', '이서율', '김민준')
    query_name = (name or display_id or "").strip()
    if not student_entry and query_name:
        # 5-1. 정확 일치 (name == query_name)
        for u, st in workspace_data.items():
            st_name = (st.get("name") or "").strip()
            if st_name and st_name == query_name:
                student_entry = st
                resolved_uuid = u
                resolved_display_id = st.get("display_id") or u
                break

        # 5-2. display_id가 query_name으로 시작 (예: '김윤성' ➔ '김윤성1113')
        if not student_entry:
            for u, st in workspace_data.items():
                st_disp = (st.get("display_id") or "").strip()
                if st_disp and st_disp.startswith(query_name):
                    student_entry = st
                    resolved_uuid = u
                    resolved_display_id = st_disp
                    break

        # 5-3. query_name이 st_name에 포함되거나 st_name이 query_name에 포함 (예: '서율' in '이서율')
        if not student_entry and len(query_name) >= 2:
            for u, st in workspace_data.items():
                st_name = (st.get("name") or "").strip()
                st_disp = (st.get("display_id") or "").strip()
                if (st_name and (query_name in st_name or st_name in query_name)) or (query_name in st_disp):
                    student_entry = st
                    resolved_uuid = u
                    resolved_display_id = st_disp or st_name
                    break

        # 매칭 성공 & portal_id가 있으면 portal_mapping.json에 자동 등록
        if student_entry and portal_id:
            try:
                pid_str = str(portal_id).strip()
                portal_mappings[pid_str] = {
                    "student_name": student_entry.get("name") or query_name,
                    "type": "OJ",
                    "oj_uuid": resolved_uuid,
                    "oj_display_id": resolved_display_id,
                    "note": "auto_mapped",
                    "updated_at": today
                }
                portal_mapping_file.write_text(
                    json.dumps({"mappings": portal_mappings}, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                print(f"[portal_mapping] 자동 저장 실패: {e}")

    if not student_entry:
        raise KeyError(f"Student not found (name={name}, display_id={display_id}, uuid={user_uuid}, portal_id={portal_id})")

    student_name = student_entry.get("name") or name or resolved_display_id or "학생"
    resolved_portal_id = str(portal_id or student_entry.get("portal_id", "")).strip()

    # ─── 유저 doc 로드 ──────────────────────────────────────────────────────
    doc = load_doc_by_any(resolved_uuid)

    # ─── 당일 homework_log 추출 ─────────────────────────────────────────────
    logs = doc.get("homework_logs") or []
    try:
        logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
    except Exception:
        pass

    today_logs = [lg for lg in logs if str(lg.get("created_at") or lg.get("ts") or "").startswith(today)]
    latest_log = today_logs[0] if today_logs else {}

    # ─── 문제 & 챕터 메타데이터 매핑 딕셔너리 로드 ──────────────────────────
    from config import PROBLEM_DIR
    import os, urllib.parse
    title_map = {}
    prob_meta_map = {}
    prob_file = os.path.join(PROBLEM_DIR, "all_problems.json")
    if os.path.exists(prob_file):
        try:
            with open(prob_file, encoding="utf-8") as f:
                _p_data = json.load(f)
                if isinstance(_p_data, dict) and _p_data.get("_schema_version") == 2:
                    _groups = _p_data.get("groups", {})
                    for _pid, _pinfo in _p_data.get("problems", {}).items():
                        _t = _pinfo.get("title", "")
                        title_map[str(_pid)] = _t
                        title_map[str(_pid).lower()] = _t

                        _gid = _pinfo.get("group_id")
                        _g = _groups.get(_gid, {}) if _gid else {}
                        _g_title = _g.get("title") or _pinfo.get("chapter_id") or "코딩 실습 및 숙제"
                        _c_code = _g.get("chapter_code") or "p101"
                        _clean_tag = str(_g_title).strip()
                        _url = f"http://edu.doingcoding.com/{_c_code}?tag={urllib.parse.quote(_clean_tag)}" if _c_code else "http://edu.doingcoding.com"

                        _meta_entry = {
                            "title": _t,
                            "chapter_code": _c_code,
                            "group_title": _g_title,
                            "url": _url,
                        }
                        prob_meta_map[str(_pid)] = _meta_entry
                        prob_meta_map[str(_pid).lower()] = _meta_entry
        except Exception:
            pass

    homework_problems: list[dict] = []
    teacher_memo: str = ""
    mode: str = "comment"

    if latest_log:
        mode = latest_log.get("mode") or ("homework" if latest_log.get("problems") else "comment")
        teacher_memo = latest_log.get("teacher_memo") or ""
        for p in (latest_log.get("problems") or []):
            l_code = p.get("legacy_code") or ""
            p_meta = prob_meta_map.get(str(l_code)) or prob_meta_map.get(str(l_code).lower()) or {}
            p_title = p.get("title") or p_meta.get("title") or title_map.get(str(l_code)) or l_code
            homework_problems.append({
                "legacy_code": l_code,
                "title": p_title,
                "chapter_code": p_meta.get("chapter_code") or "p101",
                "group_title": p_meta.get("group_title") or "코딩 실습 및 숙제",
                "url": p_meta.get("url") or "http://edu.doingcoding.com",
                "server_problem_id": p.get("server_problem_id") or None,
            })

    # ─── 당일 OJ 제출 이력 & 디버깅 코드 스니펫 추출 ─────────────────────────
    solved_problems: list[dict] = []
    wrong_problems: list[dict] = []
    debugging_snippets: list[dict] = []

    def _clean_code_snippet(code_text: str, max_chars: int = 150) -> str:
        if not code_text:
            return ""
        lines = [line.rstrip() for line in code_text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        if len(cleaned) > max_chars:
            return cleaned[:max_chars].rstrip() + "\n..."
        return cleaned

    raw_submissions: list[dict] = []
    api_session = None

    # ─── 후보 계정 목록 수집 (본계정 + accounts에 등록된 부계정들) ───────────
    _base_start = ([resolved_display_id] if resolved_display_id else [])
    _base_extra = [str(a) for a in (student_entry.get("accounts") or []) if a] if student_entry else []
    base_accounts: list[str] = list(dict.fromkeys(_base_start + _base_extra))

    # accounts_last_login 캐시 로드
    acc_last_login: dict[str, str] = {}
    if student_entry:
        acc_last_login = student_entry.get("accounts_last_login") or {}

    # ─── OJ 세션 초기화 ──────────────────────────────────────────────────────
    try:
        from utils.utils_common import get_api_session, fetch_submissions_window
        api_session = get_api_session()
    except Exception as e:
        print(f"[get_student_today_summary] OJ 세션 초기화 예외: {e}")

    # ─── 각 후보 계정별 당일 제출 스캔 ─────────────────────────────────────
    # acc → list[raw_submission] 매핑
    acc_subs_map: dict[str, list[dict]] = {}

    for acc in base_accounts:
        if not acc or not api_session:
            acc_subs_map[acc] = []
            continue
        try:
            raw_subs = fetch_submissions_window(api_session, acc, 0, days=1)
            today_subs = []
            for rec in raw_subs:
                ct = str(rec.get("create_time") or "")
                ct_kst = ""
                try:
                    from datetime import datetime as _dt
                    dt_utc = _dt.fromisoformat(ct.replace("Z", "+00:00"))
                    ct_kst = dt_utc.astimezone(KST).strftime("%Y-%m-%d")
                except Exception:
                    pass
                if ct_kst == today:
                    today_subs.append(rec)
            acc_subs_map[acc] = today_subs
        except Exception as e:
            print(f"[get_student_today_summary] 계정({acc}) 제출 조회 예외: {e}")
            acc_subs_map[acc] = []

    # ─── Auto-Active Resolution: 오늘 제출이 있는 계정으로 자동 전환 ─────────
    auto_switched = False
    active_accs = [a for a in base_accounts if acc_subs_map.get(a)]

    if active_accs:
        best_acc = active_accs[0]
        if best_acc != resolved_display_id:
            auto_switched = True
            resolved_display_id = best_acc
    elif resolved_display_id not in base_accounts and base_accounts:
        # 아무도 제출이 없으면 마지막 로그인 시간이 가장 최근인 계정 선택
        def _parse_login_dt(acc_id: str) -> float:
            ts = acc_last_login.get(acc_id, "")
            if not ts:
                return 0.0
            try:
                from datetime import datetime as _dt2
                return _dt2.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except Exception:
                return 0.0
        sorted_by_login = sorted(base_accounts, key=_parse_login_dt, reverse=True)
        resolved_display_id = sorted_by_login[0]

    # 최종 선택된 계정의 오늘 제출 목록
    raw_submissions = acc_subs_map.get(resolved_display_id, [])

    # ─── accounts_summary 메타데이터 조립 ─────────────────────────────────────
    accounts_summary: list[dict] = []
    for acc in base_accounts:
        subs = acc_subs_map.get(acc, [])
        today_count = len(subs)

        # 가장 최근 제출 시각 (KST HH:MM)
        last_sub_time: str | None = None
        if subs:
            try:
                from datetime import datetime as _dt3
                latest_ct = max(subs, key=lambda r: str(r.get("create_time") or ""))
                ct_str = str(latest_ct.get("create_time") or "")
                dt_utc = _dt3.fromisoformat(ct_str.replace("Z", "+00:00"))
                last_sub_time = dt_utc.astimezone(KST).strftime("%H:%M")
            except Exception:
                pass

        # 최근 로그인 시각 (가독성 포맷)
        last_login_str = acc_last_login.get(acc, "")

        accounts_summary.append({
            "display_id": acc,
            "today_count": today_count,
            "last_sub_time": last_sub_time,        # 오늘 최근 제출 HH:MM, 없으면 None
            "is_active": today_count > 0,           # 오늘 제출 여부
            "is_selected": acc == resolved_display_id,  # 현재 선택된 계정
            "last_login": last_login_str,           # 마지막 접속 ISO 문자열
            "is_primary": acc == base_accounts[0],  # 첫 번째 등록 계정이 본계정
        })

    # 오늘 제출 목록 정렬 (최신순) → 정답/오답 분류
    for rec in raw_submissions:
        prob_code = rec.get("problem") or ""
        p_title = title_map.get(str(prob_code)) or title_map.get(str(prob_code).lower()) or str(prob_code)
        res_code = rec.get("result")
        res_tag = "정답(AC 100점)" if res_code == 0 else "오답(WA)"
        lang = rec.get("language") or ""

        entry = {
            "id": rec.get("id"),
            "code": prob_code,
            "title": p_title,
            "result_tag": res_tag,
            "result": res_tag,
            "language": lang,
            "date": today,
        }
        if res_code == 0:
            solved_problems.append(entry)
        else:
            wrong_problems.append(entry)

    # ─── 디버깅 코드 스니펫(오답 ➔ 정답 페어) 추출 ───────────────────────────
    if raw_submissions and api_session:
        from collections import defaultdict
        by_prob = defaultdict(list)
        for rec in raw_submissions:
            by_prob[rec.get("problem")].append(rec)

        # 1. 오답 후 정답을 맞춘 문제 (WA -> AC) 우선 탐색 (최대 1~2개)
        for prob, items in by_prob.items():
            if len(debugging_snippets) >= 2:
                break
            wrong_item = next((x for x in reversed(items) if x.get("result") != 0), None)
            correct_item = next((x for x in items if x.get("result") == 0), None)
            if wrong_item and correct_item and wrong_item.get("id") and correct_item.get("id"):
                try:
                    w_res = api_session.get(f"http://edu.doingcoding.com/api/submission?id={wrong_item['id']}", timeout=3).json().get("data", {})
                    c_res = api_session.get(f"http://edu.doingcoding.com/api/submission?id={correct_item['id']}", timeout=3).json().get("data", {})
                    w_code = _clean_code_snippet(w_res.get("code") or "")
                    c_code = _clean_code_snippet(c_res.get("code") or "")
                    p_title = title_map.get(str(prob)) or title_map.get(str(prob).lower()) or str(prob)
                    lang = correct_item.get("language") or wrong_item.get("language") or ""
                    if w_code or c_code:
                        debugging_snippets.append({
                            "problem_code": prob,
                            "problem_title": p_title,
                            "language": lang,
                            "type": "debugging_pair",
                            "wrong_code": w_code,
                            "correct_code": c_code,
                        })
                except Exception as e:
                    print(f"[debugging_snippets] pair fetch error: {e}")

        # 2. 페어가 없는 경우: 최근 정답 문제 1개 코드 추출
        if not debugging_snippets:
            latest_ac = next((x for x in raw_submissions if x.get("result") == 0), None)
            if latest_ac and latest_ac.get("id"):
                try:
                    ac_res = api_session.get(f"http://edu.doingcoding.com/api/submission?id={latest_ac['id']}", timeout=3).json().get("data", {})
                    ac_code = _clean_code_snippet(ac_res.get("code") or "", max_chars=200)
                    prob = latest_ac.get("problem") or ""
                    p_title = title_map.get(str(prob)) or title_map.get(str(prob).lower()) or str(prob)
                    lang = latest_ac.get("language") or ""
                    if ac_code:
                        debugging_snippets.append({
                            "problem_code": prob,
                            "problem_title": p_title,
                            "language": lang,
                            "type": "single_ac",
                            "wrong_code": "",
                            "correct_code": ac_code,
                        })
                except Exception as e:
                    print(f"[debugging_snippets] single fetch error: {e}")

    is_no_submission = len(solved_problems) == 0 and len(wrong_problems) == 0

    candidate_accounts = list(dict.fromkeys(
        [resolved_display_id] + [str(a) for a in student_entry.get("accounts", []) if a]
    )) if student_entry else []

    return {
        "ok": True,
        "student_name": student_name,
        "display_id": resolved_display_id,
        "user_uuid": resolved_uuid,
        "portal_id": resolved_portal_id,
        "date": today,
        "candidate_accounts": candidate_accounts,
        "accounts_summary": accounts_summary,   # 🆕 계정별 활동 현황
        "auto_switched": auto_switched,          # 🆕 부계정으로 자동 전환 여부
        "solved_problems": solved_problems,
        "wrong_problems": wrong_problems,
        "debugging_snippets": debugging_snippets,
        "is_no_submission": is_no_submission,
        "homework_problems": homework_problems,
        "teacher_memo": teacher_memo,
        "mode": mode,
    }


def add_student_sub_account(
    new_display_id: str,
    portal_id: str | None = None,
    user_uuid: str | None = None,
) -> dict:
    """
    구글 문서 사이드바에서 강사가 낯선 계정을 연결했을 때,
    해당 계정을 학생의 부계정 목록(accounts)에 영구적으로 추가합니다.

    탐색 우선순위: user_uuid → portal_id
    이미 accounts에 있으면 중복 추가하지 않습니다.

    Returns:
        {"ok": True, "display_id": ..., "student_name": ..., "accounts": [...]}
    """
    new_id = (new_display_id or "").strip()
    if not new_id:
        raise ValueError("new_display_id는 필수입니다.")

    workspace_data = _load_workspace_students()

    resolved_uuid: str | None = None
    resolved_entry: dict | None = None

    # 1순위: user_uuid 직접
    if user_uuid:
        if user_uuid in workspace_data:
            resolved_uuid = user_uuid
            resolved_entry = workspace_data[user_uuid]

    # 2순위: portal_id → portal_mapping.json
    if not resolved_entry and portal_id:
        from core.storage import META_DIR
        portal_mapping_file = META_DIR / "portal_mapping.json"
        if portal_mapping_file.exists():
            try:
                m_data = json.loads(portal_mapping_file.read_text(encoding="utf-8"))
                pid_str = str(portal_id).strip()
                saved = m_data.get("mappings", {}).get(pid_str, {})
                target_uuid = saved.get("oj_uuid")
                if target_uuid and target_uuid in workspace_data:
                    resolved_uuid = target_uuid
                    resolved_entry = workspace_data[target_uuid]
            except Exception:
                pass

    # 3순위: portal_id → workspace_students.json 직접 탐색
    if not resolved_entry and portal_id:
        pid_str = str(portal_id).strip()
        for u, st in workspace_data.items():
            if str(st.get("portal_id", "")).strip() == pid_str:
                resolved_uuid = u
                resolved_entry = st
                break

    if not resolved_entry or not resolved_uuid:
        raise KeyError(f"학생을 찾을 수 없습니다. (portal_id={portal_id}, user_uuid={user_uuid})")

    # 중복 체크 후 accounts에 추가
    current_accounts: list[str] = list(resolved_entry.get("accounts") or [])
    if new_id in current_accounts:
        return {
            "ok": True,
            "already_exists": True,
            "display_id": resolved_entry.get("display_id"),
            "student_name": resolved_entry.get("name"),
            "accounts": current_accounts,
        }

    current_accounts.append(new_id)
    resolved_entry["accounts"] = current_accounts
    workspace_data[resolved_uuid] = resolved_entry
    _save_workspace_students(workspace_data)

    return {
        "ok": True,
        "already_exists": False,
        "display_id": resolved_entry.get("display_id"),
        "student_name": resolved_entry.get("name"),
        "accounts": current_accounts,
    }


def search_public_student_accounts(query: str, limit: int = 10) -> list[dict]:
    """
    구글 문서 사이드바 계정 검색용:
    1,040명 전체 학생 데이터에서 display_id, name, accounts를 실시간 검색합니다.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    workspace_data = _load_workspace_students()
    results = []

    for u, st in workspace_data.items():
        disp = (st.get("display_id") or "").lower()
        name = (st.get("name") or "").lower()
        accs = [str(a).lower() for a in st.get("accounts", []) if a]

        if q in disp or q in name or any(q in a for a in accs):
            results.append({
                "display_id": st.get("display_id") or u,
                "name": st.get("name") or "",
                "user_uuid": u,
                "accounts": st.get("accounts", []),
            })
            if len(results) >= limit:
                break

    return results


def update_portal_student_mapping(portal_id: str, oj_display_id: str, student_name: str | None = None) -> dict:
    """
    특정 portal_id의 OJ 계정 매핑을 영구적으로 갱신(meta/portal_mapping.json)합니다.
    """
    from core.storage import META_DIR
    from datetime import datetime, timezone, timedelta

    KST = timezone(timedelta(hours=9))
    today = datetime.now(tz=KST).strftime("%Y-%m-%d")

    pid_str = str(portal_id).strip()
    disp_str = str(oj_display_id).strip()
    if not pid_str or not disp_str:
        raise ValueError("portal_id와 oj_display_id는 필수입니다.")

    workspace_data = _load_workspace_students()
    resolved_uuid = None
    resolved_name = student_name or disp_str

    for u, st in workspace_data.items():
        if st.get("display_id") == disp_str or u == disp_str or any(a == disp_str for a in st.get("accounts", [])):
            resolved_uuid = u
            resolved_name = st.get("name") or student_name or disp_str
            break

    portal_mapping_file = META_DIR / "portal_mapping.json"
    portal_mappings = {}
    if portal_mapping_file.exists():
        try:
            m_data = json.loads(portal_mapping_file.read_text(encoding="utf-8"))
            portal_mappings = m_data.get("mappings", {})
        except Exception:
            pass

    portal_mappings[pid_str] = {
        "student_name": resolved_name,
        "type": "OJ",
        "oj_uuid": resolved_uuid or disp_str,
        "oj_display_id": disp_str,
        "note": "manual_switched",
        "updated_at": today,
    }

    portal_mapping_file.write_text(
        json.dumps({"mappings": portal_mappings}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "ok": True,
        "portal_id": pid_str,
        "oj_display_id": disp_str,
        "student_name": resolved_name,
        "oj_uuid": resolved_uuid,
    }



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


