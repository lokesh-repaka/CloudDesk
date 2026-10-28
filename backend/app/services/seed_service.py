"""Seed Service — Local Demo Bootstrap and Fixture Ingestion.

Loads sample domain fixtures from `sample_data/` (customers, workspaces,
subscriptions, products, incidents, knowledge base articles, and tickets)
into the database for offline development, local demonstration, and automated testing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import get_session_factory
from backend.app.models.entities import (
    Customer,
    Incident,
    Product,
    Profile,
    Subscription,
    SupportArticle,
    Ticket,
    TicketMessage,
    Workspace,
)
from backend.app.schemas.common import RoleEnum


def get_sample_data_dir(sample_data_dir: Path | str | None = None) -> Path:
    """Resolve sample_data directory path."""
    if sample_data_dir is not None:
        return Path(sample_data_dir).resolve()
    settings = get_settings()
    return Path(settings.SAMPLE_DATA_DIR).resolve()


def _read_json_file(file_path: Path) -> list[dict[str, Any]]:
    """Synchronously read and parse a JSON dataset file."""
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def load_knowledge_articles(sample_data_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Parse markdown files in sample_data/knowledge_base/ extracting YAML frontmatter and body."""
    base_dir = get_sample_data_dir(sample_data_dir)
    kb_dir = base_dir / "knowledge_base"
    articles: list[dict[str, Any]] = []

    if not kb_dir.exists():
        return articles

    for file_path in sorted(kb_dir.glob("*.md")):
        raw = file_path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            continue

        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue

        meta = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()

        slug = file_path.stem
        articles.append(
            {
                "id": f"art-{slug}",
                "slug": slug,
                "title": meta.get("title", slug.replace("-", " ").title()),
                "category": meta.get("category", "other"),
                "tags": meta.get("tags", []),
                "summary": meta.get("summary", ""),
                "content": body,
                "published": True,
            }
        )

    return articles


