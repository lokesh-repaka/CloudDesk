"""Terraform Infrastructure and CI Delivery Scaffolds Tests (P14-4, CLAUDE.md §13, §15).

Verifies multi-cloud Terraform roots (AWS, Azure, GCP), shared modules, environment var-files,
lifecycle deployment scripts, refusal of --auto-approve on staging/prod, GitHub Actions CI workflows,
and OIDC cloud security in accordance with:
- CLAUDE.md §13 (compose services, Dockerfile hygiene, deployment tests)
- CLAUDE.md §15 (Containers, infrastructure, delivery)
- CWE-200 (Information Exposure / no plaintext secrets in terraform or CI)
- CWE-250 (Execution with Unnecessary Privileges / OIDC without long-lived keys)
- CWE-732 (Incorrect Permission Assignment / production safeguard on auto-approve)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPLOYMENT_DIR = REPO_ROOT / "deployment"
MODULES_DIR = DEPLOYMENT_DIR / "modules"
ENVIRONMENTS_DIR = DEPLOYMENT_DIR / "environments"
SCRIPTS_DIR = DEPLOYMENT_DIR / "scripts"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


# ============================================================================
# 1. Multi-Cloud Terraform Roots & Modules Structure (CLAUDE.md §15)
# ============================================================================


def test_terraform_cloud_roots_exist():
    """Verify Terraform roots exist for aws, azure, and gcp (CLAUDE.md §15)."""
    for cloud in ("aws", "azure", "gcp"):
        root_dir = DEPLOYMENT_DIR / cloud
        assert root_dir.is_dir(), f"Missing Terraform root directory for {cloud}"
        assert (root_dir / "main.tf").is_file(), f"Missing main.tf in {root_dir}"
        assert (root_dir / "variables.tf").is_file(), f"Missing variables.tf in {root_dir}"
        assert (root_dir / "outputs.tf").is_file(), f"Missing outputs.tf in {root_dir}"


def test_terraform_shared_modules_exist():
    """Verify 7 shared Terraform modules exist under deployment/modules (CLAUDE.md §15)."""
    expected_modules = (
        "networking",
        "container-registry",
        "secrets",
        "compute",
        "load-balancer",
        "monitoring",
        "redis",
    )
    for module_name in expected_modules:
        mod_dir = MODULES_DIR / module_name
        assert mod_dir.is_dir(), f"Missing shared Terraform module: {mod_dir}"
        assert (mod_dir / "main.tf").is_file(), f"Missing main.tf in module {module_name}"
        assert (mod_dir / "variables.tf").is_file(), f"Missing variables.tf in module {module_name}"
        assert (mod_dir / "outputs.tf").is_file(), f"Missing outputs.tf in module {module_name}"


def test_terraform_environment_var_files_exist_without_copies_of_code():
    """Verify environments are var-files under deployment/environments/{dev,staging,prod}/terraform.tfvars."""
    for env in ("dev", "staging", "prod"):
        env_dir = ENVIRONMENTS_DIR / env
        assert env_dir.is_dir(), f"Missing environment directory for {env}"
        tfvars = env_dir / "terraform.tfvars"
        assert tfvars.is_file(), f"Missing terraform.tfvars in {env_dir}"

        # Verify no copies of code: only variable assignments
        content = tfvars.read_text(encoding="utf-8")
        assert not re.search(r"^\s*resource\s+", content, re.MULTILINE), (
            f"Environment {env} must only be a var-file, not a copy of code (CLAUDE.md §15)."
        )
        assert not re.search(r"^\s*module\s+", content, re.MULTILINE), (
            f"Environment {env} must only be a var-file, not a copy of code."
        )


def test_terraform_backend_hcl_is_git_ignored():
    """Verify backend.hcl remote state configuration is git-ignored (CLAUDE.md §15)."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.is_file(), ".gitignore must exist"
    gitignore_content = gitignore_path.read_text(encoding="utf-8")

    assert "backend.hcl" in gitignore_content, (
        "backend.hcl remote state configuration must be git-ignored per CLAUDE.md §15."
    )


# ============================================================================
# 2. Lifecycle Deployment Scripts & Production Guardrails (CLAUDE.md §15)
# ============================================================================


def test_deployment_scripts_exist():
    """Verify all 5 required deployment lifecycle scripts exist in deployment/scripts (CLAUDE.md §15)."""
    expected_scripts = (
        "deploy.sh",
        "build_and_push.sh",
        "smoke_test.sh",
        "rollback.sh",
        "destroy.sh",
    )
    for script_name in expected_scripts:
        script_file = SCRIPTS_DIR / script_name
        assert script_file.is_file(), f"Missing lifecycle script: {script_file}"


