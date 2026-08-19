import time
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_full_workflow_execution():
    # 1. Create Workflow
    payload = {
        "name": "E2E Test Workflow",
        "dag": {
            "nodes": [
                {"id": "A", "handler": "input", "dependencies": []},
                {"id": "B", "handler": "call_external_service", "dependencies": ["A"], "config": {"url": "http://mock/user"}},
                {"id": "C", "handler": "call_external_service", "dependencies": ["A"], "config": {"url": "http://mock/posts"}},
                {"id": "D", "handler": "output", "dependencies": ["B", "C"]}
            ]
        }
    }
    
    response = httpx.post(f"{BASE_URL}/workflow", json=payload)
    assert response.status_code == 200
    workflow_id = response.json()["id"]
    
    # 2. Trigger Workflow
    response = httpx.post(f"{BASE_URL}/workflow/trigger/{workflow_id}")
    assert response.status_code == 200
    execution_id = response.json()["execution_id"]
    
    # 3. Poll for completion (Wait up to 10 seconds)
    max_retries = 10
    completed = False
    
    for _ in range(max_retries):
        time.sleep(1) # Worker takes 1s for call_external_service
        res = httpx.get(f"{BASE_URL}/workflows/{execution_id}")
        assert res.status_code == 200
        
        status_data = res.json()
        if status_data["status"] == "COMPLETED":
            completed = True
            break
        elif status_data["status"] == "FAILED":
            pytest.fail("Workflow execution failed!")
            
    assert completed, "Workflow did not complete within the timeout period"
    
    # 4. Verify Results
    res = httpx.get(f"{BASE_URL}/workflows/{execution_id}/results")
    assert res.status_code == 200
    results = res.json()["results"]
    
    assert "A" in results
    assert "B" in results
    assert "C" in results
    assert "D" in results
    assert results["B"]["status"] == 200
    assert results["C"]["status"] == 200
