"""Base tool abstractions and data structures for CloudDesk.

Provides ToolResult and ToolDefinition models along with a @tool decorator
that bridges callable python functions with the centralized ToolRegistry and
LangChain ecosystem.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Structured result returned by ToolRegistry execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ok: bool = Field(..., description="Whether the tool execution succeeded.")
    data: Any = Field(default=None, description="Result data or payload if successful.")
    error: str | None = Field(default=None, description="Error message if execution failed.")
    tool_name: str | None = Field(default=None, description="Identifier of the executed tool.")
    duration_ms: float | None = Field(
        default=None, description="Elapsed execution time in milliseconds."
    )


class ToolDefinition:
    """Metadata and execution wrapper for a registered platform tool."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        is_async: bool = False,
        is_consequential: bool = False,
        requires_approval: bool = False,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description.strip() if description else ""
        self.func = func
        self.is_async = is_async
        self.is_consequential = is_consequential
        self.requires_approval = requires_approval
        self.parameters = parameters or {}

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the underlying function, awaiting if asynchronous."""
        if self.is_async:
            return await self.func(*args, **kwargs)
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<ToolDefinition name='{self.name}' async={self.is_async}>"


def tool(
    _func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    is_consequential: bool = False,
    requires_approval: bool = False,
) -> Any:
    """Decorator to declare and configure a platform tool.

    Can be used bare (`@tool`) or parameterized (`@tool(name='...')`).
    """

    def decorator(fn: Callable[..., Any]) -> ToolDefinition:
        tool_name = name or fn.__name__
        tool_desc = description or fn.__doc__ or ""
        is_async = inspect.iscoroutinefunction(fn)

        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_desc,
            func=fn,
            is_async=is_async,
            is_consequential=is_consequential,
            requires_approval=requires_approval,
        )
        # Preserve original function reference for introspection
        wraps(fn)(tool_def)
        return tool_def

    if _func is not None:
        return decorator(_func)
    return decorator

