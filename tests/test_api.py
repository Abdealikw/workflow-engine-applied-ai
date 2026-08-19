import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_create_invalid_workflow_cycle():
    payload = {
        "name": "Invalid Cycle",
        "dag": {
            "nodes": [
                {"id": "A", "handler": "input", "dependencies": ["B"]},
                {"id": "B", "handler": "process", "dependencies": ["A"]}
            ]
        }
    }
    response = httpx.post(f"{BASE_URL}/workflow", json=payload)
    assert response.status_code == 422
    assert "Cycle detected" in response.text

def test_create_invalid_missing_dependency():
    payload = {
        "name": "Missing Dep",
        "dag": {
            "nodes": [
                {"id": "A", "handler": "input", "dependencies": ["Z"]}
            ]
        }
    }
    response = httpx.post(f"{BASE_URL}/workflow", json=payload)
    assert response.status_code == 422
    assert "does not exist" in response.text

def test_trigger_non_existent():
    response = httpx.post(f"{BASE_URL}/workflow/trigger/invalid-uuid-1234")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"

def test_get_status_non_existent():
    response = httpx.get(f"{BASE_URL}/workflows/invalid-uuid-1234")
    assert response.status_code == 404
    
def test_get_results_non_existent():
    response = httpx.get(f"{BASE_URL}/workflows/invalid-uuid-1234/results")
    assert response.status_code == 404
