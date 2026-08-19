import requests

project_id = "1163587263"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    # 1. 최신 project_token 발급
    meta_url = f"https://api.scratch.mit.edu/projects/{project_id}"
    meta_res = requests.get(meta_url, headers=headers)
    meta_res.raise_for_status()
    project_token = meta_res.json().get("project_token")

    # 2. project.json 요청
    data_url = f"https://projects.scratch.mit.edu/{project_id}?token={project_token}"
    project_res = requests.get(data_url, headers=headers)
    project_res.raise_for_status()
    
    project_json = project_res.json()
    
    print(f"==========================================")
    print(f" 📌 스크래치 프로젝트 ({project_id}) 주석 목록")
    print(f"==========================================\n")
    
    total_comment_count = 0
    targets = project_json.get("targets", [])
    
    for target in targets:
        sprite_name = target.get("name", "이름 없음")
        comments = target.get("comments", {})
        
        if comments:
            total_comment_count += len(comments)
            print(f"▶ [오브젝트: {sprite_name}] (주석 {len(comments)}개)")
            
            for idx, (comment_id, comment_info) in enumerate(comments.items(), start=1):
                comment_text = comment_info.get("text", "(내용 없음)").strip()
                block_id = comment_info.get("blockId")
                
                # 블록에 첨부된 주석인지 확인
                attach_info = f"블록({block_id})에 연결됨" if block_id else "바탕화면 주석"
                
                print(f"  {idx}. [{attach_info}]")
                # 주석 내용이 여러 줄일 수 있으므로 들여쓰기 처리
                indented_text = "\n     ".join(comment_text.splitlines())
                print(f"     내용: {indented_text}\n")
            
            print("-" * 42)

    if total_comment_count == 0:
        print("프로젝트에 등록된 주석이 없습니다.")
    else:
        print(f"\n총 {total_comment_count}개의 주석을 발견했습니다.")

except requests.exceptions.HTTPError as e:
    print(f"요청 실패: {e}")