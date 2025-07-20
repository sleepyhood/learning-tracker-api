import json


def summarize_progress(problem_file, solve_file):
    with open(problem_file, "r", encoding="utf-8") as f:
        problem_data = json.load(f)

    with open(solve_file, "r", encoding="utf-8") as f:
        user_solves_raw = json.load(f)

    # ID 기준으로 매핑: P101v0101 → status
    user_solves = {entry["_id"]: entry["status"] for entry in user_solves_raw.values()}

    result = []

    for chapter_name, groups in problem_data.items():
        total = 0
        solved = 0
        wrong = 0
        partial = 0
        group_details = []

        for group_name, group_info in groups.items():
            problems = group_info.get("problem_names", {})
            g_total = len(problems)
            g_solved = g_wrong = g_partial = 0

            for pid in problems:
                status = user_solves.get(pid)
                if status == 0:
                    g_solved += 1
                elif status == -1:
                    g_wrong += 1
                elif status is not None:
                    g_partial += 1

            # 그룹 단위 집계
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

            # 챕터 단위 합산
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
                "groups": group_details,  # 👈 새로 추가된 필드
            }
        )

    return result


def summarize_user_chapter_group(user_data, all_problems, chapter, group_id):
    problem_group_data = all_problems.get(chapter, {}).get(group_id)
    if problem_group_data is None:
        raise KeyError(f"'{chapter}' 챕터 내 '{group_id}' 그룹을 찾을 수 없습니다.")

    problem_names = problem_group_data.get("problem_names", {})  # dict: {pid: title}

    user_status_map = {v["_id"]: v["status"] for v in user_data.values()}

    problems_with_status = []
    for pid, title in problem_names.items():
        status = user_status_map.get(pid, None)
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
                "pid": pid,
                "title": title,
                "status": solved_status,
                "raw_status": status,
            }
        )

    return {
        "group_title": problem_group_data.get("title", ""),
        "problem_names": problems_with_status,
    }
