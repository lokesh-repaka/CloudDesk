"""Schemas for Model Context Protocol (MCP) Tool Discovery."""

from typing import Any

from pydantic import BaseModel, Field


class McpToolDefinitionResponse(BaseModel):
    """Schema representing an MCP-exposed tool definition and policy parameters."""

    name: str = Field(..., description="Tool identifier for invocation.")
    description: str = Field(..., description="Human and model-readable description of tool capabilities.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for accepted arguments.")
    is_consequential: bool = Field(default=False, description="Whether tool performs state-modifying actions.")
    requires_approval: bool = Field(default=False, description="Whether human approval is required.")
