"""
services/problem_catalog_service.py

문제 카탈로그 관련 순수 비즈니스 로직 계층.
HTTP 요청/응답에 의존하지 않으며, 라우트 핸들러에서 호출됩니다.

담당 기능:
  - 문제 커스텀 메타데이터 CRUD (custom_metadata.json)
  - 커리큘럼 목록 CRUD (curriculum_config.json)
  - Micro-registry 빌드 및 Canonical Key 매칭
  - 문제 검색 필터링 연산
  - 문제 메타데이터 Export / Import
  - 문제 텍스트 파싱 & Batch Add
"""

import json
import os
import re

from config import PROBLEM_DIR

CURRICULUM_CONFIG_FILE = os.path.join(PROBLEM_DIR, "curriculum_config.json")
CUSTOM_METADATA_FILE = os.path.join(PROBLEM_DIR, "problem_custom_metadata.json")


# ─────────────────────────────────────────
# 내부 헬퍼: Custom Metadata I/O
# ─────────────────────────────────────────

def load_problem_custom_metadata() -> dict:
    """problem_custom_metadata.json 파일을 불러옵니다."""
    if os.path.exists(CUSTOM_METADATA_FILE):
        try:
            with open(CUSTOM_METADATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print("[custom_metadata] load error:", e)
    return {}


def save_problem_custom_metadata(data: dict):
    """problem_custom_metadata.json 파일을 저장합니다."""
    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(CUSTOM_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────
# 내부 헬퍼: 정렬 및 Canonical Key
# ─────────────────────────────────────────

def natural_sort_key(text: str):
    """숫자가 섞인 문자열을 자연어 순으로 정렬하기 위한 키 함수."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text or '')]


def make_canonical_key(major: str, sub: str, title: str) -> str:
    """대단원/소단원/제목 조합으로 고유 Canonical Key를 생성합니다."""
    clean_t = re.sub(r'\[.*?\]', '', title or '').strip().lower()
    return f"{(major or '').strip()}:{(sub or '').strip()}:{clean_t}"


# ─────────────────────────────────────────
# Micro-registry 빌드
# ─────────────────────────────────────────

def build_micro_registry(raw_json: dict) -> dict:
    """
    문제 JSON 파일 원본과 custom_metadata를 병합하여
    화면 표시용 Micro-registry를 반환합니다.

    Args:
        raw_json: 문제 JSON 파일의 최상위 dict

    Returns:
        {prob_id: {id, title, concept, major, sub, learning_goal, ...}} 형태의 dict
    """
    registry = {}
    if not isinstance(raw_json, dict):
        return registry

    custom_meta = load_problem_custom_metadata()

    # Canonical Index (2nd-stage Fallback Matching용)
    canonical_index = {}
    for c_id, c_val in custom_meta.items():
        if isinstance(c_val, dict):
            c_maj = c_val.get("major", "")
            c_sub = c_val.get("sub", "")
            c_title = c_val.get("title", "")
            if c_maj or c_sub or c_title:
                ck = make_canonical_key(c_maj, c_sub, c_title)
                canonical_index[ck] = c_val

    dirty_custom_meta = False

    for key, value in raw_json.items():
        if not isinstance(value, dict):
            continue
        if "title" in value and ("major" in value or "concept" in value or "id" in value):
            prob_id = value.get("id") or key
            maj = value.get("major", "기타")
            sub_title = value.get("sub", "일반")
            prob_t = value.get("title", prob_id)
            concept = value.get("concept", "")

            c_entry = custom_meta.get(prob_id)
            if not c_entry:
                ck = make_canonical_key(maj, sub_title, prob_t)
                c_entry = canonical_index.get(ck)
                if c_entry:
                    custom_meta[prob_id] = dict(c_entry)
                    custom_meta[prob_id]["id"] = prob_id
                    c_entry = custom_meta[prob_id]
                    dirty_custom_meta = True

            c_entry = c_entry or {}
            l_goal = c_entry.get("learning_goal") or value.get("learning_goal", "")

            sol_codes = c_entry.get("solution_codes") or value.get("solution_codes") or {}
            if not sol_codes and (c_entry.get("solution_code") or value.get("solution_code")):
                sol_codes = {"c": c_entry.get("solution_code") or value.get("solution_code")}

            registry[prob_id] = {
                "id": prob_id,
                "title": prob_t,
                "concept": c_entry.get("concept") or concept,
                "major": maj,
                "sub": sub_title,
                "learning_goal": l_goal,
                "solution_codes": sol_codes,
                "solution_code": sol_codes.get("c") or sol_codes.get("python") or c_entry.get("solution_code") or "",
                "tags": c_entry.get("tags") or value.get("tags") or []
            }
        else:
            major_ch = key
            for group_id, group_data in value.items():
                if not isinstance(group_data, dict):
                    continue
                sub_title = group_data.get("title", "")
                problem_names = group_data.get("problem_names", {})
                if isinstance(problem_names, dict):
                    for prob_id, prob_title in problem_names.items():
                        concept = ""
                        if "[" in prob_title and "]" in prob_title:
                            concept = prob_title.split("[")[1].split("]")[0]

                        c_entry = custom_meta.get(prob_id)
                        if not c_entry:
                            ck = make_canonical_key(major_ch, sub_title, prob_title)
                            c_entry = canonical_index.get(ck)
                            if c_entry:
                                custom_meta[prob_id] = dict(c_entry)
                                custom_meta[prob_id]["id"] = prob_id
                                c_entry = custom_meta[prob_id]
                                dirty_custom_meta = True

                        c_entry = c_entry or {}
                        l_goal = c_entry.get("learning_goal", "")
                        sol_codes = c_entry.get("solution_codes") or {}
                        if not sol_codes and c_entry.get("solution_code"):
                            sol_codes = {"c": c_entry.get("solution_code")}

                        registry[prob_id] = {
                            "id": prob_id,
                            "title": prob_title,
                            "concept": c_entry.get("concept") or concept,
                            "major": major_ch,
                            "sub": sub_title,
                            "learning_goal": l_goal,
                            "solution_codes": sol_codes,
                            "solution_code": sol_codes.get("c") or sol_codes.get("python") or c_entry.get("solution_code") or "",
                            "tags": c_entry.get("tags") or []
                        }

    if dirty_custom_meta:
        save_problem_custom_metadata(custom_meta)

    # 학습목표 Fallback 보정
    for prob_id, item in registry.items():
        if not item.get("learning_goal"):
            sub_t = item.get("sub")
            maj_t = item.get("major")
            if sub_t and sub_t != "일반":
                item["learning_goal_fallback"] = f"[{sub_t}] 단원 핵심 개념 및 알고리즘 풀이"
            elif maj_t and maj_t != "기타":
                item["learning_goal_fallback"] = f"[{maj_t}] 학습 문제 이해 및 구현"
            else:
                item["learning_goal_fallback"] = "코딩 문제 해결 및 로직 구현"

    return registry


# ─────────────────────────────────────────
# 커리큘럼 목록 I/O
# ─────────────────────────────────────────

_DEFAULT_CURRICULUMS = [
    {"key": "prog1", "name": "💻 프로그래밍 I (기초/기본)", "url": "http://edu.doingcoding.com/p101", "file": "all_problems.json"},
    {"key": "prog2", "name": "💻 프로그래밍 II (심화)", "url": "http://edu.doingcoding.com/p102", "file": "prog2_problems.json"},
    {"key": "block", "name": "🧩 블록코딩 활동", "url": "", "file": "block_problems.json"},
    {"key": "external", "name": "📘 외부 교재 / 자격증", "url": "", "file": "external_problems.json"},
]


def load_curriculum_configs() -> list:
    """curriculum_config.json에서 커리큘럼 목록을 불러옵니다. 없으면 기본값 반환."""
    if os.path.exists(CURRICULUM_CONFIG_FILE):
        try:
            with open(CURRICULUM_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return list(_DEFAULT_CURRICULUMS)


def save_curriculum_configs(configs: list):
    """curriculum_config.json에 커리큘럼 목록을 저장합니다."""
    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(CURRICULUM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def load_registry_for_curriculum(curr_key: str, configs: list) -> dict:
    """
    커리큘럼 키로부터 문제 JSON을 로드하고 build_micro_registry를 실행합니다.

    Returns:
        registry dict (문제 ID → 문제 정보)
    """
    target_config = next((c for c in configs if c.get("key") == curr_key), None)
    if not target_config:
        return {}
    target_file = os.path.join(PROBLEM_DIR, target_config.get("file", f"{curr_key}_problems.json"))
    if not os.path.exists(target_file):
        return {}
    try:
        with open(target_file, encoding="utf-8") as f:
            return build_micro_registry(json.load(f))
    except Exception as e:
        print(f"[catalog_service] registry load error ({target_file}):", e)
        return {}


# ─────────────────────────────────────────
# 문제 검색 연산
# ─────────────────────────────────────────

def search_problems_in_registry(
    registry: dict,
    q: str,
    chapter_filter: str,
    sub_filter: str,
    solved_set: set,
    wrong_set: set,
    curr_key: str,
    target_config: dict | None,
    limit: int,
) -> tuple[list, dict]:
    """
    registry에서 검색 조건에 맞는 문제 목록과 챕터 트리를 반환합니다.

    Returns:
        (results: list, chapters_tree: dict)
    """
    chapters_tree: dict[str, set] = {}
    for p_id, item in registry.items():
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")
        if maj not in chapters_tree:
            chapters_tree[maj] = set()
        chapters_tree[maj].add(sub_title)

    formatted_tree = {m: sorted(list(subs), key=natural_sort_key) for m, subs in chapters_tree.items()}

    results = []
    for p_id, item in registry.items():
        title = item.get("title", "")
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")
        concept = item.get("concept", "")

        if chapter_filter != "all" and maj != chapter_filter:
            continue
        if sub_filter != "all" and sub_title != sub_filter:
            continue

        if q and q != "all":
            match_q = (
                (q in p_id.lower())
                or (q in title.lower())
                or (q in maj.lower())
                or (q in sub_title.lower())
                or (q in concept.lower())
            )
            if not match_q:
                continue

        status = "normal"
        if p_id in solved_set:
            status = "solved"
        elif p_id in wrong_set:
            status = "wrong"

        ch_code = item.get("chapter_code") or item.get("chapter_id")
        if not ch_code and target_config and target_config.get("url"):
            url_str = target_config.get("url", "")
            match = re.search(r'doingcoding\.com/([^/?#]+)', url_str)
            if match:
                ch_code = match.group(1)
        if not ch_code:
            ch_code = "p101" if curr_key == "prog1" else ("p102" if curr_key == "prog2" else curr_key)

        results.append({
            "legacy_code": p_id,
            "title": title,
            "concept": concept,
            "major": maj,
            "sub": sub_title,
            "group_title": sub_title,
            "chapter_code": ch_code,
            "curriculum": curr_key,
            "learning_goal": item.get("learning_goal", ""),
            "learning_goal_fallback": item.get("learning_goal_fallback", ""),
            "tags": item.get("tags", []),
            "status": status,
        })

        if len(results) >= limit:
            break

    return results, formatted_tree


# ─────────────────────────────────────────
# 문제 메타데이터 업데이트
# ─────────────────────────────────────────

def update_problem_metadata(items_to_update: list) -> int:
    """
    문제 메타데이터 목록을 받아 custom_metadata에 반영하고 저장합니다.

    Returns:
        updated_count: 업데이트된 항목 수
    """
    custom_meta = load_problem_custom_metadata()
    updated_count = 0

    for item in items_to_update:
        pid = str(item.get("prob_id") or item.get("id") or "").strip()
        if not pid:
            continue

        entry = custom_meta.setdefault(pid, {})
        entry["id"] = pid
        if "learning_goal" in item:
            entry["learning_goal"] = str(item["learning_goal"]).strip()
        if "concept" in item:
            entry["concept"] = str(item["concept"]).strip()
        if "tags" in item and isinstance(item["tags"], list):
            entry["tags"] = [str(t).strip() for t in item["tags"] if t]

        if "solution_codes" in item and isinstance(item["solution_codes"], dict):
            entry_sol = entry.setdefault("solution_codes", {})
            for lang_k, code_v in item["solution_codes"].items():
                if code_v is not None:
                    entry_sol[str(lang_k).lower().strip()] = str(code_v).strip()
        elif "solution_code" in item and item["solution_code"] is not None:
            code_str = str(item["solution_code"]).strip()
            lang_key = str(item.get("lang") or "c").lower().strip()
            entry_sol = entry.setdefault("solution_codes", {})
            entry_sol[lang_key] = code_str
            entry["solution_code"] = code_str

        updated_count += 1

    save_problem_custom_metadata(custom_meta)
    return updated_count


# ─────────────────────────────────────────
# 문제 메타데이터 Export
# ─────────────────────────────────────────

def export_problem_metadata(registry: dict, major_filter: str, sub_filter: str) -> tuple[list, dict]:
    """
    registry에서 필터 조건에 맞는 문제 목록을 Export 형식으로 반환합니다.

    Returns:
        (export_list, formatted_tree)
    """
    chapters_tree: dict[str, set] = {}
    export_list = []

    for pid, item in registry.items():
        maj = item.get("major", "기타")
        sub_title = item.get("sub", "일반")

        if maj not in chapters_tree:
            chapters_tree[maj] = set()
        chapters_tree[maj].add(sub_title)

        if major_filter != "all" and maj != major_filter:
            continue
        if sub_filter != "all" and sub_title != sub_filter:
            continue

        sol_codes = item.get("solution_codes") or {}
        export_list.append({
            "id": pid,
            "title": item.get("title", ""),
            "major": maj,
            "sub": sub_title,
            "concept": item.get("concept", ""),
            "learning_goal": item.get("learning_goal", ""),
            "learning_goal_fallback": item.get("learning_goal_fallback", ""),
            "solution_codes": sol_codes,
            "solution_code": item.get("solution_code", ""),
        })

    formatted_tree = {m: sorted(list(subs), key=natural_sort_key) for m, subs in chapters_tree.items()}
    return export_list, formatted_tree


# ─────────────────────────────────────────
# 문제 메타데이터 Import
# ─────────────────────────────────────────

def import_problem_metadata(raw_text: str, problems_arr: list) -> int:
    """
    TSV 텍스트 또는 JSON 배열로부터 문제 메타데이터를 가져와 저장합니다.

    Returns:
        updated_count: 처리된 항목 수
    """
    custom_meta = load_problem_custom_metadata()
    updated_count = 0

    if raw_text:
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                pid = parts[0].strip()
                l_goal = parts[1].strip()
                concept = parts[2].strip() if len(parts) >= 3 else ""
                sol_c = parts[3].strip() if len(parts) >= 4 else ""
                sol_py = parts[4].strip() if len(parts) >= 5 else ""

                entry = custom_meta.setdefault(pid, {})
                entry["id"] = pid
                entry["learning_goal"] = l_goal
                if concept:
                    entry["concept"] = concept
                if sol_c or sol_py:
                    entry_sol = entry.setdefault("solution_codes", {})
                    if sol_c:
                        entry_sol["c"] = sol_c
                    if sol_py:
                        entry_sol["python"] = sol_py
                updated_count += 1

    for item in problems_arr:
        if isinstance(item, dict):
            pid = str(item.get("id") or item.get("prob_id") or "").strip()
            if not pid:
                continue
            l_goal = str(item.get("learning_goal") or "").strip()
            concept = str(item.get("concept") or "").strip()
            sol_codes = item.get("solution_codes")

            entry = custom_meta.setdefault(pid, {})
            entry["id"] = pid
            if l_goal:
                entry["learning_goal"] = l_goal
            if concept:
                entry["concept"] = concept
            if isinstance(sol_codes, dict):
                entry["solution_codes"] = sol_codes
            elif item.get("solution_code"):
                entry.setdefault("solution_codes", {})["c"] = str(item["solution_code"]).strip()
            updated_count += 1

    save_problem_custom_metadata(custom_meta)
    return updated_count


# ─────────────────────────────────────────
# 문제 Batch Add
# ─────────────────────────────────────────

def batch_add_problems(key: str, major: str, sub: str, raw_text: str, configs: list) -> tuple[int, int]:
    """
    텍스트 형식의 문제 목록을 파싱하여 지정된 커리큘럼 JSON 파일에 추가합니다.

    Returns:
        (added_count, total_count)
    """
    target = next((c for c in configs if c.get("key") == key), None)
    if not target:
        raise ValueError(f"Invalid curriculum key: {key}")

    target_file = os.path.join(PROBLEM_DIR, target.get("file", f"{key}_problems.json"))
    current_data = {}
    if os.path.exists(target_file):
        try:
            with open(target_file, encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            current_data = {}

    added_count = 0
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            prob_id, prob_title = parts[0].strip(), parts[1].strip()
        else:
            prob_id = parts[0].strip()
            prob_title = prob_id

        concept = ""
        if "[" in prob_title and "]" in prob_title:
            concept = prob_title.split("[")[1].split("]")[0]

        current_data[prob_id] = {
            "id": prob_id,
            "title": prob_title,
            "concept": concept,
            "major": major,
            "sub": sub,
        }
        added_count += 1

    os.makedirs(PROBLEM_DIR, exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

    return added_count, len(current_data)
