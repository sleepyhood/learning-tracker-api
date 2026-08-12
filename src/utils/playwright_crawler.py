"""
Playwright-based robust problem crawler for DoingCoding & external curricula.
Extracts DOM elements directly from browser context to prevent breakage on irregular problem IDs.
Outputs clean ID-Indexed Micro-Registry format JSON.
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

# Add parent directory to sys.path if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from config import BASE_URL, PROBLEM_DIR, COOKIE_PATH
except ImportError:
    BASE_URL = os.environ.get("API_BASE_URL", "http://edu.doingcoding.com")
    PROBLEM_DIR = os.path.join(os.path.dirname(__file__), "..", "problems_data")
    COOKIE_PATH = os.path.join(os.path.dirname(__file__), "..", "cookies.json")


def save_session_cookies(cookies, username=None):
    """Saves session cookies to COOKIE_PATH and src/cookies/{username}.json"""
    try:
        os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
        with open(COOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        cookie_dir = Path(COOKIE_PATH).parent / "cookies"
        os.makedirs(cookie_dir, exist_ok=True)
        user_cookie_file = cookie_dir / f"{username or 'default'}.json"
        with open(user_cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"💾 [Playwright] 세션 쿠키 저장 완료: {user_cookie_file}")
    except Exception as e:
        print(f"⚠️ [Playwright] 쿠키 저장 실패: {e}")


# DoingCoding 관리자 로그인 상수 (StepCode 제공 정확한 셀렉터)
_DC_CSRF_SEED_URL     = "http://edu.doingcoding.com/api/profile"
_DC_ADMIN_LOGIN_URL   = "http://edu.doingcoding.com/admin/login"
_DC_ID_SELECTOR       = 'xpath=//*[@id="app"]/form/div[1]/div/div/input'
_DC_PW_SELECTOR       = 'xpath=//*[@id="app"]/form/div[2]/div/div/input'
_DC_BTN_SELECTOR      = 'xpath=//*[@id="app"]/form/div[3]/div/button'


def perform_doingcoding_login(page, context, username="", password="", base_url="http://edu.doingcoding.com", headless=True):
    """
    Classic Selenium-style Header Modal Login implementation for Playwright.
    Steps:
      1. Navigate to BASE_URL (http://edu.doingcoding.com)
      2. Check session validity via /api/profile
      3. If unauthenticated, click header login button (xpath=//*[@id="header"]/ul/div[2]/button[1])
      4. Fill ID and PW in the login modal popover
      5. Save updated session cookies to cookies.json
    """
    print(f"🔐 [Playwright] DoingCoding 고전 헤더 모달 로그인 검증 시작 ({base_url})...")
    CRAWL_STATUS.update({
        "log_msg": "🔐 DoingCoding 헤더 모달 로그인 처리 중...",
        "updated_at": time.time()
    })

    try:
        # Step 1: BASE_URL 접속
        print(f"[Playwright] 🌐 메인 페이지 접속 (타임아웃 60초): {base_url}")
        try:
            page.goto(base_url, wait_until="commit", timeout=60000)
        except Exception as e:
            print(f"[Playwright] ⚠️ 메인 페이지 접속 지연 경고: {e}")

        time.sleep(1.0)

        # Step 2: /api/profile 접속하여 로그인 세션 유효성 검사
        try:
            res = page.goto(_DC_CSRF_SEED_URL, wait_until="commit", timeout=60000)
            time.sleep(0.5)
            content = page.content()
            if res and res.status == 200 and ("username" in content or "user" in content or "admin" in content or '"error":null' in content or '"error": null' in content):
                print("✅ [Playwright] 기존 로그인 세션이 유효합니다. (수집 단계 진행)")
                CRAWL_STATUS.update({
                    "log_msg": "✅ 기존 로그인 세션 유효 (수집 단계 진행)",
                    "updated_at": time.time()
                })
                # 메인 페이지로 복귀
                try: page.goto(base_url, wait_until="commit", timeout=60000)
                except Exception: pass
                return True
        except Exception as seed_err:
            print(f"[Playwright] ⚠️ 세션 검증 경고 (무시 및 헤더 로그인 진행): {seed_err}")

        # 복귀
        try: page.goto(base_url, wait_until="commit", timeout=60000)
        except Exception: pass
        time.sleep(1.0)

        # Step 3: 헤더의 로그인 버튼 클릭 (고전 방식)
        header_login_xpath = 'xpath=//*[@id="header"]/ul/div[2]/button[1]'
        print(f"[Playwright] 🔘 헤더 로그인 버튼 클릭 시도 ({header_login_xpath})")
        
        login_btn_clicked = False
        try:
            page.wait_for_selector(header_login_xpath, timeout=8000)
            page.locator(header_login_xpath).click()
            login_btn_clicked = True
            print("[Playwright] ✅ 헤더 로그인 버튼 클릭 성공!")
        except Exception:
            try:
                # Fallback: 로그인 버튼 텍스트 매칭
                btn = page.locator("button:has-text('로그인'), a:has-text('로그인')").first
                btn.click()
                login_btn_clicked = True
                print("[Playwright] ✅ 헤더 로그인 버튼 클릭 성공! (텍스트 폴백)")
            except Exception as btn_err:
                print(f"[Playwright] ⚠️ 헤더 로그인 버튼 탐색 실패: {btn_err}")

        time.sleep(1.0)

        # Step 4: 모달 팝업 내 ID/PW 입력
        modal_id_xpaths = [
            'xpath=/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[1]/div/div[1]/input',
            _DC_ID_SELECTOR,
            'input[type="text"]'
        ]
        modal_pw_xpaths = [
            'xpath=/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[2]/div/div/input',
            _DC_PW_SELECTOR,
            'input[type="password"]'
        ]

        if username and password:
            print(f"[Playwright] 🔑 모달 팝업 폼 작성 중... (계정: {username})")
            id_filled = False
            for selector in modal_id_xpaths:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=3000):
                        loc.fill(username)
                        id_filled = True
                        break
                except Exception:
                    continue

            pw_filled = False
            for selector in modal_pw_xpaths:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=3000):
                        loc.fill(password)
                        pw_filled = True
                        time.sleep(0.3)
                        loc.press("Enter")
                        break
                except Exception:
                    continue

            time.sleep(1.5)

            # 로그인 성공 여부 검사 (쿠키 확보 및 profile 검증)
            cookies = context.cookies()
            if cookies:
                save_session_cookies(cookies, username)
                print(f"✅ [Playwright] 고전 헤더 모달 로그인 완료! (쿠키 {len(cookies)}개 확보)")
                CRAWL_STATUS.update({
                    "log_msg": "✅ DoingCoding 로그인 완료 (세션 쿠키 갱신)",
                    "updated_at": time.time()
                })
                return True

        # 수동 로그인 대기 (Headed 모드)
        if not headless:
            manual_msg = "🔑 [수동 로그인 대기] 열린 헤더 모달 브라우저 창에서 로그인을 완료해 주세요 (최대 60초 대기...)"
            print(f"👉 {manual_msg}")
            CRAWL_STATUS.update({
                "log_msg": manual_msg,
                "updated_at": time.time()
            })
            try:
                page.wait_for_function(
                    "() => !document.querySelector('.el-dialog__wrapper') || document.cookie.includes('session')",
                    timeout=60000
                )
                print("✅ [Playwright] 수동 로그인 완료 감지!")
                time.sleep(1.5)
                cookies = context.cookies()
                if cookies:
                    save_session_cookies(cookies, username or "manual_user")
                return True
            except Exception:
                print("⚠️ [Playwright] 수동 로그인 60초 대기 타임아웃")

        cookies = context.cookies()
        if cookies:
            save_session_cookies(cookies, username)
            return True
        return False

    except Exception as e:
        print(f"⚠️ [Playwright] 고전 로그인 처리 중 예외 발생: {e}")
        return False


def load_session_cookies():
    """Attempts to load session cookies for Playwright context if available."""
    cookie_file = Path(COOKIE_PATH)
    if not cookie_file.exists():
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
                elif isinstance(data, dict):
                    cookie_list = []
                    domain = BASE_URL.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
                    for k, v in data.items():
                        if k in ("timestamp", "user", "username"):
                            continue
                        cookie_list.append({
                            "name": str(k),
                            "value": str(v),
                            "domain": domain,
                            "path": "/"
                        })
                    return cookie_list
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


PROG1_CHAPTERS = [
    {"slug": "p101", "name": "1. 기초문법1"},
    {"slug": "p102", "name": "2. 기초문법2"},
    {"slug": "p201", "name": "3. 알고리즘 초급"},
    {"slug": "p202", "name": "4. 알고리즘 중급1"},
    {"slug": "p203", "name": "5. 알고리즘 중급2"},
    {"slug": "p206", "name": "6. 알고리즘 중급3"},
    {"slug": "p204", "name": "7. 알고리즘 고급1"},
    {"slug": "p205", "name": "8. 알고리즘 고급2"},
]

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

CRAWL_STATUS = {
    "running": False,
    "major_name": "",
    "current_chapter": "",
    "current_sub": "",
    "scraped_count": 0,
    "current_index": 0,
    "total_chapters": 0,
    "log_msg": "수집 대기 중...",
    "updated_at": 0
}

STATUS_FILE_PATH = os.path.join(PROBLEM_DIR, "crawl_status.json")

def update_crawl_status(updates: dict):
    """Updates CRAWL_STATUS dictionary and persists to crawl_status.json for cross-process sync."""
    CRAWL_STATUS.update(updates)
    try:
        os.makedirs(PROBLEM_DIR, exist_ok=True)
        with open(STATUS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(CRAWL_STATUS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_crawl_status():
    if os.path.exists(STATUS_FILE_PATH):
        try:
            with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict) and saved.get("updated_at", 0) >= CRAWL_STATUS.get("updated_at", 0):
                    return saved
        except Exception:
            pass
    return CRAWL_STATUS.copy()


def do_playwright_crawling(
    target_url: str = None,
    output_filename: str = "prog2_problems.json",
    major_name: str = "프로그래밍 II 심화",
    headless: bool = True,
    chapter_slug: str = None,
    progress_callback = None,
    username: str = None,
    password: str = None,
    timeout_sec: int = 60,
) -> str:
    """
    Crawls target curriculum URLs using Playwright Headless Browser.
    Supports single URL crawl or crawling all major chapter slugs sequentially.
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
                    if existing.get("_schema_version") == 2:
                        probs = existing.get("problems", {})
                        groups = existing.get("groups", {})
                        for pid, pitem in probs.items():
                            if isinstance(pitem, dict):
                                gid = pitem.get("group_id")
                                sub_title = groups.get(gid, {}).get("title", "기타 소단원")
                                micro_registry[pid] = {
                                    "id": pid,
                                    "title": pitem.get("title", pid),
                                    "concept": parse_concept_tag(pitem.get("title", "")),
                                    "major": pitem.get("chapter_id", "기타 대단원"),
                                    "sub": sub_title
                                }
                    else:
                        micro_registry = {k: v for k, v in existing.items() if isinstance(v, dict) and "title" in v}
        except Exception:
            pass

    cookies = load_session_cookies()

    # Determine crawling tasks (urls to visit)
    tasks = []
    base_domain = BASE_URL.rstrip('/') if BASE_URL else "http://edu.doingcoding.com"

    if chapter_slug and str(chapter_slug).lower() != "all":
        # Specific chapter requested
        c_str = str(chapter_slug).strip()
        is_prog2 = ("prog2" in output_filename) or ("프로그래밍 II" in major_name) or (target_url and "prog2" in target_url)
        curr_chapters = PROG2_CHAPTERS if is_prog2 else PROG1_CHAPTERS
        
        found = None
        if c_str.isdigit():
            idx = int(c_str) - 1
            if 0 <= idx < len(curr_chapters):
                found = curr_chapters[idx]
        
        if not found:
            found = next((ch for ch in curr_chapters if ch["slug"].upper() == c_str.upper() or ch["name"].startswith(f"{c_str}.") or ch["name"].startswith(c_str)), None)
            
        if found:
            dest_url = f"{base_domain}/{found['slug']}"
            tasks.append((dest_url, found["name"]))
        elif target_url:
            tasks.append((target_url, major_name))
        else:
            tasks.append((f"{base_domain}/{c_str}", major_name))
    else:
        # FULL CURRICULUM CRAWL ("all")
        if ("prog2" in output_filename) or ("프로그래밍 II" in major_name) or (target_url and "prog2" in target_url):
            for ch in PROG2_CHAPTERS:
                tasks.append((f"{base_domain}/{ch['slug']}", ch["name"]))
        else:
            for ch in PROG1_CHAPTERS:
                tasks.append((f"{base_domain}/{ch['slug']}", ch["name"]))

    print(f"🚀 [Playwright] 총 {len(tasks)}개 단원 수집 시작...")
    CRAWL_STATUS.update({
        "running": True,
        "major_name": major_name,
        "scraped_count": 0,
        "current_index": 0,
        "total_chapters": len(tasks),
        "current_chapter": "",
        "current_sub": "",
        "log_msg": f"🚀 [{major_name}] 수집 준비 중...",
        "updated_at": time.time()
    })

    scraped_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
            extra_http_headers={
                "Referer": f"{base_domain}/",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

        timeout_ms = max(10000, int(timeout_sec) * 1000)
        context.set_default_navigation_timeout(timeout_ms)
        context.set_default_timeout(timeout_ms)
        print(f"⏱️ [Playwright] 동적 페이지 대기시간 적용: {timeout_sec}초 ({timeout_ms}ms)")

        if cookies:
            try:
                context.add_cookies(cookies)
                print(f"🔑 [Playwright] 세션 쿠키 {len(cookies)}개 적용 완료")
            except Exception as e:
                print(f"⚠️ [Playwright] 쿠키 적용 실패: {e}")

        page = context.new_page()

        # 불필요한 폰트, 미디어, 외부 CDN 리소스 안전 처리하여 무한 로딩 방지
        def block_unnecessary_resources(route):
            req = route.request
            resource_type = req.resource_type
            url = req.url.lower()
            if resource_type in ["font", "media"] or any(ext in url for ext in [".woff", ".woff2", ".ttf", "fonts.googleapis.com", "fonts.gstatic.com", "jsdelivr.net"]):
                try:
                    route.fulfill(status=200, content_type="text/plain", body="")
                except Exception:
                    try:
                        route.abort()
                    except Exception:
                        pass
            else:
                try:
                    route.continue_()
                except Exception:
                    pass

        try:
            page.route("**/*", block_unnecessary_resources)
        except Exception:
            pass

        perform_doingcoding_login(page, context, username=username, password=password, base_url=base_domain, headless=headless)

        last_detected_error = ""
        consecutive_error_count = 0

        print(f"🔄 [Playwright] 로그인 완료 후 총 {len(tasks)}개 대단원 수집을 동일 브라우저 세션(Context)에서 진행합니다.")

        for idx, (url, m_name) in enumerate(tasks, 1):
            log_str = f"[{idx}/{len(tasks)}] '{m_name}' 수집 중... (로그인 세션 유지)"
            CRAWL_STATUS.update({
                "current_chapter": m_name,
                "current_sub": "페이지 로딩",
                "current_index": idx,
                "scraped_count": scraped_count,
                "log_msg": log_str,
                "updated_at": time.time()
            })
            if progress_callback:
                progress_callback(idx, len(tasks), m_name, log_str)
            print(f"🌐 [대단원 {idx}/{len(tasks)}] [{m_name}] 수집 탭 이동: {url}")
            
            # 대단원이 2개 이상일 때 새 탭 생성하여 기존 로그인 세션 100% 공유
            task_page = context.new_page() if idx > 1 else page
            try:
                task_page.route("**/*", block_unnecessary_resources)
            except Exception:
                pass
            
            task_success = False
            task_error_reason = ""

            try:
                response = None
                try:
                    response = task_page.goto(url, wait_until="commit", timeout=timeout_ms)
                except Exception as g_err:
                    print(f"   ⚠️ 1차 페이지 접속 타임아웃 발생 ({timeout_sec}초 초과). 1회 자동 재시도 중...: {g_err}")
                    time.sleep(2.0)
                    try:
                        response = task_page.goto(url, wait_until="commit", timeout=timeout_ms)
                    except Exception as g_err2:
                        task_error_reason = f"페이지 접속 타임아웃 ({timeout_sec}초 초과: {g_err2})"
                        print(f"   ⚠️ 페이지 접속 지연 경고 (재시도 실패): {g_err2}")

                # Vue SPA 동적 API 호출 및 렌더링 완성 대기 (networkidle 및 selector 대기)
                try:
                    task_page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass

                # 접속 후 상태 검사
                curr_url = task_page.url.lower()
                status_code = response.status if response and hasattr(response, 'status') else 0

                if "admin/login" in curr_url or "login" in curr_url:
                    task_error_reason = f"세션 만료로 인한 로그인 페이지 리다이렉트 ({curr_url})"
                elif status_code == 403:
                    task_error_reason = "서버 접근 권한 거부 (HTTP 403 Forbidden)"
                elif status_code == 404:
                    task_error_reason = f"존재하지 않는 단원 URL 경로 (HTTP 404: {url})"
                elif status_code >= 500:
                    task_error_reason = f"서버 내부 오류 (HTTP {status_code})"

                # 1. 초기 렌더링 대기 (서버 응답 지연 대비)
                time.sleep(3.0)

                # 1. 초기 렌더링 대기 (서버 응답 지연 대비)
                time.sleep(3.5)

                # 2. 소단원 버튼 / 테이블 렌더링 완성될 때까지 동적 재시도 폴링 루프 (지연시간 비율 동적 계산)
                max_polling_retries = max(8, int(timeout_sec / 2))
                target_keywords = [
                    "Lv", "STRLv", "SSTRLv", "ALLv", "SALLv", "SALL", "SSTR", "SAL",
                    "단원", "장", "기초", "심화", "출력", "변수", "조건",
                    "반복", "배열", "포인터", "문자열", "입출력", "함수", "구조체", "재귀",
                    "알고리즘", "자료구조", "브론즈", "실버", "골드", "AL", "STR"
                ]

                clickable_buttons = []
                sub_buttons = []
                last_btn_count = -1

                for retry_idx in range(1, max_polling_retries + 1):
                    try:
                        task_page.wait_for_selector("button.sub-btn, table tbody tr, table", timeout=5000)
                    except Exception:
                        pass
                    
                    sub_buttons = task_page.query_selector_all("button.sub-btn, button")
                    clickable_buttons = []
                    for btn in sub_buttons:
                        txt = (btn.text_content() or "").strip()
                        cls = (btn.get_attribute("class") or "")
                        # 구분선 버튼(:::) 또는 비활성 버튼(disabled) 제외
                        if "disabled" in cls or "divider" in cls or ":::" in txt or txt.startswith("::") or txt.endswith("::"):
                            continue

                        # "아래는 이전" 구획 감지 시 탐색 중단 (break)하여 레거시 소단원 완전 수집 차단
                        try:
                            is_legacy_divider = btn.evaluate("""el => {
                                let container = el.closest('.list-group') || el.parentElement || document.body;
                                let fullText = container.innerText || container.textContent || "";
                                if (!fullText.includes("아래는 이전") && !fullText.includes("이전 소단원")) return false;
                                
                                try {
                                    let range = document.createRange();
                                    range.setStart(container, 0);
                                    range.setEndBefore(el);
                                    let textBefore = range.toString();
                                    return textBefore.includes("아래는 이전") || textBefore.includes("이전 소단원");
                                } catch(e) {
                                    return false;
                                }
                            }""")
                            if is_legacy_divider:
                                print(f"   🛑 ['아래는 이전' 감지] 레거시 구획 진입으로 소단원 버튼 탐색 즉시 중단 (break)")
                                break
                        except Exception:
                            pass

                        # 개별 문제 서브 필터 버튼 제외 (예: "01. [완전탐색 기초 - 1] 키 순서", "[완전탐색 기초 - 1]")
                        if re.search(r"^\d+\s*[\.\:]\s*\[", txt) or re.search(r"\[.*-\s*\d+\]", txt):
                            continue

                        if "sub-btn" in cls or any(k in txt for k in target_keywords):
                            clickable_buttons.append((btn, txt))
                    
                    # 지연 대기 2회 이상 지나고 소단원 버튼 개수가 안정화(더 이상 늘어나지 않음)되면 렌더링 완결로 판단
                    if len(clickable_buttons) > 0 and (retry_idx >= 2 or len(clickable_buttons) == last_btn_count):
                        print(f"   ✅ [SPA 렌더링 완결 확인 - {retry_idx}회차] 발견된 소단원 버튼: {len(clickable_buttons)}개 / 전체 버튼: {len(sub_buttons)}개")
                        break
                    
                    last_btn_count = len(clickable_buttons)
                    print(f"   ⏳ [SPA DOM 렌더링 대기 중...] ({retry_idx}/{max_polling_retries}회차 - 소단원 마운트 대기 2초 후 재시도)")
                    time.sleep(2.0)

                if len(clickable_buttons) == 0:
                    print(f"   ⚠️ [최종 렌더링 확인] 발견된 소단원 버튼: 0개 / 전체 버튼: {len(sub_buttons)}개")

                sub_scraped_before = len(micro_registry)
                chapter_scraped_count = 0

                if clickable_buttons:
                    for b_elem, b_txt in clickable_buttons:
                        sub_log = f"[{idx}/{len(tasks)}] {m_name} ➔ 소단원 [{b_txt}] 수집 중..."
                        update_crawl_status({
                            "current_chapter": m_name,
                            "current_sub": b_txt,
                            "current_index": idx,
                            "scraped_count": len(micro_registry),
                            "log_msg": sub_log,
                            "updated_at": time.time()
                        })
                        print(f"   📂 소단원 탐색: {sub_log}")
                        try:
                            b_elem.click()
                            time.sleep(2.5) # 클릭 후 서버 API 응답 대기
                        except Exception:
                            pass
                        
                        # 클릭 후 테이블 행 데이터 수신 대기 (최대 5회 x 1.5초 = 7.5초 폴링)
                        rows = []
                        for row_retry in range(1, 6):
                            try:
                                task_page.wait_for_selector("table tbody tr", timeout=4000)
                            except Exception:
                                pass
                            rows = task_page.query_selector_all("table tbody tr, table tr")
                            if len(rows) > 0:
                                break
                            time.sleep(1.5)

                        for row in rows:
                            tds = row.query_selector_all("td")
                            if len(tds) >= 3:
                                # iView table: tds[0]=Status Icon, tds[1]=Problem ID, tds[2]=Problem Title
                                prob_id = tds[1].text_content().strip()
                                prob_title = tds[2].text_content().strip()
                            elif len(tds) == 2:
                                prob_id = tds[0].text_content().strip()
                                prob_title = tds[1].text_content().strip()
                            else:
                                continue

                            if prob_id and prob_title and prob_id != "#":
                                concept = parse_concept_tag(prob_title)
                                existing_sub = micro_registry.get(prob_id, {}).get("sub", "")
                                target_sub = b_txt
                                if existing_sub and re.search(r"^\d+\s*[\.\:]\s*\[", target_sub):
                                    target_sub = existing_sub

                                micro_registry[prob_id] = {
                                    "id": prob_id,
                                    "title": prob_title,
                                    "concept": concept,
                                    "major": m_name,
                                    "sub": target_sub
                                }
                                scraped_count += 1
                                chapter_scraped_count += 1
                else:
                    rows = task_page.query_selector_all("table tbody tr")
                    for row in rows:
                        tds = row.query_selector_all("td")
                        if len(tds) >= 3:
                            prob_id = tds[1].text_content().strip()
                            prob_title = tds[2].text_content().strip()
                        elif len(tds) == 2:
                            prob_id = tds[0].text_content().strip()
                            prob_title = tds[1].text_content().strip()
                        else:
                            continue

                        if prob_id and prob_title and prob_id != "#":
                            concept = parse_concept_tag(prob_title)
                            micro_registry[prob_id] = {
                                "id": prob_id,
                                "title": prob_title,
                                "concept": concept,
                                "major": m_name,
                                "sub": "주요 문제"
                            }
                            scraped_count += 1
                            chapter_scraped_count += 1

                if chapter_scraped_count > 0 or len(micro_registry) > sub_scraped_before:
                    task_success = True
                elif not task_error_reason:
                    task_error_reason = f"페이지 내 문제 목록 테이블(table tbody tr) 탐색 실패 (단원: {m_name})"

            except Exception as err:
                task_error_reason = f"수집 처리 중 예외 발생 ({err})"
                print(f"   ⚠️ [{m_name}] 수집 중 오류: {err}")

            if not task_success:
                consecutive_error_count += 1
                last_detected_error = task_error_reason
                print(f"⚠️ [연속 오류 {consecutive_error_count}/2회] 원인: {last_detected_error}")
                if consecutive_error_count >= 2:
                    error_msg = f"오류발생: [{last_detected_error}]"
                    print(f"🚨 {error_msg}")
                    CRAWL_STATUS.update({
                        "running": False,
                        "scraped_count": len(micro_registry),
                        "log_msg": error_msg,
                        "updated_at": time.time()
                    })
                    browser.close()
                    return out_path
            else:
                consecutive_error_count = 0

        browser.close()

    actual_total_count = len(micro_registry)
    print(f"DEBUG: micro_registry len = {actual_total_count}, scraped_count = {scraped_count}")

    # 안전장치: 수집된 문제가 0개이고 데이터가 없을 때 명확한 원인 메시지 출력
    if actual_total_count == 0:
        error_cause = last_detected_error or "페이지 접속 지연 또는 쿠키 세션 만료"
        final_err_msg = f"오류발생: [{error_cause}]"
        print(f"🚨 {final_err_msg}")

        if not os.path.exists(out_path):
            empty_v2 = {
                "_schema_version": 2,
                "chapters": [],
                "groups": {},
                "problems": {},
                "_last_updated": datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S"),
                "_stats": {
                    "total_problems": 0,
                    "total_chapters": len(tasks),
                    "total_subs": 0,
                    "major_name": major_name,
                }
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(empty_v2, f, ensure_ascii=False, indent=2)
            print(f"✨ [Playwright] 신규 스키마 파일 생성 완료: {out_path}")
        else:
            print(f"⚠️ [Playwright] 수집된 문제가 0개이므로 기존 파일을 보호하기 위해 덮어쓰기를 취소합니다: {out_path}")
        
        CRAWL_STATUS.update({
            "running": False,
            "scraped_count": 0,
            "log_msg": final_err_msg,
            "updated_at": time.time()
        })
        return out_path

    # Save to JSON in Schema V2 format, with _last_updated metadata
    v2_data = convert_micro_registry_to_v2_schema(micro_registry)
    print(f"DEBUG: v2_data problems len = {len(v2_data.get('problems', {}))}")
    now_kst = datetime.now(tz=KST)
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    total_subs = len({(item.get("major", ""), item.get("sub", "")) for item in micro_registry.values() if isinstance(item, dict)})
    v2_data["_last_updated"] = now_str
    v2_data["_stats"] = {
        "total_problems": actual_total_count,
        "total_chapters": len(tasks),
        "total_subs": total_subs,
        "major_name": major_name,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(v2_data, f, ensure_ascii=False, indent=2)

    finish_msg = f"✨ [{major_name}] 총 {actual_total_count}개 문제 수집 완료!"
    CRAWL_STATUS.update({
        "running": False,
        "scraped_count": actual_total_count,
        "log_msg": finish_msg,
        "last_crawled": now_str,
        "last_crawled_stats": v2_data["_stats"],
        "updated_at": time.time()
    })
    print(f"✅ [Playwright] {finish_msg} 저장 경로: {out_path}")
    print(f"✅ [Playwright] {finish_msg} 저장 경로: {out_path}")
    return out_path


def convert_micro_registry_to_v2_schema(micro_registry: dict) -> dict:
    if not isinstance(micro_registry, dict):
        return {"_schema_version": 2, "chapters": [], "groups": {}, "problems": {}}

    chapters_dict = {}
    groups = {}
    problems = {}
    group_map = {}

    for key, item in micro_registry.items():
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DoingCoding Playwright Problem Crawler")
    parser.add_argument("--url", type=str, default="", help="Target URL to crawl (e.g. http://edu.doingcoding.com/p102)")
    parser.add_argument("--out", type=str, default="prog2_problems.json", help="Output JSON filename in problems_data directory")
    parser.add_argument("--major", type=str, default="프로그래밍 II 심화", help="Major chapter category name")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser window")
    parser.add_argument("--chapter", type=str, default=None, help="Specific chapter slug or index to crawl (e.g. AL100, 1)")
    parser.add_argument("--username", type=str, default="", help="DoingCoding account username")
    parser.add_argument("--password", type=str, default="", help="DoingCoding account password")
    parser.add_argument("--timeout", type=int, default=60, help="Page load timeout in seconds")

    args = parser.parse_args()
    
    out_file = do_playwright_crawling(
        target_url=args.url,
        output_filename=args.out,
        major_name=args.major,
        headless=not args.headed,
        chapter_slug=args.chapter,
        username=args.username,
        password=args.password,
        timeout_sec=args.timeout,
    )

    st = get_crawl_status()
    log_msg = st.get("log_msg", "")

    # 에러 발생 시 로그 파일 저장
    if "오류발생:" in log_msg or "⚠️" in log_msg or st.get("scraped_count", 0) == 0:
        err_log_file = os.path.join(PROBLEM_DIR, "last_crawl_error.log")
        try:
            with open(err_log_file, "w", encoding="utf-8") as f:
                f.write(f"[{datetime.now(tz=KST).strftime('%Y-%m-%d %H:%M:%S')}]\n{log_msg}\n")
            print(f"📝 [로그 저장] 오류 상세 내역이 기록되었습니다: {err_log_file}")
        except Exception:
            pass

    # GUI(Headed) 모드이거나 오류 발생 시 CMD 창이 바로 닫히지 않도록 대기
    if args.headed or "오류발생:" in log_msg or st.get("scraped_count", 0) == 0:
        print("\n" + "=" * 60)
        print(f"📌 [최종 상태 결과] {log_msg}")
        print("=" * 60)
        print("🛑 CMD 콘솔 창 자동 닫힘 방지: 20초간 대기 후 종료됩니다...")
        print("   (즉시 종료하시려면 이 창에서 Ctrl+C를 누르세요)")
        time.sleep(20)

