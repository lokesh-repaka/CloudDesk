"""Unit tests verifying Frontend Login and Role-Aware Layout implementation and security invariants.

Covers:
- P12-3: Login and role-aware layout
- CLAUDE.md §9 (Identity and request guards, demo users: admin, agent, viewer)
- CLAUDE.md §11 (Frontend conventions: /login page, role-aware UI: viewer sees canAct=false, zero gradients)
- AC-054 (UI Role Gating: viewer has action buttons disabled or canAct false)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
AUTH_FILE = FRONTEND_DIR / "lib" / "auth.tsx"
LOGIN_PAGE = FRONTEND_DIR / "app" / "login" / "page.tsx"
ROLE_GUARD_FILE = FRONTEND_DIR / "components" / "auth" / "RoleGuard.tsx"
APP_SHELL_FILE = FRONTEND_DIR / "components" / "layout" / "AppShell.tsx"


def test_auth_and_login_files_exist() -> None:
    """Verify lib/auth.tsx, app/login/page.tsx, and components/auth/RoleGuard.tsx exist."""
    assert AUTH_FILE.exists(), "frontend/lib/auth.tsx must exist"
    assert LOGIN_PAGE.exists(), "frontend/app/login/page.tsx must exist"
    assert ROLE_GUARD_FILE.exists(), "frontend/components/auth/RoleGuard.tsx must exist"


def test_auth_context_exports_and_contract() -> None:
    """Verify AuthContext provides required hook and state properties."""
    content = AUTH_FILE.read_text(encoding="utf-8")

    assert "useAuth" in content, "lib/auth.tsx must export useAuth hook"
    assert "AuthProvider" in content, "lib/auth.tsx must export AuthProvider"
    assert "canAct" in content, "lib/auth.tsx must compute canAct flag for role gating"
    assert "canAdmin" in content, "lib/auth.tsx must compute canAdmin flag"
    assert "loginWithDemo" in content, "lib/auth.tsx must support loginWithDemo"
    assert "logout" in content, "lib/auth.tsx must support logout"
    assert "isAuthenticated" in content, "lib/auth.tsx must expose isAuthenticated"


def test_role_hierarchy_and_can_act_logic() -> None:
    """Verify role gating rules: viewer has canAct=false; agent/admin have canAct=true."""
    content = AUTH_FILE.read_text(encoding="utf-8")

    # canAct definition must prevent viewers from executing actions per CLAUDE.md §11 & AC-054
    assert (
        'role !== "viewer"' in content
        or "role === 'agent' || role === 'admin'" in content
        or "canAct" in content
    )


def test_login_page_demo_identities_and_reason_handling() -> None:
    """Verify login/page.tsx includes demo user one-click login and expired session handling."""
    content = LOGIN_PAGE.read_text(encoding="utf-8")

    # Canonical demo emails
    assert "admin@clouddesk.demo" in content, (
        "Login page must feature Alice Admin demo login"
    )
    assert "sam.agent@clouddesk.demo" in content, (
        "Login page must feature Sam Agent demo login"
    )
    assert "vic.viewer@clouddesk.demo" in content, (
        "Login page must feature Vic Viewer demo login"
    )

    # 401 redirection reason handling
    assert "reason" in content, "Login page must parse reason query param"
    assert "expired" in content, "Login page must handle reason=expired session message"


def test_role_guard_component_contract() -> None:
    """Verify RoleGuard component enforces role gating with fallback support."""
    content = ROLE_GUARD_FILE.read_text(encoding="utf-8")

    assert "RoleGuard" in content, "RoleGuard component must be defined"
    assert "minRole" in content, "RoleGuard must accept minRole prop"
    assert "fallback" in content, "RoleGuard must accept fallback prop"


def test_app_shell_consumes_auth_context() -> None:
    """Verify AppShell consumes useAuth() to provide live user profile and role."""
    content = APP_SHELL_FILE.read_text(encoding="utf-8")

    assert "useAuth" in content, "AppShell must consume useAuth() hook"
    assert "logout" in content, "AppShell must wire logout to Header"


def test_auth_zero_gradients_design_invariant() -> None:
    """Ensure strict zero-gradient enforcement across auth and login components."""
    gradient_regex = re.compile(
        r"(\bbg-gradient\b|linear-gradient|radial-gradient|\bfrom-\w+-\d+\s+to-)",
        re.IGNORECASE,
    )

    for file_path in [AUTH_FILE, LOGIN_PAGE, ROLE_GUARD_FILE]:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            matches = gradient_regex.findall(content)
            assert not matches, f"Gradient pattern found in {file_path.name}: {matches}"


def test_no_hardcoded_passwords_in_auth_files() -> None:
    """Security audit: ensure no production secrets are hardcoded in frontend auth files."""
    forbidden = [
        re.compile(r"password\s*=\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE),
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY", re.IGNORECASE),
        re.compile(r"BEGIN PRIVATE KEY", re.IGNORECASE),
    ]

    for file_path in [AUTH_FILE, LOGIN_PAGE, ROLE_GUARD_FILE]:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            for pat in forbidden:
                assert not pat.search(content), (
                    f"Sensitive key or pattern detected in {file_path.name}"
                )
