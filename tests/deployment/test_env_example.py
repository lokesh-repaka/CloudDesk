import subprocess
from pathlib import Path

from backend.app.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_env_example_exists():
    """Verify that .env.example exists in the repository root."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example file must exist at repository root"


def test_env_example_covers_all_settings_fields():
    """Verify that every field declared in Settings is documented in .env.example."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists()

    example_keys = set()
    with open(env_example, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                example_keys.add(key)

    settings_fields = set(Settings.model_fields.keys())

    missing = settings_fields - example_keys
    assert not missing, f".env.example is missing configuration fields: {missing}"


def test_no_committed_env_file():
    """Verify that .env file is git-ignored and never committed to version control."""
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "", ".env file must not be committed to Git repository"


def test_makefile_exists_and_contains_targets():
    """Verify Makefile exists and provides required development lifecycle targets."""
    makefile = REPO_ROOT / "Makefile"
    assert makefile.exists(), "Makefile must exist at repository root"

    content = makefile.read_text(encoding="utf-8")
    required_targets = ["setup:", "test:", "lint:", "backend:", "demo:"]
    for target in required_targets:
        assert target in content, f"Makefile must define target '{target}'"


def test_env_example_contains_safe_placeholders_only():
    """Verify .env.example contains placeholder values and no real API secrets."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists()

    content = env_example.read_text(encoding="utf-8")
    assert "sk-proj-" not in content, "Real OpenAI key detected in .env.example"
    assert "sk-ant-" not in content, "Real Anthropic key detected in .env.example"
