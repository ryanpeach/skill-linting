"""Verify no unlinked or broken path references in tracked .md files."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).parent.parent


def _get_tracked_md_files() -> list[Path]:
    """Get all git-tracked markdown files."""
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / p for p in result.stdout.splitlines() if p]


def test_no_unlinked_md_paths():
    result = subprocess.run(
        [
            "uv",
            "run",
            str(
                ROOT
                / ".claude"
                / "skills"
                / "skill-linting"
                / "bin"
                / "link_md_paths.py"
            ),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Path issues found:\n{result.stdout}{result.stderr}"


def test_md_file_links() -> None:
    """Test each markdown file individually for unlinked/broken paths."""
    result = subprocess.run(
        [
            "uv",
            "run",
            str(
                ROOT
                / ".claude"
                / "skills"
                / "skill-linting"
                / "bin"
                / "link_md_paths.py"
            ),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Path issues found:\n{result.stdout}{result.stderr}"
