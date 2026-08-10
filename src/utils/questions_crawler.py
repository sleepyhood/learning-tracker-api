"""
Bridge wrapper module for Playwright crawler.
Replaces legacy Selenium dependency with ultra-fast Playwright engine.
"""

import os
import json
import time

DIFFICULTIES = ["p101", "p102", "p201", "p202", "p203", "p206", "p204", "p205"]
DIFFICULTY_NAMES = [
    "기초문법1",
    "기초문법2",
    "알고리즘 초급",
    "알고리즘 중급1",
    "알고리즘 중급2",
    "알고리즘 중급3",
    "알고리즘 고급1",
    "알고리즘 고급2",
]

def chapter_count():
    return len(DIFFICULTIES)

def chapter_name(index):
    if 0 <= index < len(DIFFICULTY_NAMES):
        return DIFFICULTY_NAMES[index]
    return f"단원_{index+1}"

def resolve_chapter_index(chapter_token):
    if not chapter_token:
        raise ValueError("Chapter token is empty")
    token_str = str(chapter_token).strip()
    if token_str.isdigit():
        idx = int(token_str) - 1
        if 0 <= idx < len(DIFFICULTIES):
            return idx
        raise ValueError(f"Invalid chapter index: {token_str}")
    token_lower = token_str.lower()
    for idx, d in enumerate(DIFFICULTIES):
        if d.lower() == token_lower:
            return idx
    for idx, name in enumerate(DIFFICULTY_NAMES):
        if name.lower() == token_lower:
            return idx
    raise ValueError(f"Cannot resolve chapter token: {chapter_token}")

def crawl_questions(select=0):
    """Legacy compatibility placeholder."""
    print(f"[questions_crawler] Legacy crawl_questions called for index {select}")
    return []

def do_crawling(output_dir=None, filename="all_problems.json", chapter=None, url=None, **kwargs):
    """
    Playwright-backed ultra-fast crawling handler.
    Maintains 100% backwards compatibility with legacy callers.
    When headless=False (show_browser mode), launches an independent subprocess
    so Windows OS can render a visible desktop GUI window.
    """
    from config import PROBLEM_DIR, BASE_URL

    if not output_dir:
        output_dir = PROBLEM_DIR

    target_url = url
    if not target_url:
        if "prog2" in filename:
            target_url = BASE_URL
        else:
            target_url = f"{BASE_URL}/p101"

    major_name = "프로그래밍 II 심화" if "prog2" in filename else "프로그래밍 I"
    out_path = os.path.join(output_dir, filename)

    chapter_slug = str(chapter) if (chapter is not None and str(chapter).strip()) else None
    headless_opt = kwargs.get("headless", True)
    username = kwargs.get("username", "")
    password = kwargs.get("password", "")
    timeout_sec = kwargs.get("timeout_sec", 60)

    if not headless_opt:
        # GUI 모드: Windows 데스크탑 세션에 브라우저 창을 띄우기 위해 독립 subprocess로 실행
        _run_crawling_subprocess(
            target_url=target_url,
            output_filename=filename,
            major_name=major_name,
            chapter_slug=chapter_slug,
            headed=True,
            username=username,
            password=password,
            timeout_sec=timeout_sec,
        )
    else:
        # Headless 모드: 기존 in-process 방식 유지
        from utils.playwright_crawler import do_playwright_crawling
        try:
            do_playwright_crawling(
                target_url=target_url,
                output_filename=filename,
                major_name=major_name,
                chapter_slug=chapter_slug,
                headless=True,
                username=username,
                password=password,
                timeout_sec=timeout_sec,
            )
        except Exception as e:
            print(f"[questions_crawler] Playwright crawling process notice: {e}")

    return out_path


def _run_crawling_subprocess(target_url, output_filename, major_name, chapter_slug=None, headed=False, username="", password="", timeout_sec=60):
    """
    Spawns playwright_crawler.py as a separate OS process with CREATE_NEW_CONSOLE
    (Windows) so the Chromium window appears on the user's desktop session.
    Blocks until the subprocess finishes so the caller gets results synchronously.
    """
    import sys
    import subprocess

    crawler_script = os.path.join(os.path.dirname(__file__), "playwright_crawler.py")

    cmd = [
        sys.executable,
        crawler_script,
        "--url", target_url,
        "--out", output_filename,
        "--major", major_name,
        "--timeout", str(timeout_sec),
    ]
    if headed:
        cmd.append("--headed")
    if chapter_slug:
        cmd.extend(["--chapter", chapter_slug])
    if username:
        cmd.extend(["--username", username])
    if password:
        cmd.extend(["--password", password])

    creationflags = 0
    if sys.platform == "win32":
        # CREATE_NEW_CONSOLE (0x10) forces a new console window associated with
        # the user's interactive desktop session, making the browser visible.
        creationflags = subprocess.CREATE_NEW_CONSOLE

    print(f"[questions_crawler] 🖥️ GUI subprocess 실행: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            creationflags=creationflags,
            timeout=600,
        )
        if proc.returncode != 0:
            print(f"[questions_crawler] ⚠️ subprocess 종료 코드: {proc.returncode}")
    except subprocess.TimeoutExpired:
        print("[questions_crawler] ⚠️ subprocess 타임아웃 (600s)")
    except Exception as e:
        print(f"[questions_crawler] ⚠️ subprocess 실행 오류: {e}")
