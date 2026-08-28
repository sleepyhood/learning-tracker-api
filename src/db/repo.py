"""
src/db/repo.py
DB Repository 레이어 - 비즈니스 로직에서 SQL 직접 작성 금지, repo 함수만 호출
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, case, func, delete

from db.models import User, ExternalAccount, Problem, Submission, Assignment, AssignmentSubmission, Group, Chapter

KST = timezone(timedelta(hours=9))


# ─── 유저 조회 ──────────────────────────────────────────────────────────────

def get_user_by_internal_id(session: Session, internal_user_id: str) -> Optional[User]:
    """internal_user_id로 User 조회"""
    return session.scalar(select(User).where(User.internal_user_id == internal_user_id))


def get_user_by_handle(session: Session, site: str, handle: str) -> Optional[User]:
    """
    외부 계정 handle(casefold 정규화)로 User 조회.
    위험요소 #6: handle은 casefold 후 비교
    """
    h = handle.strip().casefold()
    ext = session.scalar(
        select(ExternalAccount).where(
            and_(ExternalAccount.site == site, ExternalAccount.handle == h)
        )
    )
    return ext.user if ext else None


def get_or_create_user(session: Session, internal_user_id: str, name: str, role: str = "student") -> User:
    """존재하면 조회, 없으면 생성"""
    user = get_user_by_internal_id(session, internal_user_id)
    if user is None:
        user = User(internal_user_id=internal_user_id, name=name, role=role)
        session.add(user)
        session.flush()
    return user


def resolve_user_any(session: Session, id_or_handle: str, site: str = "doingcoding") -> Optional[User]:
    """
    Dual-Lookup Adapter: internal_user_id, UUID(hyphenated), handle, 또는 name 어느 것이 와도 User 반환.
    위험요소 #2 (하위 호환성) 대응.
    """
    q = str(id_or_handle or "").strip()
    if not q:
        return None
    # 1) internal_user_id direct match
    user = get_user_by_internal_id(session, q)
    if user:
        return user
    # 2) hyphenated UUID -> u_<hex>
    clean_hex = q.replace("-", "").lower()
    if len(clean_hex) == 32:
        user = get_user_by_internal_id(session, f"u_{clean_hex}")
        if user:
            return user
    # 3) external account handle (casefold)
    user = get_user_by_handle(session, site, q)
    if user:
        return user
    # 4) user name fallback
    return session.scalar(select(User).where(User.name == q))


# ─── 문제 조회 ──────────────────────────────────────────────────────────────

def get_or_create_unknown_problem(session: Session) -> Problem:
    """
    위험요소 #7: 미매핑 문제 FK 제약 실패 방지용 unknown_problem 레코드 보장
    """
    prob = session.scalar(select(Problem).where(Problem.is_unknown == True))
    if prob is None:
        prob = Problem(
            site="doingcoding",
            server_problem_id="UNKNOWN",
            legacy_code="UNKNOWN",
            title="[미매핑 문제]",
            is_unknown=True,
        )
        session.add(prob)
        session.flush()
    return prob


def get_problem_by_legacy(session: Session, legacy_code: str) -> Optional[Problem]:
    return session.scalar(select(Problem).where(Problem.legacy_code == legacy_code))


def get_problem_by_server_id(session: Session, server_problem_id: str) -> Optional[Problem]:
    return session.scalar(select(Problem).where(Problem.server_problem_id == server_problem_id))


# ─── 숙제 최신 조회 & CUD ───────────────────────────────────────────────────

def get_latest_assignment_for_user(session: Session, user_identifier: str) -> Optional[dict]:
    """
    유저의 최근 숙제 로그를 DB에서 직접 조회하고, 실시간 제출 현황(Submission 및 JSON 캐시)을 반영하여
    문제 메타데이터와 풀이 현황을 반환.
    """
    user = resolve_user_any(session, user_identifier)
    if not user:
        return None

    # 최신 Assignment 찾기 (Assignment.created_at 기준 역순)
    latest_assignment = session.scalar(
        select(Assignment)
        .join(AssignmentSubmission, Assignment.id == AssignmentSubmission.assignment_id)
        .where(AssignmentSubmission.user_id == user.id)
        .order_by(Assignment.created_at.desc(), Assignment.id.desc())
    )
    if not latest_assignment:
        return None

    items = session.scalars(
        select(AssignmentSubmission)
        .where(
            and_(
                AssignmentSubmission.assignment_id == latest_assignment.id,
                AssignmentSubmission.user_id == user.id,
            )
        )
        .order_by(AssignmentSubmission.id.asc())
    ).all()

    # 실시간 풀이 상태 대조를 위한 유저 JSON 캐시 보조 로드 (Dual-Store 동기화 지원)
    json_solved_map = {}
    try:
        from utils.utils_user_doc import load_doc_by_any
        user_doc = load_doc_by_any(user_identifier) or {}
        oi_probs = user_doc.get("oi_problems") or {}
        if isinstance(oi_probs, dict):
            for k, v in oi_probs.items():
                if isinstance(v, dict):
                    c = v.get("_id") or v.get("legacy_code") or k
                    if c:
                        json_solved_map[str(c)] = v
    except Exception:
        pass

    problems_list = []
    counts = {"total": 0, "passed": 0, "partial": 0, "wrong": 0, "pending": 0}

    for item in items:
        prob = item.problem
        lc = item.legacy_code or (prob.legacy_code if prob else "") or ""
        
        # 1. 문제 메타데이터 조회
        p_title = ""
        group_title = ""
        chapter_code = ""
        chapter_title = ""
        server_prob_id = None

        if prob and not prob.is_unknown:
            p_title = prob.title or ""
            server_prob_id = prob.server_problem_id
            if prob.group:
                group_title = prob.group.title or ""
                if prob.group.chapter:
                    chapter_code = prob.group.chapter.curriculum or ""
                    chapter_title = prob.group.chapter.title or ""
        
        # 2. RDB Submission 및 JSON 캐시 기반 실시간 상태/점수 산출
        subs = []
        if prob:
            subs = session.scalars(
                select(Submission)
                .where(
                    and_(
                        Submission.user_id == user.id,
                        Submission.problem_id == prob.id,
                    )
                )
                .order_by(Submission.score.desc(), Submission.submitted_at.desc())
            ).all()

        is_passed = False
        is_wrong = False
        max_score = 0

        # RDB submissions 검사
        for sub in subs:
            if sub.score == 100 or (sub.verdict and sub.verdict.upper() in ["AC", "PASSED", "SOLVED", "0"]):
                is_passed = True
                max_score = 100
                break
            elif sub.score > max_score:
                max_score = sub.score
            elif (sub.verdict and sub.verdict.upper() in ["WA", "WRONG", "FAILED"]) and max_score == 0:
                is_wrong = True

        # JSON 캐시 검사 보조
        if not is_passed:
            for k in filter(None, [lc, lc.lower() if lc else None, server_prob_id]):
                if k in json_solved_map:
                    entry = json_solved_map[k]
                    e_score = int(entry.get("score") or 0)
                    e_status = entry.get("status")
                    if e_score == 100 or e_status in [0, "0", "PASSED", "solved", "passed", "AC", "ACCEPTED"]:
                        is_passed = True
                        max_score = 100
                        break
                    elif e_score > max_score:
                        max_score = e_score
                    elif e_status in [-1, "-1", "WRONG", "wrong", "FAILED"]:
                        is_wrong = True

        if is_passed or max_score == 100:
            st = "passed"
            score_val = 100
        elif max_score > 0:
            st = "partial"
            score_val = max_score
        elif is_wrong:
            st = "wrong"
            score_val = 0
        else:
            raw_st = (item.status or "pending").lower()
            if raw_st in ["passed", "solved"]:
                st = "passed"
                score_val = 100
            elif raw_st == "wrong":
                st = "wrong"
                score_val = 0
            elif raw_st == "partial":
                st = "partial"
                score_val = item.score or 50
            else:
                st = "pending"
                score_val = 0

        counts["total"] += 1
        counts[st] = counts.get(st, 0) + 1

        problems_list.append({
            "legacy_code": lc,
            "server_problem_id": server_prob_id,
            "title": p_title or lc or "",
            "status": st,
            "score": score_val,
            "group_title": group_title,
            "chapter_code": chapter_code,
            "chapter_title": chapter_title,
        })

    # UTC -> KST 변환
    def to_kst_iso(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).isoformat()

    log_key = latest_assignment.log_id or str(latest_assignment.id)
    return {
        "ok": True,
        "log": {
            "id": log_key,
            "key": log_key,
            "log_id": log_key,
            "title": latest_assignment.title,
            "mode": latest_assignment.mode,
            "channel": latest_assignment.channel,
            "message": latest_assignment.message,
            "comment": latest_assignment.comment,
            "ts": to_kst_iso(latest_assignment.created_at),
            "created_at": to_kst_iso(latest_assignment.created_at),
            "due_at": to_kst_iso(latest_assignment.due_at),
            "problems": problems_list,
            "counts": counts,
        },
        "student_name": user.name,
    }


def create_or_update_assignment_rdb(session: Session, user_identifier: str, log: dict) -> Optional[Assignment]:
    """
    신규 숙제/알림장을 RDB Assignment 및 AssignmentSubmission 테이블에 생성 또는 갱신.
    Dual-Store 동기화 지원.
    """
    user = resolve_user_any(session, user_identifier)
    if not user:
        return None

    log_id = log.get("id") or log.get("log_id") or log.get("key")
    if log_id:
        log_id = str(log_id).strip()

    asn = None
    if log_id:
        asn = session.scalar(select(Assignment).where(Assignment.log_id == log_id))

    title = log.get("title") or "숙제"
    mode = log.get("mode") or "homework"
    channel = log.get("channel") or "kakao"
    message = log.get("message")
    comment = log.get("comment")
    ts_str = log.get("ts") or log.get("created_at")

    created_at = None
    if ts_str:
        try:
            dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            created_at = dt.astimezone(timezone.utc)
        except Exception:
            created_at = None
    if not created_at:
        created_at = datetime.now(timezone.utc)

    due_at = None
    due_str = log.get("due_at")
    if due_str:
        try:
            dt = datetime.fromisoformat(str(due_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            due_at = dt.astimezone(timezone.utc)
        except Exception:
            due_at = None

    if asn is None:
        asn = Assignment(
            log_id=log_id,
            title=title,
            mode=mode,
            channel=channel,
            message=message,
            comment=comment,
            created_at=created_at,
            due_at=due_at,
        )
        session.add(asn)
        session.flush()
    else:
        asn.title = title
        asn.mode = mode
        asn.channel = channel
        asn.message = message
        asn.comment = comment
        asn.created_at = created_at
        asn.due_at = due_at
        session.execute(
            delete(AssignmentSubmission).where(AssignmentSubmission.assignment_id == asn.id)
        )
        session.flush()

    unknown_prob = get_or_create_unknown_problem(session)
    seen_prob_ids = set()

    for prob_item in (log.get("problems") or []):
        if not isinstance(prob_item, dict):
            prob_item = {"legacy_code": str(prob_item)}

        lc = prob_item.get("legacy_code") or prob_item.get("code") or prob_item.get("pid") or prob_item.get("_id") or prob_item.get("problem_id")
        p_status = str(prob_item.get("status") or "pending").lower()
        p_score = int(prob_item.get("score") or 0)

        prob = None
        if lc:
            prob = session.scalar(select(Problem).where(Problem.legacy_code == str(lc).strip()))
        if prob is None and prob_item.get("server_problem_id"):
            prob = session.scalar(select(Problem).where(Problem.server_problem_id == str(prob_item.get("server_problem_id")).strip()))
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
            legacy_code=str(lc).strip() if lc else None,
            created_at=created_at,
        )
        session.add(asub)

    session.flush()
    return asn


def delete_assignment_rdb(session: Session, log_id_or_key: str) -> bool:
    """
    RDB에서 Assignment 레코드를 삭제 (CASCADE로 하위 AssignmentSubmission 자동 삭제)
    """
    if not log_id_or_key:
        return False
    target = str(log_id_or_key).strip()
    asn = None
    if target.isdigit():
        asn = session.get(Assignment, int(target))
    if asn is None:
        asn = session.scalar(select(Assignment).where(Assignment.log_id == target))
    if asn is not None:
        session.delete(asn)
        session.flush()
        return True
    return False


# ─── 취약 단원 진단 및 문제 추천 ───────────────────────────────────────────

def analyze_user_weakness(session: Session, user_identifier: str) -> list[dict]:
    """
    수강생의 Submission 및 AssignmentSubmission 제출 이력을 소단원(Group) 단위로 집계하여
    취약도 지수(W_G) 및 상태(DANGER, WARNING, GOOD)를 산출합니다.
    """
    user = resolve_user_any(session, user_identifier)
    if not user:
        return []

    # 1. Submission 기반 소단원별 점수/오답 집계
    sub_stats = session.execute(
        select(
            Problem.group_id,
            func.count(Submission.id).label("total_attempts"),
            func.sum(case((Submission.score < 100, 1), else_=0)).label("wrong_count"),
            func.avg(Submission.score).label("avg_score"),
            func.max(Submission.submitted_at).label("last_submitted")
        )
        .join(Problem, Submission.problem_id == Problem.id)
        .where(
            and_(
                Submission.user_id == user.id,
                Problem.group_id.isnot(None),
                Problem.is_unknown == False
            )
        )
        .group_by(Problem.group_id)
    ).all()

    # 2. AssignmentSubmission 기반 집계
    asub_stats = session.execute(
        select(
            Problem.group_id,
            func.count(AssignmentSubmission.id).label("total_attempts"),
            func.sum(case((AssignmentSubmission.score < 100, 1), else_=0)).label("wrong_count"),
            func.avg(AssignmentSubmission.score).label("avg_score")
        )
        .join(Problem, AssignmentSubmission.problem_id == Problem.id)
        .where(
            and_(
                AssignmentSubmission.user_id == user.id,
                Problem.group_id.isnot(None),
                Problem.is_unknown == False
            )
        )
        .group_by(Problem.group_id)
    ).all()

    group_map = {}

    for gid, attempts, wrong, avg_s, last_sub in sub_stats:
        if gid not in group_map:
            group_map[gid] = {"attempts": 0, "wrong": 0, "scores": [], "last_sub": last_sub}
        group_map[gid]["attempts"] += (attempts or 0)
        group_map[gid]["wrong"] += (wrong or 0)
        if avg_s is not None:
            group_map[gid]["scores"].append(float(avg_s))

    for gid, attempts, wrong, avg_s in asub_stats:
        if gid not in group_map:
            group_map[gid] = {"attempts": 0, "wrong": 0, "scores": [], "last_sub": None}
        group_map[gid]["attempts"] += (attempts or 0)
        group_map[gid]["wrong"] += (wrong or 0)
        if avg_s is not None:
            group_map[gid]["scores"].append(float(avg_s))

    if not group_map:
        return []

    group_ids = list(group_map.keys())
    groups = session.scalars(
        select(Group).where(Group.id.in_(group_ids))
    ).all()
    group_obj_map = {g.id: g for g in groups}

    results = []
    now = datetime.now(timezone.utc)

    for gid, data in group_map.items():
        grp = group_obj_map.get(gid)
        if not grp:
            continue

        attempts = data["attempts"]
        wrong = data["wrong"]
        scores = data["scores"]
        avg_score = sum(scores) / len(scores) if scores else 100.0

        recent_bonus = 0
        if data["last_sub"]:
            dt = data["last_sub"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (now - dt).days <= 14:
                recent_bonus = 15

        weakness_score = round((100.0 - avg_score) * 0.6 + (wrong * 10) + recent_bonus, 2)

        if avg_score < 60 or wrong >= 3 or weakness_score >= 50:
            status = "DANGER"
        elif avg_score < 80 or wrong >= 1 or weakness_score >= 25:
            status = "WARNING"
        else:
            status = "GOOD"

        results.append({
            "group_id": grp.id,
            "group_title": grp.title,
            "chapter_id": grp.chapter_id,
            "avg_score": round(avg_score, 1),
            "wrong_count": wrong,
            "total_attempts": attempts,
            "weakness_score": weakness_score,
            "status": status,
        })

    results.sort(key=lambda x: x["weakness_score"], reverse=True)
    return results


def get_recommended_problems(session: Session, user_identifier: str, limit: int = 3) -> list[dict]:
    """
    수강생 식별자를 기반으로 Tier 1 (오답 재도전), Tier 2 (취약 단원 미시도), Tier 3 (기초/연관 단원)
    맞춤 추천 문제를 최대 limit개 반환합니다.
    """
    user = resolve_user_any(session, user_identifier)
    if not user:
        return []

    recommendations = []
    seen_problem_ids = set()

    # 1. 수강생이 맞춘 문제 ID 목록 (100점)
    passed_problem_ids = set(
        session.scalars(
            select(Submission.problem_id)
            .where(and_(Submission.user_id == user.id, Submission.score == 100))
        ).all()
    )
    passed_problem_ids.update(
        session.scalars(
            select(AssignmentSubmission.problem_id)
            .where(and_(AssignmentSubmission.user_id == user.id, AssignmentSubmission.score == 100))
        ).all()
    )

    # Tier 1: 오답 재도전 (과거 시도했으나 100점 미만인 문제)
    wrong_sub_problems = session.scalars(
        select(Problem)
        .join(Submission, Submission.problem_id == Problem.id)
        .where(
            and_(
                Submission.user_id == user.id,
                Submission.score < 100,
                Problem.id.notin_(passed_problem_ids),
                Problem.is_unknown == False
            )
        )
        .order_by(Submission.submitted_at.desc())
        .limit(limit)
    ).all()

    for p in wrong_sub_problems:
        if p.id not in seen_problem_ids:
            seen_problem_ids.add(p.id)
            recommendations.append({
                "problem_id": p.id,
                "legacy_code": p.legacy_code or "",
                "server_problem_id": p.server_problem_id or "",
                "title": p.title or p.legacy_code or f"문제 #{p.id}",
                "tier": 1,
                "reason": "오답 재도전",
                "difficulty": p.difficulty or 1,
            })
        if len(recommendations) >= limit:
            return recommendations

    # Tier 2: 취약 단원 내 미풀이 문항
    weak_groups = analyze_user_weakness(session, user_identifier)
    for wg in weak_groups:
        if wg["status"] in ["DANGER", "WARNING"]:
            g_problems = session.scalars(
                select(Problem)
                .where(
                    and_(
                        Problem.group_id == wg["group_id"],
                        Problem.id.notin_(passed_problem_ids),
                        Problem.id.notin_(seen_problem_ids),
                        Problem.is_unknown == False
                    )
                )
                .order_by(Problem.order_in_group.asc())
                .limit(limit - len(recommendations))
            ).all()

            for p in g_problems:
                if p.id not in seen_problem_ids:
                    seen_problem_ids.add(p.id)
                    recommendations.append({
                        "problem_id": p.id,
                        "legacy_code": p.legacy_code or "",
                        "server_problem_id": p.server_problem_id or "",
                        "title": p.title or p.legacy_code or f"문제 #{p.id}",
                        "tier": 2,
                        "reason": f"취약 단원 보완 ({wg['group_title']})",
                        "difficulty": p.difficulty or 1,
                    })
                if len(recommendations) >= limit:
                    return recommendations

    # Tier 3: 미풀이 기초 문제 fallback
    if len(recommendations) < limit:
        tier3_problems = session.scalars(
            select(Problem)
            .where(
                and_(
                    Problem.id.notin_(passed_problem_ids),
                    Problem.id.notin_(seen_problem_ids),
                    Problem.is_unknown == False
                )
            )
            .order_by(Problem.order_in_group.asc(), Problem.id.asc())
            .limit(limit - len(recommendations))
        ).all()

        for p in tier3_problems:
            if p.id not in seen_problem_ids:
                seen_problem_ids.add(p.id)
                recommendations.append({
                    "problem_id": p.id,
                    "legacy_code": p.legacy_code or "",
                    "server_problem_id": p.server_problem_id or "",
                    "title": p.title or p.legacy_code or f"문제 #{p.id}",
                    "tier": 3,
                    "reason": "개념 응용 추천",
                    "difficulty": p.difficulty or 1,
                })
            if len(recommendations) >= limit:
                break

    return recommendations

