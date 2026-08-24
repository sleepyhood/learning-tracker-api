"""
daemon_server.py
────────────────────────────────────────────────────────
스텔스 헤드리스 API 데몬 진입점.

- 브라우저 자동 오픈 없음
- UI 렌더링 라우트(/ , /workspace) 비활성화
- 127.0.0.1 루프백 + 비표준 포트(58120) 고정
- dc_cli.py 에서 X-Rebel-Secret 헤더를 실어 API 호출

실행 방법:
    python daemon_server.py              # 포그라운드 (디버그)
    pythonw daemon_server.py            # 백그라운드 (윈도우 창 없음)
    start /B pythonw daemon_server.py   # 숨김 백그라운드 실행

환경변수(.env):
    DAEMON_PORT    : 바인딩 포트 (기본 58120)
    DAEMON_SECRET  : X-Rebel-Secret 인증 토큰
    FLASK_DEBUG    : 디버그 모드 (기본 0)
"""

import os
import sys
from pathlib import Path

# .env 로드 (src/ 안에 있을 때)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip("'\"")
            if _k not in os.environ:
                os.environ[_k] = _v

# -- Flask app 임포트 (기존 app.py 공유) ---
from app import app

# -- UI 전용 라우트 비활성화 (404 반환) --
# 학원 컴퓨터에서 브라우저로 직접 열어도 아무것도 안 보이게
_BLOCKED_UI_ROUTES = ["/", "/workspace", "/login", "/user"]


@app.before_request
def _block_ui_routes():
    from flask import request, Response
    if request.path in _BLOCKED_UI_ROUTES or request.path.startswith("/static"):
        return Response("<html><body>Not Found</body></html>", status=404, mimetype="text/html")


if __name__ == "__main__":
    host = "127.0.0.1"  # 루프백 고정 -- 학원 내 다른 PC에서 스캔 불가
    port = int(os.environ.get("DAEMON_PORT", "58120"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")

    # 시크릿 검증
    secret = os.environ.get("DAEMON_SECRET", "").strip()
    if not secret:
        print("[Daemon] WARNING: DAEMON_SECRET 이 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    print(f"[Daemon] Stealth API daemon started: http://{host}:{port}")
    print(f"[Daemon]    X-Rebel-Secret header auth enabled")
    print(f"[Daemon]    UI routes blocked (404)")

    app.run(host=host, port=port, debug=debug)
