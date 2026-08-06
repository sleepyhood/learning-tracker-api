"""
Playwright-based robust problem crawler for DoingCoding & external curricula.
Extracts DOM elements directly from browser context to prevent breakage on irregular problem IDs.
Outputs clean ID-Indexed Micro-Registry format JSON.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Add parent directory to sys.path if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from config import BASE_URL, PROBLEM_DIR, COOKIE_PATH
except ImportError:
    BASE_URL = os.environ.get("API_BASE_URL", "http://edu.doingcoding.com")
    PROBLEM_DIR = os.path.join(os.path.dirname(__file__), "..", "problems_data")
    COOKIE_PATH = os.path.join(os.path.dirname(__file__), "..", "cookies.json")


def load_session_cookies():
    """Attempts to load session cookies for Playwright context if available."""
    cookie_file = Path(COOKIE_PATH)
    if not cookie_file.exists():
        # Fallback to cookies/ folder
        cookie_dir = cookie_file.parent / "cookies"
        if cookie_dir.exists():
            files = list(cookie_dir.glob("*.json"))
            if files:
                cookie_file = files[0]

    if cookie_file.exists():
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[playwright_crawler] Failed to load cookies: {e}")
    return []


def parse_concept_tag(title):
    """Extracts concept tag from brackets inside title e.g. [출력-기본1] -> 출력-기본1"""
    if not title:
        return ""
    if "[" in title and "]" in title:
        try:
            return title.split("[")[1].split("]")[0].strip()
        except Exception:
            return ""
    return ""


PROG2_CHAPTERS = [
    {"slug": "AL100", "name": "1. 알고리즘 기초"},
    {"slug": "STR101", "name": "2. 자료구조 브론즈1"},
    {"slug": "AL101", "name": "3. 알고리즘 브론즈1"},
    {"slug": "STR102", "name": "4. 자료구조 브론즈2"},
    {"slug": "AL102", "name": "5. 알고리즘 브론즈2"},
    {"slug": "STR201", "name": "6. 자료구조 실버"},
    {"slug": "AL201", "name": "7. 알고리즘 실버1"},
    {"slug": "AL202", "name": "8. 알고리즘 실버2"},
    {"slug": "AL301", "name": "9. 알고리즘 골드1"},
    {"slug": "AL302", "name": "10. 알고리즘 골드2"},
]


def do_playwright_crawling(
    target_url: str = None,
    output_filename: str = "prog2_problems.json",
    major_name: str = "프로그래밍 II 심화",
    headless: bool = True,
    chapter_slug: str = None,
    progress_callback = None
) -> str:
    """
    Crawls target curriculum URLs using Playwright Headless Browser.
    Supports single URL crawl or crawling all PROG2 major chapter slugs sequentially.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright가 설치되어 있지 않습니다. 'pip install playwright && playwright install chromium'을 실행해주세요.")

    os.makedirs(PROBLEM_DIR, exist_ok=True)
    out_path = os.path.join(PROBLEM_DIR, output_filename)

    micro_registry = {}

    # Load existing registry if updating
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict):
                    micro_registry = existing
        except Exception:
            pass

    cookies = load_session_cookies()

    # Determine crawling tasks (urls to visit)
    tasks = []
    base_domain = BASE_URL.rstrip('/') if BASE_URL else "http://edu.doingcoding.com"

    if chapter_slug:
        # Find matching chapter
        found = next((ch for ch in PROG2_CHAPTERS if ch["slug"].upper() == chapter_slug.upper() or ch["name"].startswith(chapter_slug)), None)
        c_name = found["name"] if found else major_name
        slug = found["slug"] if found else chapter_slug
        tasks.append((f"{base_domain}/{slug}", c_name))
    elif target_url and "p102" not in target_url and not target_url.endswith("/p102"):
        tasks.append((target_url, major_name))
    else:
        # Full PROG2 crawl: visit all 10 chapter URLs!
        for ch in PROG2_CHAPTERS:
            tasks.append((f"{base_domain}/{ch['slug']}", ch["name"]))

    print(f"🚀 [Playwright] 총 {len(tasks)}개 단원 수집 시작...")

    scraped_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        if cookies:
            try:
                context.add_cookies(cookies)
                print(f"🔑 [Playwright] 세션 쿠키 {len(cookies)}개 적용 완료")
            except Exception as e:
                print(f"⚠️ [Playwright] 쿠키 적용 실패: {e}")

        page = context.new_page()

        for idx, (url, m_name) in enumerate(tasks, 1):
            if progress_callback:
                progress_callback(idx, len(tasks), m_name, f"[{idx}/{len(tasks)}] '{m_name}' 페이지 수집 중...")
            print(f"🌐 페이지 이동 중... [{idx}/{len(tasks)}] [{m_name}] {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(1.5)

                sub_buttons = page.query_selector_all("button")
                sub_titles = []
                for btn in sub_buttons:
                    txt = (btn.text_content() or "").strip()
                    if txt and ("Lv" in txt or "단원" in txt or "장" in txt or "기초" in txt or "심화" in txt):
                        sub_titles.append(txt)

                rows = page.query_selector_all("table tbody tr")
                print(f"   📊 [{m_name}] 수집된 문제 행: {len(rows)}개")

                for row in rows:
                    tds = row.query_selector_all("td")
                    if len(tds) >= 2:
                        prob_id = tds[0].text_content().strip()
                        prob_title = tds[1].text_content().strip()

                        if prob_id and prob_title:
                            concept = parse_concept_tag(prob_title)
                            sub_name = sub_titles[0] if sub_titles else "주요 문제"

                            micro_registry[prob_id] = {
                                "id": prob_id,
                                "title": prob_title,
                                "concept": concept,
                                "major": m_name,
                                "sub": sub_name
                            }
                            scraped_count += 1
            except Exception as err:
                print(f"   ⚠️ [{m_name}] 수집 중 오류: {err}")

        browser.close()

    # Save to JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(micro_registry, f, ensure_ascii=False, indent=2)

    print(f"✅ [Playwright] 총 {scraped_count}개 문제 수집 완료! 저장 경로: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DoingCoding Playwright Problem Crawler")
    parser.add_argument("--url", type=str, default="", help="Target URL to crawl (e.g. http://edu.doingcoding.com/p102)")
    parser.add_argument("--out", type=str, default="prog2_problems.json", help="Output JSON filename in problems_data directory")
    parser.add_argument("--major", type=str, default="프로그래밍 II 심화", help="Major chapter category name")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser window")

    args = parser.parse_args()
    do_playwright_crawling(
        target_url=args.url,
        output_filename=args.out,
        major_name=args.major,
        headless=not args.headed
    )
