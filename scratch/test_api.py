import os, sys, time, json
os.environ["API_BASE_URL"] = "http://test"
sys.path.insert(0, "src")
from db.session import get_db_session
from db.repo import analyze_user_weakness, get_recommended_problems
from app import app
from utils.utils_common import is_admin_profile

# Mock admin check for test
import utils.utils_common as uc
uc.ensure_admin_or_403 = lambda: (None, None)

client = app.test_client()
res = client.get("/api/students/6973f152-3e1e-4e4a-85ff-7f7e80c60706/recommendations")
print("HTTP Status:", res.status_code)
print("JSON Response:", json.dumps(res.get_json(), ensure_ascii=False, indent=2))
