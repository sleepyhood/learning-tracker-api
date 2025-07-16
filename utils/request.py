import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_PATH = "cookies.json"
LOGIN_URL = "http://edu.doingcoding.com/api/profile"  # 인증 필요한 URL


def load_cookies():
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH, "r") as f:
            return json.load(f)
    return None


def save_cookies(cookie_dict):
    with open(COOKIE_PATH, "w") as f:
        json.dump(cookie_dict, f)


def selenium_login():
    print("🔁 셀레니움으로 로그인 중...")
    options = Options()
    # options.add_argument("--headless")  # 필요시 주석 해제
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get("http://edu.doingcoding.com/")
    time.sleep(2)

    # 로그인 버튼 클릭
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

    username_input.send_keys("osw1110")
    password_input.send_keys("lucky636!")
    password_input.send_keys(Keys.RETURN)

    time.sleep(2)

    # 쿠키 추출
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


# --------------------
# 실행 흐름
# --------------------
cookies = load_cookies()

if cookies:
    print("✅ 저장된 쿠키 로드")
    session = get_authenticated_session(cookies)
    if not is_cookie_valid(session):
        print("❌ 쿠키 만료됨. 재로그인 필요")
        cookies = selenium_login()
        session = get_authenticated_session(cookies)
else:
    print("⚠️ 쿠키 없음. 로그인 필요")
    cookies = selenium_login()
    session = get_authenticated_session(cookies)

# 테스트 요청
res = session.get(LOGIN_URL)
# print(f"👤 사용자 프로필 정보:\n{res.text}")


# user = "원용우1023"
# # res = session.get(f"http://edu.doingcoding.com/api/profile?username={user}")
# res = session.get(
#     f"http://edu.doingcoding.com/api/submissions?myself=0&starred=0&result=&username={user}&page=1&limit=12&offset=0"
# )

# print(f"👤 {user} 프로필 응답:", res.text)
# http://edu.doingcoding.com/api/profile?username=%EC%9B%90%EC%9A%A9%EC%9A%B01023

# # JSON 파싱
# data = json.loads(res.text)

# # 문제 목록 추출
# problems = data["data"]["oi_problems_status"]["problems"]

# # 통계 정보
# total_problems = len(problems)
# solved = [p for p in problems.values() if p["score"] > 0]
# unsolved = [p for p in problems.values() if p["score"] == 0]

# # 출력
# print(f"✅ 전체 문제 수: {total_problems}")
# print(f"🎯 푼 문제 수: {len(solved)}")
# print(f"❌ 안 푼 문제 수: {len(unsolved)}")

# print("\n🔍 미해결 문제 목록:")
# for prob in unsolved:
#     print(f"- {prob['_id']} (score: {prob['score']})")

# BASE_URL = "http://edu.doingcoding.com/api/problem"
# PROBLEM_DETAIL_URL = "http://edu.doingcoding.com/problem/detail/{}"

# # res1 = session.get(f"{BASE_URL}?paging=true&offset=0&limit=100&tag={'Lv1 출력'}&page=1")
# # parsed = json.loads(res1.text)

# # # 파일로 저장 (사람이 읽을 수 있게)
# # with open("Lv1 출력.json", "w", encoding="utf-8") as f:
# #     json.dump(parsed, f, ensure_ascii=False, indent=2)


# headers = {
#     "Accept": "application/json",
#     "Referer": "http://edu.doingcoding.com/",
#     "User-Agent": "Mozilla/5.0",
# }
# res = session.get(f"{BASE_URL}/tags", headers=headers)

# tags_data = res.json()

# if tags_data.get("error") is None:
#     all_tags = tags_data.get("data", [])
# else:
#     print("태그 조회 중 오류 발생")
#     all_tags = []

# all_problems = {}

# # 2. 접두사 필터링: Lv 또는 SLv로 시작하는 태그만
# filtered_tags = [
#     tag
#     for tag in all_tags
#     if tag["name"].startswith("Lv") or tag["name"].startswith("SLv")
# ]

# print(f"총 태그 개수: {len(all_tags)}")
# print(f"필터링된 태그 개수 (Lv/SLv 시작): {len(filtered_tags)}")

# # 3. 문제 수집
# BASE_URL = "http://edu.doingcoding.com/api/problem"
# PROBLEM_DETAIL_URL = "http://edu.doingcoding.com/problem/detail/{}"

# all_problems = {}

# for tag in filtered_tags:
#     tag_id = tag["id"]
#     tag_name = tag["name"]

#     url = f"{BASE_URL}?paging=true&offset=0&limit=100&tag={tag_name}&page=1"
#     res = requests.get(url, headers=headers)
#     data = res.json()

#     results = data.get("data", {}).get("results", [])

#     for item in results:
#         pid = item["_id"]
#         all_problems[pid] = {
#             "title": item["title"],
#             "tag": tag_name,
#             "description": item["description"],
#             "input_description": item["input_description"],
#             "output_description": item["output_description"],
#             "samples": item["samples"],
#             "languages": item["languages"],
#             "time_limit": item["time_limit"],
#             "memory_limit": item["memory_limit"],
#             "difficulty": item["difficulty"],
#             "url": PROBLEM_DETAIL_URL.format(pid),
#         }

#     print(f"[✅] 태그 '{tag_name}' 완료 - {len(results)}개 수집")
#     time.sleep(0.3)

# # 4. 저장
# with open("problem_data_filtered.json", "w", encoding="utf-8") as f:
#     json.dump(all_problems, f, ensure_ascii=False, indent=2)

# print("🎉 필터링된 문제 데이터 저장 완료 → problem_data_filtered.json")
