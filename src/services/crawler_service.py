"""
services/crawler_service.py

크롤러 백그라운드 실행 및 상태 관리 서비스 계층.

담당 기능:
  - 크롤링 상태 파일 조회 (crawl_status.json)
  - 백그라운드 스레드로 크롤러 subprocess 실행
"""

import json
import os
import subprocess
import sys
import threading

from config import PROBLEM_DIR

CRAWL_STATUS_FILE = os.path.join(PROBLEM_DIR, "crawl_status.json")


def get_crawl_status() -> dict:
    """
    crawl_status.json 파일을 읽어 현재 크롤링 상태를 반환합니다.

    Returns:
        상태 dict. 파일이 없으면 {"is_running": False, "message": "대기 중"}
    """
    if os.path.exists(CRAWL_STATUS_FILE):
        try:
            with open(CRAWL_STATUS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"상태 파일 읽기 오류: {e}")
    return {"is_running": False, "message": "대기 중"}


def trigger_crawl(key: str, target_config: dict, target_file: str):
    """
    지정된 커리큘럼의 문제 목록을 백그라운드 스레드에서 크롤링합니다.

    Args:
        key: 커리큘럼 키 (e.g. 'prog1')
        target_config: 커리큘럼 설정 dict (name, url 포함)
        target_file: 크롤링 결과를 저장할 JSON 파일 경로
    """
    url = target_config.get("url", "")
    name = target_config.get("name", key)

    def run_crawler_bg():
        try:
            with open(CRAWL_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"is_running": True, "key": key, "message": f"'{name}' 문제 목록을 크롤링 중입니다..."},
                    f,
                    ensure_ascii=False,
                )

            cmd = [sys.executable, "-m", "utils.questions_crawler", "--url", url, "--output", target_file]
            res = subprocess.run(cmd, capture_output=True, text=True)

            if res.returncode == 0:
                status = {"is_running": False, "key": key, "message": "크롤링 완료!", "success": True}
            else:
                status = {
                    "is_running": False,
                    "key": key,
                    "message": f"크롤링 실패: {res.stderr[:200]}",
                    "success": False,
                }
        except Exception as e:
            status = {"is_running": False, "key": key, "message": f"오류 발생: {str(e)}", "success": False}

        with open(CRAWL_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False)

    t = threading.Thread(target=run_crawler_bg, daemon=True)
    t.start()
