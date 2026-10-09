# tests/test_analysis.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_analyze():
    response = client.post("/api/analyze", json={
        "text": "We may change these terms at any time without notice."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] >= 1
    assert "segments" in data
