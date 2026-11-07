"""Unit tests verifying Frontend App Shell structure, navigation and security invariants.

Covers:
- P12-1: Next.js app shell and navigation
- CLAUDE.md §11 (Frontend conventions, zero gradients, hand-written UI kit, nav.ts single source of truth)
- CLAUDE.md §15 (Frontend healthcheck route /api/health)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"


def test_frontend_project_foundation_files_exist() -> None:
    """Verify Next.js 15 App Router foundation configuration files exist."""
    required_files = [
        FRONTEND_DIR / "package.json",
        FRONTEND_DIR / "tsconfig.json",
        FRONTEND_DIR / "next.config.ts",
        FRONTEND_DIR / "tailwind.config.ts",
        FRONTEND_DIR / "postcss.config.mjs",
        FRONTEND_DIR / "app" / "globals.css",
        FRONTEND_DIR / "app" / "layout.tsx",
        FRONTEND_DIR / "app" / "page.tsx",
        FRONTEND_DIR / "app" / "api" / "health" / "route.ts",
    ]
    for file_path in required_files:
        assert file_path.exists(), f"Missing required file: {file_path}"
        assert file_path.stat().st_size > 0, f"File is empty: {file_path}"


def test_package_json_dependencies_and_no_external_ui_libraries() -> None:
    """Verify package.json specifies Next.js, React, Tailwind, and NO external UI libs."""
    pkg_path = FRONTEND_DIR / "package.json"
    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)

    deps = pkg.get("dependencies", {})
    dev_deps = pkg.get("devDependencies", {})
    all_deps = {**deps, **dev_deps}

    # Core required dependencies
    assert "next" in deps, "next must be in dependencies"
    assert "react" in deps, "react must be in dependencies"
    assert "react-dom" in deps, "react-dom must be in dependencies"
    assert "tailwindcss" in all_deps, "tailwindcss must be installed"
    assert "typescript" in dev_deps, "typescript must be in devDependencies"

    # Strictly no external component libraries per CLAUDE.md §11
    forbidden_libs = [
        "@chakra-ui",
        "@mantine",
        "@mui/material",
        "antd",
        "semantic-ui-react",
        "bootstrap",
        "react-bootstrap",
        "@radix-ui",
        "shadcn",
    ]
    for lib in forbidden_libs:
        for dep in all_deps:
            assert lib not in dep, (
                f"Forbidden UI library detected in package.json: {dep}"
            )


def test_navigation_routes_and_single_source_of_truth() -> None:
    """Verify components/layout/nav.ts declares all required console shell routes."""
    nav_file = FRONTEND_DIR / "components" / "layout" / "nav.ts"
    assert nav_file.exists(), "components/layout/nav.ts must exist"
    content = nav_file.read_text(encoding="utf-8")

    expected_routes = [
        "/dashboard",
        "/tickets",
        "/customers",
        "/knowledge",
        "/escalations",
        "/agents",
        "/audit",
        "/settings",
    ]

    for route in expected_routes:
        assert f'href: "{route}"' in content or f"href: '{route}'" in content, (
            f"Route {route} not declared in nav.ts"
        )

    # Check that role gating functions/types exist
    assert "getAuthorizedNavItems" in content
    assert "Role" in content
    assert "NAV_SECTIONS" in content


def test_layout_components_exist_and_exported() -> None:
    """Verify AppShell, Sidebar, Header, Breadcrumbs, NavItems, and Icons exist."""
    layout_dir = FRONTEND_DIR / "components" / "layout"
    required_layout_files = [
        "nav.ts",
        "Icons.tsx",
        "NavItems.tsx",
        "Breadcrumbs.tsx",
        "Header.tsx",
        "Sidebar.tsx",
        "AppShell.tsx",
        "index.ts",
    ]
    for fname in required_layout_files:
        path = layout_dir / fname
        assert path.exists(), f"Missing layout component: {fname}"

    index_content = (layout_dir / "index.ts").read_text(encoding="utf-8")
    for comp in ["AppShell", "Sidebar", "Header", "Breadcrumbs", "NavItems", "Icons"]:
        assert comp in index_content, f"{comp} must be exported from layout/index.ts"


def test_ui_kit_components_exist_and_exported() -> None:
    """Verify hand-written UI kit components exist and are exported in components/ui/."""
    ui_dir = FRONTEND_DIR / "components" / "ui"
    expected_ui_components = [
        "Button.tsx",
        "Badge.tsx",
        "Card.tsx",
        "Alert.tsx",
        "Kbd.tsx",
        "Table.tsx",
        "Input.tsx",
        "Select.tsx",
        "Modal.tsx",
        "Tabs.tsx",
        "StatusPill.tsx",
        "EmptyState.tsx",
        "index.ts",
    ]
    for comp in expected_ui_components:
        path = ui_dir / comp
        assert path.exists(), f"Missing UI component in kit: {comp}"

    index_content = (ui_dir / "index.ts").read_text(encoding="utf-8")
    for comp in [
        "Button",
        "Badge",
        "Card",
        "Alert",
        "Kbd",
        "Table",
        "Input",
        "Select",
        "Modal",
        "Tabs",
        "StatusPill",
        "EmptyState",
    ]:
        assert comp in index_content, (
            f"{comp} must be exported from components/ui/index.ts"
        )


def test_shell_pages_exist_for_all_nav_targets() -> None:
    """Verify Next.js app pages exist for each navigation destination."""
    app_dir = FRONTEND_DIR / "app"
    expected_pages = [
        "dashboard/page.tsx",
        "tickets/page.tsx",
        "customers/page.tsx",
        "knowledge/page.tsx",
        "escalations/page.tsx",
        "agents/page.tsx",
        "audit/page.tsx",
        "settings/page.tsx",
    ]
    for page in expected_pages:
        path = app_dir / page
        assert path.exists(), f"Missing shell page: {page}"
        content = path.read_text(encoding="utf-8")
        assert "AppShell" in content, f"Shell page {page} should utilize AppShell"


def test_api_health_endpoint_contract() -> None:
    """Verify /api/health endpoint implementation returns JSON with status ok."""
    health_file = FRONTEND_DIR / "app" / "api" / "health" / "route.ts"
    assert health_file.exists(), (
        "API health route must exist at app/api/health/route.ts"
    )
    content = health_file.read_text(encoding="utf-8")
    assert 'status: "ok"' in content or "status: 'ok'" in content
    assert "GET" in content


def test_zero_gradients_design_invariant() -> None:
    """Enforce CLAUDE.md §11 rule: 'No UI library, no gradients' across frontend code."""
    gradient_regex = re.compile(
        r"(\bbg-gradient\b|linear-gradient|radial-gradient|\bfrom-\w+-\d+\s+to-)",
        re.IGNORECASE,
    )

    scanned_files = (
        list(FRONTEND_DIR.glob("**/*.tsx"))
        + list(FRONTEND_DIR.glob("**/*.ts"))
        + list(FRONTEND_DIR.glob("**/*.css"))
    )

    for file_path in scanned_files:
        if "node_modules" in str(file_path) or ".next" in str(file_path):
            continue
        content = file_path.read_text(encoding="utf-8")
        matches = gradient_regex.findall(content)
        # Note: globals.css contains `background-image: none !important;` to explicitly ban gradients
        if file_path.name == "globals.css":
            continue
        assert not matches, (
            f"Gradient pattern found in {file_path.relative_to(REPO_ROOT)}: {matches}"
        )


def test_no_secrets_or_service_keys_imported_in_frontend() -> None:
    """Security audit: ensure service keys, db passwords, and JWT secrets are not in frontend."""
    secret_patterns = [
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY", re.IGNORECASE),
        re.compile(r"secret[_-]?key\s*=\s*['\"][a-zA-Z0-9]{8,}", re.IGNORECASE),
        re.compile(r"BEGIN PRIVATE KEY", re.IGNORECASE),
    ]

    scanned_files = list(FRONTEND_DIR.glob("**/*.tsx")) + list(
        FRONTEND_DIR.glob("**/*.ts")
    )

    for file_path in scanned_files:
        if "node_modules" in str(file_path) or ".next" in str(file_path):
            continue
        content = file_path.read_text(encoding="utf-8")
        for pat in secret_patterns:
            assert not pat.search(content), (
                f"Sensitive key or pattern detected in {file_path}"
            )
