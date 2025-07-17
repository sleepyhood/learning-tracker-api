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
    for name, value in cookie_dict.items():
        session.cookies.set(name, value)
    return session


def is_cookie_valid(session):
    try:
        res = session.get(LOGIN_URL)
        if res.status_code == 200 and '"error": null' in res.text:
            return True
    except:
        pass
    return False


def do_login(username=None, password=None):
    try:
        cookies = load_cookies()
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

            session = requests.Session()

        # 수정 필요: 쿠키가 이미 있으면 새로 json 안 불러오게끔
        try:
            # res = session.get(f"http://edu.doingcoding.com/api/profile?username={username}")
            session = get_authenticated_session(cookies)
            res = session.get(f"http://edu.doingcoding.com/api/profile")
            print(res.text)
        except:
            print("유효하지 않은 아이디")

        return True, session  # ✅ 성공 상태와 세션을 반환

    except Exception as e:
        print("❌ 로그인 실패:", e)
        return False, str(e)  # ✅ 실패 시 False와 메시지 반환
