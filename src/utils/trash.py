# def extract_level(name):
#     # Lv 또는 SLv 다음 숫자 추출
#     match = re.match(r"(S?Lv)\s*(\d+)", name)
#     if match:
#         prefix = match.group(1)
#         level_num = int(match.group(2))
#         # Lv는 SLv보다 우선 (숫자가 같으면 Lv 먼저)
#         priority = 0 if prefix == "Lv" else 1  # Lv=0, SLv=1
#         return (level_num, priority)
#     else:
#         # 매칭 안되면 최하위 처리
#         return (float("inf"), float("inf"))


# 정렬 기준: Lv1, Lv2, SLv1, ...
# def extract_level(tag_name):
#     import re

#     match = re.search(r"(?:S)?Lv(\d+)", tag_name)
#     return int(match.group(1)) if match else float("inf")


# def sort_tags_by_level(tags):
#     return sorted(tags, key=lambda tag: extract_level(tag["name"]))


# 파일로 저장
# def save_tags_to_file(tags, filename="tags.json"):
#     with open(filename, "w", encoding="utf-8") as f:
#         json.dump(tags, f, ensure_ascii=False, indent=2)


# "Lv", "SLv"로 시작하는 태그만 필터링
# def filter_level_tags(tags):
#     paired = defaultdict(set)

#     for tag in tags:
#         name = tag["name"]
#         if name.startswith("Lv") or name.startswith("SLv"):
#             # 접두사 분리
#             if name.startswith("Lv"):
#                 prefix = "Lv"
#                 suffix = name[2:].strip()
#             else:
#                 prefix = "SLv"
#                 suffix = name[3:].strip()

#             paired[suffix].add(prefix)

#     # Lv와 SLv가 모두 있는 suffix만 필터링
#     valid_suffixes = {
#         suffix
#         for suffix, prefixes in paired.items()
#         if {"Lv", "SLv"}.issubset(prefixes)
#     }

#     # 최종 필터링
#     return [
#         tag
#         for tag in tags
#         if (tag["name"].startswith("Lv") and tag["name"][2:].strip() in valid_suffixes)
#         or (tag["name"].startswith("SLv") and tag["name"][3:].strip() in valid_suffixes)
#     ]


# 문제 태그 불러오기
# def fetch_problem_tags(session):
#     url = "http://edu.doingcoding.com/api/problem/tags"
#     response = session.get(url)
#     response.raise_for_status()
#     return response.json()["data"]


# def group_problems_by_prefix(
#     problem_dir="problems_by_tag", output_path="problem_groups.json"
# ):
#     grouped = defaultdict(lambda: {"title": "", "total": 0, "problem_names": {}})

#     for filename in os.listdir(problem_dir):
#         if not filename.endswith(".json"):
#             continue

#         tag_name = filename.replace(".json", "")
#         with open(os.path.join(problem_dir, filename), "r", encoding="utf-8") as f:
#             data = json.load(f)

#         for problem in data:
#             pid = problem["_id"]
#             title = problem["title"]

#             # 접두사 추출 (예: P101v0101 → P101v01)
#             prefix = pid[:7]
#             grouped[prefix]["problem_names"][pid] = title
#             grouped[prefix]["total"] += 1

#             # 첫 등장 태그로 title 지정 (이미 있으면 유지)
#             if not grouped[prefix]["title"]:
#                 grouped[prefix]["title"] = tag_name

#     # 저장
#     with open(output_path, "w", encoding="utf-8") as f:
#         # json.dump(grouped, f, ensure_ascii=False, indent=2)
#         sorted_data = dict(
#             sorted(grouped.items(), key=lambda x: extract_numeric_key(x[0]))
#         )
#         json.dump(sorted_data, f, indent=2, ensure_ascii=False)

#     print(f"✅ 그룹화 완료: {output_path}")


# def group_by_difficulty(
#     grouped_path="problem_groups.json", output_path="problem_by_difficulty.json"
# ):
#     with open(grouped_path, "r", encoding="utf-8") as f:
#         grouped_data = json.load(f)

#     difficultys = ["p101", "p102", "p301", "p401", "p601", "p701"]
#     difficultys_names = [
#         "1. 기초문법1",
#         "2. 기초문법2",
#         "3. 알고리즘 초급",
#         "4. 알고리즘 중급1",
#         "5. 알고리즘 중급3",
#         "6. 알고리즘 고급1",
#     ]

#     difficulty_mapping = {
#         prefix: name for prefix, name in zip(difficultys, difficultys_names)
#     }

#     grouped_by_difficulty = defaultdict(dict)

#     for key, value in grouped_data.items():
#         prefix = key[:4].lower()  # ex: P101v01 → p101
#         difficulty = difficulty_mapping.get(prefix)

#         if difficulty:
#             grouped_by_difficulty[difficulty][key] = value

#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(grouped_by_difficulty, f, ensure_ascii=False, indent=2)

#     print(f"✅ 난이도별 그룹화 완료: {output_path}")


# api 로 태그 불러오는거 별로임... 그냥 크롤링으로 대체

# @app.route("/api/problems", methods=["GET"])
# def get_problem_list():
#     cookies = load_cookies(COOKIE_PATH)
#     session = get_authenticated_session(cookies)

#     try:
#         # 1. 태그 저장
#         raw_tags = fetch_problem_tags(session)
#         filtered = filter_level_tags(raw_tags)
#         sorted_tags = sort_tags_by_level(filtered)

#         for tag in sorted_tags:
#             print(f"{tag['name']} (id: {tag['id']})")

#         # save_tags_to_file(sorted_tags)  # tags.json

#         # 2. 태그별 문제 페이지 로드
#         ## 여기에는 모든 태그별 문제가 세부적으로 problems_by_tag>{해당 파트}.json으로 저장함.
#         save_problems_by_tag(sorted_tags)

#         # 3. 태그를 그룹화 (접두사를 중심으로 함.)
#         ## problem_groups.json으로 저장
#         group_problems_by_prefix()

#         # 4. 큰 카테고리로 묶기
#         ## problem_by_difficulty.json으로 저장
#         group_by_difficulty()  # 2차 난이도 그룹화

#         return jsonify({"success": True, "problems": sorted_tags})

#     except Exception as e:
#         print("문제 목록 API 호출 실패:", e)
#         return jsonify({"success": False, "error": str(e)})


import re


def extract_numeric_key(key):
    """
    예: "P101v02" → ("P101", 2)
    """
    match = re.match(r"(.*?v)(\d+)$", key)
    if match:
        prefix, num = match.groups()
        return (prefix, int(num))
    return (key, 0)  # fallback


API_BASE = "http://edu.doingcoding.com/api/problem?paging=true&offset=0&limit=100&tag="


# def save_problems_by_tag(tag_list, save_dir="problems_by_tag"):
#     os.makedirs(save_dir, exist_ok=True)

#     for tag in tag_list:
#         tag_name = tag["name"]
#         encoded_name = quote(tag_name)  # URL 인코딩

#         url = f"{API_BASE}{encoded_name}"
#         try:
#             res = requests.get(url)
#             res.raise_for_status()
#             data = res.json()
#             data = data["data"]["results"]
#             filename = os.path.join(save_dir, f"{tag_name}.json")
#             with open(filename, "w", encoding="utf-8") as f:
#                 json.dump(data, f, ensure_ascii=False, indent=2)

#             print(f"✅ 저장됨: {filename}")
#         except Exception as e:
#             print(f"❌ 오류 발생: {tag_name} -> {e}")
