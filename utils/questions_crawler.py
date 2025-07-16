from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import json
import os
from collections import defaultdict
import urllib.parse
from collections import deque

# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")


def get_text(btns, result):

    # 텍스트 추출
    for btn in btns:
        # print(btn.text)
        result.append(btn.text)

    return result


def crawl_questions(select):
    driver = webdriver.Chrome()

    time.sleep(0.5)

    tmpTags = []  # 문제 태그(제목)

    # 기초문법1
    driver.get(f"{BASE_URL}/{difficultys[select]}")
    print(f"{BASE_URL}/{difficultys[select]}")

    time.sleep(0.5)

    # XPath로 div 내부의 button 태그 중 두 번째부터 모두 선택

    # 기초문법 1, 2는 같은 형식
    if select < 2:
        divs = driver.find_elements(
            By.XPATH, "/html/body/div[1]/div[2]/div[1]/div[1]/div"
        )

        for i, div in enumerate(divs, start=1):
            buttons = div.find_elements(By.XPATH, f"./button[position() > 1]")
            tmpTags = get_text(buttons, tmpTags)

    else:

        # 1. 반복 대상 div[i]들을 전부 가져옴
        divs = driver.find_elements(
            By.XPATH, "/html/body/div[1]/div[2]/div[1]/div[1]/div"
        )

        # 2. 각 div[i]에 대해 내부 button[1] 추출
        for i in range(1, len(divs) + 1):
            try:
                xpath = f"/html/body/div[1]/div[2]/div[1]/div[1]/div[{i}]/div/div[1]/div/div[2]/button"
                buttons = driver.find_elements(By.XPATH, xpath)
                tmpTags = get_text(buttons, tmpTags)
            except Exception as e:
                print(f"div[{i}] 버튼 없음 or 에러: {e}")

    validTags = []
    validRows = []
    validFormats = []
    validProblemNames = []  # 누적할 리스트 추가

    # 각 태그별 문제 개수
    for i in range(len(tmpTags)):
        utltag = tmpTags[i].replace(".", "")
        url = f"{BASE_URL}/{difficultys[select]}?tag={utltag}"

        encoded_url = urllib.parse.quote(url, safe=":/?=")  # safe 문자들은 인코딩 제외

        driver.get(encoded_url)
        time.sleep(0.5)

        # tbody 안의 모든 tr 가져오기
        # 이는 각 레벨별 문제 개수
        rows = driver.find_elements(
            By.XPATH,
            "/html/body/div[1]/div[2]/div[1]/div[2]/div[1]/div[3]/div/div/div/div[2]/table/tbody/tr",
        )

        # 주의: 문제가 하나도 없다면, 더 이상 볼 필요가 없다.
        # 문제 개수도 반영 안하기

        if len(rows) == 0:
            # tmpTags.pop(i)
            continue

        # tbody 안의 td 내부의 span 텍스트
        # 이는 각 문제의 ID 포맷

        try:
            _format = driver.find_element(
                By.XPATH,
                "/html/body/div[1]/div[2]/div[1]/div[2]/div[1]/div[3]/div/div/div/div[2]/table/tbody/tr[1]/td[1]/div/button",
            )
            _format = _format.text
            _format = _format[:-2]
            # print(f"{tag}의 총 row 개수와 문제 형식: {_format}")

        except Exception as e:
            # tmpFormats.append("")
            print(f"{tmpTags[i]}에 문제가 존재하지 않음 or 에러")
            continue

        # 문제 이름 리스트 수집
        problem_dict = {}
        for idx in range(1, len(rows) + 1):
            try:
                # 문제 ID (td[1])
                id_xpath = f"/html/body/div[1]/div[2]/div[1]/div[2]/div[1]/div[3]/div/div/div/div[2]/table/tbody/tr[{idx}]/td[1]/div/button"
                id_elem = driver.find_element(By.XPATH, id_xpath)
                problem_id = id_elem.text

                # 문제 제목 (td[2])
                name_xpath = f"/html/body/div[1]/div[2]/div[1]/div[2]/div[1]/div[3]/div/div/div/div[2]/table/tbody/tr[{idx}]/td[2]/div/button"
                name_elem = driver.find_element(By.XPATH, name_xpath)
                problem_title = name_elem.text

                problem_dict[problem_id] = problem_title

            except Exception as e:
                print(f"{idx}번째 문제 ID 또는 제목 추출 실패: {e}")
                continue

        validTags.append(tmpTags[i])
        validRows.append(len(rows))
        validFormats.append(_format)
        validProblemNames.append(problem_dict)  # ← 여기 추가해야 누적됨

        print(f"{tmpTags[i]}의 총 row 개수: {len(rows)} 와 문제 형식: {_format}")
        print(problem_dict)
        time.sleep(0.5)

    return validTags, validRows, validFormats, validProblemNames


difficultys = ["p101", "p102", "p201", "p202", "p203", "p206", "p204", "p205"]
difficultys_names = [
    "기초문법1",
    "기초문법2",
    "알고리즘 초급",
    "알고리즘 중급1",
    "알고리즘 중급2",
    "알고리즘 중급3",
    "알고리즘 고급1",
    "알고리즘 고급2",
]

for i in range(len(difficultys)):
    qTags = []  # 문제 태그(제목)
    qFormats = []  # 문제 ID 형식
    qRows = []  # 문제 개수
    qProblemNames = []  # 문제 제목들

    qTags, qRows, qFormats, qProblemNames = crawl_questions(i)

    # 이제 데이터를 저장하기
    # id를 기준으로 하나의 딕셔너리 구성
    problem_info = {}
    for pid, title, total, names in zip(qFormats, qTags, qRows, qProblemNames):
        problem_info[pid] = {"title": title, "total": total, "problem_names": names}

    # 현재 파일 기준 상위 폴더로 이동 후, problems_data 폴더 지정
    output_dir = os.path.join(os.path.dirname(__file__), "..", "problems_data")
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"{i+1}. {difficultys_names[i]}.json")

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(problem_info, f, ensure_ascii=False, indent=4)
