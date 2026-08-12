# summarize_progress.py
import json


def _load_json(p):
    if isinstance(p, dict):
        return p
    if not p or not isinstance(p, str):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _legacy_to_server_id(legacy_id: str, legacy_to_server: dict) -> str:
    return legacy_to_server.get(legacy_id, legacy_id)


def _normalize_code(code: str) -> str:
    if not code:
        return ""
    import re
    s = str(code).strip().lower()
    m = re.match(r"^([a-z0-9]+)v0*(\d+)$", s)
    return f"{m.group(1)}v{m.group(2)}" if m else s


def _ensure_v2_schema(problem_data: dict) -> dict:
    """Converts V1 nested dict or Playwright flat micro-registry to Schema V2 flat schema on-the-fly."""
    if not isinstance(problem_data, dict):
        return {"_schema_version": 2, "chapters": [], "groups": {}, "problems": {}}

    if problem_data.get("_schema_version") == 2:
        return problem_data

    # Check if problem_data is a flat micro-registry e.g. {"P101v0101": {"title": ..., "major": ...}}
    is_micro_registry = False
    for v in problem_data.values():
        if isinstance(v, dict) and ("major" in v or "title" in v) and "problem_names" not in v:
            is_micro_registry = True
            break

    if is_micro_registry:
        chapters_dict = {}
        groups = {}
        problems = {}
        group_map = {}

        for key, item in problem_data.items():
            if not isinstance(item, dict) or "title" not in item:
                continue
            pid = item.get("id") or item.get("pid") or key
            title = item.get("title", pid)
            major = item.get("major") or "기타 대단원"
            sub = item.get("sub") or "기타 소단원"

            pair = (major, sub)
            if pair not in group_map:
                gid = item.get("group_id") or f"G_{abs(hash(pair)) % 1000000:06d}"
                group_map[pair] = gid
                groups[gid] = {
                    "chapter_id": major,
                    "chapter_code": "p101",
                    "title": sub,
                    "total": 0,
                    "problem_ids": []
                }
                if major not in chapters_dict:
                    chapters_dict[major] = []
                chapters_dict[major].append(gid)

            gid = group_map[pair]
            groups[gid]["problem_ids"].append(pid)
            groups[gid]["total"] += 1

            problems[pid] = {
                "pid": pid,
                "group_id": gid,
                "chapter_id": major,
                "title": title
            }

        chapters = []
        for order, (major_name, g_ids) in enumerate(chapters_dict.items(), start=1):
            chapters.append({
                "id": major_name,
                "name": major_name,
                "order": order,
                "group_ids": g_ids
            })

        return {
            "_schema_version": 2,
            "chapters": chapters,
            "groups": groups,
            "problems": problems
        }

    # V1 -> V2 on-the-fly conversion
    chapters = []
    groups = {}
    problems = {}
    chapter_order = 0

    for chapter_name, groups_dict in problem_data.items():
        if not isinstance(groups_dict, dict):
            continue
        chapter_order += 1
        group_ids_in_chapter = []

        for group_id, group_info in groups_dict.items():
            if not isinstance(group_info, dict):
                continue
            group_ids_in_chapter.append(group_id)
            prob_names = group_info.get("problem_names", {})
            prob_ids_in_group = list(prob_names.keys())

            groups[group_id] = {
                "chapter_id": chapter_name,
                "chapter_code": group_info.get("chapter_id", ""),
                "title": group_info.get("title", ""),
                "total": group_info.get("total", len(prob_ids_in_group)),
                "problem_ids": prob_ids_in_group,
            }

            for pid, title in prob_names.items():
                problems[pid] = {
                    "pid": pid,
                    "group_id": group_id,
                    "chapter_id": chapter_name,
                    "title": title,
                }

        chapters.append(
            {
                "id": chapter_name,
                "name": chapter_name,
                "order": chapter_order,
                "group_ids": group_ids_in_chapter,
            }
        )

    return {
        "_schema_version": 2,
        "chapters": chapters,
        "groups": groups,
        "problems": problems,
    }


