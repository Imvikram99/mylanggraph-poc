"""FastAPI router for collecting annotation preferences."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..rlhf.preferences import Preference, PreferenceStore
from ..rlhf.queue import AnnotationQueue, AnnotationTask

router = APIRouter(prefix="/annotations", tags=["annotations"])


class PreferenceRequest(BaseModel):
    prompt: str
    response_a: str
    response_b: str
    winner: str
    annotator_id: str
    notes: str | None = ""


class QueueRequest(BaseModel):
    prompt: str
    response_a: str
    response_b: str
    priority: int = 0


class QueueCompleteRequest(BaseModel):
    task_id: str


@router.post("/preferences")
async def add_preference(payload: PreferenceRequest):
    if payload.winner not in {"A", "B"}:
        raise HTTPException(status_code=400, detail="winner must be 'A' or 'B'")
    store = PreferenceStore()
    store.add(
        Preference(
            prompt=payload.prompt,
            response_a=payload.response_a,
            response_b=payload.response_b,
            winner=payload.winner,
            annotator_id=payload.annotator_id,
            notes=payload.notes or "",
        )
    )
    return {"status": "ok"}


@router.get("/preferences")
async def list_preferences():
    store = PreferenceStore()
    return store.list()


@router.get("/bias-metrics")
async def bias_metrics():
    store = PreferenceStore()
    return store.bias_metrics()


@router.post("/queue")
async def enqueue(payload: QueueRequest):
    queue = AnnotationQueue()
    record = queue.enqueue(
        AnnotationTask(
            prompt=payload.prompt,
            response_a=payload.response_a,
            response_b=payload.response_b,
            priority=payload.priority,
        )
    )
    return record


@router.get("/queue/next")
async def next_task():
    queue = AnnotationQueue()
    task = queue.next_task()
    if not task:
        raise HTTPException(status_code=404, detail="No pending tasks.")
    return task


@router.post("/queue/complete")
async def complete_task(payload: QueueCompleteRequest):
    queue = AnnotationQueue()
    queue.complete(payload.task_id)
    return {"status": "completed", "task_id": payload.task_id}


@router.get("/dashboard")
async def dashboard(top_k: int = 5):
    store = PreferenceStore()
    queue = AnnotationQueue()
    entries = queue.list()
    return {
        "total_preferences": len(store.list()),
        "bias": store.bias_metrics(),
        "queue_pending": len([task for task in entries if task.get("status") == "pending"]),
        "recent_tasks": entries[-top_k:],
    }


@router.get("/active-learning")
async def active_learning(top_k: int = 5):
    store = PreferenceStore()
    return {"uncertain": store.uncertain_samples(top_k=top_k)}