def test_deployment_scripts_refuse_auto_approve_for_staging_and_prod():
    """Verify scripts refuse --auto-approve for staging and prod by the script itself (CLAUDE.md §15)."""
    for script_name in ("deploy.sh", "destroy.sh"):
        script_file = SCRIPTS_DIR / script_name
        content = script_file.read_text(encoding="utf-8")

        # Must inspect arguments for --auto-approve and check staging/prod
        assert "--auto-approve" in content, (
            f"{script_name} must inspect and handle the '--auto-approve' flag."
        )
        assert "staging" in content and "prod" in content, (
            f"{script_name} must explicitly check for staging and prod environments."
        )
        # Must refuse / exit with error when auto-approve is attempted on staging or prod
        assert re.search(r"refus(?:ed|ing)|not allowed|prohibited|cannot be used", content, re.IGNORECASE), (
            f"{script_name} must explicitly refuse --auto-approve on staging and prod."
        )


# ============================================================================
# 3. GitHub Actions CI Delivery Scaffolds (CLAUDE.md §15)
# ============================================================================


def test_github_actions_workflows_exist():
    """Verify all required GitHub Actions workflow scaffolds exist (CLAUDE.md §15)."""
    expected_workflows = (
        "test.yml",
        "security.yml",
        "docker-build.yml",
        "terraform-validate.yml",
        "_deploy.yml",
    )
    for wf in expected_workflows:
        wf_path = WORKFLOWS_DIR / wf
        assert wf_path.is_file(), f"Missing GitHub Actions workflow scaffold: {wf_path}"


def test_security_workflow_scans():
    """Verify security.yml covers gitleaks, pip-audit, Trivy, and checkov (CLAUDE.md §15)."""
    sec_content = (WORKFLOWS_DIR / "security.yml").read_text(encoding="utf-8")

    assert "gitleaks" in sec_content.lower(), "security.yml must include gitleaks scan"
    assert "pip-audit" in sec_content.lower(), "security.yml must include pip-audit scan"
    assert "trivy" in sec_content.lower(), "security.yml must include Trivy container scan"
    assert "checkov" in sec_content.lower(), "security.yml must include checkov IaC scan"


def test_docker_build_workflow_uses_git_sha_tag():
    """Verify docker-build.yml tags container images with the git commit SHA (CLAUDE.md §15)."""
    docker_content = (WORKFLOWS_DIR / "docker-build.yml").read_text(encoding="utf-8")

    assert "github.sha" in docker_content, (
        "docker-build.yml must use ${{ github.sha }} tag per CLAUDE.md §15."
    )


def test_deploy_pipeline_structure_and_prod_environment():
    """Verify _deploy.yml reusable pipeline implements required stages and prod-apply environment."""
    deploy_content = (WORKFLOWS_DIR / "_deploy.yml").read_text(encoding="utf-8")

    # Reusable workflow
    assert "workflow_call:" in deploy_content, "_deploy.yml must be a reusable workflow (workflow_call)"

    # Stages: bootstrap-registry, build-and-push, plan, apply, smoke
    assert "bootstrap-registry" in deploy_content, "_deploy.yml must include bootstrap-registry job"
    assert "build-and-push" in deploy_content, "_deploy.yml must include build-and-push job"
    assert "plan" in deploy_content, "_deploy.yml must include plan job"
    assert "apply" in deploy_content, "_deploy.yml must include apply job"
    assert "smoke" in deploy_content, "_deploy.yml must include smoke job"

    # Prod uses GitHub Environment prod-apply
    assert "prod-apply" in deploy_content, (
        "_deploy.yml must reference GitHub Environment 'prod-apply' per CLAUDE.md §15."
    )

    # OIDC authentication (id-token: write), no long-lived static cloud keys
    assert "id-token: write" in deploy_content, (
        "_deploy.yml must use OIDC permissions ('id-token: write') per CLAUDE.md §15."
    )


# ============================================================================
# 4. Security & Secret Hygiene Audits (CWE-200, CWE-250)
# ============================================================================


def test_security_cwe_200_no_secrets_in_terraform_or_ci():
    """Security Audit (CWE-200): Ensure no real API keys, cloud tokens, or passwords exist in IaC or CI files."""
    scanned_dirs = [DEPLOYMENT_DIR, WORKFLOWS_DIR]

    for base_dir in scanned_dirs:
        for file_path in base_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in (".tf", ".tfvars", ".yml", ".yaml", ".sh"):
                content = file_path.read_text(encoding="utf-8")
                assert "sk-proj-" not in content, f"Real OpenAI key detected in {file_path}"
                assert "sk-ant-" not in content, f"Real Anthropic key detected in {file_path}"
                assert "ghp_" not in content, f"Real GitHub token detected in {file_path}"
                assert "AKIA" not in content, f"Real AWS access key detected in {file_path}"
                assert not re.search(r"password\s*=\s*[\"'][^\"'$]{8,}[\"']", content, re.IGNORECASE), (
                    f"Potential hardcoded password found in {file_path}"
                )
