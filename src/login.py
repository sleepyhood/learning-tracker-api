# login.py

import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

from config import (
    USER_DATA_DIR,
    BASE_URL,
    USER_DATA_DIR,
    COOKIE_PATH,
)  # 필요 시 조정


MAX_DATA_AGE_SECONDS = 86400  # 하루(60*60*24)

COOKIE_DIR = Path(COOKIE_PATH).parent / "cookies"
ACTIVE_USER_PATH = Path(COOKIE_PATH).parent / "active_user.json"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_username(username: str) -> str:
    return (username or "").strip().replace("/", "_").replace("\\", "_")


def _cookie_path_for(username: str) -> Path:
    return COOKIE_DIR / f"{_safe_username(username)}.json"


def _read_active_username() -> str | None:
    if not ACTIVE_USER_PATH.exists():
        return None
    try:
        data = json.loads(ACTIVE_USER_PATH.read_text(encoding="utf-8"))
        name = (data.get("username") or "").strip()
        return name or None
    except Exception:
        return None


def set_active_username(username: str):
    ACTIVE_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_USER_PATH.write_text(
        json.dumps({"username": username}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_active_session():
    removed = []
    active = _read_active_username()
    if active:
        p = _cookie_path_for(active)
        if p.exists():
            p.unlink()
            removed.append(str(p))
    else:
        # If active user is unknown, clear all stored cookies.
        for p in COOKIE_DIR.glob("*.json"):
            try:
                p.unlink()
                removed.append(str(p))
            except Exception:
                pass
    if ACTIVE_USER_PATH.exists():
        ACTIVE_USER_PATH.unlink()
        removed.append(str(ACTIVE_USER_PATH))
    try:
        legacy = Path(COOKIE_PATH)
        if legacy.exists():
            legacy.unlink()
            removed.append(str(legacy))
    except Exception:
        pass
    return removed


def load_cookies(cookie_path=COOKIE_PATH, username: str | None = None):
    print(f"[load_cookies] cookie_path: {cookie_path}")

    target_path = None
    if username:
        target_path = _cookie_path_for(username)
    else:
        active = _read_active_username()
        if active:
            target_path = _cookie_path_for(active)
        else:
            target_path = Path(cookie_path)

    # legacy migration: root cookies.json -> target_path
    try:
        legacy_path = Path("cookies.json")
        if legacy_path.exists() and not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(legacy_path), str(target_path))
    except Exception as e:
        print("[load_cookies] legacy cookie migration failed:", e)

    if target_path.exists():
        with open(target_path, "r") as f:
            return json.load(f)

    print("login.py: cookie not found")
    return None


def save_cookies(cookie_dict, username: str | None = None):
    cookie_dict["timestamp"] = datetime.now().isoformat()
    if username:
        target_path = _cookie_path_for(username)
    else:
        target_path = Path(COOKIE_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w") as f:
        json.dump(cookie_dict, f)


def selenium_login(username, password):
    print("🔁 셀레니움으로 로그인 중...")
    options = Options()
    options.add_argument("--headless")  # 필요시 주석 해제
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # driver_path = ChromeDriverManager().install()
    # driver = webdriver.Chrome(executable_path=driver_path, options=options)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    print(f"BASE_URL: {BASE_URL}")
    driver.get(BASE_URL)
    time.sleep(2)

    driver.find_element(By.XPATH, '//*[@id="header"]/ul/div[2]/button[1]').click()
    time.sleep(1)

    username_input = driver.find_element(
        By.XPATH,
        "/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[1]/div/div[1]/input",
    )
    password_input = driver.find_element(
        By.XPATH,
        "/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[2]/div/div/input",
    )

    username_input.send_keys(username)
    password_input.send_keys(password)
    password_input.send_keys(Keys.RETURN)

    time.sleep(2)

    cookies = driver.get_cookies()
    driver.quit()

    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    save_cookies(cookie_dict, username)
    if username:
        set_active_username(username)

    return cookie_dict


def get_authenticated_session(cookie_dict):
    if not cookie_dict:
        print("cookie_dict가 존재하지 않습니다.")
        return None

    session = requests.Session()
    domain = urlparse(BASE_URL).hostname
    # 저장 시 넣었던 timestamp는 무시
    for name, value in cookie_dict.items():
        if name == "timestamp":
            continue
        # 도메인/경로 함께 지정 (requests가 올바르게 전송하도록)
        session.cookies.set(name, value, domain=domain, path="/")
    return session


def is_cookie_valid(session):
    print(f"BASE_URL: {BASE_URL}")
    try:
        res = session.get(f"{BASE_URL}/api/profile", timeout=10)
        print(f"is_cookie_valid의 response: {res.status_code}")
        if res.status_code != 200:
            return False
        try:
            data = res.json()
        except ValueError:
            return False

        return data.get("data", {}).get("user") is not None
    except Exception as e:
        print("❌ 쿠키 유효성 검사 실패:", e)
        return False


def is_data_stale(file_path):
    if not os.path.exists(file_path):
        return True
    modified_time = os.path.getmtime(file_path)
    current_time = time.time()
    return (current_time - modified_time) > MAX_DATA_AGE_SECONDS




def _session_username(session):
    try:
        res = session.get(f"{BASE_URL}/api/profile", timeout=10)
        data = res.json()
        return (data.get("data", {}).get("user", {}) or {}).get("username")
    except Exception:
        return None


def do_login(username=None, password=None):
    print(f"do_login? BASE_URL : {BASE_URL }")
    try:
        cookies = load_cookies(COOKIE_PATH, username)

        if cookies:
            print("?? ??? ?? ??")
            session = get_authenticated_session(cookies)
            print(f"session: {session}")
            if not is_cookie_valid(session):
                print("?? ?? ??, ???? ??")
                cookies = selenium_login(username, password)
                session = get_authenticated_session(cookies)
            else:
                if username:
                    current_user = _session_username(session)
                    if current_user and current_user != username:
                        print(
                            f"?? ???({current_user})? ?? ???({username})? ?? ???????."
                        )
                        cookies = selenium_login(username, password)
                        session = get_authenticated_session(cookies)
        else:
            print("??? ?? ??. ??? ??")
            cookies = selenium_login(username, password)
            session = get_authenticated_session(cookies)

        if username:
            set_active_username(username)
        # ?? ??? ?? ?? ??
        user_id = username or "unknown_user"
        filename = f"{user_id}.json"
        user_path = os.path.join(USER_DATA_DIR, filename)

        # ?? ??? ?? ??? ??
        os.makedirs(USER_DATA_DIR, exist_ok=True)

        if is_data_stale(user_path):
            print("??? ??? ?? ?..")
            res = session.get(f"{BASE_URL}/api/profile?username={username}")
            data = json.loads(res.text)
            print()
            with open(user_path, "w", encoding="utf-8") as f:
                json.dump(
                    data["data"]["oi_problems_status"]["problems"],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"?? ??? ?? ??: {filename}")
        else:
            print("?? ???? ?? ?????.")

        return True, session

    except Exception as e:
        print("??? ??:", e)
        return False, str(e)
