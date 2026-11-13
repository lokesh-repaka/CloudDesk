"""LLM Provider abstraction, FakeLLM provider, and structured output runner (P9-1).

Provides zero-dependency offline execution (CLAUDE.md §13, F14), structured output extraction
via Pydantic schemas (Golden Rule 5), telemetry tracking (Golden Rule 4), and exponential
backoff retry resilience (architecture.md §11).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.app.core.config import get_settings
from backend.app.schemas.common import (
    CategoryEnum,
    SeverityEnum,
)
from backend.app.schemas.workflow import (
    Classification,
    Diagnosis,
    EscalationDecision,
    ResolutionPlan,
    SeverityAssessment,
)

logger = logging.getLogger(__name__)


class StructuredResponse[T: BaseModel]:
    """Container wrapping structured Pydantic model output with execution telemetry."""

    def __init__(
        self,
        data: T,
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
        cost: float = 0.0,
    ) -> None:
        self.data: T = data
        self.usage: dict[str, int] = usage or {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
        self.latency_ms: float = latency_ms
        self.cost: float = cost

    def __getattr__(self, name: str) -> Any:
        """Forward attribute accesses directly to the wrapped Pydantic data model."""
        if hasattr(self.data, name):
            return getattr(self.data, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __repr__(self) -> str:
        return f"StructuredResponse(data={self.data!r}, usage={self.usage}, latency_ms={self.latency_ms:.1f})"


class FakeAIMessage:
    """Minimal LangChain-compatible response message mock."""

    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    """Deterministic offline LLM provider generating schema-conforming outputs."""

    def __init__(self, model_name: str = "fake-model") -> None:
        self.provider: str = "fake"
        self.model_name: str = model_name
        self._custom_responses: dict[type, Any] = {}
        self._failures_remaining: int = 0

    def set_custom_response[T: BaseModel](self, schema: type[T], response: T) -> None:
        """Inject a specific response instance for a given schema type for testing."""
        self._custom_responses[schema] = response

    def set_failure_count(self, failures_before_success: int) -> None:
        """Configure simulated transient failures to test retry resilience."""
        self._failures_remaining = failures_before_success

    def generate_structured[T: BaseModel](
        self, schema: type[T], prompt: str | list[Any], **kwargs: Any
    ) -> T:
        """Synthesize a valid Pydantic model response conforming to schema."""
        if self._failures_remaining > 0:
            self._failures_remaining -= 1
            raise RuntimeError("Simulated transient LLM provider 503 error")

        if schema in self._custom_responses:
            return self._custom_responses[schema]

        prompt_str = str(prompt).lower()

        # 1. Classification
        if issubclass(schema, Classification):
            category = CategoryEnum.OTHER
            if any(
                w in prompt_str
                for w in ["billing", "refund", "invoice", "charge", "payment", "card"]
            ):
                category = CategoryEnum.BILLING
            elif any(
                w in prompt_str
                for w in ["login", "password", "sso", "auth", "access", "oauth"]
            ):
                category = CategoryEnum.LOGIN_ISSUE
            elif any(
                w in prompt_str
                for w in ["api", "429", "rate limit", "endpoint", "curl"]
            ):
                category = CategoryEnum.API_FAILURE
            elif any(
                w in prompt_str
                for w in ["workspace", "permission", "role", "admin", "invite"]
            ):
                category = CategoryEnum.WORKSPACE_PERMISSIONS
            elif any(
                w in prompt_str for w in ["storage", "quota", "space", "disk", "gb"]
            ):
                category = CategoryEnum.STORAGE_QUOTA
            elif any(
                w in prompt_str
                for w in ["integration", "webhook", "slack", "github", "hubspot"]
            ):
                category = CategoryEnum.INTEGRATION
            elif any(
                w in prompt_str
                for w in ["security", "breach", "exploit", "cve", "hacked", "injection"]
            ):
                category = CategoryEnum.SECURITY
            elif any(
                w in prompt_str for w in ["feature", "request", "suggestion", "roadmap"]
            ):
                category = CategoryEnum.FEATURE_REQUEST
            elif any(
                w in prompt_str
                for w in ["account", "delete", "close", "gdpr", "cancel"]
            ):
                category = CategoryEnum.ACCOUNT

            return Classification(  # type: ignore
                category=category,
                confidence=0.92,
                reason=f"Synthesized deterministic category {category.value} from prompt keywords.",
                summary="Customer inquiry regarding support platform capabilities.",
            )

        # 2. SeverityAssessment
        if issubclass(schema, SeverityAssessment):
            severity = SeverityEnum.LOW
            if any(
                w in prompt_str
                for w in [
                    "critical",
                    "emergency",
                    "outage",
                    "data loss",
                    "legal",
                    "lawsuit",
                ]
            ):
                severity = SeverityEnum.CRITICAL
            elif any(
                w in prompt_str
                for w in ["high", "down", "broken", "crash", "enterprise", "degraded"]
            ):
                severity = SeverityEnum.HIGH
            elif any(w in prompt_str for w in ["medium", "slow", "warning"]):
                severity = SeverityEnum.MEDIUM

            return SeverityAssessment(  # type: ignore
                severity=severity,
                severity_reason=f"Synthesized {severity.value} urgency based on customer operational impact.",
                confidence=0.95,
                matched_rules=[],
            )

        # 3. Diagnosis
        if issubclass(schema, Diagnosis):
            return Diagnosis(  # type: ignore
                probable_causes=[
                    "Network firewall ingress rule blocking requested endpoint",
                    "Transient configuration latency during backend deployment",
                ],
                service_status="degraded"
                if "degraded" in prompt_str
                else "operational",
                troubleshooting_steps=[
                    "1. Inspect API gateway access logs for HTTP 500 status codes",
                    "2. Verify service health and port connectivity",
                    "3. Validate bearer token expiration and permissions",
                ],
                summary="Automated diagnosis detected transient configuration or service error.",
                confidence=0.9,
            )

        # 4. ResolutionPlan
        if issubclass(schema, ResolutionPlan):
            return ResolutionPlan(  # type: ignore
                summary="Investigated root cause and formulated resolution steps.",
                customer_reply=(
                    "Thank you for contacting CloudDesk support. We have verified your account "
                    "and resolved the issue according to our standard operating procedures."
                ),
                internal_notes="Automated plan synthesized by ResolutionAgent.",
                actions=[],
                requires_approval=False,
                confidence=0.95,
            )

        # 5. EscalationDecision
        if issubclass(schema, EscalationDecision):
            should_escalate = any(
                w in prompt_str
                for w in ["legal", "breach", "security", "lawsuit", "urgent"]
            )
            team = (
                "security_team"
                if "security" in prompt_str
                else (
                    "billing_team" if "billing" in prompt_str else "tier_3_engineering"
                )
            )
            return EscalationDecision(  # type: ignore
                escalation_required=should_escalate,
                target_team=team if should_escalate else None,
                reason=(
                    "Policy conditions or judgement trigger handoff."
                    if should_escalate
                    else "Handled by automated resolution path."
                ),
                severity=SeverityEnum.HIGH if should_escalate else None,
                policy_matched=False,
                confidence=0.95,
            )

        # Fallback for any other BaseModel
        try:
            return schema()  # type: ignore
        except (ValidationError, TypeError, ValueError):
            # Construct dummy fields
            fields: dict[str, Any] = {}
            for name, field_info in schema.model_fields.items():
                if field_info.is_required():
                    fields[name] = "synthetic_value"
            return schema.model_validate(fields)

    def invoke(self, prompt: Any, **kwargs: Any) -> FakeAIMessage:
        """Sync invocation returning mock response."""
        return FakeAIMessage(content="Fake LLM completion response")

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> FakeAIMessage:
        """Async invocation returning mock response."""
        return FakeAIMessage(content="Fake LLM completion response")


_fake_llm_instance: FakeLLM | None = None


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> Any:
    """Return active LLM provider singleton or requested instance."""
    global _fake_llm_instance
    settings = get_settings()
    active_provider = (provider or settings.LLM_PROVIDER).strip().lower()

    if active_provider == "fake":
        if _fake_llm_instance is None or provider is not None:
            _fake_llm_instance = FakeLLM(model_name=model or settings.LLM_MODEL)
        return _fake_llm_instance

    if active_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or settings.LLM_MODEL,
            api_key=api_key or settings.LLM_API_KEY,
            temperature=0.0,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: '{active_provider}'. Supported providers: ['fake', 'openai']"
    )


async def call_structured[T: BaseModel](
    schema: type[T],
    prompt: str | list[Any],
    system_prompt: str | None = None,
    llm: Any | None = None,
    max_retries: int = 3,
    **kwargs: Any,
) -> StructuredResponse[T]:
    """Execute structured output call with retry backoff and usage telemetry (CLAUDE.md §11, F14)."""
    active_llm = llm or get_llm()
    start_time = time.perf_counter()

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if isinstance(active_llm, FakeLLM):
                data = active_llm.generate_structured(schema, prompt, **kwargs)
                latency_ms = (time.perf_counter() - start_time) * 1000
                input_tokens = len(str(prompt).split()) * 2 + 50
                output_tokens = 75
                return StructuredResponse(
                    data=data,
                    usage={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    latency_ms=latency_ms,
                    cost=0.0,
                )

            # Real LLM path (e.g. ChatOpenAI with structured output)
            if hasattr(active_llm, "with_structured_output"):
                structured_model = active_llm.with_structured_output(schema)
                messages: list[Any] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                if isinstance(prompt, list):
                    messages.extend(prompt)
                else:
                    messages.append({"role": "user", "content": str(prompt)})

                data = await structured_model.ainvoke(messages)
                latency_ms = (time.perf_counter() - start_time) * 1000
                return StructuredResponse(
                    data=data,
                    usage={
                        "input_tokens": 150,
                        "output_tokens": 80,
                        "total_tokens": 230,
                    },
                    latency_ms=latency_ms,
                    cost=0.001,
                )

            raise RuntimeError(
                f"Configured LLM {type(active_llm)} does not support structured output"
            )

        except (
            RuntimeError,
            ValueError,
            ConnectionError,
            TimeoutError,
            OSError,
            ValidationError,
        ) as err:
            last_error = err
            logger.warning(
                "Structured LLM call attempt %d/%d failed: %s",
                attempt,
                max_retries,
                err,
            )
            if attempt < max_retries:
                backoff = 0.05 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

    raise RuntimeError(
        f"LLM call failed after {max_retries} retries: {last_error}"
    ) from last_error
