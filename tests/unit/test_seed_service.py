import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import (
    Base,
    Customer,
    SupportArticle,
    Ticket,
    TicketMessage,
)
from backend.app.schemas.common import CategoryEnum, CustomerPlanEnum

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_DATA_DIR = REPO_ROOT / "sample_data"
KB_DIR = SAMPLE_DATA_DIR / "knowledge_base"
SEED_SQL = REPO_ROOT / "database" / "seed.sql"


@pytest.fixture
async def memory_db_session():
    """Isolated in-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestSampleDataFiles:
    """Validate sample_data/ JSON files and structure according to CLAUDE.md section 5."""

    def test_sample_data_files_exist_and_valid_json(self):
        """Verify presence and valid JSON structure of all required sample dataset files."""
        required_files = [
            "customers.json",
            "subscriptions.json",
            "workspaces.json",
            "products.json",
            "incidents.json",
            "previous_resolutions.json",
            "tickets.json",
        ]
        for filename in required_files:
            file_path = SAMPLE_DATA_DIR / filename
            assert file_path.exists(), f"Missing required dataset: {file_path}"
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert isinstance(data, list), f"{filename} root must be a JSON array"
                assert len(data) > 0, f"{filename} must not be empty"

    def test_customers_cover_all_plans_and_count_is_eight(self):
        """CLAUDE.md mandates exactly 8 customers covering free, pro, business, and enterprise."""
        customers_path = SAMPLE_DATA_DIR / "customers.json"
        with open(customers_path, "r", encoding="utf-8") as f:
            customers = json.load(f)

        assert len(customers) == 8, f"Expected exactly 8 customers, got {len(customers)}"
        plans_present = {c["plan"] for c in customers}
        expected_plans = {p.value for p in CustomerPlanEnum}
        assert plans_present == expected_plans, f"Plans mismatch: {plans_present} vs {expected_plans}"

    def test_tickets_cover_thirteen_demo_scenarios(self):
        """CLAUDE.md mandates exactly 13 tickets (CD-1001 through CD-1013)."""
        tickets_path = SAMPLE_DATA_DIR / "tickets.json"
        with open(tickets_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)

        assert len(tickets) == 13, f"Expected exactly 13 tickets, got {len(tickets)}"
        ticket_ids = [t["id"] for t in tickets]
        expected_ids = [f"CD-{1001 + i}" for i in range(13)]
        assert ticket_ids == expected_ids

        # Verify key ticket scenarios from CLAUDE.md table
        ticket_map = {t["id"]: t for t in tickets}
        assert "SSO login" in ticket_map["CD-1001"]["subject"]
        assert ticket_map["CD-1001"]["category"] == CategoryEnum.LOGIN_ISSUE.value
        assert ticket_map["CD-1002"]["category"] == CategoryEnum.BILLING.value
        assert ticket_map["CD-1003"]["category"] == CategoryEnum.API_FAILURE.value
        assert ticket_map["CD-1004"]["category"] == CategoryEnum.STORAGE_QUOTA.value
        assert ticket_map["CD-1005"]["category"] == CategoryEnum.SECURITY.value
        assert ticket_map["CD-1007"]["category"] == CategoryEnum.WORKSPACE_PERMISSIONS.value
        assert ticket_map["CD-1008"]["category"] == CategoryEnum.INTEGRATION.value
        assert ticket_map["CD-1010"]["category"] == CategoryEnum.FEATURE_REQUEST.value
        assert ticket_map["CD-1010"]["severity"] == "low"
        assert ticket_map["CD-1013"]["category"] == CategoryEnum.SECURITY.value

    def test_knowledge_base_articles_count_and_frontmatter(self):
        """CLAUDE.md section 4.3 mandates 15 articles with YAML front-matter."""
        assert KB_DIR.exists(), f"Knowledge base directory missing: {KB_DIR}"
        articles = list(KB_DIR.glob("*.md"))
        assert len(articles) == 15, f"Expected 15 knowledge base articles, found {len(articles)}"

        categories_found = set()
        for article in articles:
            content = article.read_text(encoding="utf-8")
            assert content.startswith("---"), f"Article {article.name} missing front-matter start"
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"Article {article.name} invalid front-matter block"
            fm = parts[1]
            body = parts[2].strip()
            assert len(body) > 50, f"Article {article.name} body too short"

            # Check required front-matter fields
            assert re.search(r"title:\s*.+", fm), f"Article {article.name} missing title"
            cat_match = re.search(r"category:\s*[\"']?([a-zA-Z0-9_]+)[\"']?", fm)
            assert cat_match, f"Article {article.name} missing category"
            category = cat_match.group(1)
            categories_found.add(category)
            assert re.search(r"tags:\s*\[.*\]", fm), f"Article {article.name} missing tags"
            assert re.search(r"summary:\s*.+", fm), f"Article {article.name} missing summary"

        # Check all 10 canonical categories are covered across the 15 articles
        expected_categories = {c.value for c in CategoryEnum}
        assert expected_categories.issubset(categories_found), (
            f"Missing category coverage in KB: {expected_categories - categories_found}"
        )

    def test_seed_sql_file_exists_and_valid(self):
        """database/seed.sql must exist and provide valid SQL INSERT statements."""
        assert SEED_SQL.exists(), "database/seed.sql must exist"
        content = SEED_SQL.read_text(encoding="utf-8")
        assert "INSERT INTO customers" in content
        assert "INSERT INTO workspaces" in content
        assert "INSERT INTO products" in content
        assert "INSERT INTO support_articles" in content
        assert "INSERT INTO tickets" in content


class TestSeedServiceBootstrap:
    """Validate backend/app/services/seed_service.py bootstrap functionality."""

    async def test_bootstrap_demo_data_populates_empty_database(self, memory_db_session: AsyncSession):
        from backend.app.services.seed_service import bootstrap_demo_data

        stats = await bootstrap_demo_data(
            session=memory_db_session,
            sample_data_dir=SAMPLE_DATA_DIR,
        )

        assert stats["customers"] == 8
        assert stats["subscriptions"] == 8
        assert stats["workspaces"] >= 8
        assert stats["products"] >= 3
        assert stats["incidents"] >= 2
        assert stats["tickets"] == 13
        assert stats["ticket_messages"] == 13
        assert stats["support_articles"] == 15
        assert stats["profiles"] >= 3

        # Verify database contents directly
        cust_count = (await memory_db_session.execute(select(func.count()).select_from(Customer))).scalar_one()
        assert cust_count == 8

        ticket_count = (await memory_db_session.execute(select(func.count()).select_from(Ticket))).scalar_one()
        assert ticket_count == 13

        msg_count = (await memory_db_session.execute(select(func.count()).select_from(TicketMessage))).scalar_one()
        assert msg_count == 13

        article_count = (await memory_db_session.execute(select(func.count()).select_from(SupportArticle))).scalar_one()
        assert article_count == 15

    async def test_bootstrap_demo_data_is_idempotent(self, memory_db_session: AsyncSession):
        """Calling bootstrap_demo_data when records already exist should skip or return existing counts without error."""
        from backend.app.services.seed_service import bootstrap_demo_data

        # First run
        stats1 = await bootstrap_demo_data(
            session=memory_db_session,
            sample_data_dir=SAMPLE_DATA_DIR,
        )
        assert stats1["customers"] == 8

        # Second run (should be idempotent)
        stats2 = await bootstrap_demo_data(
            session=memory_db_session,
            sample_data_dir=SAMPLE_DATA_DIR,
        )
        assert stats2["status"] == "skipped" or stats2["customers"] == 8

        # Verify no duplicate tickets were created
        ticket_count = (await memory_db_session.execute(select(func.count()).select_from(Ticket))).scalar_one()
        assert ticket_count == 13

    async def test_security_sanitization_in_sample_data(self):
        """Penetration test: verify sample datasets do not leak live secrets, passwords, or live keys."""
        forbidden_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key
            r"ghp_[a-zA-Z0-9]{30,}",  # GitHub token
            r"eyJ[a-zA-Z0-9_-]{30,}\.eyJ[a-zA-Z0-9_-]{30,}",  # Real JWT token
            r"(?i)password\s*[:=]\s*['\"][^'\"]{8,}['\"]",  # Plaintext password
        ]

        # Scan all JSON files in sample_data/
        for json_file in SAMPLE_DATA_DIR.glob("*.json"):
            content = json_file.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                match = re.search(pattern, content)
                assert match is None, f"Sensitive secret pattern matched in {json_file.name}: {match.group(0)}"

        # Scan seed.sql
        if SEED_SQL.exists():
            seed_content = SEED_SQL.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                match = re.search(pattern, seed_content)
                assert match is None, f"Sensitive secret pattern matched in database/seed.sql: {match.group(0)}"
