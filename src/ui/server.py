"""FastAPI playground for interacting with the LangGraph agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..runner import execute_scenario, stream_scenario
from ..services.feature_flags import FeatureFlags
from ..services.rate_limiter import RateLimiter
from ..services.tenant_registry import TenantRegistry
from .annotations import router as annotations_router

app = FastAPI(title="LangGraph Playground")
app.include_router(annotations_router)
feature_flags = FeatureFlags()
tenant_registry = TenantRegistry()
rate_limiter = RateLimiter()


class RunRequest(BaseModel):
    prompt: str
    context: Dict[str, Any] = {}
    scenario_id: Optional[str] = None
    graph_config: Optional[str] = None


def tenant_dependency(tenant_id: str = Header("default", alias="X-Tenant-ID")) -> Dict[str, Any]:
    config = dict(tenant_registry.get(tenant_id))
    config.setdefault("feature_flags", {})
    config["id"] = tenant_id
    return config


@app.get("/healthz")
async def health(tenant: Dict[str, Any] = Depends(tenant_dependency)):
    """Health endpoint for readiness probes."""
    return {
        "status": "ok",
        "tenant": tenant["id"],
        "features": feature_flags.snapshot(tenant.get("feature_flags")),
    }


@app.post("/run")
async def run(request: RunRequest, tenant: Dict[str, Any] = Depends(tenant_dependency)):
    """Execute a single scenario via HTTP."""
    if not feature_flags.is_enabled("agent_run", tenant.get("feature_flags")):
        raise HTTPException(status_code=403, detail="Agent execution disabled for this tenant.")
    if not rate_limiter.allow(tenant["id"], tenant.get("rate_limit_rpm")):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for tenant.")
    payload = {"prompt": request.prompt, "context": request.context or {}}
    if request.scenario_id:
        payload["context"]["scenario_id"] = request.scenario_id
    payload["context"]["tenant_id"] = tenant["id"]
    if tenant.get("model_provider"):
        payload["context"].setdefault("model_provider", tenant["model_provider"])
    result = execute_scenario(
        payload,
        scenario_name=payload["context"].get("scenario_id", "http"),
        graph_config=request.graph_config,
    )
    return {
        "output": result.get("output"),
        "route": result.get("route"),
        "metadata": result.get("metadata"),
        "artifacts": result.get("artifacts"),
    }


@app.websocket("/ws")
async def ws_run(websocket: WebSocket):
    """Stream LangGraph events over WebSocket."""
    tenant = _tenant_from_header(websocket.headers.get("x-tenant-id", "default"))
    if not feature_flags.is_enabled("streaming", tenant.get("feature_flags")):
        await websocket.close(code=4003)
        return
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            if not rate_limiter.allow(tenant["id"], tenant.get("rate_limit_rpm")):
                await websocket.send_json({"label": "error", "payload": "rate limit exceeded"})
                continue
            prompt = payload.get("prompt", "")
            context = payload.get("context") or {}
            scenario_id = payload.get("scenario_id") or context.get("scenario_id") or "ws"
            wrapper = {"prompt": prompt, "context": context}
            wrapper["context"]["tenant_id"] = tenant["id"]
            if tenant.get("model_provider"):
                wrapper["context"].setdefault("model_provider", tenant["model_provider"])
            async for label, event in _stream(wrapper, scenario_id, payload.get("graph_config")):
                await websocket.send_json({"label": label, "payload": event})
    except WebSocketDisconnect:
        return


async def _stream(payload: Dict[str, Any], scenario_id: str, graph_config: Optional[str]):
    for label, event in stream_scenario(payload, scenario_name=scenario_id, graph_config=graph_config):
        yield label, event


def _tenant_from_header(tenant_id: str) -> Dict[str, Any]:
    config = dict(tenant_registry.get(tenant_id))
    config.setdefault("feature_flags", {})
    config["id"] = tenant_id
    return config
