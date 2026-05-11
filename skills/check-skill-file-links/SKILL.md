---
description: Ensure every file path mentioned in a skill's markdown is a real markdown link to an existing file, so linters and humans can verify references.
---

# Check Skill File Links

Skill docs reference other files constantly: sibling `SKILL.md`s, bin scripts, asset symlinks, external standards. If those references are bare backticks or plain text, nothing catches it when the target gets renamed or deleted. Making every path a real markdown link turns "did I break a reference?" into a fast, mechanical check.

## The rule

Every file path mentioned in markdown must be a proper markdown link so linters can verify it exists:

```markdown
<!-- wrong -->
See `STYLEGUIDE.md` for conventions.

<!-- right -->
See [STYLEGUIDE.md](STYLEGUIDE.md) for conventions.
```

The exception is filenames that are referencing a *type* of file, not a specific file. For example, `SKILL.md` might refer to a specific file OR to the general type of file that all skills have. In the first case, it should be a link. In the second, it should not. If it should be a link, prefer [`./SKILL.md`](./SKILL.md) to be explicit that it's referring to the file in the current directory.

## Run the checker

[`./bin/link_md_paths.py`](./bin/link_md_paths.py) finds and (optionally) fixes path references in markdown. It detects three issues:

1. Backtick paths (`` `file.ext` ``) not yet linked → resolves bare filenames, converts to `[`path`](path)` links.
2. Plain-text paths (`path/to/file.ext`, no backticks) that exist on disk → wraps them in `[`path`](path)` links.
3. Backtick paths that look like file references but don't resolve → broken, reported as warnings.

Common invocations:

```
# Fix everything in tracked .md files
uv run skills/check-skill-file-links/bin/link_md_paths.py

# CI / pytest mode: report issues, exit 1 if any
uv run skills/check-skill-file-links/bin/link_md_paths.py --check

# Preview without writing
uv run skills/check-skill-file-links/bin/link_md_paths.py --dry-run

# Specific files
uv run skills/check-skill-file-links/bin/link_md_paths.py README.md
```

## When the script misses or over-reports

If you find a path the script should have linked but didn't, update the script — usually that means adding an extension to `_KNOWN_EXTS` or extending the grammar. If the script flags something it shouldn't (e.g. a conceptual filename used as a type, not a real file), update these guidelines to describe the edge case so future readers know why a bare reference is correct.