def summarize_progress(problem_file, solve_file, legacy_map_file=None):
    problem_raw = _load_json(problem_file)
    v2_data = _ensure_v2_schema(problem_raw)
    user_solves_raw = _load_json(solve_file)
    legacy_map = _load_json(legacy_map_file) if legacy_map_file else {}

    solves_by_sid = {}
    solves_by_norm = {}
    solves_by_title = {}

    if isinstance(user_solves_raw, dict):
        for record_key, rec in user_solves_raw.items():
            if not isinstance(rec, dict):
                continue
            st = rec.get("status")
            sid = str(record_key).strip()
            if sid:
                solves_by_sid[sid] = st
                norm = _normalize_code(sid)
                if norm:
                    solves_by_norm[norm] = st
            _id = str(rec.get("_id", "")).strip()
            if _id:
                solves_by_sid[_id] = st
                norm = _normalize_code(_id)
                if norm:
                    solves_by_norm[norm] = st
            legacy_code = str(rec.get("legacy_code", "")).strip()
            if legacy_code:
                solves_by_sid[legacy_code] = st
                norm = _normalize_code(legacy_code)
                if norm:
                    solves_by_norm[norm] = st
            title = str(rec.get("title") or rec.get("problem_title") or "").strip()
            if title:
                solves_by_title[title] = st

    def resolve_status(legacy_pid: str, p_title: str = ""):
        sid = _legacy_to_server_id(legacy_pid, legacy_map)
        st = solves_by_sid.get(sid)
        if st is not None:
            return st
        st = solves_by_sid.get(legacy_pid)
        if st is not None:
            return st
        norm = _normalize_code(legacy_pid)
        if norm and norm in solves_by_norm:
            return solves_by_norm[norm]
        if p_title and p_title in solves_by_title:
            return solves_by_title[p_title]
        return None

    result = []
    groups_dict = v2_data.get("groups", {})

    for ch in v2_data.get("chapters", []):
        chapter_name = ch.get("name") or ch.get("id")
        total = solved = wrong = partial = 0
        group_details = []

        for group_id in ch.get("group_ids", []):
            g_info = groups_dict.get(group_id, {})
            prob_ids = g_info.get("problem_ids", [])
            g_total = len(prob_ids)
            g_solved = g_wrong = g_partial = 0

            for legacy_pid in prob_ids:
                p_item = v2_data.get("problems", {}).get(legacy_pid, {})
                p_title = p_item.get("title", "")
                status = resolve_status(legacy_pid, p_title)

                if status == 0:
                    g_solved += 1
                elif status == -1:
                    g_wrong += 1
                elif status is not None:
                    g_partial += 1

            group_details.append(
                {
                    "group_id": group_id,
                    "title": g_info.get("title", ""),
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
    v2_data = _ensure_v2_schema(all_problems)

    groups_dict = v2_data.get("groups", {})
    problems_dict = v2_data.get("problems", {})

    group_info = groups_dict.get(group_id)
    if group_info is None:
        raise KeyError(f"'{chapter}' 챕터 내 '{group_id}' 그룹을 찾을 수 없습니다.")

    problem_chapter_id = group_info.get("chapter_code", "")
    prob_ids = group_info.get("problem_ids", [])

    user_status_map = {}
    if isinstance(user_data, dict):
        for record_key, rec in user_data.items():
            sid = str(record_key).strip()
            if not sid or not isinstance(rec, dict):
                continue
            user_status_map[sid] = rec.get("status")

    problems_with_status = []
    for legacy_pid in prob_ids:
        p_item = problems_dict.get(legacy_pid, {})
        title = p_item.get("title", legacy_pid)
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
                "pid": legacy_pid,
                "title": title,
                "status": solved_status,
                "raw_status": status,
            }
        )

    return {
        "problem_chapter_id": problem_chapter_id,
        "group_title": group_info.get("title", ""),
        "problem_names": problems_with_status,
    }


def summarize_drilldown_progress(problem_file, solve_file, legacy_map_file=None):
    """
    Returns a complete 3-level hierarchical drilldown structure:
    [
      {
        "chapter": "1. 기초문법1",
        "solved": 188, "partial": 0, "wrong": 1, "total": 660, "percent": 28.5,
        "groups": [
          {
            "group_id": "P101v01", "title": "Lv1 출력",
            "solved": 20, "partial": 0, "wrong": 0, "total": 20, "percent": 100.0,
            "problems": [
              {
                "pid": "P101v0101",
                "title": "01. [출력-기본1] Hello 출력",
                "status": "solved",
                "raw_status": 0,
                "url": "http://edu.doingcoding.com/problem/P101v0101"
              }, ...
            ]
          }, ...
        ]
      }, ...
    ]
    """
    problem_raw = _load_json(problem_file)
    v2_data = _ensure_v2_schema(problem_raw)

    user_solves_raw = _load_json(solve_file)
    legacy_map = _load_json(legacy_map_file) if legacy_map_file else {}

    solves_by_sid = {}
    if isinstance(user_solves_raw, dict):
        for record_key, rec in user_solves_raw.items():
            if not isinstance(rec, dict):
                continue
            st = rec.get("status")
            sid = str(record_key).strip()
            if sid:
                solves_by_sid[sid] = st
            _id = str(rec.get("_id", "")).strip()
            if _id:
                solves_by_sid[_id] = st
            legacy_code = str(rec.get("legacy_code", "")).strip()
            if legacy_code:
                solves_by_sid[legacy_code] = st

    result = []
    groups_dict = v2_data.get("groups", {})
    problems_dict = v2_data.get("problems", {})

    for ch in v2_data.get("chapters", []):
        chapter_name = ch.get("name") or ch.get("id")
        total = solved = wrong = partial = 0
        group_details = []

        for group_id in ch.get("group_ids", []):
            g_info = groups_dict.get(group_id, {})
            prob_ids = g_info.get("problem_ids", [])
            g_total = len(prob_ids)
            g_solved = g_wrong = g_partial = 0
            problems_in_group = []

            for legacy_pid in prob_ids:
                p_item = problems_dict.get(legacy_pid, {})
                p_title = p_item.get("title", legacy_pid)
                sid = _legacy_to_server_id(legacy_pid, legacy_map)
                status = solves_by_sid.get(sid)
                if status is None:
                    status = solves_by_sid.get(legacy_pid)

                if status == 0:
                    g_solved += 1
                    solved_status = "solved"
                elif status == -1:
                    g_wrong += 1
                    solved_status = "wrong"
                elif status is not None:
                    g_partial += 1
                    solved_status = "partial"
                else:
                    solved_status = "unsolved"

                problems_in_group.append({
                    "pid": legacy_pid,
                    "title": p_title,
                    "status": solved_status,
                    "raw_status": status,
                    "url": f"http://edu.doingcoding.com/problem/{legacy_pid}"
                })

            group_details.append({
                "group_id": group_id,
                "title": g_info.get("title", ""),
                "solved": g_solved,
                "partial": g_partial,
                "wrong": g_wrong,
                "total": g_total,
                "percent": round(g_solved / g_total * 100, 1) if g_total else 0,
                "problems": problems_in_group
            })

            total += g_total
            solved += g_solved
            wrong += g_wrong
            partial += g_partial

        percent = round(solved / total * 100, 1) if total else 0
        result.append({
            "chapter": chapter_name,
            "solved": solved,
            "partial": partial,
            "wrong": wrong,
            "total": total,
            "percent": percent,
            "groups": group_details
        })

    return result
