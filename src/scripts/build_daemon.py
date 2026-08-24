"""
scripts/build_daemon.py
────────────────────────────────────────────────────────
PyInstaller 를 사용하여 daemon_server.py 를 단일 .exe 바이너리로 빌드.

소스코드(.py) 없이 학원 PC 에 .exe 파일만 배치 가능.

사용법:
    cd src
    python scripts/build_daemon.py
    
결과물:
    src/dist/learning_tracker_daemon.exe
"""

import subprocess
import sys
import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent  # src/
ENTRY   = SRC_DIR / "daemon_server.py"
DIST    = SRC_DIR / "dist"
WORK    = SRC_DIR / "build_tmp"
SPEC    = SRC_DIR / "daemon_server.spec"

# PyInstaller 옵션
CMD = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",            # 단일 .exe
    "--noconsole",          # 콘솔 창 없음 (백그라운드 실행)
    "--name", "learning_tracker_daemon",
    "--distpath", str(DIST),
    "--workpath", str(WORK),
    "--specpath", str(SRC_DIR),
    # 데이터 파일 포함 (문제 카탈로그, 메타 등)
    "--add-data", f"{SRC_DIR / 'meta'};meta",
    "--add-data", f"{SRC_DIR / 'problems_data'};problems_data",
    # 숨겨진 임포트 (Flask 플러그인 계열 자동 감지 안될 수 있음)
    "--hidden-import", "flask_cors",
    "--hidden-import", "sqlalchemy",
    "--hidden-import", "dotenv",
    str(ENTRY),
]

print("[Build] PyInstaller 빌드 시작...")
print(f"[Build] 진입점: {ENTRY}")
print(f"[Build] 결과물: {DIST / 'learning_tracker_daemon.exe'}")
print()

result = subprocess.run(CMD, cwd=str(SRC_DIR))
if result.returncode == 0:
    print()
    print("[Build] ✅ 빌드 성공!")
    print(f"[Build]    결과물: {DIST / 'learning_tracker_daemon.exe'}")
    print("[Build]    학원 PC 배치 시 .env 파일과 함께 같은 폴더에 넣을 것.")
else:
    print()
    print("[Build] ❌ 빌드 실패. 위 에러 메세지를 확인하세요.")
    sys.exit(1)
