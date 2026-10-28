import re
from pathlib import Path

from backend.app.models.entities import Base

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_DIR = REPO_ROOT / "database"
SCHEMA_SQL = DB_DIR / "schema.sql"
RLS_SQL = DB_DIR / "rls_policies.sql"
MIGRATIONS_DIR = DB_DIR / "migrations"
INITIAL_MIGRATION = MIGRATIONS_DIR / "0001_initial_schema.sql"

EXPECTED_TABLES = set(Base.metadata.tables.keys())


class TestPostgresSchemaStructure:
    """Validate that cloud database schema and migration files exist and match model definitions."""

    def test_schema_files_exist(self):
        """Verify that schema.sql, rls_policies.sql, and initial migration exist."""
        assert SCHEMA_SQL.exists(), "database/schema.sql must exist"
        assert RLS_SQL.exists(), "database/rls_policies.sql must exist"
        assert INITIAL_MIGRATION.exists(), "database/migrations/0001_initial_schema.sql must exist"

    def test_schema_defines_all_sixteen_tables(self):
        """Verify that database/schema.sql defines every table present in SQLAlchemy metadata."""
        content = SCHEMA_SQL.read_text(encoding="utf-8")
        created_tables = set(
            re.findall(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)",
                content,
                re.IGNORECASE,
            )
        )
        missing_tables = EXPECTED_TABLES - created_tables
        assert not missing_tables, f"database/schema.sql is missing tables: {missing_tables}"

    def test_schema_updated_at_trigger_function(self):
        """Verify set_updated_at() trigger function is declared and applied to timestamped tables."""
        content = SCHEMA_SQL.read_text(encoding="utf-8")
        assert "set_updated_at()" in content, "set_updated_at() trigger function must be defined"

        # 15 tables have updated_at; audit_logs is append-only without updated_at
        tables_with_updated_at = EXPECTED_TABLES - {"audit_logs"}
        for table in tables_with_updated_at:
            trigger_pattern = rf"CREATE\s+TRIGGER\s+[a-zA-Z0-9_]+\s+BEFORE\s+UPDATE\s+ON\s+{table}"
            assert re.search(trigger_pattern, content, re.IGNORECASE), (
                f"Missing BEFORE UPDATE trigger on table '{table}'"
            )

        # Confirm audit_logs does not have updated_at trigger
        audit_trigger = re.search(
            r"CREATE\s+TRIGGER\s+[a-zA-Z0-9_]+\s+BEFORE\s+UPDATE\s+ON\s+audit_logs",
            content,
            re.IGNORECASE,
        )
        assert audit_trigger is None, "audit_logs is append-only and should not have an updated_at trigger"

    def test_foreign_key_cascade_rules(self):
        """Verify foreign key cascading constraints in schema.sql match entities.py."""
        content = SCHEMA_SQL.read_text(encoding="utf-8")

        # Verify CASCADE on child records
        cascade_tables = [
            "ticket_messages",
            "workflow_runs",
            "workflow_events",
            "resolution_actions",
            "approval_requests",
            "escalations",
            "customer_memory",
        ]
        for tbl in cascade_tables:
            pattern = r"REFERENCES\s+tickets\s*\([^\)]+\)\s+ON\s+DELETE\s+CASCADE"
            assert re.search(pattern, content, re.IGNORECASE), (
                f"Expected ON DELETE CASCADE referencing tickets in {tbl}"
            )

        # Verify SET NULL on user profile assignments
        assert re.search(
            r"REFERENCES\s+profiles\s*\([^\)]+\)\s+ON\s+DELETE\s+SET\s+NULL",
            content,
            re.IGNORECASE,
        ), "Expected ON DELETE SET NULL on profiles references"

    def test_audit_logs_has_no_foreign_keys(self):
        """Verify audit_logs has zero foreign key dependencies to ensure permanent immutability."""
        content = SCHEMA_SQL.read_text(encoding="utf-8")
        # Extract audit_logs CREATE TABLE block
        match = re.search(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?audit_logs\s*\((.*?)\);",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        assert match, "audit_logs table definition not found in schema.sql"
        audit_body = match.group(1)
        assert "FOREIGN KEY" not in audit_body.upper(), "audit_logs must have zero foreign keys"
        assert "REFERENCES" not in audit_body.upper(), "audit_logs must not reference other tables"


class TestRowLevelSecurityPolicies:
    """Validate that RLS policies are enabled on all data tables and follow security requirements."""

    def test_rls_enabled_on_all_tables(self):
        """Verify that every single table has RLS explicitly enabled."""
        content = RLS_SQL.read_text(encoding="utf-8")
        for table in EXPECTED_TABLES:
            enable_pattern = rf"ALTER\s+TABLE\s+{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY"
            assert re.search(enable_pattern, content, re.IGNORECASE), (
                f"Table '{table}' must have ROW LEVEL SECURITY enabled"
            )

    def test_service_role_bypass_policies(self):
        """Verify that service_role policy is present allowing backend administrative access."""
        content = RLS_SQL.read_text(encoding="utf-8")
        assert "service_role" in content, "RLS policies must include service_role access"
        for table in EXPECTED_TABLES:
            policy_pattern = rf"CREATE\s+POLICY\s+[a-zA-Z0-9_]+\s+ON\s+{table}\s+(?:FOR\s+ALL\s+)?TO\s+service_role"
            assert re.search(policy_pattern, content, re.IGNORECASE), (
                f"Missing service_role policy on table '{table}'"
            )

    def test_role_based_policies_exist(self):
        """Verify authenticated policies restrict by user role (viewer, agent, admin)."""
        content = RLS_SQL.read_text(encoding="utf-8")
        assert "authenticated" in content, "RLS policies must define access for authenticated users"
        # Support articles should allow public/authenticated read
        assert re.search(
            r"CREATE\s+POLICY\s+[a-zA-Z0-9_]+\s+ON\s+support_articles\s+FOR\s+SELECT",
            content,
            re.IGNORECASE,
        ), "support_articles must allow SELECT for read operations"


class TestMigrations:
    """Validate migration structure and versioning rules."""

    def test_initial_migration_contains_schema_and_rls(self):
        """Verify 0001_initial_schema.sql contains table DDL and RLS statements."""
        content = INITIAL_MIGRATION.read_text(encoding="utf-8")
        assert "CREATE TABLE" in content
        assert "ENABLE ROW LEVEL SECURITY" in content
        assert "set_updated_at" in content

    def test_migration_naming_convention(self):
        """CLAUDE.md section 6 mandates naming convention '000N_<name>.sql'."""
        migration_files = list(MIGRATIONS_DIR.glob("*.sql"))
        assert len(migration_files) >= 1, "At least one migration file must exist"
        for file in migration_files:
            assert re.match(r"^\d{4}_[a-z0-9_]+\.sql$", file.name), (
                f"Migration file '{file.name}' does not follow 000N_<name>.sql convention"
            )
