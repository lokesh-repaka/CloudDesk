import json
import logging
from io import StringIO
import pytest
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import (
    JSONFormatter,
    setup_logging,
    set_request_id,
    get_request_id,
    set_workflow_id,
    get_workflow_id,
    clear_context,
)


class TestSettings:
    def test_default_settings(self):
        """Test default values conform to CLAUDE.md specification."""
        settings = Settings()
        assert settings.DEMO_MODE is True
        assert settings.ENVIRONMENT == "development"
        assert "http://localhost:3000" in settings.CORS_ORIGINS
        assert settings.effective_jwt_secret == settings.JWT_SECRET
        assert "support.db" in settings.DATABASE_URL
        assert settings.CHECKPOINT_DB_PATH == "./data/checkpoints.db"
        assert settings.USE_FAKE_REDIS is True
        assert settings.LLM_PROVIDER == "fake"
        assert settings.EMBEDDING_PROVIDER == "fake"
        assert settings.EMBEDDING_DIMENSIONS == 384
        assert settings.VECTOR_STORE == "memory"
        assert settings.QDRANT_COLLECTION == "clouddesk_knowledge"
        assert settings.APPROVAL_REQUIRED_FOR_REFUNDS is True
        assert settings.MAX_REFUND_WITHOUT_APPROVAL == 0.0
        assert settings.TOOL_TIMEOUT_SECONDS == 30
        assert settings.RATE_LIMIT_PER_MINUTE == 120
        assert settings.SAMPLE_DATA_DIR == "./sample_data"
        assert settings.LANGCHAIN_PROJECT == "clouddesk-support"

    def test_effective_jwt_secret_prefers_supabase(self, monkeypatch):
        """SUPABASE_JWT_SECRET overrides JWT_SECRET when set."""
        monkeypatch.setenv("JWT_SECRET", "jwt-fallback")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "supabase-secret-key")
        settings = Settings()
        assert settings.effective_jwt_secret == "supabase-secret-key"

    def test_effective_jwt_secret_fallback(self, monkeypatch):
        """JWT_SECRET is used when SUPABASE_JWT_SECRET is not set."""
        monkeypatch.setenv("JWT_SECRET", "custom-jwt-key")
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        settings = Settings()
        assert settings.effective_jwt_secret == "custom-jwt-key"

    def test_cors_origins_parsing(self, monkeypatch):
        """CORS_ORIGINS can be passed as JSON string or comma-separated."""
        monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000", "https://app.clouddesk.demo"]')
        settings = Settings()
        assert "https://app.clouddesk.demo" in settings.CORS_ORIGINS

    def test_get_settings_caching(self):
        """get_settings() returns the same cached instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_redis_configuration(self, monkeypatch):
        """is_fake_redis reflects USE_FAKE_REDIS and REDIS_URL."""
        s_default = Settings()
        assert s_default.is_fake_redis is True

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("USE_FAKE_REDIS", "false")
        s_real = Settings()
        assert s_real.is_fake_redis is False

    def test_numeric_and_boolean_overrides(self, monkeypatch):
        """Test numeric and boolean env vars can be overridden properly."""
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "60")
        monkeypatch.setenv("MAX_REFUND_WITHOUT_APPROVAL", "50.0")
        monkeypatch.setenv("APPROVAL_REQUIRED_FOR_REFUNDS", "false")
        settings = Settings()
        assert settings.RATE_LIMIT_PER_MINUTE == 60
        assert settings.MAX_REFUND_WITHOUT_APPROVAL == 50.0
        assert settings.APPROVAL_REQUIRED_FOR_REFUNDS is False

    def test_production_rejects_default_jwt_secret(self, monkeypatch):
        """In production or staging, default dev secret is rejected."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-prod")
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(ValueError, match="Production or staging deployments must specify a secure"):
            Settings()

    def test_production_accepts_valid_jwt_secret(self, monkeypatch):
        """In production, a custom secure secret is accepted."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET", "super-secret-unique-production-key-999")
        settings = Settings()
        assert settings.effective_jwt_secret == "super-secret-unique-production-key-999"


class TestJSONLogging:
    @pytest.fixture(autouse=True)
    def clean_ctx(self):
        clear_context()
        yield
        clear_context()

    def test_context_set_and_get(self):
        assert get_request_id() is None
        assert get_workflow_id() is None

        set_request_id("req-12345")
        set_workflow_id("wf-67890")

        assert get_request_id() == "req-12345"
        assert get_workflow_id() == "wf-67890"

        clear_context()
        assert get_request_id() is None
        assert get_workflow_id() is None

    def test_json_formatter_basic(self):
        formatter = JSONFormatter()
        logger = logging.getLogger("test_basic_logger")
        record = logger.makeRecord(
            name=logger.name,
            level=logging.INFO,
            fn="test_file.py",
            lno=42,
            msg="User %s logged in",
            args=("admin",),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_basic_logger"
        assert data["message"] == "User admin logged in"
        assert "timestamp" in data
        assert "request_id" in data
        assert "workflow_id" in data
        assert data["request_id"] is None
        assert data["workflow_id"] is None

    def test_json_formatter_with_context(self):
        formatter = JSONFormatter()
        set_request_id("req-abc-999")
        set_workflow_id("wf-xyz-111")

        logger = logging.getLogger("test_context_logger")
        record = logger.makeRecord(
            name=logger.name,
            level=logging.WARNING,
            fn="test_file.py",
            lno=100,
            msg="High latency observed",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "WARNING"
        assert data["message"] == "High latency observed"
        assert data["request_id"] == "req-abc-999"
        assert data["workflow_id"] == "wf-xyz-111"

    def test_json_formatter_with_exception(self):
        formatter = JSONFormatter()
        logger = logging.getLogger("test_exc_logger")

        try:
            raise ValueError("Invalid ticket state")
        except ValueError:
            import sys
            record = logger.makeRecord(
                name=logger.name,
                level=logging.ERROR,
                fn="test_file.py",
                lno=200,
                msg="Operation failed",
                args=(),
                exc_info=sys.exc_info(),
            )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "ERROR"
        assert data["message"] == "Operation failed"
        assert "exception" in data
        assert "ValueError: Invalid ticket state" in data["exception"]

    def test_setup_logging_integration(self):
        stream = StringIO()
        setup_logging(level="DEBUG", stream=stream)

        set_request_id("req-stream-test")
        test_log = logging.getLogger("integration.test")
        test_log.info("Hello CloudDesk!")

        output = stream.getvalue().strip()
        lines = output.splitlines()
        assert len(lines) >= 1
        last_line = json.loads(lines[-1])
        assert last_line["message"] == "Hello CloudDesk!"
        assert last_line["request_id"] == "req-stream-test"
        assert last_line["level"] == "INFO"

    def test_json_formatter_extra_fields(self):
        stream = StringIO()
        setup_logging(level="INFO", stream=stream)

        logger = logging.getLogger("extra.fields.test")
        logger.info("Processing ticket", extra={"ticket_id": "CD-1002", "refund_amount": 120.5})

        output = stream.getvalue().strip()
        last_line = json.loads(output.splitlines()[-1])
        assert last_line["ticket_id"] == "CD-1002"
        assert last_line["refund_amount"] == 120.5

    def test_json_formatter_non_string_object(self):
        stream = StringIO()
        setup_logging(level="INFO", stream=stream)

        class CustomData:
            def __str__(self):
                return "custom-data-obj"

        logger = logging.getLogger("object.test")
        logger.info("Object test", extra={"payload": CustomData()})

        output = stream.getvalue().strip()
        last_line = json.loads(output.splitlines()[-1])
        assert last_line["payload"] == "custom-data-obj"

    def test_json_formatter_masks_sensitive_extra_fields(self):
        stream = StringIO()
        setup_logging(level="INFO", stream=stream)

        logger = logging.getLogger("security.redaction.test")
        logger.info(
            "Authentication event",
            extra={
                "username": "admin",
                "password": "super-secret-password",
                "api_key": "sk-1234567890",
                "token": "bearer-token-abc",
                "normal_field": "visible-data",
            },
        )

        output = stream.getvalue().strip()
        last_line = json.loads(output.splitlines()[-1])
        assert last_line["username"] == "admin"
        assert last_line["normal_field"] == "visible-data"
        assert last_line["password"] == "***REDACTED***"
        assert last_line["api_key"] == "***REDACTED***"
        assert last_line["token"] == "***REDACTED***"
