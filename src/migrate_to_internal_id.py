#!/usr/bin/env python3
"""
migrate_to_internal_id.py

외부 ID/핸들로 이름 붙인 유저 JSON 파일들을
내부 사용자 ID(예: u_<UUID4>) 기반 구조로 마이그레이션합니다.

- 각 JSON에 "schema_version": 1, "internal_user_id": "<uuid>" 필드를 보장
- 외부 계정 정보가 없으면 (site, handle)을 추정해 external_accounts 배열을 채움
- 새 레이아웃으로 저장:
    users/by_internal/<internal_id>.json
    submissions/<internal_id>.json   (제출 파일이 있다면)
- 매핑 로그를 JSONL로 추가:
    mapping/external_accounts.jsonl   (한 줄당 하나의 매핑 레코드)

기본은 드라이런(미적용). 실제 적용하려면 --no-dry-run.

예시:
  python migrate_to_internal_id.py \
    --root . \
    --users-dir users_data \
    --submissions-dir submissions_data \
    --site doingcoding \
    --backup \
    --no-dry-run
"""

from pathlib import Path
import json
import uuid
import shutil
import argparse
import datetime
import os
from typing import Optional, Dict, Any, Tuple

# ---------- 유틸 ----------


def iso_now_local() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to read JSON: {path} ({e})")
        return None


def atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # 동일 파일시스템 내 원자적 교체


def gen_internal_id() -> str:
    return f"u_{uuid.uuid4().hex}"


def normalize_handle(s: str) -> str:
    return str(s).strip().casefold()


def guess_external_from_payload(
    payload: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:

    # ⬇️ 이 줄 추가
    if not isinstance(payload, dict):
        return None, None
    # 아래 기존 로직 그대로...
    """
    JSON 모양이 제각각일 수 있어 가능한 여러 패턴을 시도.
    반환: (site, handle_or_server_id)
    """
    # 1) 권장 형태: external_accounts 리스트
    ext = payload.get("external_accounts")
    if isinstance(ext, list) and ext:
        first = ext[0]
        site = first.get("site")
        handle = first.get("handle") or first.get("server_user_id")
        if site and handle:
            return site, str(handle)

    # 2) 흔한 대체 키들
    for key in ("doingcoding_handle", "boj_handle", "username", "user_id", "handle"):
        if key in payload:
            return None, str(payload[key])

    # 3) 실패
    return None, None


def write_mapping_line(
    mapping_path: Path, internal_id: str, site: str, handle: str
) -> None:
    rec = {
        "internal_user_id": internal_id,
        "site": site,
        "handle": handle,
        "generated_at": iso_now_local(),
        "source": "migration_script",
    }
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------- 마이그레이션 본체 ----------


def migrate_users(
    users_dir: Path,
    dest_users_dir: Path,
    mapping_path: Path,
    default_site: str,
    dry_run: bool,
    backup: bool,
) -> None:
    print(f"[INFO] Migrating users from {users_dir} -> {dest_users_dir}")
    files = sorted(p for p in users_dir.glob("*.json") if p.is_file())
    if not files:
        print("[INFO] No user json files found.")
        return

    for src in files:
        payload = load_json(src) or {}
        # ⬇️ 이 두 줄 추가
        if not isinstance(payload, dict):
            payload = {"data": payload} if payload is not None else {}
        site, handle = guess_external_from_payload(payload)
        if not handle:
            # 파일명에서 유추
            handle = src.stem
        if not site:
            site = default_site

        # 내부 ID 보장
        internal_id = payload.get("internal_user_id") or gen_internal_id()

        # 헤더/배열 보강
        payload.setdefault("schema_version", 1)
        payload["internal_user_id"] = internal_id
        ext = payload.get("external_accounts")
        if not isinstance(ext, list):
            payload["external_accounts"] = [{"site": site, "handle": handle}]
        else:
            # (site, handle) 포함 보장
            norm_set = {
                (e.get("site"), normalize_handle(e.get("handle", "")))
                for e in ext
                if isinstance(e, dict)
            }
            if (site, normalize_handle(handle)) not in norm_set:
                payload["external_accounts"].append({"site": site, "handle": handle})

        dest = dest_users_dir / f"{internal_id}.json"

        print(
            f"[USER] {src.name} -> {dest.name}  (site={site}, handle={handle}, internal_id={internal_id})"
        )
        if dry_run:
            continue

        if backup:
            bak = src.with_suffix(".json.bak")
            if not bak.exists():
                shutil.copy2(src, bak)

        # 새 위치에 원자적으로 기록
        atomic_write_json(dest, payload)

        # 원본 삭제(경로가 다르면)
        if src.resolve() != dest.resolve():
            try:
                src.unlink()
            except Exception as e:
                print(f"[WARN] Could not delete old file {src}: {e}")

        # 매핑 로그 추가
        write_mapping_line(mapping_path, internal_id, site, handle)


def migrate_submissions(
    submissions_dir: Path,
    dest_dir: Path,
    mapping_path: Path,
    default_site: str,
    dry_run: bool,
    backup: bool,
) -> None:
    """
    제출 파일이 <외부핸들>.json 형태라면,
    매핑 로그를 읽어 <내부ID>.json으로 바꿔 이동.
    """
    if not submissions_dir.exists():
        print(f"[INFO] Submissions dir not found: {submissions_dir} (skipping)")
        return

    # 매핑 파일로 핸들→내부ID 인덱스 구성
    handle_to_internal = {}
    if mapping_path.exists():
        with mapping_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    site = rec.get("site") or default_site
                    handle = rec.get("handle")
                    internal = rec.get("internal_user_id")
                    if site and handle and internal:
                        handle_to_internal[(site, normalize_handle(handle))] = internal
                except Exception:
                    continue

    print(f"[INFO] Migrating submissions from {submissions_dir} -> {dest_dir}")
    files = sorted(p for p in submissions_dir.glob("*.json") if p.is_file())
    for src in files:
        handle = src.stem
        internal = handle_to_internal.get((default_site, normalize_handle(handle)))
        if not internal:
            print(f"[WARN] No mapping for submissions file {src.name}; skipping.")
            continue

        dest = dest_dir / f"{internal}.json"
        print(f"[SUBM] {src.name} -> {dest.name}")
        if dry_run:
            continue

        if backup:
            bak = src.with_suffix(".json.bak")
            if not bak.exists():
                shutil.copy2(src, bak)

        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dest)  # 이동(원자적 교체)


