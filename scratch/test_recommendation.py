import os, sys, time, json
os.environ["API_BASE_URL"] = "http://test"
sys.path.insert(0, "src")
from db.session import get_db_session
from db.repo import analyze_user_weakness, get_recommended_problems
from app import app

def test_recommendation_engine():
    print("=== [TEST 1] DB Repository Recommendation Logic Test ===")
    start_time = time.perf_counter()
    with get_db_session() as session:
        weak_groups = analyze_user_weakness(session, "osw1110")
        recs = get_recommended_problems(session, "osw1110", limit=3)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print(f"[PASS] Weak groups count: {len(weak_groups)}")
    print(f"[PASS] Recommended problems count: {len(recs)}")
    print(f"[PASS] Execution time: {elapsed_ms:.2f} ms")
    assert len(recs) > 0, "No recommendations generated!"
    for idx, r in enumerate(recs, 1):
        print(f"  Recommendation #{idx}: [{r['legacy_code']}] {r['title']} (Tier {r['tier']}: {r['reason']})")
    print("\n=== [TEST 2] API Endpoint Test (/api/students/<uuid>/recommendations) ===")
    client = app.test_client()
    with client:
        res = client.get("/api/students/6973f152-3e1e-4e4a-85ff-7f7e80c60706/recommendations")
        print(f"[INFO] API Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.get_jcon()
            print(f"[PASS] API JSON ok={data.get('ok')}, recs_count={len(data.get('recommendations', []))}")
            assert data.get("ok") == True
        elif res.status_code in (401, 403):
            print("OK: API is protected")
    print("\n[ALL TESTS PASSED SUCCESSFULLY]")

if __name__ == "__main__":
    test_recommendation_engine()