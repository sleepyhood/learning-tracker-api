import re
import csv
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_scratch_comments(project_id, max_retries=3):
    """스크래치 API를 통해 프로젝트의 주석 목록을 문자열로 추출 (재시도 및 타임아웃 15초 적용)"""
    for attempt in range(1, max_retries + 1):
        try:
            meta_url = f"https://api.scratch.mit.edu/projects/{project_id}"
            meta_res = requests.get(meta_url, headers=HEADERS, timeout=15)
            meta_res.raise_for_status()
            project_token = meta_res.json().get("project_token")

            data_url = f"https://projects.scratch.mit.edu/{project_id}?token={project_token}"
            data_res = requests.get(data_url, headers=HEADERS, timeout=15)
            data_res.raise_for_status()
            project_json = data_res.json()

            comments_summary = []
            for target in project_json.get("targets", []):
                sprite_name = target.get("name", "오브젝트")
                comments = target.get("comments", {})
                if comments:
                    comments_summary.append(f"[{sprite_name}]")
                    for _, c_info in comments.items():
                        c_text = c_info.get("text", "").strip()
                        if c_text:
                            comments_summary.append(f"- {c_text}")

            return "\n".join(comments_summary) if comments_summary else "(등록된 주석 없음)"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            return f"(주석 추출 실패: {e})"

def crawl_curriculum():
    url = "http://doingcoding.dothome.co.kr/dc/index.html"
    res = requests.get(url, headers=HEADERS)
    res.encoding = 'utf-8' # 인코딩 맞춤
    soup = BeautifulSoup(res.text, "html.parser")

    results = []
    
    # 1. Step 1 ~ 6 모달 탐색
    for step_num in range(1, 7):
        modal = soup.find("div", id=f"portfolioModal{step_num}")
        if not modal:
            continue
        
        step_title = f"STEP {step_num}"
        
        # 단계 부제목 (예: 코딩 개념 이해하고...)
        sub_desc = modal.find("h3", class_="port_text")
        sub_desc_text = sub_desc.get_text(strip=True) if sub_desc else ""
        
        # 프로젝트 링크 a 태그들 찾기
        links = modal.find_all("a", href=re.compile(r"scratch\.mit\.edu/projects/(\d+)"))
        
        for a_tag in links:
            href = a_tag["href"]
            match = re.search(r"projects/(\d+)", href)
            if not match:
                continue
            project_id = match.group(1)
            
            # 프로젝트 이름 추출
            h6 = a_tag.find("h6", class_="port_text")
            project_name = h6.get_text(strip=True) if h6 else "이름 없음"
            
            print(f"🔍 [{step_title}] '{project_name}' ({project_id}) 주석 수집 중...")
            comments = get_scratch_comments(project_id)
            time.sleep(0.3) # API 매너 딜레이
            
            thumbnail_url = f"https://uploads.scratch.mit.edu/get_image/project/{project_id}_480x360.png"
            
            results.append({
                "단원": step_title,
                "대주제": sub_desc_text,
                "프로젝트명": project_name,
                "프로젝트ID": project_id,
                "URL": f"https://scratch.mit.edu/projects/{project_id}/",
                "썸네일URL": thumbnail_url,
                "주석": comments
            })

    # CSV 파일로 저장
    with open("scratch_curriculum.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["단원", "대주제", "프로젝트명", "프로젝트ID", "URL", "썸네일URL", "주석"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ 총 {len(results)}개 프로젝트의 주석 수집 및 'scratch_curriculum.csv' 저장 완료!")

if __name__ == "__main__":
    crawl_curriculum()