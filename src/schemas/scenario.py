"""Pydantic schemas for scenario IO validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class Assertion(BaseModel):
    type: str
    value: Optional[str] = None
    equals: Optional[Any] = None
    path: Optional[List[Any]] = None


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    prompt: str = Field(default="Hello LangGraph!")
    context: Dict[str, Any] = Field(default_factory=dict)
    assertions: Optional[List[Assertion]] = None


class ScenarioOutput(BaseModel):
    output: str
    metadata: Dict[str, Any]
    route: Optional[str]


class IOAuditRecord(BaseModel):
    scenario_id: str
    valid_input: bool
    valid_output: bool
    route: Optional[str]
    workflow_phase: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
