import json, os, re
from typing import Dict, Tuple, List, Optional


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_code(code: str) -> str:
    if not code:
        return ""
    s = str(code).strip().lower()
    m = re.match(r"^([a-z0-9]+)v0*(\d+)$", s)
    return f"{m.group(1)}v{m.group(2)}" if m else s


def build_legacy_map(
    problem_file: str,
    server_dump_path: str,
    out_map_path: Optional[str] = None,  # server→legacy 저장 경로
    out_unmatched_path: Optional[str] = None,  # 미매핑 목록
) -> Tuple[str, str]:
    """
    API의 `_id` = 레거시코드, `id` = 서버PK(정수)로 가정.
    정규화 패턴 매칭 + 제목 기반 2차 매핑 적용.
    저장 형태: '서버ID → 레거시ID' 및 '레거시ID → 서버ID' (legacy_map.json 동시 생성)
    """
    base_dir = os.path.dirname(os.path.abspath(problem_file))
    if not out_map_path:
        out_map_path = os.path.join(
            base_dir, "server_legacy_map.json"
        )
    if not out_unmatched_path:
        out_unmatched_path = os.path.join(base_dir, "legacy_unmatched.json")

    book = _load_json(problem_file)
    dump = _load_json(server_dump_path)
    results = dump.get("results", [])

    # 1. API 다중 인덱스 구축 (정확한 _id, 정규화_id, 제목)
    api_legacy_to_server: Dict[str, str] = {}
    api_norm_to_server: Dict[str, str] = {}
    api_title_to_server: Dict[str, str] = {}

    for p in results:
        legacy = str(p.get("_id") or "").strip()
        sid = p.get("id")
        title = str(p.get("title") or "").strip()

        if sid is not None:
            sid_str = str(sid)
            if legacy:
                api_legacy_to_server[legacy] = sid_str
                norm = _normalize_code(legacy)
                if norm and norm not in api_norm_to_server:
                    api_norm_to_server[norm] = sid_str
            if title and title not in api_title_to_server:
                api_title_to_server[title] = sid_str

    # 2. 최종 매핑 산출물
    server_to_legacy: Dict[str, str] = {}  # 서버ID → 레거시ID
    legacy_to_server: Dict[str, str] = {}  # 레거시ID → 서버ID
    unmatched: List[Dict] = []

    def resolve_sid(legacy_code: str, title: str = "") -> Optional[str]:
        # 1단계: 정확한 legacy_code 매칭
        if legacy_code in api_legacy_to_server:
            return api_legacy_to_server[legacy_code]
        # 2단계: 정규화 숫자 매칭 (예: P101v1531 -> 1531)
        norm = _normalize_code(legacy_code)
        if norm and norm in api_norm_to_server:
            return api_norm_to_server[norm]
        # 3단계: 제목(title) 기반 매칭
        if title and title in api_title_to_server:
            return api_title_to_server[title]
        return None

    # 3. 크롤링된 모든 문제 매핑 실행
    if isinstance(book, dict) and book.get("_schema_version") == 2:
        problems_dict = book.get("problems", {})
        for pid, prob in problems_dict.items():
            if not isinstance(prob, dict):
                continue
            legacy_code = str(prob.get("pid") or pid).strip()
            title = str(prob.get("title") or "").strip()
            sid = resolve_sid(legacy_code, title)

            if sid:
                server_to_legacy[sid] = legacy_code
                legacy_to_server[legacy_code] = sid
            else:
                unmatched.append(
                    {
                        "legacy_code": legacy_code,
                        "title": title,
                        "chapter": prob.get("chapter_id", ""),
                        "group": prob.get("group_id", ""),
                    }
                )
    elif isinstance(book, dict):
        for chap_title, groups in book.items():
            if not isinstance(groups, dict):
                continue
            for group_code, info in groups.items():
                if not isinstance(info, dict):
                    continue
                for legacy_code in (info.get("problem_names") or {}).keys():
                    sid = resolve_sid(legacy_code)
                    if sid:
                        server_to_legacy[sid] = legacy_code
                        legacy_to_server[legacy_code] = sid
                    else:
                        unmatched.append(
                            {
                                "legacy_code": legacy_code,
                                "chapter": chap_title,
                                "group": group_code,
                            }
                        )

    # 4. 저장
    with open(out_map_path, "w", encoding="utf-8") as f:
        json.dump(server_to_legacy, f, ensure_ascii=False, indent=2)

    reverse_path = os.path.join(
        os.path.dirname(out_map_path),
        os.path.splitext(os.path.basename(out_map_path))[0] + "_reverse.json",
    )
    with open(reverse_path, "w", encoding="utf-8") as f:
        json.dump(legacy_to_server, f, ensure_ascii=False, indent=2)

    # legacy_map.json 파일에도 보증 저장
    legacy_map_direct_path = os.path.join(base_dir, "legacy_map.json")
    with open(legacy_map_direct_path, "w", encoding="utf-8") as f:
        json.dump(legacy_to_server, f, ensure_ascii=False, indent=2)

    with open(out_unmatched_path, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)

    return os.path.abspath(out_map_path), os.path.abspath(out_unmatched_path)
