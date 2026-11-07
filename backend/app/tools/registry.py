"""Central tool registry and sandboxed execution manager.

Enforces:
- Centralized execution: All tool invocations flow through ToolRegistry.execute().
- Policy gating: Blocks unapproved consequential operations.
- Resilience: Timeouts (TOOL_TIMEOUT_SECONDS) and exception sandboxing to prevent
  LangGraph engine crashes.
"""

import asyncio
import inspect
import logging
import time
from functools import lru_cache
from typing import Any

from backend.app.core.config import Settings, get_settings
from backend.app.tools.base import ToolDefinition, ToolResult
from backend.app.tools.policy import ToolPolicy, get_tool_policy

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry managing available tools, policy gates, and sandboxed execution."""

    def __init__(
        self,
        policy: ToolPolicy | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.policy = policy or get_tool_policy()
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool_input: ToolDefinition | Any) -> ToolDefinition:
        """Register a tool definition, decorated function, or compatible tool."""
        if isinstance(tool_input, ToolDefinition):
            tool_def = tool_input
        elif hasattr(tool_input, "name") and hasattr(tool_input, "func"):
            # If wrapped by langchain or custom object
            tool_def = ToolDefinition(
                name=tool_input.name,
                description=getattr(tool_input, "description", "") or "",
                func=tool_input.func,
                is_async=inspect.iscoroutinefunction(tool_input.func),
            )
        elif callable(tool_input):
            tool_name = getattr(tool_input, "__name__", "unnamed_tool")
            tool_desc = getattr(tool_input, "__doc__", "") or ""
            is_async = inspect.iscoroutinefunction(tool_input)
            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                func=tool_input,
                is_async=is_async,
            )
        else:
            raise TypeError(f"Cannot register object of type {type(tool_input)} as a tool.")

        self._tools[tool_def.name] = tool_def
        logger.debug("Registered tool in registry: %s", tool_def.name)
        return tool_def

    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve a registered tool definition by name."""
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        """Return list of all registered tool names."""
        return list(self._tools.keys())

    async def execute(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        approved: bool = False,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a tool with policy verification, timeout bounds, and exception isolation."""
        start_time = time.perf_counter()
        call_args = args or {}

        # 1. Enforce policy gating
        permitted, err_reason = self.policy.check_execution_permitted(
            tool_name=name,
            args=call_args,
            approved=approved,
        )
        if not permitted:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Tool '%s' blocked by policy: %s", name, err_reason)
            return ToolResult(
                ok=False,
                error=err_reason,
                tool_name=name,
                duration_ms=round(duration_ms, 2),
            )

        # 2. Check registration existence
        tool_def = self.get(name)
        if tool_def is None:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                ok=False,
                error=f"Tool '{name}' is not registered.",
                tool_name=name,
                duration_ms=round(duration_ms, 2),
            )

        # 3. Execute tool under timeout and exception sandbox
        effective_timeout = (
            timeout if timeout is not None else float(self.settings.TOOL_TIMEOUT_SECONDS)
        )

        try:
            if tool_def.is_async:
                result_data = await asyncio.wait_for(
                    tool_def(**call_args),
                    timeout=effective_timeout,
                )
            else:
                result_data = await asyncio.wait_for(
                    asyncio.to_thread(tool_def.func, **call_args),
                    timeout=effective_timeout,
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                ok=True,
                data=result_data,
                tool_name=name,
                duration_ms=round(duration_ms, 2),
            )

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = f"Tool '{name}' timed out after {effective_timeout} seconds."
            logger.error(error_msg)
            return ToolResult(
                ok=False,
                error=error_msg,
                tool_name=name,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception("Error executing tool '%s'", name)
            return ToolResult(
                ok=False,
                error=str(exc),
                tool_name=name,
                duration_ms=round(duration_ms, 2),
            )


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Return a cached singleton ToolRegistry instance."""
    return ToolRegistry()
