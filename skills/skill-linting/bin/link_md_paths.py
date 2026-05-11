#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyparsing>=3.1"]
# ///
"""
link_md_paths.py — Find and fix path references in markdown.

Three checks:
  1. Backtick paths (`file.ext`) not yet linked → resolve bare filenames,
     convert to [`path`](path) links.
  2. Plain-text paths (path/to/file.ext, no backtick) that exist on disk →
     wrap in [`path`](path) links.
  3. Backtick paths that look like file references but don't resolve → broken.

Modes:
  fix   (default): apply fixes 1+2, warn on 3
  check (--check): report all issues, exit 1 if any found (CI/pytest mode)

Usage:
  uv run bin/link_md_paths.py                     # fix all tracked .md files
  uv run bin/link_md_paths.py --check             # report issues
  uv run bin/link_md_paths.py --dry-run           # preview fixes
  uv run bin/link_md_paths.py README.md           # specific file(s)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pyparsing as pp
import typer

app = typer.Typer()

# File extensions that qualify as linkable paths (excludes TLDs like .io .com .net)
_KNOWN_EXTS = frozenset(
    {
        "md",
        "py",
        "mjs",
        "js",
        "ts",
        "tsx",
        "mts",
        "cts",
        "jsx",
        "yml",
        "yaml",
        "json",
        "toml",
        "html",
        "htm",
        "tex",
        "csv",
        "tsv",
        "txt",
        "sh",
        "bash",
        "cfg",
        "ini",
        "xml",
    }
)

# ── pyparsing grammars ───────────────────────────────────────────────────────

pp.ParserElement.enable_packrat()

# Character classes
_ALPHANUMS = pp.alphanums
_PATH_FIRST_CHAR = pp.alphanums + "_."
_PATH_CHARS = pp.alphanums + "_.-/"
_EXT_CHARS = pp.alphas

# File extension: .ext (2-5 letters)
_ext = pp.Combine(pp.Literal(".") + pp.Word(_EXT_CHARS, min=2, max=5))

# Path body: characters valid in file paths
_path_body = pp.Word(_PATH_CHARS)

# Backtick path: `file.ext` or `path/to/file.ext`
_backtick_path = (
    pp.Literal("`").suppress()
    + pp.Combine(
        pp.Word(_PATH_FIRST_CHAR, exact=1) + pp.Optional(pp.Word(_PATH_CHARS)) + _ext
    )("path")
    + pp.Literal("`").suppress()
)

# Plain path with at least one slash: path/to/file.ext
_plain_path = pp.Combine(
    pp.Word(pp.alphas, exact=1)
    + pp.Optional(pp.Word(_PATH_CHARS))
    + pp.Literal("/")
    + pp.Word(_PATH_FIRST_CHAR, exact=1)
    + pp.Optional(pp.Word(_PATH_CHARS))
    + _ext
)("path")

# Already-linked backtick: [`text`](url)
# Use QuotedString for backticks (same open/close), nested_expr for brackets/parens
_link_text_backtick = pp.QuotedString("`", unquote_results=False)
_link_url = pp.nested_expr("(", ")", ignore_expr=None)
_linked_backtick = pp.Literal("[") + _link_text_backtick + pp.Literal("]") + _link_url

# Already-linked plain: [text](url)
_link_text_plain = pp.nested_expr("[", "]", ignore_expr=None)
_linked_plain = _link_text_plain + _link_url

# Fenced code block: ```...```
# Using QuotedString with multiline support
_fence = pp.QuotedString("```", multiline=True, unquote_results=False)

# Inline code: `text` (no newlines)
_inline_code = pp.QuotedString("`", unquote_results=False)

# URL: http:// or https://
_url_scheme = pp.Literal("https://") | pp.Literal("http://")
_url_chars = pp.Word(pp.printables, exclude_chars=" \t\n\r")
_url = pp.Combine(_url_scheme + _url_chars)


class IssueKind(str, Enum):
    FIXABLE_BACKTICK = "fixable_backtick"
    FIXABLE_PLAIN = "fixable_plain"
    BROKEN_BACKTICK = "broken_backtick"


@dataclass
class Issue:
    kind: IssueKind
    start: int
    end: int
    original: str
    replacement: str | None  # None for BROKEN_BACKTICK


# ── helpers ──────────────────────────────────────────────────────────────────


def _has_known_ext(path: str) -> bool:
    return Path(path).suffix.lstrip(".").lower() in _KNOWN_EXTS


def _is_personal(path: str) -> bool:
    return path.startswith("personal/") or path.startswith("personal\\")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _find_bare(filename: str, repo_root: Path, md_path: Path) -> Path | None:
    """
    Resolve a bare filename (no slashes) to a repo path.
    Deduplicates symlinks by resolved real path.
    Preference order: same dir as md_path → personal/ → unique match.
    """
    seen: dict[Path, Path] = {}  # real_path → logical path
    for p in repo_root.rglob(filename):
        if ".git" in p.parts or "node_modules" in p.parts:
            continue
        real = p.resolve()
        if real not in seen:
            seen[real] = p

    if not seen:
        return None
    if len(seen) == 1:
        return next(iter(seen.values()))

    # Prefer file in the same directory as the markdown file
    for real, p in seen.items():
        if p.parent.resolve() == md_path.parent.resolve():
            return real

    # Prefer personal/ (canonical user data)
    for real, p in seen.items():
        try:
            if str(p.relative_to(repo_root)).startswith("personal/"):
                return real
        except ValueError:
            pass

    return None


def _resolve(raw: str, repo_root: Path, md_path: Path) -> tuple[Path | None, str]:
    """
    Return (abs_path_or_None, display_path).
    display_path may differ from raw when a bare filename is expanded or
    a relative path is normalised to repo-root-relative.
    abs_path is None when unresolvable.
    """
    stripped = raw.strip()
    if not _has_known_ext(stripped):
        return None, stripped

    # Try from repo root
    candidate = (repo_root / stripped).resolve()
    if candidate.exists() and _is_within(candidate, repo_root):
        return candidate, stripped

    # Try relative to the markdown file's directory (handles ../../ paths)
    rel_candidate = (md_path.parent / stripped).resolve()
    if rel_candidate.exists() and _is_within(rel_candidate, repo_root):
        display = str(rel_candidate.relative_to(repo_root))
        return rel_candidate, display

    # personal/ files are runtime user data — link even when absent from repo
    if _is_personal(stripped):
        return candidate, stripped

    # Bare filename: search the repo with priority heuristics
    if "/" not in stripped and "\\" not in stripped:
        found = _find_bare(stripped, repo_root, md_path)
        if found:
            display = str(found.relative_to(repo_root))
            return found, display

    return None, stripped


def _href(candidate: Path, display: str, md_path: Path, repo_root: Path) -> str:
    if _is_personal(display) and not candidate.exists():
        return display
    try:
        return str(candidate.relative_to(md_path.parent.resolve()))
    except ValueError:
        return str(candidate.relative_to(repo_root))


# ── protected spans ───────────────────────────────────────────────────────────


def _protected_spans(text: str, *, include_inline_code: bool) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    grammars = [_fence, _linked_backtick, _linked_plain, _url]
    if include_inline_code:
        grammars.append(_inline_code)

    for grammar in grammars:
        try:
            for tokens, start, end in grammar.scan_string(text):
                spans.append((start, end))
        except pp.ParseException:
            continue
    return spans


def _in_protected(pos: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= pos and end <= e for s, e in spans)


# ── issue collection ──────────────────────────────────────────────────────────


def _collect_issues(text: str, md_path: Path, repo_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    base_protected = _protected_spans(text, include_inline_code=False)
    full_protected = _protected_spans(text, include_inline_code=True)

    # Phase A: backtick paths
    try:
        for tokens, start, end in _backtick_path.scan_string(text):
            # Calculate actual start/end including backticks
            actual_start = start - 1  # account for leading backtick
            actual_end = end + 1  # account for trailing backtick
            if _in_protected(actual_start, actual_end, base_protected):
                continue
            raw = str(tokens["path"])
            if not _has_known_ext(raw.strip()):
                continue
            resolved, display = _resolve(raw, repo_root, md_path)
            if resolved is not None:
                href = _href(resolved, display, md_path, repo_root)
                repl = f"[`{display}`]({href})"
                original = f"`{raw}`"
                issues.append(
                    Issue(
                        IssueKind.FIXABLE_BACKTICK,
                        actual_start,
                        actual_end,
                        original,
                        repl,
                    )
                )
            else:
                stripped = raw.strip()
                # Only flag broken if it looks like an explicit path (contains /).
                # Bare filenames (no /) may be conceptual references — silently skip.
                if "/" in stripped or "\\" in stripped:
                    original = f"`{raw}`"
                    issues.append(
                        Issue(
                            IssueKind.BROKEN_BACKTICK,
                            actual_start,
                            actual_end,
                            original,
                            None,
                        )
                    )
    except pp.ParseException:
        pass

    # Phase B: plain-text paths with slashes that exist on disk
    try:
        for tokens, start, end in _plain_path.scan_string(text):
            if _in_protected(start, end, full_protected):
                continue
            raw = str(tokens["path"])
            if not _has_known_ext(raw):
                continue
            candidate = (repo_root / raw.strip()).resolve()
            if not candidate.exists():
                # Also try relative to md file
                rel = (md_path.parent / raw.strip()).resolve()
                if rel.exists() and _is_within(rel, repo_root):
                    candidate = rel
                    raw = str(rel.relative_to(repo_root))
                else:
                    continue
            href = _href(candidate, raw, md_path, repo_root)
            repl = f"[`{raw}`]({href})"
            issues.append(Issue(IssueKind.FIXABLE_PLAIN, start, end, raw, repl))
    except pp.ParseException:
        pass

    return issues


# ── file processing ───────────────────────────────────────────────────────────


def process_file(
    md_path: Path,
    repo_root: Path,
    *,
    dry_run: bool,
    check: bool,
) -> tuple[int, int]:
    """Return (fixable_count, broken_count)."""
    text = md_path.read_text()
    issues = _collect_issues(text, md_path, repo_root)

    fixable = [i for i in issues if i.kind != IssueKind.BROKEN_BACKTICK]
    broken = [i for i in issues if i.kind == IssueKind.BROKEN_BACKTICK]
    rel = md_path.relative_to(repo_root)

    if check:
        for i in fixable:
            print(f"  {rel}: unlinked: {i.original!r} → {i.replacement!r}")
        for i in broken:
            print(f"  {rel}: broken: {i.original!r}")
        return len(fixable), len(broken)

    if fixable:
        if dry_run:
            for i in fixable:
                print(f"  {rel}: {i.original!r} → {i.replacement!r}")
        else:
            result = text
            for i in sorted(fixable, key=lambda x: x.start, reverse=True):
                assert i.replacement is not None
                result = result[: i.start] + i.replacement + result[i.end :]
            md_path.write_text(result)
            print(f"  {rel}: {len(fixable)} link(s) added")

    for i in broken:
        print(f"  {rel}: WARNING broken path: {i.original!r}")

    return len(fixable), len(broken)


def tracked_md_files(repo_root: Path) -> list[Path]:
    out = subprocess.check_output(
        ["git", "ls-files", "*.md"],
        cwd=repo_root,
        text=True,
    )
    paths = []
    for p in out.splitlines():
        if not p:
            continue
        full = repo_root / p
        if not full.exists() or full.is_symlink():
            continue
        paths.append(full)
    return paths


@app.command()
def main(
    files: list[Path] = typer.Argument(
        default=None, help="Specific .md files (default: all tracked)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing."),
    check: bool = typer.Option(
        False, "--check", help="Report issues, exit 1 if any (CI mode)."
    ),
    repo_root: Path = typer.Option(Path("."), "--root", help="Repo root directory."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress bar."),
) -> None:
    repo_root = repo_root.resolve()
    targets = [f.resolve() for f in files] if files else tracked_md_files(repo_root)

    total_fixes = 0
    total_broken = 0

    if quiet:
        for f in targets:
            fixes, broken = process_file(f, repo_root, dry_run=dry_run, check=check)
            total_fixes += fixes
            total_broken += broken
    else:
        with typer.progressbar(targets, label="Scanning files") as progress:
            for f in progress:
                fixes, broken = process_file(f, repo_root, dry_run=dry_run, check=check)
                total_fixes += fixes
                total_broken += broken

    if check:
        print(
            f"\n{total_fixes} unlinked + {total_broken} broken across {len(targets)} file(s)."
        )
        if total_fixes > 0 or total_broken > 0:
            raise typer.Exit(1)
    else:
        action = "Would add" if dry_run else "Added"
        print(f"\n{action} {total_fixes} link(s) across {len(targets)} file(s).")
        if total_broken:
            print(f"WARNING: {total_broken} broken backtick path(s) — fix manually.")


if __name__ == "__main__":
    app()
