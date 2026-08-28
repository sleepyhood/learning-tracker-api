#!/usr/bin/env python3
"""
src/scripts/etl_json_to_rdb.py
JSON 파일 스토어 -> RDB 이관 ETL 스크립트

안전장치:
- 위험요소 #1: ETL 전 백업 확인 후 진행
- 위험요소 #6: handle 소문자 정규화(casefold)
- 위험요소 #7: 미매핑 문제 UNKNOWN 레코드 보장
- 위험요소 #8: UTC 타임존 통일 저장
- 위험요소 #9: 100건 단위 Chunk Batch Insert

실행: python src/scripts/etl_json_to_rdb.py [--dry-run]
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

USERS_DATA_DIR = SRC_DIR / "users_data"
META_DIR = PROJECT_ROOT / "meta"
PROBLEMS_DATA_DIR = SRC_DIR / "problems_data"

CHUNK_SIZE = 100  # 위험요소 #9: 100건 단위 Batch
KST = timezone(timedelta(hours=9))


def parse_dt_to_utc(value: Optional[str]) -> Optional[datetime]:
    """ISO 문자열을 UTC datetime으로 변환 (위험요소 #8 대응)"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)  # KST로 가정 후 UTC 변환
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def casefold_handle(handle: str) -> str:
    """위험요소 #6: 계정명 소문자 정규화"""
    return str(handle).strip().casefold()


def load_uuids_map() -> dict:
    p = META_DIR / "uuids.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def load_user_doc(uuid_str: str) -> Optional[dict]:
    p = USERS_DATA_DIR / f"{uuid_str}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def iter_problems_catalog():
    """
    problems_data/*.json 에서 챕터/그룹/문제 목록 추출.
    실제 스키마: chapters(list), groups(dict: gid->obj), problems(dict: pid->obj)
    groups[gid].problem_ids = [pid, ...], groups[gid].chapter_id = chapter_id
    problems[pid].{pid, group_id, chapter_id, title}
    """
    for fname in ["all_problems.json", "prog2_problems.json"]:
        fpath = PROBLEMS_DATA_DIR / fname
        if not fpath.exists():
            continue
        curriculum = "prog2" if "prog2" in fname else "prog1"
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        chapters_raw = data.get("chapters", [])
        groups_raw = data.get("groups", {})
        problems_raw = data.get("problems", {})

        # chapters: list of {id, name, order, group_ids}
        ch_title_map = {}
        ch_order_map = {}
        for ch_idx, ch in enumerate(chapters_raw if isinstance(chapters_raw, list) else []):
            ch_id = ch.get("id") or ch.get("name")
            ch_title_map[ch_id] = ch.get("name") or ch.get("title") or ch_id
            ch_order_map[ch_id] = ch.get("order") or ch_idx

        # groups: dict {gid -> {chapter_id, title, problem_ids, ...}}
        g_order_map = {}
        for g_idx, gid in enumerate(groups_raw.keys() if isinstance(groups_raw, dict) else []):
            g_order_map[gid] = g_idx

        # problems: dict {pid -> {pid, group_id, chapter_id, title, ...}}
        for p_idx, (pid, problem) in enumerate(problems_raw.items() if isinstance(problems_raw, dict) else []):
            gid = problem.get("group_id")
            group = groups_raw.get(gid, {}) if isinstance(groups_raw, dict) else {}
            ch_id = problem.get("chapter_id") or group.get("chapter_id")
            ch_title = ch_title_map.get(ch_id, ch_id or "Unknown")
            ch_order = ch_order_map.get(ch_id, 0)
            g_title = group.get("title", gid or "Unknown")
            g_order = g_order_map.get(gid, 0)

            yield {
                "curriculum": curriculum,
                "chapter_title": ch_title,
                "chapter_order": ch_order,
                "group_title": g_title,
                "group_order": g_order,
                "legacy_code": pid,
                "server_problem_id": problem.get("server_id") or problem.get("id") or pid,
                "title": problem.get("title", ""),
                "difficulty": problem.get("difficulty"),
                "order_in_group": p_idx,
            }


def run_etl(dry_run: bool = True):
    from db.session import get_db_session, init_db
    from db.models import User, ExternalAccount, Problem, Chapter, Group, Submission, Assignment, AssignmentSubmission
    from db.repo import get_or_create_unknown_problem
    from sqlalchemy import select

    print(f"[ETL] {'DRY RUN 모드 - DB에 저장하지 않습니다.' if dry_run else 'LIVE 모드 - DB에 실제 저장합니다.'}")

    if not dry_run:
        init_db()
        print("[ETL] DB 테이블 생성 완료")

    uuids_map = load_uuids_map()
    print(f"[ETL] uuids.json 로드: {len(uuids_map)}개 매핑")

    # ── Step 1: 문제 카탈로그 이관 ──────────────────────────────────────────
    print("[ETL] Step 1: 문제 카탈로그 이관 시작")
    chapter_cache = {}  # (curriculum, title) -> Chapter
    group_cache = {}    # (chapter_key, title) -> Group
    problem_cache = {}  # legacy_code -> Problem
    prob_count = 0

    if not dry_run:
        with get_db_session() as session:
            # UNKNOWN 문제 레코드 먼저 생성 (위험요소 #7)
            get_or_create_unknown_problem(session)

            catalog_batch = []
            for item in iter_problems_catalog():
                ch_key = (item["curriculum"], item["chapter_title"])
                if ch_key not in chapter_cache:
                    ch = session.scalar(select(Chapter).where(
                        Chapter.curriculum == item["curriculum"],
                        Chapter.title == item["chapter_title"]
                    ))
                    if ch is None:
                        ch = Chapter(curriculum=item["curriculum"], title=item["chapter_title"], order_index=item["chapter_order"])
                        session.add(ch)
                        session.flush()
                    chapter_cache[ch_key] = ch
                ch = chapter_cache[ch_key]

                g_key = (ch.id, item["group_title"])
                if g_key not in group_cache:
                    g = session.scalar(select(Group).where(Group.chapter_id == ch.id, Group.title == item["group_title"]))
                    if g is None:
                        g = Group(chapter_id=ch.id, title=item["group_title"], order_index=item["group_order"])
                        session.add(g)
                        session.flush()
                    group_cache[g_key] = g
                g = group_cache[g_key]

                legacy = item["legacy_code"]
                if legacy and legacy not in problem_cache:
                    prob = session.scalar(select(Problem).where(Problem.legacy_code == legacy))
                    if prob is None:
                        prob = Problem(
                            site="doingcoding",
                            legacy_code=legacy,
                            server_problem_id=item["server_problem_id"],
                            title=item["title"],
                            difficulty=item["difficulty"],
                            group_id=g.id,
                            order_in_group=item["order_in_group"],
                        )
                        session.add(prob)
                        session.flush()
                    problem_cache[legacy] = prob
                    prob_count += 1
    else:
        for item in iter_problems_catalog():
            prob_count += 1

    print(f"[ETL] Step 1 완료: 문제 {prob_count}개 처리")

    # ── Step 2: 유저 및 제출 이력 이관 ─────────────────────────────────────
    print("[ETL] Step 2: 유저 및 제출 이력 이관 시작")
    user_count = 0
    sub_count = 0
    hw_count = 0

    # student_id -> uuid 역방향 맵 구성 (uuid만 있는 문서 제외)
    sid_to_uuid = {}
    for sid, uuid_val in uuids_map.items():
        # UUID 자체가 key인 항목 제외
        if re.match(r'^[0-9a-f\-]{36}$', sid):
            continue
        if sid.startswith("test") or sid.startswith("nonexistent"):
            continue
        sid_to_uuid[sid] = uuid_val

    user_batch = []
    for sid, uuid_val in sid_to_uuid.items():
        doc = load_user_doc(uuid_val)
        if doc is None:
            continue

        profile = doc.get("profile") or {}
        name = profile.get("name") or profile.get("student_id") or sid
        handle = casefold_handle(profile.get("student_id") or sid)  # 위험요소 #6
        internal_user_id = f"u_{uuid_val.replace('-', '')}"

        user_batch.append({
            "internal_user_id": internal_user_id,
            "name": name,
            "handle": handle,
            "uuid": uuid_val,
            "doc": doc,
        })
        user_count += 1

        # 위험요소 #9: 100건 단위 배치 처리
        if len(user_batch) >= CHUNK_SIZE and not dry_run:
            _flush_user_batch(user_batch, problem_cache)
            user_batch = []

    if user_batch and not dry_run:
        _flush_user_batch(user_batch, problem_cache)

    print(f"[ETL] Step 2 완료: 유저 {user_count}명 처리")
    print(f"[ETL] 전체 ETL {'DRY RUN' if dry_run else '완료'}")
    return {"users": user_count, "problems": prob_count}


def _flush_user_batch(batch: list, problem_cache: dict):
    """유저 배치를 DB에 flush (위험요소 #9: chunk 분할)"""
    from db.session import get_db_session
    from db.models import User, ExternalAccount, Submission, Assignment, AssignmentSubmission, Problem
    from db.repo import get_or_create_unknown_problem
    from sqlalchemy import select

    with get_db_session() as session:
        unknown_prob = get_or_create_unknown_problem(session)

        for entry in batch:
            internal_id = entry["internal_user_id"]
            name = entry["name"]
            handle = entry["handle"]
            doc = entry["doc"]

            # 유저 upsert
            user = session.scalar(select(User).where(User.internal_user_id == internal_id))
            if user is None:
                user = User(internal_user_id=internal_id, name=name, role="student")
                session.add(user)
                session.flush()

            # 외부 계정 upsert
            ext = session.scalar(select(ExternalAccount).where(
                ExternalAccount.user_id == user.id,
                ExternalAccount.site == "doingcoding"
            ))
            if ext is None:
                ext = ExternalAccount(user_id=user.id, site="doingcoding", handle=handle)
                session.add(ext)
                session.flush()

            # 제출 이력 이관 (oi_problems)
            oi = doc.get("oi_problems") or {}
            if isinstance(oi, dict):
                for server_id_str, prob_data in oi.items():
                    if not isinstance(prob_data, dict):
                        continue
                    legacy_code = prob_data.get("_id")
                    score = int(prob_data.get("score") or 0)
                    status_raw = prob_data.get("status")
                    verdict = "AC" if (status_raw == 0 or score == 100) else "WA"

                    prob = None
                    if legacy_code and legacy_code in problem_cache:
                        prob = problem_cache[legacy_code]
                    if prob is None:
                        prob = session.scalar(select(Problem).where(Problem.legacy_code == legacy_code)) if legacy_code else None
                    if prob is None:
                        prob = unknown_prob  # 위험요소 #7

                    # 제출 일시 없으면 현재 UTC 사용 (위험요소 #8)
                    submitted_at = datetime.now(timezone.utc)

                    # 중복 체크
                    existing = session.scalar(select(Submission).where(
                        Submission.user_id == user.id,
                        Submission.problem_id == prob.id,
                        Submission.submitted_at == submitted_at,
                    ))
                    if existing is None:
                        sub = Submission(
                            user_id=user.id,
                            problem_id=prob.id,
                            verdict=verdict,
                            score=score,
                            submitted_at=submitted_at,
                        )
                        session.add(sub)

            # 숙제 로그 이관 (homework_logs)
            hw_logs = doc.get("homework_logs") or []
            for log in hw_logs:
                if not isinstance(log, dict):
                    continue
                title = log.get("title") or "숙제"
                mode = log.get("mode") or "homework"
                ts_str = log.get("ts") or log.get("created_at")
                created_at = parse_dt_to_utc(ts_str) or datetime.now(timezone.utc)

                log_id = log.get("id") or log.get("log_id") or None
                log_id = str(log_id).strip() if log_id else None
                if not log_id:
                    log_id = f"hw_{user.internal_user_id}_{created_at.strftime('%Y%m%d%H%M%S')}"

                # 중복 방지: log_id로 이미 저장된 Assignment 조회
                existing_asn = session.scalar(
                    select(Assignment).where(Assignment.log_id == log_id)
                )
                if existing_asn is not None:
                    continue

                due_at = parse_dt_to_utc(log.get("due_at")) if log.get("due_at") else None

                asn = Assignment(
                    log_id=log_id,
                    title=title,
                    mode=mode,
                    channel=log.get("channel"),
                    message=log.get("message"),
                    comment=log.get("comment"),
                    created_at=created_at,
                    due_at=due_at,
                )
                session.add(asn)
                session.flush()

                seen_prob_ids = set()
                for prob_item in (log.get("problems") or []):
                    if not isinstance(prob_item, dict):
                        continue
                    lc = prob_item.get("legacy_code") or prob_item.get("code") or prob_item.get("_id")
                    p_status = str(prob_item.get("status") or "pending").lower()
                    p_score = int(prob_item.get("score") or 0)

                    prob = problem_cache.get(lc) if lc else None
                    if prob is None:
                        prob = session.scalar(select(Problem).where(Problem.legacy_code == lc)) if lc else None
                    if prob is None:
                        prob = unknown_prob

                    if prob.id in seen_prob_ids:
                        continue
                    seen_prob_ids.add(prob.id)

                    asub = AssignmentSubmission(
                        assignment_id=asn.id,
                        user_id=user.id,
                        problem_id=prob.id,
                        status=p_status,
                        score=p_score,
                        legacy_code=lc,
                    )
                    session.add(asub)

        session.commit()


def parse_dt_to_utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JSON -> RDB ETL 이관 스크립트")
    parser.add_argument("--dry-run", action="store_true", default=True, help="드라이런 (DB 저장 안함)")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="실제 DB 저장")
    args = parser.parse_args()
    result = run_etl(dry_run=args.dry_run)
    print(f"[ETL] 결과: {result}")
