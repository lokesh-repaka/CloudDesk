"""Comprehensive Deployment Hygiene & Security Audit Tests (P14-5, CLAUDE.md §13, §15, §18).

Enforces deployment hygiene across the entire delivery surface:
- CWE-200: Exposure of Sensitive Information to an Unauthorized Actor (.dockerignore, .gitignore, secret scans)
- CWE-250: Execution with Unnecessary Privileges (non-root containers, OIDC, least privilege)
- CWE-312: Cleartext Storage of Sensitive Information (no committed credentials or state)
- CWE-345: Insufficient Verification of Data Authenticity (healthchecks, service dependency chaining, git SHA tagging)
- CWE-522: Insufficiently Protected Credentials (TF_VAR isolation, placeholder-only env examples)
- CWE-668: Exposure of Resource to Wrong Sphere (network segmentation, pinned container tags)
- CWE-863: Incorrect Authorization (auto-approve prevention on staging/prod, manual approval gate)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from backend.app.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPLOYMENT_DIR = REPO_ROOT / "deployment"
SCRIPTS_DIR = DEPLOYMENT_DIR / "scripts"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
BACKEND_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile"
ROOT_DOCKERIGNORE = REPO_ROOT / ".dockerignore"
FRONTEND_DOCKERIGNORE = REPO_ROOT / "frontend" / ".dockerignore"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
GITIGNORE_FILE = REPO_ROOT / ".gitignore"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"
MAKEFILE = REPO_ROOT / "Makefile"


# ============================================================================
# 1. Secret Leakage & Git Tracking Hygiene (CWE-200, CWE-312, CWE-522)
# ============================================================================


def test_no_sensitive_or_state_files_tracked_in_git():
    """Verify that git-tracked files do not include secrets, databases, state, or private keys.

    Enforces CLAUDE.md §18 Rule 11:
    'Never commit .env, data/, *.db, terraform.tfvars, backend.hcl, tfplan, or any real key.'
    """
    cmd = ["git", "ls-files"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    forbidden_patterns = [
        re.compile(r"^\.env(?:\.(?!example$|template$).+)?$"),
        re.compile(r".*\.pem$"),
        re.compile(r".*\.key$"),
        re.compile(r".*\.db$"),
        re.compile(r".*\.sqlite[0-9]?$"),
        re.compile(r"^data/.*"),
        re.compile(r".*backend\.hcl$"),
        re.compile(r".*\.tfstate(?:.*)?$"),
        re.compile(r".*\.tfplan$"),
        re.compile(r".*tfplan$"),
        re.compile(r"^\.terraform/.*"),
    ]

    violations = []
    for filepath in tracked_files:
        for pat in forbidden_patterns:
            if pat.search(filepath):
                violations.append((filepath, pat.pattern))

    assert not violations, (
        "Forbidden sensitive/state files tracked in Git repository (CWE-200, CWE-312):\n"
        + "\n".join(f"  - {f} (matched: {p})" for f, p in violations)
    )


def test_repo_wide_secret_leak_scanning():
    """Scan all tracked files for accidentally committed secrets or credential signatures.

    Checks for live OpenAI keys, Anthropic keys, GitHub PATs, AWS access keys, and private keys.
    """
    cmd = ["git", "ls-files"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # Secret signatures to detect
    secret_patterns = [
        ("OpenAI Project API Key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{30,}\b")),
        ("Anthropic API Key", re.compile(r"\bsk-ant-api[0-9]{2}-[A-Za-z0-9_-]{30,}\b")),
        ("GitHub Personal Access Token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
        ("GitHub Fine-Grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
        ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("Slack Bot Token", re.compile(r"\bxoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24}\b")),
    ]

    # Exclude binaries or test assets if any
    allowed_extensions = {".py", ".ts", ".tsx", ".sh", ".tf", ".tfvars", ".yml", ".yaml", ".json", ".md", ".toml"}

    findings = []
    for rel_path in tracked_files:
        # Skip unit/integration tests that contain synthetic dummy test vectors for secret scrubbers
        if rel_path.startswith("tests/"):
            continue

        p = REPO_ROOT / rel_path
        if not p.is_file() or p.suffix not in allowed_extensions:
            continue

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pat in secret_patterns:
            matches = pat.findall(content)
            if matches:
                findings.append(f"{rel_path}: Matched {label} ({matches})")

    assert not findings, "Potential plaintext secrets discovered in repository (CWE-522):\n" + "\n".join(findings)


def test_gitignore_comprehensive_hygiene():
    """Verify that .gitignore actively excludes all runtime, credential, and cache patterns."""
    assert GITIGNORE_FILE.is_file(), "Missing .gitignore file in repository root"
    content = GITIGNORE_FILE.read_text(encoding="utf-8")

    required_gitignore_entries = [
        ".venv/",
        ".env",
        "*.env",
        "data/",
        "*.db",
        "*.sqlite",
        ".terraform/",
        "*.tfstate",
        "backend.hcl",
        "*.tfplan",
        "__pycache__/",
        ".pytest_cache/",
        "node_modules/",
        ".next/",
    ]

    for entry in required_gitignore_entries:
        assert entry in content, (
            f".gitignore is missing required exclusion rule: '{entry}' (CLAUDE.md §18 Rule 11)"
        )


def test_dockerignore_parity_and_secret_filtering():
    """Verify both root and frontend .dockerignore exclude sensitive files and directories."""
    assert ROOT_DOCKERIGNORE.is_file(), "Missing root .dockerignore"
    assert FRONTEND_DOCKERIGNORE.is_file(), "Missing frontend/.dockerignore"

    root_content = ROOT_DOCKERIGNORE.read_text(encoding="utf-8")
    frontend_content = FRONTEND_DOCKERIGNORE.read_text(encoding="utf-8")

    # Critical exclusions for container build contexts (CWE-200)
    for name, content in [("root .dockerignore", root_content), ("frontend/.dockerignore", frontend_content)]:
        for item in (".git", ".env", "node_modules"):
            assert re.search(rf"^\s*{re.escape(item)}", content, re.MULTILINE), (
                f"{name} must exclude '{item}' to prevent container context bloat or secret leakage"
            )


# ============================================================================
# 2. Container Architecture & Least Privilege Hygiene (CWE-250, CWE-345)
# ============================================================================


def test_backend_dockerfile_security_and_runtime_hygiene():
    """Verify backend/Dockerfile satisfies multi-stage, pinned base, non-root user, and HEALTHCHECK."""
    assert BACKEND_DOCKERFILE.is_file(), f"Missing backend Dockerfile at {BACKEND_DOCKERFILE}"
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    # 1. Multi-stage build with pinned python:3.12-slim or python:3.13-slim
    assert "AS builder" in content, "Backend Dockerfile must define an AS builder stage"
    assert re.search(r"python:(?:3\.12|3\.13)-slim", content), (
        "Backend Dockerfile must pin python:3.12-slim or 3.13-slim (CLAUDE.md §15)"
    )
    assert "python:latest" not in content, "Backend Dockerfile must not use :latest tag (CWE-668)"

    # 2. Non-root user creation and activation (CWE-250)
    assert re.search(r"(?:useradd|adduser)\b.*app", content), (
        "Backend Dockerfile must create dedicated non-root user 'app'"
    )
    assert re.search(r"^USER\s+app\b", content, re.MULTILINE), (
        "Backend Dockerfile must activate non-root USER app before CMD"
    )

    # 3. Active HEALTHCHECK instruction on /health/live (CWE-345)
    assert "HEALTHCHECK" in content, "Backend Dockerfile must declare HEALTHCHECK instruction"
    assert "/health/live" in content, "Backend HEALTHCHECK must probe /health/live (CLAUDE.md §15)"
    assert "8000" in content, "Backend HEALTHCHECK must probe port 8000"

    # 4. Port exposure and CMD exec syntax
    assert "EXPOSE 8000" in content, "Backend Dockerfile must EXPOSE port 8000"
    assert re.search(r'CMD\s*\[\s*"uvicorn"', content), (
        "Backend CMD must use exec array format: CMD [\"uvicorn\", ...]"
    )


def test_frontend_dockerfile_security_and_runtime_hygiene():
    """Verify frontend/Dockerfile satisfies multi-stage, pinned base, non-root user, and HEALTHCHECK."""
    assert FRONTEND_DOCKERFILE.is_file(), f"Missing frontend Dockerfile at {FRONTEND_DOCKERFILE}"
    content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    # 1. Multi-stage build with pinned node:22-alpine
    assert "AS deps" in content, "Frontend Dockerfile must define deps stage"
    assert "AS builder" in content, "Frontend Dockerfile must define builder stage"
    assert "AS runner" in content, "Frontend Dockerfile must define runner stage"
    assert "node:22-alpine" in content, "Frontend Dockerfile must pin node:22-alpine (CLAUDE.md §15)"
    assert "node:latest" not in content, "Frontend Dockerfile must not use :latest tag (CWE-668)"

    # 2. Non-root system user nextjs (CWE-250)
    assert "nextjs" in content, "Frontend Dockerfile must create non-root user nextjs"
    assert re.search(r"^USER\s+nextjs\b", content, re.MULTILINE), (
        "Frontend Dockerfile must switch to USER nextjs"
    )

    # 3. Standalone output packaging and non-root ownership preservation
    assert "standalone" in content, "Frontend Dockerfile must support Next.js standalone output"
    assert "--chown=nextjs:nodejs" in content, (
        "Frontend COPY instructions must assign ownership to nextjs:nodejs"
    )

    # 4. HEALTHCHECK probing /api/health (CWE-345)
    assert "HEALTHCHECK" in content, "Frontend Dockerfile must declare HEALTHCHECK instruction"
    assert "/api/health" in content, "Frontend HEALTHCHECK must probe /api/health (CLAUDE.md §15)"
    assert "3000" in content, "Frontend HEALTHCHECK must probe port 3000"

    # 5. Port exposure and CMD exec syntax
    assert "EXPOSE 3000" in content, "Frontend Dockerfile must EXPOSE port 3000"
    assert re.search(r'CMD\s*\[\s*"node",\s*"server\.js"\s*\]', content), (
        "Frontend CMD must execute standalone server: CMD [\"node\", \"server.js\"]"
    )


# ============================================================================
# 3. Docker Compose Stack Hygiene (CWE-345, CWE-668)
# ============================================================================


def test_docker_compose_service_orchestration_and_health_chain():
    """Verify docker-compose.yml configures healthy dependency chain and isolation."""
    assert COMPOSE_FILE.is_file(), f"Missing docker-compose.yml at {COMPOSE_FILE}"
    content = COMPOSE_FILE.read_text(encoding="utf-8")

    # 1. All 4 services declared
    for s in ("frontend:", "backend:", "redis:", "qdrant:"):
        assert s in content, f"docker-compose.yml must define service '{s}'"

    # 2. Healthcheck chaining (frontend -> backend -> redis, qdrant)
    assert "condition: service_healthy" in content, (
        "Compose services must enforce 'condition: service_healthy' (CLAUDE.md §15)"
    )

    # 3. Restart policy on services
    assert content.count("restart: unless-stopped") >= 4, (
        "All 4 compose services must configure restart: unless-stopped"
    )

    # 4. Named persistent volumes
    assert "redis_data:" in content, "Compose file must configure named volume redis_data"
    assert "qdrant_data:" in content, "Compose file must configure named volume qdrant_data"

    # 5. Network segmentation
    assert "clouddesk-network:" in content, "Compose file must configure dedicated clouddesk-network"


# ============================================================================
# 4. Environment Variables & Safe Placeholders (CWE-200, CWE-522)
# ============================================================================


def test_env_example_complete_coverage_and_safe_defaults():
    """Verify .env.example covers 100% of Settings fields and contains only safe placeholders."""
    assert ENV_EXAMPLE_FILE.is_file(), f"Missing .env.example at {ENV_EXAMPLE_FILE}"
    content = ENV_EXAMPLE_FILE.read_text(encoding="utf-8")

    example_keys = set()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            example_keys.add(key)

    settings_fields = set(Settings.model_fields.keys())
    missing_fields = settings_fields - example_keys

    assert not missing_fields, (
        f".env.example is missing declared Settings fields: {missing_fields}"
    )

    # Verify no real keys in .env.example
    assert "sk-proj-" not in content, "Real OpenAI key detected in .env.example"
    assert "sk-ant-" not in content, "Real Anthropic key detected in .env.example"
    assert "ghp_" not in content, "Real GitHub token detected in .env.example"


# ============================================================================
# 5. Multi-Cloud Terraform Infrastructure Hygiene (CWE-250, CWE-522, CWE-863)
# ============================================================================


def test_terraform_multicloud_roots_and_shared_modules_hygiene():
    """Verify multi-cloud roots (aws, azure, gcp) compose shared modules without code duplication."""
    assert DEPLOYMENT_DIR.is_dir(), f"Missing deployment directory at {DEPLOYMENT_DIR}"

    # Verify 3 cloud roots
    for cloud in ("aws", "azure", "gcp"):
        root_dir = DEPLOYMENT_DIR / cloud
        assert root_dir.is_dir(), f"Missing Terraform root for {cloud}"
        assert (root_dir / "main.tf").is_file(), f"Missing main.tf in {cloud}"
        assert (root_dir / "variables.tf").is_file(), f"Missing variables.tf in {cloud}"
        assert (root_dir / "outputs.tf").is_file(), f"Missing outputs.tf in {cloud}"

    # Verify 7 shared modules
    modules_dir = DEPLOYMENT_DIR / "modules"
    expected_modules = [
        "networking",
        "container-registry",
        "secrets",
        "compute",
        "load-balancer",
        "monitoring",
        "redis",
    ]
    for mod in expected_modules:
        mod_dir = modules_dir / mod
        assert mod_dir.is_dir(), f"Missing shared Terraform module '{mod}'"
        assert (mod_dir / "main.tf").is_file(), f"Missing main.tf in module '{mod}'"
        assert (mod_dir / "variables.tf").is_file(), f"Missing variables.tf in module '{mod}'"
        assert (mod_dir / "outputs.tf").is_file(), f"Missing outputs.tf in module '{mod}'"

    # Verify environment tfvars exist without duplicated resource logic
    env_dir = DEPLOYMENT_DIR / "environments"
    for env in ("dev", "staging", "prod"):
        tfvars = env_dir / env / "terraform.tfvars"
        assert tfvars.is_file(), f"Missing terraform.tfvars for environment '{env}'"
        tfvars_content = tfvars.read_text(encoding="utf-8")
        assert "resource " not in tfvars_content, (
            f"terraform.tfvars for {env} must not declare resources (code duplication)"
        )


def test_terraform_tfvars_contain_no_plaintext_passwords_or_keys():
    """Verify environment tfvars do not store plaintext secrets (CWE-522, CLAUDE.md §15)."""
    env_dir = DEPLOYMENT_DIR / "environments"
    sensitive_keys = ["jwt_secret", "supabase_jwt_secret", "llm_api_key", "qdrant_api_key", "password"]

    for env in ("dev", "staging", "prod"):
        tfvars = env_dir / env / "terraform.tfvars"
        content = tfvars.read_text(encoding="utf-8").lower()
        for s in sensitive_keys:
            assert f"{s} = " not in content, (
                f"Plaintext secret '{s}' found in {env}/terraform.tfvars. "
                "Secrets must only be passed through TF_VAR_* environment variables (CLAUDE.md §15)."
            )


# ============================================================================
# 6. Operational Scripts Safety & Guardrails (CWE-863, CLAUDE.md §15)
# ============================================================================


def test_deployment_scripts_exist_and_use_strict_shell_options():
    """Verify all 5 deployment lifecycle scripts exist with strict bash error handling."""
    assert SCRIPTS_DIR.is_dir(), f"Missing scripts directory at {SCRIPTS_DIR}"

    expected_scripts = [
        "deploy.sh",
        "destroy.sh",
        "build_and_push.sh",
        "smoke_test.sh",
        "rollback.sh",
    ]

    for script_name in expected_scripts:
        script_path = SCRIPTS_DIR / script_name
        assert script_path.is_file(), f"Missing deployment script: {script_name}"
        content = script_path.read_text(encoding="utf-8")

        # Verify shebang and strict shell options
        assert content.startswith("#!/usr/bin/env bash"), (
            f"{script_name} must specify #!/usr/bin/env bash shebang"
        )
        assert "set -euo pipefail" in content, (
            f"{script_name} must configure strict error handling: 'set -euo pipefail'"
        )


def test_deployment_scripts_enforce_auto_approve_guardrail_on_staging_and_prod():
    """Verify deploy.sh and destroy.sh programmatically refuse --auto-approve for staging/prod (CWE-863)."""
    for script_name in ("deploy.sh", "destroy.sh"):
        script_path = SCRIPTS_DIR / script_name
        content = script_path.read_text(encoding="utf-8")

        assert "--auto-approve" in content, (
            f"{script_name} must inspect and handle '--auto-approve' parameter"
        )
        assert "staging" in content and "prod" in content, (
            f"{script_name} must check against staging and prod environments"
        )
        # Ensure exit 1 on refusal
        assert "exit 1" in content, (
            f"{script_name} must exit with code 1 when --auto-approve is passed for staging or prod"
        )


# ============================================================================
# 7. CI/CD Pipeline & Delivery Security (CWE-250, CWE-345, CWE-522)
# ============================================================================


def test_ci_cd_workflow_scaffolds_and_security_controls():
    """Verify GitHub Actions workflows enforce security scans, SHA image tags, and prod gate."""
    assert WORKFLOWS_DIR.is_dir(), f"Missing workflows directory at {WORKFLOWS_DIR}"

    # 1. security.yml has gitleaks, pip-audit, trivy, checkov
    security_yml = WORKFLOWS_DIR / "security.yml"
    assert security_yml.is_file(), "Missing .github/workflows/security.yml"
    sec_content = security_yml.read_text(encoding="utf-8")
    for tool in ("gitleaks", "pip-audit", "trivy", "checkov"):
        assert tool in sec_content, f"security.yml must run vulnerability tool: {tool}"

    # 2. docker-build.yml tags with github.sha
    docker_yml = WORKFLOWS_DIR / "docker-build.yml"
    assert docker_yml.is_file(), "Missing .github/workflows/docker-build.yml"
    docker_content = docker_yml.read_text(encoding="utf-8")
    assert "github.sha" in docker_content, (
        "docker-build.yml must tag container images with github.sha (CLAUDE.md §15)"
    )

    # 3. terraform-validate.yml matrix covers all 3 clouds
    tf_val_yml = WORKFLOWS_DIR / "terraform-validate.yml"
    assert tf_val_yml.is_file(), "Missing .github/workflows/terraform-validate.yml"
    tf_content = tf_val_yml.read_text(encoding="utf-8")
    for cloud in ("aws", "azure", "gcp"):
        assert cloud in tf_content, f"terraform-validate.yml matrix must include {cloud}"

    # 4. _deploy.yml has OIDC id-token: write and prod-apply environment
    deploy_yml = WORKFLOWS_DIR / "_deploy.yml"
    assert deploy_yml.is_file(), "Missing .github/workflows/_deploy.yml"
    deploy_content = deploy_yml.read_text(encoding="utf-8")
    assert "id-token: write" in deploy_content, (
        "_deploy.yml must configure OIDC 'id-token: write' permissions"
    )
    assert "prod-apply" in deploy_content, (
        "_deploy.yml must gate production applies via 'prod-apply' environment (CLAUDE.md §15)"
    )


# ============================================================================
# 8. Makefile Lifecycle Targets Completeness (CLAUDE.md §14)
# ============================================================================


def test_makefile_comprehensive_targets():
    """Verify Makefile provides all development, testing, and operational lifecycle targets."""
    assert MAKEFILE.is_file(), f"Missing Makefile at {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    required_targets = [
        "setup:",
        "seed:",
        "ingest:",
        "backend:",
        "demo:",
        "mcp:",
        "test:",
        "lint:",
        "terraform-validate:",
        "smoke:",
    ]
    for target in required_targets:
        assert target in content, f"Makefile must define operational target '{target}' (CLAUDE.md §14)"
