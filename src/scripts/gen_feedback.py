"""
gen_feedback.py (완전 독립 실행형 피드백 도구)
프로젝트 외부에서도 DATA_ROOT만 가리키면 100% 자립 실행됩니다.
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("[!] requests 패키지가 필요합니다: pip install requests")
    sys.exit(1)

TOOL_DIR = Path(__file__).resolve().parent

def _load_env():
    env_file = TOOL_DIR / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip(); v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v

_load_env()

DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(TOOL_DIR)))
KST = timezone(timedelta(hours=9))

def _today_kst() -> str:
    return datetime.now(tz=KST).strftime("%Y-%m-%d")

def _now_time_kst() -> str:
    return datetime.now(tz=KST).strftime("%H:%M:%S")

def _get_drafts_dir() -> Path:
    d = TOOL_DIR / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _load_today_state(today: str) -> set:
    state_file = _get_drafts_dir() / f".state_{today}.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return set(data.get("completed_uuids", []))
        except Exception:
            pass
    return set()

def _mark_student_done(today: str, uuid: str):
    state_file = _get_drafts_dir() / f".state_{today}.json"
    completed = _load_today_state(today)
    completed.add(uuid)
    try:
        state_file.write_text(json.dumps({"completed_uuids": list(completed)}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _append_feedback_backup(today: str, student_name: str, mode: str, feedback: str):
    backup_file = _get_drafts_dir() / f"{today}_feedbacks.txt"
    time_str = _now_time_kst()
    divider = "─" * 55
    entry = f"\n[{time_str}] {student_name} ({mode} 모드)\n{divider}\n{feedback}\n{divider}\n"
    try:
        with open(backup_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[!] 백업 파일 저장 실패: {e}")

def _get_user_data_dir() -> Path:
    for candidate in [DATA_ROOT / "src" / "users_data", DATA_ROOT / "users_data"]:
        if candidate.exists():
            return candidate
    return DATA_ROOT / "src" / "users_data"

def _get_meta_dir() -> Path:
    for candidate in [DATA_ROOT / "meta", DATA_ROOT / "src" / "meta"]:
        if candidate.exists():
            return candidate
    return DATA_ROOT / "meta"

WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]

def _fetch_portal_attendance(today: str) -> tuple:
    """
    학원 포털 대시보드 API (http://59.17.114.51:1325/api/admin/academy/dashboard) 호출
    반환: (출석 학생 리스트, 소스 상태 문자열)
    """
    portal_url = os.environ.get("PORTAL_API_URL", "http://59.17.114.51:1325/api/admin/academy/dashboard").strip()
    session_id = os.environ.get("PORTAL_SESSION_ID", "").strip()

    if not session_id:
        return None, "PORTAL_SESSION_ID 미설정 (로컬 시간표 Fallback)"

    try:
        # session= 접두어 처리
        s_val = session_id.split("session=")[-1].split(";")[0].strip() if "session=" in session_id else session_id
        cookies = {"session": s_val}
        params = {"date": today, "late_min": 5}
        resp = requests.get(portal_url, params=params, cookies=cookies, timeout=4)

        if resp.status_code == 200:
            data = resp.json()
            raw_list = []
            if isinstance(data, list):
                raw_list = data
            elif isinstance(data, dict):
                for key in ["lessons", "students", "items", "data", "list", "dashboard", "slots"]:
                    if key in data and isinstance(data[key], list):
                        raw_list = data[key]
                        break

            parsed = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                st_name = item.get("student_name") or item.get("name") or item.get("student") or item.get("user_name") or ""
                st_acc = item.get("account") or item.get("username") or item.get("user_id") or ""
                course = item.get("course") or item.get("subject") or item.get("lesson_name") or item.get("label") or ""
                time_slot = item.get("time") or item.get("lesson_time") or item.get("slot") or ""
                status = item.get("status") or item.get("attendance") or item.get("state") or ""

                if st_name or st_acc:
                    parsed.append({
                        "name": str(st_name).strip(),
                        "account": str(st_acc).strip(),
                        "course": str(course).strip(),
                        "time": str(time_slot).strip(),
                        "status": str(status).strip(),
                    })

            if parsed:
                return parsed, "📡 학원 포털 실시간 출석부"
            return None, "포털 응답 목록 비어있음"
        elif resp.status_code in (401, 403):
            return None, "포털 세션 만료 (재로그인 필요)"
        else:
            return None, f"포털 HTTP {resp.status_code} 응답"
    except requests.exceptions.Timeout:
        return None, "포털 서버 응답 시간 초과"
    except Exception as e:
        return None, f"포털 연결 실패 ({e})"


def _get_all_students_info():
    meta_dir = _get_meta_dir()
    user_data_dir = _get_user_data_dir()
    today = _today_kst()
    
    students = {}
    ws_path = meta_dir / "workspace_students.json"
    if ws_path.exists():
        try:
            ws_data = json.loads(ws_path.read_text(encoding="utf-8"))
            for uuid, st in ws_data.items():
                if st.get("status") == "inactive":
                    continue
                students[uuid] = {
                    "uuid": uuid,
                    "name": st.get("name") or st.get("display_id") or "수강생",
                    "display_id": st.get("display_id") or "",
                    "accounts": st.get("accounts") or [],
                    "latest_hw_ts": "",
                    "is_today": False,
                    "is_done": False,
                    "is_scheduled": False,
                    "course_label": "",
                    "student_note": "",
                    "source_type": "",
                }
        except Exception:
            pass

    # 1. 포털 실시간 출석부 API 시도 (1순위)
    portal_students, source_status = _fetch_portal_attendance(today)
    attendance_source_msg = source_status

    if portal_students:
        for p in portal_students:
            p_name = p["name"]
            p_acc = p["account"]
            matched_uuid = None

            # 이름 또는 계정명으로 학생 매칭
            for u, st in students.items():
                if p_name and (st["name"] == p_name or p_name in st["name"]):
                    matched_uuid = u; break
                if p_acc and (p_acc in st["accounts"] or st["display_id"] == p_acc):
                    matched_uuid = u; break

            if matched_uuid:
                students[matched_uuid]["is_scheduled"] = True
                if p["course"]: students[matched_uuid]["course_label"] = p["course"]
                time_info = f"({p['time']})" if p['time'] else ""
                students[matched_uuid]["student_note"] = f"{time_info} {p['status']}".strip()
                students[matched_uuid]["source_type"] = "포털"
            else:
                # 메타에 없는 외부 등록 학생도 목록에 포함
                fake_u = f"portal_{p_name}_{p_acc}"
                students[fake_u] = {
                    "uuid": fake_u,
                    "name": p_name or p_acc or "포털학생",
                    "display_id": p_acc or p_name,
                    "accounts": [p_acc] if p_acc else [],
                    "latest_hw_ts": "",
                    "is_today": False,
                    "is_done": False,
                    "is_scheduled": True,
                    "course_label": p["course"] or "코딩",
                    "student_note": f"{p['time']} {p['status']}".strip(),
                    "source_type": "포털",
                }
    else:
        # 2. 로컬 schedule.json 시간표 Fallback (2순위)
        today_dt = datetime.now(tz=KST)
        py_weekday = today_dt.weekday()      # 0=월 ... 4=금, 5=토, 6=일
        target_weekday = py_weekday + 1      # schedule.json 기준: 1=월 ... 5=금, 6=토

        sched_path = meta_dir / "schedule.json"
        if sched_path.exists():
            try:
                sched_data = json.loads(sched_path.read_text(encoding="utf-8"))
                for slot in sched_data.get("slots", []):
                    if slot.get("weekday") == target_weekday:
                        lbl = slot.get("label") or "코딩"
                        notes = slot.get("student_notes") or {}
                        for s_uuid in slot.get("students", []):
                            if s_uuid in students:
                                students[s_uuid]["is_scheduled"] = True
                                students[s_uuid]["course_label"] = lbl
                                students[s_uuid]["source_type"] = "시간표"
                                if s_uuid in notes:
                                    students[s_uuid]["student_note"] = notes[s_uuid]
            except Exception:
                pass

    # 3. 오늘 웹 숙제/피드백 저장 여부 및 완료 상태 확인
    completed_uuids = _load_today_state(today)

    for uuid, info in students.items():
        if uuid in completed_uuids:
            info["is_done"] = True

        jpath = user_data_dir / f"{uuid}.json"
        if not jpath.exists():
            alt = user_data_dir / "by_internal" / f"u_{uuid.replace('-','')}.json"
            if alt.exists():
                jpath = alt
        if jpath.exists():
            try:
                doc = json.loads(jpath.read_text(encoding="utf-8"))
                logs = doc.get("homework_logs") or []
                if logs:
                    latest = max(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""))
                    ts = str(latest.get("created_at") or latest.get("ts") or "")
                    info["latest_hw_ts"] = ts
                    if ts.startswith(today):
                        info["is_today"] = True
            except Exception:
                pass

    return students, attendance_source_msg

def _search_students(query: str, students: dict) -> list[dict]:
    q = query.strip().lower()
    exact_matches = []
    starts_matches = []
    partial_matches = []

    for uuid, st in students.items():
        name = str(st["name"]).lower()
        disp = str(st["display_id"]).lower()
        accs = [str(a).lower() for a in st["accounts"]]

        if q == name or q == disp or q in accs or q == uuid.lower():
            exact_matches.append(st)
        elif name.startswith(q) or disp.startswith(q) or any(a.startswith(q) for a in accs):
            starts_matches.append(st)
        elif q in name or q in disp or any(q in a for a in accs):
            partial_matches.append(st)

    seen = set()
    result = []
    for group in [exact_matches, starts_matches, partial_matches]:
        sorted_group = sorted(group, key=lambda x: (not x["is_today"], x["name"]))
        for item in sorted_group:
            if item["uuid"] not in seen:
                seen.add(item["uuid"])
                result.append(item)

    return result

def _resolve_student_interactive(query: str | None = None) -> str | None:
    students, source_msg = _get_all_students_info()
    today = _today_kst()
    today_dt = datetime.now(tz=KST)
    weekday_str = WEEKDAYS_KR[today_dt.weekday()]

    current_q = query
    while True:
        if not current_q:
            # 오늘 스케줄에 있거나 오늘 웹 저장이 있는 학생 추출
            today_candidates = [s for s in students.values() if s["is_today"] or s["is_scheduled"]]
            # 정렬: 오늘 웹 저장 학생 우선 -> 스케줄 학생 -> 미완료 우선 -> 이름순
            today_students = sorted(
                today_candidates,
                key=lambda x: (x["is_done"], not x["is_today"], not x["is_scheduled"], x["name"])
            )
            done_count = sum(1 for s in today_students if s["is_done"])
            total_today = len(today_students)

            print(f"\n{'═' * 55}")
            if total_today > 0:
                print(f"📅 [{today} ({weekday_str})] 오늘 출석 & 수업 학생 (진행도: {done_count}/{total_today}명)")
                print(f"ℹ️  출석부 출처: {source_msg}")
                print(f"{'═' * 55}")
                display_list = today_students
                for idx, s in enumerate(display_list, 1):
                    status_badge = "[✅완료]" if s["is_done"] else "[⏳대기]"
                    course_badge = f" [{s['course_label']}]" if s["course_label"] else ""
                    oj_badge = " [📝OJ숙제]" if s["is_today"] else (" [💡출석부]" if s["is_scheduled"] else "")
                    note_str = f" ({s['student_note']})" if s["student_note"] else ""
                    print(f"  [{idx:2d}] {status_badge} {s['name']} (@{s['display_id']}){course_badge}{oj_badge}{note_str}")
            else:
                print(f"📅 [{today} ({weekday_str})] 오늘 출석 & 수업 학생 (0명)")
                print(f"ℹ️  출석부 출처: {source_msg}")
                print(f"  ⚠️  오늘 시간표에 배정된 학생이나 웹 저장 내역이 없습니다.")
                print(f"{'═' * 55}")
                print(f"📋 [전체 등록 학생 목록] (원하는 학생 번호 선택 또는 검색)")
                display_list = list(students.values())[:15]
                for idx, s in enumerate(display_list, 1):
                    acc_str = f" | 계정: {','.join(s['accounts'][:2])}" if s['accounts'] else ""
                    print(f"  [{idx:2d}] {s['name']} (@{s['display_id']}){acc_str}")

            print(f"{'─' * 55}")
            user_input = input("👉 학생 번호 선택 또는 이름/아이디 검색 (종료: q): ").strip()
            if not user_input or user_input.lower() == 'q':
                return None

            if user_input.isdigit():
                choice = int(user_input)
                if 1 <= choice <= len(display_list):
                    return display_list[choice - 1]["uuid"]
                print("[!] 잘못된 번호입니다.")
                continue
            else:
                current_q = user_input

        matches = _search_students(current_q, students)

        if len(matches) == 1:
            chosen = matches[0]
            status_badge = "[✅완료]" if chosen["is_done"] else "[⏳대기]"
            course_badge = f" [{chosen['course_label']}]" if chosen["course_label"] else ""
            print(f"✅ 학생 선택: {status_badge} {chosen['name']} (@{chosen['display_id']}){course_badge}")
            return chosen["uuid"]

        elif len(matches) > 1:
            print(f"\n[?] '{current_q}' 검색 결과 {len(matches)}명이 발견되었습니다:")
            print(f"{'─' * 55}")
            for idx, s in enumerate(matches, 1):
                status_badge = "[✅완료]" if s["is_done"] else "[⏳대기]"
                acc_str = f" | 계정: {','.join(s['accounts'][:2])}" if s['accounts'] else ""
                hw_time = f" | 최근숙제: {s['latest_hw_ts'][:16]}" if s['latest_hw_ts'] else ""
                print(f"  [{idx:2d}] {status_badge} {s['name']} (@{s['display_id']}){acc_str}{hw_time}")
            print(f"{'─' * 55}")

            user_choice = input(f"👉 선택할 번호를 입력하세요 (1~{len(matches)}, 취소: q, 다시검색: r): ").strip()
            if user_choice.lower() == 'q':
                return None
            if user_choice.lower() == 'r':
                current_q = input("👉 다시 검색할 이름 입력: ").strip()
                continue
            if user_choice.isdigit():
                c_idx = int(user_choice)
                if 1 <= c_idx <= len(matches):
                    return matches[c_idx - 1]["uuid"]
            print("[!] 번호가 올바르지 않습니다.")
            continue

        else:
            print(f"\n[!] '{current_q}' 학생을 찾을 수 없습니다.")
            current_q = input("👉 학생 이름을 다시 입력하세요 (엔터 시 전체 목록, 종료: q): ").strip()
            if current_q.lower() == 'q':
                return None

def _load_doc(user_uuid: str) -> dict:
    user_data_dir = _get_user_data_dir()
    p = user_data_dir / f"{user_uuid}.json"
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: pass
    alt = user_data_dir / "by_internal" / f"u_{user_uuid.replace('-','')}.json"
    if alt.exists():
        try: return json.loads(alt.read_text(encoding="utf-8"))
        except Exception: pass
    return {"user_uuid": user_uuid}

def _extract_feedback_data(doc: dict) -> dict:
    profile = doc.get("profile") or {}
    name = profile.get("name") or profile.get("student_id") or doc.get("user_uuid", "학생")
    logs = doc.get("homework_logs") or []
    try:
        logs = sorted(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""), reverse=True)
    except Exception:
        pass
    latest_log = logs[0] if logs else {}
    mode = latest_log.get("mode") or ("homework" if latest_log.get("problems") else "comment")
    hw_problems = latest_log.get("problems") or []
    teacher_memo = latest_log.get("teacher_memo") or ""
    ts = latest_log.get("ts") or latest_log.get("created_at") or ""
    recent_subs = latest_log.get("recent_submissions") or doc.get("recent_submissions") or []
    return {"name": name, "mode": mode, "teacher_memo": teacher_memo,
            "hw_problems": hw_problems, "recent_submissions": recent_subs, "ts": ts}

def _build_submission_log(recent_subs: list) -> str:
    if not recent_subs:
        return "  (오늘 제출 기록 없음 또는 동기화 전)"
    today = _today_kst()
    lines = []
    for idx, sub in enumerate(recent_subs[:8], 1):
        date_str = str(sub.get("date") or "")
        is_today = sub.get("is_today") or (today in date_str)
        prefix = "[오늘]" if is_today else f"[{date_str}]"
        title = sub.get("title") or sub.get("problem") or "문제"
        result = sub.get("result_tag") or sub.get("result") or "결과불명"
        line = f"  {idx}. {prefix} {title} | 결과: {result}"
        code = sub.get("code") or ""
        if code:
            short_code = code.strip()[:300] + ("..." if len(code) > 300 else "")
            line += f"\n     제출 코드:\n`\n{short_code}\n`"
        lines.append(line)
    return "\n".join(lines)

def _build_prompt(data: dict, variation_hint: str = "") -> str:
    name = data["name"]
    mode = data["mode"]
    course_label = data.get("course_label") or "코딩"
    teacher_memo = data["teacher_memo"] or f"오늘 {course_label} 수업에 성실하게 참여하여 주어진 실습 과제를 잘 완수함."
    hw_problems = data["hw_problems"]
    sub_log = _build_submission_log(data["recent_submissions"])

    if mode == "homework" and hw_problems:
        hw_text = "\n".join([f"  - [{p.get('legacy_code', '')}] {p.get('title', '')}" for p in hw_problems])
        notice_section = f"[신규 출제 숙제 ({len(hw_problems)}개)]\n{hw_text}"
    elif mode == "review":
        notice_section = "[오늘 수업 복습 안내]\n  별도 신규 숙제 없음. 오늘 수업 내용을 집에서 복습하도록 안내."
    else:
        notice_section = "[알림]\n  수업 시간 내 실습을 모두 완료하여 별도 신규 숙제 없음."

    variation_text = f"\n[추가 요청사항] {variation_hint}\n" if variation_hint else ""

    return f"""아래는 학원 선생님이 작성한 수업 기록입니다.
학부모님께 보낼 친절하고 전문적인 수업 피드백 문자를 2~3문장으로 작성해주세요.

[학생 이름] {name}
[수업 과목] {course_label}
[선생님 관찰 메모] {teacher_memo}
[오늘 실습 및 제출 현황]
{sub_log}
{notice_section}{variation_text}
[작성 가이드라인]
- 따뜻하고 전문적인 어조로 2~3문장으로 간결하게 작성.
- 오답이나 막혔던 부분은 '디버깅 및 문제 해결 과정'으로 긍정적으로 표현.
- 인사말("안녕하세요, 두잉창의코딩학원입니다")로 시작.
"""

def _call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY 가 .env 파일에 설정되어 있지 않습니다.")

    candidates = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7}
    }

    last_error = None
    for model in candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            resp = requests.post(url, json=payload, params={"key": api_key}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates") or []
                if cands:
                    raw = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return re.sub(r"^[\s`#\-\*]+", "", raw).strip()
            last_error = f"{resp.status_code}: {resp.text[:120]}"
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(f"Gemini API 호출 실패: {last_error}")

def _copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip; pyperclip.copy(text); return True
    except Exception:
        pass
    try:
        import subprocess; subprocess.run("clip", input=text.encode("utf-8"), check=True, shell=True); return True
    except Exception:
        return False

def process_student(name_or_uuid: str | None = None, verbose: bool = True) -> str:
    user_uuid = None
    if name_or_uuid and "-" in name_or_uuid and len(name_or_uuid) > 30:
        user_uuid = name_or_uuid
    else:
        user_uuid = _resolve_student_interactive(name_or_uuid)
        if not user_uuid:
            return ""

    today = _today_kst()
    doc = _load_doc(user_uuid)
    data = _extract_feedback_data(doc)

    # 스케줄/출석 정보에서 과목 라벨 보강
    students_info, _ = _get_all_students_info()
    st_meta = students_info.get(user_uuid, {})
    data["course_label"] = st_meta.get("course_label") or "코딩"

    # 비-OJ 학생이거나 오늘 웹 기록이 없는 경우 즉석 메모 지원
    has_today_oj = data["ts"].startswith(today) and (data["hw_problems"] or data["recent_submissions"])
    if not has_today_oj and verbose:
        print(f"\n💡 [비-OJ / 오프라인 수업 모드] 오늘 웹 숙제/풀이 기록이 없습니다.")
        memo_in = input(f"👉 오늘 {data['name']} 학생 수업 관찰 메모 입력 (엔터 시 기본 피드백): ").strip()
        if memo_in:
            data["teacher_memo"] = memo_in

    if verbose:
        course_str = f" [{data['course_label']}]" if data.get("course_label") else ""
        print(f"\n▶ 대상 학생: {data['name']}{course_str} ({data['mode']} 모드)")
        print(f"  숙제: {len(data['hw_problems'])}개  |  제출기록: {len(data['recent_submissions'])}건")
        print(f"  메모: {data['teacher_memo'] or '(없음)'}")
        if data['ts']:
            print(f"  최신 저장 시각: {data['ts']}")

    feedback = ""
    retry_hint = ""

    while True:
        if verbose:
            print("\n⏳ Gemini API로 학부모 피드백 생성 중...")

        prompt = _build_prompt(data, retry_hint)
        try:
            feedback = _call_gemini(prompt)
        except Exception as e:
            print(f"[!] Gemini API 오류: {e}")
            print("\n--- 프롬프트 (직접 붙여넣기용) ---")
            print(prompt)
            return prompt

        if verbose:
            print("\n" + "═" * 55)
            print(feedback)
            print("═" * 55)
            ok = _copy_to_clipboard(feedback)
            if ok:
                print("\n✅ 클립보드 복사 완료! (카카오톡에 Ctrl+V 하세요)")
            else:
                print("\n⚠️  직접 복사해주세요")

            _append_feedback_backup(today, data['name'], data['mode'], feedback)
            _mark_student_done(today, user_uuid)
            print(f"📁 백업 완료: drafts/{today}_feedbacks.txt")

            print(f"{'─' * 55}")
            action = input("👉 [Enter]: 완료(목록으로) | [r]: 다른 톤으로 다시 생성 | [c]: 다시 복사: ").strip().lower()
            if action == 'r':
                retry_hint = "이전 생성 내용과 다른 문장 표현으로 조금 더 간결하고 생동감 있게 다시 작성해주세요."
                continue
            elif action == 'c':
                _copy_to_clipboard(feedback)
                print("✅ 다시 복사되었습니다.")
                input("👉 [Enter]를 누르면 목록으로 돌아갑니다...")
                break
            else:
                break
        else:
            _append_feedback_backup(today, data['name'], data['mode'], feedback)
            _mark_student_done(today, user_uuid)
            break

    return feedback

def process_all_today():
    today = _today_kst()
    meta_dir = _get_meta_dir()
    user_data_dir = _get_user_data_dir()
    ws_path = meta_dir / "workspace_students.json"
    if not ws_path.exists():
        print("[!] workspace_students.json 없음"); return

    ws_data = json.loads(ws_path.read_text(encoding="utf-8"))

    today_students = []
    for user_uuid, st in ws_data.items():
        if st.get("status") == "inactive":
            continue
        json_path = user_data_dir / f"{user_uuid}.json"
        if not json_path.exists():
            alt = user_data_dir / "by_internal" / f"u_{user_uuid.replace('-','')}.json"
            if alt.exists():
                json_path = alt
            else:
                continue
        try:
            doc = json.loads(json_path.read_text(encoding="utf-8"))
            logs = doc.get("homework_logs") or []
            if logs:
                latest = max(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""))
                ts = str(latest.get("created_at") or latest.get("ts") or "")
                if ts.startswith(today):
                    name = st.get("name") or st.get("display_id") or user_uuid
                    today_students.append((user_uuid, name))
        except Exception:
            continue

    if not today_students:
        print(f"\n[!] 오늘({today}) 저장된 숙제/피드백 내역이 있는 학생이 없습니다.")
        return

    print(f"\n📅 오늘 총 {len(today_students)}명의 학생이 등록되어 있습니다.")
    processed = []
    for idx, (u, s_name) in enumerate(today_students, 1):
        print(f"\n{'─' * 55}\n[{idx}/{len(today_students)}] {s_name}")
        feedback = process_student(u, verbose=True)
        if feedback:
            processed.append({"name": s_name, "feedback": feedback})

    print(f"\n🎉 오늘 총 {len(processed)}명 피드백 생성 및 클립보드 복사 완료!")
    print(f"📁 전체 백업 위치: drafts/{today}_feedbacks.txt")

def main():
    parser = argparse.ArgumentParser(description="학원 수업 피드백 생성기 (완전 독립 실행형)")
    parser.add_argument("student", nargs="?", help="학생 이름, 계정명 또는 UUID (생략 시 대화형 메뉴)")
    parser.add_argument("--all-today", action="store_true", help="오늘 숙제 저장된 전체 학생 일괄 처리")
    args = parser.parse_args()

    if args.all_today:
        process_all_today()
    else:
        while True:
            res = process_student(args.student)
            if args.student or not res:
                break

if __name__ == "__main__":
    main()
