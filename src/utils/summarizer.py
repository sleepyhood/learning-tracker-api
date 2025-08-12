# summarize_progress.py
import json


def _load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _legacy_to_server_id(legacy_id: str, legacy_to_server: dict) -> str:
    # 레거시 코드 → 서버 ID
    return legacy_to_server.get(legacy_id, legacy_id)


def summarize_progress(problem_file, solve_file, legacy_map_file=None):
    problem_data = _load_json(problem_file)
    user_solves_raw = _load_json(solve_file)
    legacy_map = _load_json(legacy_map_file) if legacy_map_file else {}

    # 학생기록 → server_id 기준 status 맵
    #
    solves_by_sid = {}
    for record_key, rec in user_solves_raw.items():
        # 바깥 키가 서버 문제 ID (신뢰 소스)
        sid = str(record_key).strip()
        if not sid or not isinstance(rec, dict):
            continue
        solves_by_sid[sid] = rec.get("status")

    result = []
    for chapter_name, groups in problem_data.items():
        total = solved = wrong = partial = 0
        group_details = []

        for group_name, group_info in groups.items():
            problems = group_info.get("problem_names", {})
            g_total = len(problems)
            g_solved = g_wrong = g_partial = 0

            for legacy_pid in problems.keys():
                sid = _legacy_to_server_id(
                    legacy_pid, legacy_map
                )  # (= legacy_to_server)
                status = solves_by_sid.get(sid)
                if status == 0:
                    g_solved += 1
                elif status == -1:
                    g_wrong += 1
                elif status is not None:
                    g_partial += 1
                # None → 미풀이

            group_details.append(
                {
                    "group": group_name,
                    "title": group_info.get("title", ""),
                    "solved": g_solved,
                    "partial": g_partial,
                    "wrong": g_wrong,
                    "total": g_total,
                    "percent": round(g_solved / g_total * 100, 1) if g_total else 0,
                }
            )

            total += g_total
            solved += g_solved
            wrong += g_wrong
            partial += g_partial

        percent = round(solved / total * 100, 1) if total else 0
        result.append(
            {
                "chapter": chapter_name,
                "solved": solved,
                "partial": partial,
                "wrong": wrong,
                "total": total,
                "percent": percent,
                "groups": group_details,
            }
        )
    return result


def summarize_user_chapter_group(
    user_data, all_problems, chapter, group_id, legacy_map=None
):
    legacy_map = legacy_map or {}
    problem_group_data = all_problems.get(chapter, {}).get(group_id)
    if problem_group_data is None:
        raise KeyError(f"'{chapter}' 챕터 내 '{group_id}' 그룹을 찾을 수 없습니다.")

    problem_chapter_id = problem_group_data.get("chapter_id")  # URL용
    problem_names = problem_group_data.get("problem_names", {})

    # 학생기록 status 맵(server_id 기준)
    user_status_map = {}
    for record_key, rec in user_data.items():
        sid = str(record_key).strip()  # 서버ID
        if not sid or not isinstance(rec, dict):
            continue
        user_status_map[sid] = rec.get("status")

    problems_with_status = []
    for legacy_pid, title in problem_names.items():
        sid = _legacy_to_server_id(legacy_pid, legacy_map)
        status = user_status_map.get(sid, None)
        if status == 0:
            solved_status = "solved"
        elif status == -1:
            solved_status = "wrong"
        elif status is not None:
            solved_status = "partial"
        else:
            solved_status = "unsolved"

        problems_with_status.append(
            {
                "pid": legacy_pid,  # 화면표시는 그대로 레거시코드
                "title": title,
                "status": solved_status,
                "raw_status": status,
            }
        )

    return {
        "problem_chapter_id": problem_chapter_id,
        "group_title": problem_group_data.get("title", ""),
        "problem_names": problems_with_status,
    }
