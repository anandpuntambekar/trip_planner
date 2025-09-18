from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app


def _sample_payload() -> dict:
    return {
        "origin": "San Francisco",
        "destinations": ["Paris", "Amsterdam"],
        "dates": {"start": "2025-10-10", "end": "2025-10-20"},
        "budget_total": 4500,
        "currency": "USD",
        "party": {"adults": 2, "children": 1, "seniors": 0},
        "prefs": {"objective": "balanced"},
    }


def test_api_plan_endpoint(monkeypatch):
    client = TestClient(app)
    orchestrator = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("app.main.orchestrate_llm_trip", orchestrator)

    response = client.post("/api/plan", json=_sample_payload())

    assert response.status_code == 200
    orchestrator.assert_awaited_once()
    called_args = orchestrator.await_args.args
    called_kwargs = orchestrator.await_args.kwargs
    called_payload = called_args[0]
    assert called_payload["purpose"] == "leisure"
    assert called_kwargs.get("openai_api_key") is None
    assert called_kwargs.get("tavily_api_key") is None
    assert response.json() == {"status": "ok"}


def test_api_plan_endpoint_handles_runtime_keys(monkeypatch):
    client = TestClient(app)
    orchestrator = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("app.main.orchestrate_llm_trip", orchestrator)

    payload = _sample_payload()
    payload.update({
        "openai_api_key": "sk-user",  # trimmed server-side
        "tavily_api_key": " tv-user ",
    })

    response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    orchestrator.assert_awaited_once()
    called_args = orchestrator.await_args.args
    called_kwargs = orchestrator.await_args.kwargs

    called_payload = called_args[0]
    assert "openai_api_key" not in called_payload
    assert "tavily_api_key" not in called_payload
    assert called_kwargs["openai_api_key"] == "sk-user"
    assert called_kwargs["tavily_api_key"] == "tv-user"


def test_trip_llm_only_endpoint(monkeypatch):
    client = TestClient(app)
    orchestrator = AsyncMock(return_value={"bundle_count": 3})
    monkeypatch.setattr("app.main.orchestrate_llm_trip", orchestrator)

    response = client.post(
        "/trip/llm_only",
        json={
            "origin": "San Francisco",
            "purpose": "family vacation",
            "budget_total": 5000,
            "currency": "USD",
            "dates": {"start": "2025-10-10", "end": "2025-10-20"},
            "party": {"adults": 2, "children": 1, "seniors": 0},
            "constraints": {},
            "interests": [],
            "destinations": ["Paris", "Amsterdam"],
            "openai_api_key": "sk-inline",
            "tavily_api_key": "tv-inline",
        },
    )

    assert response.status_code == 200
    orchestrator.assert_awaited_once()
    called_args = orchestrator.await_args.args
    called_kwargs = orchestrator.await_args.kwargs
    assert called_kwargs["openai_api_key"] == "sk-inline"
    assert called_kwargs["tavily_api_key"] == "tv-inline"
    assert response.json() == {"bundle_count": 3}
