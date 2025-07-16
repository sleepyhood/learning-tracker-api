import json
from collections import defaultdict

# 1. 문제 JSON 로드 (기존 필터된 JSON 사용)
with open("problem_data_filtered.json", "r", encoding="utf-8") as f:
    original_data = json.load(f)

# 2. 접두사 기준으로 묶기
grouped_data = defaultdict(lambda: {"title": "", "total": 0, "problem_names": {}})

# 3. 그룹화
for pid, info in original_data.items():
    prefix = pid[:8]  # SP101v01 or P101v01 등

    grouped_data[prefix]["problem_names"][pid] = info["title"]
    grouped_data[prefix]["total"] += 1

    # title은 가장 처음 들어오는 태그를 사용
    if not grouped_data[prefix]["title"]:
        grouped_data[prefix]["title"] = info["tag"]

# 4. 저장
with open("problem_grouped.json", "w", encoding="utf-8") as f:
    json.dump(grouped_data, f, ensure_ascii=False, indent=2)

print("✅ 숙제(S 포함)와 일반 문제를 구분해 그룹화 완료 → problem_grouped.json")