# ---------- CLI ----------


def main():
    ap = argparse.ArgumentParser(
        description="JSON 파일을 내부 사용자 ID 기반 구조로 마이그레이션"
    )
    ap.add_argument("--root", type=str, default=".", help="프로젝트 루트")
    ap.add_argument(
        "--users-dir", type=str, default="users_data", help="유저 JSON 디렉터리"
    )
    ap.add_argument(
        "--submissions-dir",
        type=str,
        default="submissions_data",
        help="제출 JSON 디렉터리(선택)",
    )
    ap.add_argument(
        "--site", type=str, default="doingcoding", help="기본 사이트 네임스페이스"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="실제 변경 없이 동작만 출력(기본)"
    )
    ap.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="실제 적용 모드"
    )
    ap.add_argument("--backup", action="store_true", help=".bak 백업 생성 후 처리")
    # ... argparse 인자 정의들 바로 아래에 추가
    ap.set_defaults(dry_run=True)

    args = ap.parse_args()

    root = Path(args.root).resolve()
    users_dir = (root / args.users_dir).resolve()
    submissions_dir = (root / args.submissions_dir).resolve()

    dest_users_dir = root / "users_data" / "by_internal"
    dest_submissions_dir = root / "submissions"
    mapping_path = root / "mapping" / "external_accounts.jsonl"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[START] root={root}")
    print(f"        users_dir={users_dir}")
    print(f"        submissions_dir={submissions_dir}")
    print(f"        dest_users_dir={dest_users_dir}")
    print(f"        dest_submissions_dir={dest_submissions_dir}")
    print(f"        mapping_file={mapping_path}")
    print(f"        site={args.site}")
    print(f"        dry_run={args.dry_run}, backup={args.backup}")

    migrate_users(
        users_dir, dest_users_dir, mapping_path, args.site, args.dry_run, args.backup
    )
    migrate_submissions(
        submissions_dir,
        dest_submissions_dir,
        mapping_path,
        args.site,
        args.dry_run,
        args.backup,
    )

    print("[DONE] Migration (check logs above).")


if __name__ == "__main__":
    main()