def load_all_fixtures(base_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all static sample datasets synchronously into memory before async database execution."""
    return {
        "customers": _read_json_file(base_dir / "customers.json"),
        "subscriptions": _read_json_file(base_dir / "subscriptions.json"),
        "workspaces": _read_json_file(base_dir / "workspaces.json"),
        "products": _read_json_file(base_dir / "products.json"),
        "incidents": _read_json_file(base_dir / "incidents.json"),
        "tickets": _read_json_file(base_dir / "tickets.json"),
        "articles": load_knowledge_articles(base_dir),
    }


async def bootstrap_demo_data(
    session: AsyncSession | None = None,
    sample_data_dir: Path | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Bootstrap demo fixtures into the database if empty or if forced."""
    base_dir = get_sample_data_dir(sample_data_dir)
    fixtures = load_all_fixtures(base_dir)

    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as active_session:
            return await _execute_bootstrap(active_session, fixtures, force=force)
    else:
        return await _execute_bootstrap(session, fixtures, force=force)


async def _execute_bootstrap(
    session: AsyncSession,
    fixtures: dict[str, list[dict[str, Any]]],
    force: bool = False,
) -> dict[str, Any]:
    """Execute the data loading transactions into the active session."""
    existing_customers = (
        await session.execute(select(func.count()).select_from(Customer))
    ).scalar_one()

    if existing_customers > 0 and not force:
        return {
            "status": "skipped",
            "message": "Database already contains customer records",
            "customers": existing_customers,
        }

    stats: dict[str, int] = {
        "profiles": 0,
        "customers": 0,
        "subscriptions": 0,
        "workspaces": 0,
        "products": 0,
        "incidents": 0,
        "support_articles": 0,
        "tickets": 0,
        "ticket_messages": 0,
    }

    # 1. Seed Demo Profiles (Alice Admin, Sam Agent, Vic Viewer)
    demo_profiles = [
        Profile(
            id="usr-admin-001",
            email="admin@clouddesk.demo",
            full_name="Alice Admin",
            role=RoleEnum.ADMIN.value,
        ),
        Profile(
            id="usr-agent-002",
            email="sam.agent@clouddesk.demo",
            full_name="Sam Agent",
            role=RoleEnum.AGENT.value,
        ),
        Profile(
            id="usr-viewer-003",
            email="vic.viewer@clouddesk.demo",
            full_name="Vic Viewer",
            role=RoleEnum.VIEWER.value,
        ),
    ]
    for prof in demo_profiles:
        session.add(prof)
    await session.flush()
    stats["profiles"] = len(demo_profiles)

    # 2. Customers
    customers_data = fixtures.get("customers", [])
    for item in customers_data:
        cust = Customer(
            id=item["id"],
            name=item["name"],
            email=item["email"],
            plan=item["plan"],
        )
        session.add(cust)
    await session.flush()
    stats["customers"] = len(customers_data)

    # 3. Subscriptions
    sub_data = fixtures.get("subscriptions", [])
    for item in sub_data:
        end_date = None
        if item.get("current_period_end"):
            end_date = datetime.fromisoformat(item["current_period_end"])
        sub = Subscription(
            id=item["id"],
            customer_id=item["customer_id"],
            plan=item["plan"],
            status=item.get("status", "active"),
            seats=item.get("seats", 1),
            current_period_end=end_date,
        )
        session.add(sub)
    await session.flush()
    stats["subscriptions"] = len(sub_data)

    # 4. Workspaces
    ws_data = fixtures.get("workspaces", [])
    for item in ws_data:
        ws = Workspace(
            id=item["id"],
            customer_id=item["customer_id"],
            name=item["name"],
            slug=item["slug"],
            storage_used_bytes=item.get("storage_used_bytes", 0),
            storage_limit_bytes=item.get("storage_limit_bytes", 10737418240),
        )
        session.add(ws)
    await session.flush()
    stats["workspaces"] = len(ws_data)

    # 5. Products
    prod_data = fixtures.get("products", [])
    for item in prod_data:
        prod = Product(
            id=item["id"],
            name=item["name"],
            slug=item["slug"],
            description=item.get("description"),
        )
        session.add(prod)
    await session.flush()
    stats["products"] = len(prod_data)

    # 6. Incidents
    inc_data = fixtures.get("incidents", [])
    for item in inc_data:
        inc = Incident(
            id=item["id"],
            title=item["title"],
            service=item["service"],
            status=item.get("status", "investigating"),
            severity=item.get("severity", "medium"),
            impact_summary=item.get("impact_summary"),
        )
        session.add(inc)
    await session.flush()
    stats["incidents"] = len(inc_data)

    # 7. Knowledge Base Support Articles
    articles = fixtures.get("articles", [])
    for art in articles:
        support_article = SupportArticle(
            id=art["id"],
            slug=art["slug"],
            title=art["title"],
            category=art["category"],
            tags=art["tags"],
            summary=art["summary"],
            content=art["content"],
            published=art["published"],
        )
        session.add(support_article)
    await session.flush()
    stats["support_articles"] = len(articles)

    # 8. Tickets and Initial Messages
    tickets_data = fixtures.get("tickets", [])
    for t_item in tickets_data:
        ticket = Ticket(
            id=t_item["id"],
            customer_id=t_item["customer_id"],
            subject=t_item["subject"],
            category=t_item["category"],
            severity=t_item.get("severity", "medium"),
            channel=t_item.get("channel", "web"),
            status=t_item.get("status", "new"),
        )
        session.add(ticket)
        await session.flush()
        stats["tickets"] += 1

        if t_item.get("initial_message"):
            msg = TicketMessage(
                id=f"msg-{t_item['id'].lower()}",
                ticket_id=ticket.id,
                author_role="customer",
                author_id=t_item["customer_id"],
                body=t_item["initial_message"],
            )
            session.add(msg)
            stats["ticket_messages"] += 1
    await session.flush()

    await session.commit()
    return stats
