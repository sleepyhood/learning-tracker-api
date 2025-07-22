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

COOKIE_PATH = "cookies.json"
LOGIN_URL = "http://edu.doingcoding.com/api/profile"  # 인증 확인용 URL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")


MAX_DATA_AGE_SECONDS = 86400  # 하루(60*60*24)


def load_cookies(cookie_path=None):
    if os.path.exists(cookie_path):
        with open(cookie_path, "r") as f:
            return json.load(f)
    return None


def save_cookies(cookie_dict):
    cookie_dict["timestamp"] = datetime.now().isoformat()
    with open(COOKIE_PATH, "w") as f:
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
    driver.get("http://edu.doingcoding.com/")
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
    save_cookies(cookie_dict)

    return cookie_dict


def get_authenticated_session(cookie_dict):
    session = requests.Session()

    try:
        for name, value in cookie_dict.items():
            session.cookies.set(name, value)
    except Exception as e:
        print(f"cookie_dict가 존재하지 않습니다.")
    return session


def is_cookie_valid(session):
    try:
        res = session.get("http://edu.doingcoding.com/api/profile")
        data = res.json()
        return res.status_code == 200 and data.get("data", {}).get("user") is not None
    except Exception as e:
        print("❌ 쿠키 유효성 검사 실패:", e)
        return False


def is_data_stale(file_path):
    if not os.path.exists(file_path):
        return True
    modified_time = os.path.getmtime(file_path)
    current_time = time.time()
    return (current_time - modified_time) > MAX_DATA_AGE_SECONDS


def do_login(username=None, password=None):
    try:
        cookies = load_cookies(COOKIE_PATH)

        if cookies:
            print("✅ 저장된 쿠키 로드")
            session = get_authenticated_session(cookies)
            if not is_cookie_valid(session):
                print("❌ 쿠키 만료됨. 재로그인 필요")
                cookies = selenium_login(username, password)
                session = get_authenticated_session(cookies)
        else:
            print("⚠️ 쿠키 없음. 로그인 필요")
            cookies = selenium_login(username, password)
            session = get_authenticated_session(cookies)

        # session = get_authenticated_session(cookies)

        # 유저 데이터 파일 경로 설정
        user_id = username or "unknown_user"
        filename = f"{user_id}.json"
        user_path = os.path.join(USER_DATA_DIR, filename)

        # 유저 디렉토리 없으면 생성
        os.makedirs(USER_DATA_DIR, exist_ok=True)

        if is_data_stale(user_path):
            print("🔄 사용자 데이터 갱신 중...")
            res = session.get(
                f"http://edu.doingcoding.com/api/profile?username={username}"
            )
            data = json.loads(res.text)

            with open(user_path, "w", encoding="utf-8") as f:
                json.dump(
                    data["data"]["oi_problems_status"]["problems"],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"✅ 사용자 데이터 저장됨: {filename}")
        else:
            print("📁 사용자 데이터가 최신 상태입니다.")

        return True, session

    except Exception as e:
        print("❌ 로그인 실패:", e)
        return False, str(e)
