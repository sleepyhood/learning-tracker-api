from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import json
import os
from collections import defaultdict

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")


def crawl_problems(your_id, your_password, user_name):
    driver = webdriver.Chrome()
    driver.get(BASE_URL)
    # 로그인 절차
    driver.find_element(
        By.XPATH, "/html/body/div[1]/div[1]/ul/div[2]/button[1]"
    ).click()
    driver.find_element(
        By.XPATH,
        "/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[1]/div/div[1]/input",
    ).send_keys(your_id)
    driver.find_element(
        By.XPATH,
        "/html/body/div[3]/div[2]/div/div/div[2]/div/form/div[2]/div/div/input",
    ).send_keys(your_password)
    driver.find_element(
        By.XPATH, "/html/body/div[3]/div[2]/div/div/div[2]/div/div/button"
    ).click()

    time.sleep(0.5)
    driver.get(f"{BASE_URL}/user-home?username={user_name}")
    time.sleep(1)

    solved_list = []
    buttons = driver.find_elements(By.XPATH, '//*[@id="problems"]/div[2]/div/button')
    for btn in buttons:
        try:
            span = btn.find_element(By.TAG_NAME, "span")
            solved_list.append(span.text)
        except:
            continue
    driver.quit()

    if len(solved_list) == 0:
        print(f"{user_name}은 사이트에 존재하지 않습니다.")
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # data 폴더 경로 구성
    data_dir = os.path.join(base_dir, "students_data")
    os.makedirs(data_dir, exist_ok=True)  # 없으면 생성

    file_path = os.path.join(data_dir, f"{user_name}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(solved_list, f, ensure_ascii=False, indent=2)

    print(f"크롤링 완료, 총 {len(solved_list)}개 문제 저장됨. 파일 위치: {file_path}")


def crawl_user(user_name):
    your_id = USERNAME
    your_password = PASSWORD
    crawl_problems(your_id, your_password, user_name)
