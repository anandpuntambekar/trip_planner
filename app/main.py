from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.orchestrator import orchestrate_llm_trip
from app.schemas import TripRequest

app = FastAPI(title="Trip Planner Agentic API")

# Allow local development UIs (Vite dev server, static builds, notebooks) to reach
# the API without wrestling with browser CORS restrictions. Operators can scope
# this via TRIP_PLANNER_ALLOWED_ORIGINS if they prefer something narrower.
raw_origins = os.getenv("TRIP_PLANNER_ALLOWED_ORIGINS") or "*"
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def _plan_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the incoming payload and delegate to the orchestrator."""

    payload = dict(payload)
    payload.setdefault("purpose", payload.get("purpose") or "leisure")

    raw_openai_key = payload.pop("openai_api_key", None) or payload.pop("openAiKey", None)
    raw_tavily_key = payload.pop("tavily_api_key", None) or payload.pop("tavilyKey", None)

    openai_api_key = raw_openai_key.strip() if isinstance(raw_openai_key, str) else None
    if openai_api_key == "":
        openai_api_key = None

    tavily_api_key = raw_tavily_key.strip() if isinstance(raw_tavily_key, str) else None
    if tavily_api_key == "":
        tavily_api_key = None

    try:
        TripRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    allow_domains: List[str] | None = payload.get("allow_domains")
    deny_domains: List[str] | None = payload.get("deny_domains")
    return await orchestrate_llm_trip(
        payload,
        allow_domains,
        deny_domains,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
    )

@app.post("/api/plan")
async def api_plan(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Primary endpoint consumed by the Vite frontend."""
    return await _plan_from_payload(payload)

@app.post("/trip/llm_only", include_in_schema=False)
async def trip_llm_only(
    origin: str = Body(...),
    purpose: str | None = Body(None),
    budget_total: float = Body(...),
    currency: str = Body("USD"),
    dates: dict = Body(...),
    party: dict = Body(...),
    constraints: dict = Body({}),
    interests: list = Body([]),
    destinations: list = Body(...),
    allow_domains: list[str] | None = Body(None),
    deny_domains: list[str] | None = Body(None),
    openai_api_key: str | None = Body(None),
    tavily_api_key: str | None = Body(None),
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "origin": origin,
        "purpose": purpose or "leisure",
        "budget_total": budget_total,
        "currency": currency,
        "dates": dates,
        "party": party,
        "constraints": constraints,
        "interests": interests,
        "destinations": destinations,
    }
    if allow_domains is not None:
        payload["allow_domains"] = allow_domains
    if deny_domains is not None:
        payload["deny_domains"] = deny_domains
    if openai_api_key:
        payload["openai_api_key"] = openai_api_key
    if tavily_api_key:
        payload["tavily_api_key"] = tavily_api_key
    return await _plan_from_payload(payload)
