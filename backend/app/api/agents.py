"""Agent Topology and Specialist Profiles Discovery API (P10-5).

Provides:
- GET /api/v1/agents: LangGraph nodes, edges, and 6 specialist agent profiles (viewer permitted).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agents.graph import GRAPH_EDGES, GRAPH_NODES, SPECIALIST_AGENTS
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import RoleEnum

router = APIRouter(tags=["agents"])


class SpecialistAgentResponse(BaseModel):
    """Specialist agent profile describing its nodes, tools, and rules."""

    name: str = Field(..., description="Agent specialist name")
    description: str = Field(..., description="Agent operational role and scope")
    nodes: list[str] = Field(
        default_factory=list, description="Graph nodes managed by this specialist"
    )
    tools: list[str] = Field(
        default_factory=list, description="Tool abstractions available to agent"
    )
    rules: list[str] = Field(
        default_factory=list, description="Deterministic rule layers applied"
    )


class AgentTopologyResponse(BaseModel):
    """LangGraph StateGraph topology specification and specialist catalog."""

    nodes: list[str] = Field(..., description="Ordered list of all 12 LangGraph nodes")
    edges: list[dict[str, Any]] = Field(
        ..., description="Directed graph transitions and conditional edges"
    )
    specialists: list[SpecialistAgentResponse] = Field(
        ..., description="Catalog of 6 specialist agents"
    )


@router.get(
    "",
    response_model=AgentTopologyResponse,
    summary="Get LangGraph agent topology and specialist profiles",
)
@router.get(
    "/",
    response_model=AgentTopologyResponse,
    include_in_schema=False,
)
async def get_agent_topology(
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> AgentTopologyResponse:
    """Retrieve the LangGraph pipeline topology, conditional edges, and specialist profiles (AC-060)."""
    return AgentTopologyResponse(
        nodes=GRAPH_NODES,
        edges=GRAPH_EDGES,
        specialists=[SpecialistAgentResponse(**spec) for spec in SPECIALIST_AGENTS],
    )
