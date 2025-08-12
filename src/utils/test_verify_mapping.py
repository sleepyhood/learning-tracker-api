# src/utils/verify_mapping.py
import json, os, sys
from collections import defaultdict


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def legacy_to_server_id(legacy_id: str, legacy2server: dict) -> str:
    # 레거시 코드 -> 서버 ID
    return legacy2server.get(legacy_id, legacy_id)


def label(status):
    if status == 0:
        return "solved"
    elif status == -1:
        return "wrong"
    elif status is not None:
        return "partial"
    return "unsolved"


def main(
    problem_file="src/problems_data/all_problems.json",
    # ✅ 파일명 변경: 레거시→서버 맵을 기본으로 받는다
    legacy_to_server_file="src/problems_data/legacy_map_reverse.json",
    user_file=None,
    server_dump_file="src/problems_data/server_problems.json",  # optional consistency check
    show_example=True,
):
    assert os.path.exists(problem_file), f"missing: {problem_file}"
    assert os.path.exists(legacy_to_server_file), f"missing: {legacy_to_server_file}"
    if user_file:
        assert os.path.exists(user_file), f"missing: {user_file}"

    # (옵션) API id 유효성 체크용
    if server_dump_file and os.path.exists(server_dump_file):
        server_dump = load_json(server_dump_file).get("results", [])
        api_ids = {str(p["id"]) for p in server_dump if "id" in p}
    else:
        api_ids = None

    book = load_json(problem_file)
    legacy2server = load_json(legacy_to_server_file)

    # 1) 커버리지: all_problems의 레거시 코드가 legacy2server에 얼마나 존재?
    all_legacy = []
    for chap, groups in book.items():
        for gid, info in groups.items():
            all_legacy.extend(list((info.get("problem_names") or {}).keys()))
    unique_legacy = set(all_legacy)
    covered = {k for k in unique_legacy if k in legacy2server}
    uncovered = sorted(unique_legacy - covered)

    print("=== Legacy → ServerID 매핑 커버리지 ===")
    print(f"총 레거시 문제수: {len(unique_legacy)}")
    print(f"매핑된 문제수  : {len(covered)}")
    print(f"미매핑 문제수  : {len(uncovered)}")
    if uncovered[:10]:
        print(f"  예시 미매핑  : {uncovered[:10]}")
    print()

    # 1-1) (옵션) 매핑 값이 server_problems.json의 id에 존재하는지
    if api_ids is not None:
        bad_values = {k: v for k, v in legacy2server.items() if v not in api_ids}
        print("=== 매핑 값(API id) 유효성 ===")
        print(f"API에 없는 매핑 값 개수: {len(bad_values)}")
        if bad_values:
            sample = list(bad_values.items())[:10]
            print(f"  예시: {sample}")
        print()

    # 2) 학생 풀이 → server_id 기준 status 맵 (바깥 키를 신뢰)
    solves_by_sid = {}
    if user_file:
        user_raw = load_json(user_file)
        for record_key, rec in user_raw.items():
            if not isinstance(rec, dict):
                continue
            sid = str(record_key).strip()  # ✅ 학생 JSON의 바깥 키가 서버ID
            if sid:
                solves_by_sid[sid] = rec.get("status")

        print("=== 학생 풀이 매칭 테스트 ===")
        hit = miss = 0
        per_chapter = defaultdict(lambda: {"matched": 0, "unmatched": 0})

        for chap, groups in book.items():
            for gid, info in groups.items():
                for legacy_pid in (info.get("problem_names") or {}).keys():
                    sid = legacy_to_server_id(
                        legacy_pid, legacy2server
                    )  # ✅ 레거시→서버 변환
                    if sid in solves_by_sid:
                        hit += 1
                        per_chapter[chap]["matched"] += 1
                    else:
                        miss += 1
                        per_chapter[chap]["unmatched"] += 1

        print(f"학생 풀이와 매칭된 문제수: {hit}")
        print(f"학생 풀이와 미매칭 문제수: {miss}")
        for chap, agg in per_chapter.items():
            total = agg["matched"] + agg["unmatched"]
            if total == 0:
                continue
            pct = round(agg["matched"] / total * 100, 1)
            print(f"  - {chap}: {agg['matched']}/{total} ({pct}%)")
        print()

        # 3) 예시 출력 (한 그룹에서 10개만)
        if show_example:
            for chap, groups in book.items():
                for gid, info in groups.items():
                    print("=== 샘플 그룹 상태 ===")
                    print(
                        f"Chapter: {chap} | Group: {gid} | Title: {info.get('title','')}"
                    )
                    rows = []
                    for legacy_pid, title in list(
                        (info.get("problem_names") or {}).items()
                    )[:10]:
                        sid = legacy_to_server_id(legacy_pid, legacy2server)
                        st = solves_by_sid.get(sid, None)
                        rows.append((legacy_pid, sid, label(st), title))
                    print("legacy → server_id | status | title")
                    for legacy_pid, sid, lab, title in rows:
                        print(f"{legacy_pid:>12} → {sid:<6} | {lab:<8} | {title}")
                    print()

                break


if __name__ == "__main__":
    # 인자: user_file은 필요시 지정하세요
    # 예) python -m utils.verify_mapping src/users_data/학생아이디.json

    user_file = r"src/users_data/osw1110.json"
    main(user_file=user_file)
