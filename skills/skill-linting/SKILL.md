---
description: Lint a skills repo for deep structural issues — layout, broken file links, contradictions between docs, MCP doctest hygiene, and asset isolation.
---

# Skill Linting

When running this skill, audit the repo for problematic patterns in the structure, formatting, or content of skill docs. Use the guidelines below to identify and fix issues, and delegate the two mechanical checks to the dedicated sub-skills.

## Workflow: scripts first, todos second, fixes third

Both sub-skills below produce a list of issues from a script. Before editing any files, run each script (in `--check` or default mode), then convert its output into a TodoWrite list — one todo per actionable item — and work the list item-by-item, marking each completed as you fix it. Don't skip this step on small repos either; the script's output drops out of context quickly once you start editing, and a todo list is the only thing that survives.

Order the work as:

1. Run [`../check-skill-file-links/bin/link_md_paths.py`](../check-skill-file-links/bin/link_md_paths.py) → todo list → fix.
2. Run [`../detect-skill-contradictions/bin/cross_file_checking.py`](../detect-skill-contradictions/bin/cross_file_checking.py) → todo list → fix.
3. Apply the structural rules below (layout, MCPs, asset isolation) by hand — these are judgment calls, not script-driven, but still benefit from a todo per finding.

# Layout

## Agentskills

Make sure skills are properly laid out in their canonical directory structure, as described on [agentskills.io](https://agentskills.io/).

## Claude Code Plugin Style

Make sure Claude Code plugins are formatted according to conventions in [https://code.claude.com/docs/en/plugins](https://code.claude.com/docs/en/plugins).

# Within any individual documentation file

## File paths must be links

Every file path mentioned in markdown must be a proper markdown link so linters can verify it exists. Run the dedicated skill to check and fix this mechanically:

→ [`../check-skill-file-links/SKILL.md`](../check-skill-file-links/SKILL.md)

# Across multiple documentation files

## Duplication and contradictions

Document a rule once, in the right place, and reference it by link elsewhere. If two docs say the same thing, one will rot; if they say *almost* the same thing, you have a contradiction. Run the dedicated skill to surface near-duplicate paragraphs across files:

→ [`../detect-skill-contradictions/SKILL.md`](../detect-skill-contradictions/SKILL.md)

# MCPs

Try to enforce doctests as much as possible, especially in MCPs where the docstrings become context for the agent.

MCPs should not return raw data structures that require the agent to inspect the output before it knows what it will be. They should return simple strings or structs that can be easily converted to a complete JSON schema and shown to the agent via `get_schema`.

# Structure

## Skill asset isolation

Skills must not hardcode paths outside their own directory. External files are exposed to the skill via symlinks in `skills/{skill}/assets/`:

```
skills/scan/assets/portals.yml -> ../../../personal/portals.yml
skills/scan/assets/search.yml  -> ../../../personal/search.yml
```

Use symlinks from an external file to a file in the skill if a file is needed in more than one skill.

## Skill bins

Executable scripts live in `skills/{skill}/bin/`. They must be self-contained, runnable directly, and accept all external paths as CLI options with sensible defaults.

### Python UV scripts

Standalone scripts use uv inline script metadata so they run with no manual venv:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2", "pyyaml>=6", "typer>=0.12"]
# ///
```

We do this so skills can be exported from the repo as self-contained units with no external setup.

ALSO add the dependencies to the root `pyproject.toml` if it exists so they are available in the venv for linting.
