"""Verify no near-duplicate paragraphs across markdown files."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).parent.parent
SCRIPT = (
    ROOT / ".claude" / "skills" / "skill-linting" / "bin" / "cross_file_checking.py"
)

# Similarity threshold — paragraphs above this score are flagged as duplicates
THRESHOLD = 0.92

# File pairs that are expected to have similar content (mirrors, generated, etc.)
EXPECTED_SIMILAR = {
    # CLAUDE.md and GEMINI.md share instructions by design
    frozenset(["CLAUDE.md", "GEMINI.md"]),
    # GitHub copies of root files
    frozenset([".github/SECURITY.md", "SECURITY.md"]),
    # batch-prompt is intentionally self-contained — duplicates offer commands and cv skill by design
    frozenset(["batch/batch-prompt.md", "commands/offer.md"]),
    frozenset(["batch/batch-prompt.md", "skills/cv/SKILL.md"]),
    # batch-prompt embeds archetype reference table also in profile template
    frozenset(["batch/batch-prompt.md", "templates/_profile.template.md"]),
    # data/applications.md is seeded from template — structural similarity expected
    frozenset(["data/applications.md", "templates/applications.template.md"]),
    # followup and patterns share the same ## Inputs section structure
    frozenset(["commands/followup.md", "commands/patterns.md"]),
}


def _is_expected_match(line: str) -> bool:
    """Check if a match line is expected (same file or known mirror pair)."""
    # Format: "file_a:line_a → file_b:line_b (score)"
    if "→" not in line:
        return False

    parts = line.split("→")
    file_a = parts[0].strip().rsplit(":", 1)[0]
    file_b = parts[1].strip().split()[0].rsplit(":", 1)[0]

    # Same file = expected (changelog entries, data rows, etc.)
    if file_a == file_b:
        return True

    # Known mirror pairs
    pair = frozenset([file_a, file_b])
    return pair in EXPECTED_SIMILAR


def test_no_duplicate_paragraphs():
    """Fail if any unexpected paragraph pairs exceed the similarity threshold."""
    result = subprocess.run(
        [
            "uv",
            "run",
            str(SCRIPT),
            "--quiet",
            "--threshold",
            str(THRESHOLD),
            "--brief",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    # Filter out expected matches
    unexpected = [
        line
        for line in result.stdout.strip().splitlines()
        if line and not _is_expected_match(line)
    ]

    if unexpected:
        raise AssertionError(
            f"Found unexpected duplicate paragraphs (threshold={THRESHOLD}):\n"
            + "\n".join(unexpected)
        )

    # Also fail on script errors
    if result.returncode != 0:
        raise AssertionError(f"Script failed:\n{result.stderr}")
