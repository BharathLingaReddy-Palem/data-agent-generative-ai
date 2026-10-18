"""
test_live_api.py — Verify Live API Endpoints on http://127.0.0.1:8000
=====================================================================
Manual smoke check of key health, upload/profile, AutoML polling and prediction.
Creates records and may contact configured providers. Full analysis, ownership,
restarts and failure cases are covered by the separate offline tests/ suite.
"""

import sys
import os
import time
import requests
from pathlib import Path
from test_api_session import authenticated_session

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get('DS_TEST_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
ROOT = Path(__file__).resolve().parent

def test_live():
    session = authenticated_session(BASE_URL)
    print(f"Connecting to live backend at {BASE_URL}...")
    
    # 1. Health check / Key health
    res = session.get(f"{BASE_URL}/api/keys/health", timeout=5)
    assert res.status_code == 200, f"Key health failed: {res.text}"
    print("  [1/5] Key Health API: OK (200)")

    # 2. Upload dataset (test/tested.csv)
    with (ROOT/'test'/'tested.csv').open('rb') as f:
        res = session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("tested.csv", f, "text/csv")},
            data={"user_question": "Analyze survival factors"},
            timeout=10,
        )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    upload_data = res.json()
    project_id = upload_data["project_id"]
    print(f"  [2/5] Upload API: OK (200), project_id={project_id}")

    # 3. Profile dataset
    with (ROOT/'test'/'tested.csv').open('rb') as f:
        res = session.post(
            f"{BASE_URL}/api/profile",
            files={"file": ("tested.csv", f, "text/csv")},
            timeout=10,
        )
    assert res.status_code == 200, f"Profile failed: {res.text}"
    prof_data = res.json()
    assert "column_names" in prof_data
    assert "columns" in prof_data
    print(f"  [3/5] Profile API: OK (200), Health: {prof_data['health']['score']}/100")

    # 4. Start AutoML Competition Job
    res = session.post(
        f"{BASE_URL}/api/automl/start",
        json={"project_id": project_id, "target_column": "Survived", "run_tuning": True},
        timeout=10,
    )
    assert res.status_code == 200, f"AutoML start failed: {res.text}"
    automl_job = res.json()
    job_id = automl_job["job_id"]
    print(f"  [4/5] AutoML Job Started: OK (job_id={job_id}). Polling...")

    # Poll AutoML job
    for _ in range(60):
        time.sleep(1)
        st_res = session.get(f"{BASE_URL}/api/job/{job_id}/status", timeout=5)
        st_res.raise_for_status()
        st = st_res.json()
        if st["status"] == "completed":
            print(f"        AutoML Job Completed! Fetching result...")
            break
        elif st["status"] == "failed":
            raise RuntimeError(f"AutoML job failed: {st.get('error')}")
    else:
        raise TimeoutError(f'AutoML job {job_id} did not finish within the polling deadline.')

    res_out = session.get(f"{BASE_URL}/api/job/{job_id}/result", timeout=5)
    assert res_out.status_code == 200, f"Failed to fetch AutoML result: {res_out.text}"
    automl_result = res_out.json()
    assert "leaderboard" in automl_result
    best_m = automl_result['best_model']['model_name']
    print(f"        AutoML Result: OK (200), Best Model: {best_m}, Algorithms: {len(automl_result['leaderboard'])}")

    # 5. What-If Prediction API
    pred_res = session.post(
        f"{BASE_URL}/api/predict",
        json={"project_id": project_id, "input_data": {"Pclass": 1, "Sex": "female", "Age": 29, "Fare": 100}},
        timeout=5,
    )
    assert pred_res.status_code == 200, f"Prediction failed: {pred_res.text}"
    pred_data = pred_res.json()
    print(f"  [5/5] Prediction API: OK (200), Predicted Class: {pred_data['predictions'][0]}")

    print("\nLive smoke checks passed: key health, upload/profile, AutoML and prediction.")

if __name__ == "__main__":
    test_live()
