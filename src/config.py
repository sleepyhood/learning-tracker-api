# config.py 또는 main.py 상단
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROBLEM_DIR = os.path.join(BASE_DIR, "problems_data")
USER_DATA_DIR = os.path.join(BASE_DIR, "users_data")
COOKIE_PATH = os.path.join(BASE_DIR, "cookies.json")

PROBLEM_FILE = os.path.join(PROBLEM_DIR, "all_problems.json")
SERVER_DUMP_FILE = os.path.join(PROBLEM_DIR, "server_problems.json")

# ✅ 추천: 파일명 명확화
SERVER_TO_LEGACY_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map.json")
LEGACY_TO_SERVER_FILE = os.path.join(PROBLEM_DIR, "server_legacy_map_reverse.json")
UNMATCHED_FILE = os.path.join(PROBLEM_DIR, "legacy_unmatched.json")


BASE_URL = os.environ.get("API_BASE_URL")

ADMIN_DOMAIN = os.environ.get("ADMIN_DOMAIN")
STUDENT_DOMAIN = os.environ.get("STUDENT_DOMAIN")

SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN")
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = (
    os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
)

# Comma-separated allowed origins for CORS, e.g. "https://admin.example.com,https://student.example.com"
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]


if not BASE_URL:
    raise RuntimeError("환경 변수 API_BASE_URL이 설정되지 않았습니다.")
