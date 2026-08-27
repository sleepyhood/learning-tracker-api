"""
scripts/gen_feedback.py
학원 수업 피드백 생성기 (독립 실행)

사용법:
  python src/scripts/gen_feedback.py <학생이름>
  python src/scripts/gen_feedback.py --all-today
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

def _load_env():
    for candidate in [ROOT.parent / ".env", ROOT / ".env"]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip(); v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v
            break

_load_env()

KST = timezone(timedelta(hours=9))


def _find_uuid_by_name(name: str):
    from core.storage import META_DIR, UUIDS_PATH
    # 1. workspace_students.json 에서 검색 (실명, display_id, 연동 계정명)
    ws_path = META_DIR / "workspace_students.json"
    if ws_path.exists():
        try:
            data = json.loads(ws_path.read_text(encoding="utf-8"))
            for uuid, st in data.items():
                if st.get("name") == name or st.get("display_id") == name:
                    return uuid
                for acc in st.get("accounts", []):
                    if acc == name:
                        return uuid
            # 부분 일치 검색 (예: '김도헌' 입력 시 '김도헌1111' 매칭)
            for uuid, st in data.items():
                if name in str(st.get("name", "")) or name in str(st.get("display_id", "")):
                    return uuid
        except Exception:
            pass

    # 2. uuids.json 에서 계정명 매칭 (직접 DoingCoding ID 입력 시)
    if UUIDS_PATH.exists():
        try:
            uuids_data = json.loads(UUIDS_PATH.read_text(encoding="utf-8"))
            if name in uuids_data:
                return uuids_data[name]
            for acc, u in uuids_data.items():
                if name in acc:
                    return u
        except Exception:
            pass

    return None


def _load_doc(user_uuid: str) -> dict:
    from utils.utils_user_doc import load_doc_by_any
    return load_doc_by_any(user_uuid)


def _today_kst() -> str:
    return datetime.now(tz=KST).strftime("%Y-%m-%d")


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


def _build_prompt(data: dict) -> str:
    name = data["name"]
    mode = data["mode"]
    teacher_memo = data["teacher_memo"] or "오늘 수업에 성실하게 임함 (특이사항 없음)"
    hw_problems = data["hw_problems"]
    sub_log = _build_submission_log(data["recent_submissions"])

    if mode == "homework" and hw_problems:
        hw_text = "\n".join([f"  - [{p.get('legacy_code', '')}] {p.get('title', '')}" for p in hw_problems])
        notice_section = f"[신규 출제 숙제 ({len(hw_problems)}개)]\n{hw_text}"
    elif mode == "review":
        notice_section = "[오늘 수업 복습 안내]\n  별도 신규 숙제 없음. 오늘 수업 내용을 집에서 복습하도록 안내."
    else:
        notice_section = "[알림]\n  별도 숙제 없음. 수업 시간 내 실습을 모두 완료함."

    return f"""아래는 학원 선생님이 작성한 수업 기록입니다.
학부모님께 보낼 친절하고 전문적인 수업 피드백 문자를 2~3문장으로 작성해주세요.

[학생 이름] {name}
[선생님 관찰 메모] {teacher_memo}
[오늘 실습 및 제출 현황]
{sub_log}
{notice_section}

[작성 가이드라인]
- 따뜻하고 전문적인 어조로 2~3문장으로 간결하게 작성.
- 오답은 '디버깅 및 해결 과정'으로 긍정적으로 표현.
- 인사말("안녕하세요, 두잉창의코딩학원입니다")로 시작.
"""


def _call_gemini(prompt: str) -> str:
    from services.gemini_service import generate_feedback
    return generate_feedback(prompt)


def _copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip; pyperclip.copy(text); return True
    except Exception:
        pass
    try:
        import subprocess; subprocess.run("clip", input=text.encode("utf-8"), check=True, shell=True); return True
    except Exception:
        return False


def process_student(name_or_uuid: str, verbose: bool = True) -> str:
    if "-" in name_or_uuid and len(name_or_uuid) > 30:
        user_uuid = name_or_uuid
    else:
        user_uuid = _find_uuid_by_name(name_or_uuid)
        if not user_uuid:
            print(f"[!] '{name_or_uuid}' 학생을 찾을 수 없습니다.")
            return ""

    doc = _load_doc(user_uuid)
    data = _extract_feedback_data(doc)

    if verbose:
        print(f"\n▶ 학생: {data['name']} ({data['mode']} 모드)")
        print(f"  숙제: {len(data['hw_problems'])}개  |  제출기록: {len(data['recent_submissions'])}건")
        print(f"  메모: {data['teacher_memo'] or '(없음)'}")
        print(f"  최신 저장: {data['ts']}")
        print("\n⏳ Gemini API 호출 중...")

    prompt = _build_prompt(data)
    try:
        feedback = _call_gemini(prompt)
    except Exception as e:
        print(f"[!] Gemini API 오류: {e}")
        print("\n--- 프롬프트 (직접 붙여넣기용) ---")
        print(prompt)
        return prompt

    if verbose:
        print("\n" + "=" * 55)
        print(feedback)
        print("=" * 55)
        ok = _copy_to_clipboard(feedback)
        print("\n✅ 클립보드 복사 완료! (Ctrl+V)\n" if ok else "\n⚠️  직접 복사해주세요\n")

    return feedback


def process_all_today():
    from core.storage import META_DIR
    from config import USER_DATA_DIR

    today = _today_kst()
    user_data_dir = Path(USER_DATA_DIR)
    ws_path = META_DIR / "workspace_students.json"
    if not ws_path.exists():
        print("[!] workspace_students.json 없음"); return

    ws_data = json.loads(ws_path.read_text(encoding="utf-8"))
    processed = []

    for user_uuid, st in ws_data.items():
        if st.get("status") == "inactive":
            continue
        json_path = user_data_dir / f"{user_uuid}.json"
        if not json_path.exists():
            alt = user_data_dir / "by_internal" / f"u_{user_uuid.replace('-','')}.json"
            if not alt.exists():
                continue
            json_path = alt
        try:
            doc = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        logs = doc.get("homework_logs") or []
        if not logs:
            continue
        latest = max(logs, key=lambda x: str(x.get("created_at") or x.get("ts") or ""))
        ts = str(latest.get("created_at") or latest.get("ts") or "")
        if not ts.startswith(today):
            continue
        name = st.get("name") or st.get("display_id") or user_uuid
        print(f"\n{'─' * 55}\n[{len(processed)+1}] 학생: {name}")
        feedback = process_student(user_uuid, verbose=True)
        if feedback:
            processed.append({"name": name, "feedback": feedback})
        input("   ↩  다음 학생 → Enter...")

    print(f"\n✅ 총 {len(processed)}명 처리 완료")


def main():
    parser = argparse.ArgumentParser(description="학원 수업 피드백 생성기")
    parser.add_argument("student", nargs="?", help="학생 이름 또는 UUID")
    parser.add_argument("--all-today", action="store_true", help="오늘 숙제 저장된 전체 학생")
    args = parser.parse_args()
    if args.all_today:
        process_all_today()
    elif args.student:
        process_student(args.student)
    else:
        parser.print_help(); sys.exit(1)

if __name__ == "__main__":
    main()
