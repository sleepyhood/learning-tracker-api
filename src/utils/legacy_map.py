import json, os
from typing import Dict, Tuple, List, Optional


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_legacy_map(
    problem_file: str,
    server_dump_path: str,
    out_map_path: Optional[str] = None,  # server→legacy 저장 경로
    out_unmatched_path: Optional[str] = None,  # 미매핑 목록
) -> Tuple[str, str]:
    """
    API의 `_id` = 레거시코드, `id` = 서버PK(정수)로 가정.
    저장 형태를 '서버ID → 레거시ID' 로 변경.
    (추가로 같은 폴더에 'legacy_to_server' 역방향 맵도 함께 저장)
    """
    base_dir = os.path.dirname(os.path.abspath(problem_file))
    if not out_map_path:
        out_map_path = os.path.join(
            base_dir, "server_legacy_map.json"
        )  # ← 파일명도 구분 추천
    if not out_unmatched_path:
        out_unmatched_path = os.path.join(base_dir, "legacy_unmatched.json")

    book = _load_json(problem_file)
    dump = _load_json(server_dump_path)
    results = dump.get("results", [])

    # API 인덱스: 레거시(_id) -> 서버ID(str(id))
    api_legacy_to_server: Dict[str, str] = {}
    for p in results:
        legacy = str(p.get("_id") or "").strip()
        sid = p.get("id")
        if legacy and sid is not None:
            api_legacy_to_server[legacy] = str(sid)

    # 최종 산출물
    server_to_legacy: Dict[str, str] = {}  # ✅ 주 저장물
    legacy_to_server: Dict[str, str] = {}  # 보조(역방향도 함께 저장)
    unmatched: List[Dict] = []

    # 크롤링된 모든 레거시코드를 API 인덱스에서 찾아 매핑
    for chap_title, groups in book.items():
        for group_code, info in groups.items():
            for legacy_code in (info.get("problem_names") or {}).keys():
                sid = api_legacy_to_server.get(legacy_code)
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

    # 저장
    with open(out_map_path, "w", encoding="utf-8") as f:
        json.dump(server_to_legacy, f, ensure_ascii=False, indent=2)

    # 역방향 맵도 같은 폴더에 보관(이름은 자동 생성)
    reverse_path = os.path.join(
        os.path.dirname(out_map_path),
        os.path.splitext(os.path.basename(out_map_path))[0] + "_reverse.json",
    )
    with open(reverse_path, "w", encoding="utf-8") as f:
        json.dump(legacy_to_server, f, ensure_ascii=False, indent=2)

    with open(out_unmatched_path, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)

    return os.path.abspath(out_map_path), os.path.abspath(out_unmatched_path)
