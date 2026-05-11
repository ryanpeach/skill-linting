---
description: Lint the repo's skills for deep structural issues, like contradictions, non-links, etc. These are rules that allow the skills to be checkable with traditional linting tools.
---

# Skill Style Guide

When running this skill, check the repo for any problematic patterns in the structure, formatting, or content of the skill's documentation. Use the guidelines below to identify and fix issues.

# Agentskills

Make sure that skills are properly layed out in their canonical directory structure. As described on [agentskills.io](https://agentskills.io/).

# Claude Code Plugin Style

Make sure that claude code plugins are formatted according to conventions in [https://code.claude.com/docs/en/plugins](https://code.claude.com/docs/en/plugins).

# Within any individual documentation file

## File Paths Must Be Links

Every file path mentioned in markdown must be a proper markdown link so linters can verify it exists:

```markdown
<!-- wrong -->
See `STYLEGUIDE.md` for conventions.

<!-- right -->
See [STYLEGUIDE.md](STYLEGUIDE.md) for conventions.
```

The exception to this rule is file names that are referencing a "type" of file, not a specific file. For example, `SKILL.md` might refer to a specific file OR to the general type of file that all skills have. In the first case, it should be a link. In the second case, it should not be a link. If it should be a link, please make it [`./SKILL.md`](./SKILL.md) to be explicit that it's referring to the file in the current directory.

[./bin/link_md_paths.py](./bin/link_md_paths.py) can help check for and convert plaintext paths to markdown links. If you find something this script doesn't find, then update it. If it finds something that you dont find, then update these guidelines to clarify the edge case.

# Across multiple documentation files

[./bin/cross_file_checking.py](./bin/cross_file_checking.py) will output a list of paragraphs which have high similarity scores across files. You can then check these for the following issues:

## Duplication

Document a rule once, in the right place. Reference it by link elsewhere. If two docs say the same thing, one will rot.

## Contradictions

Watch out for saying one thing in one doc and another thing in another doc.

# MCP's

Try to enforce doctests as much as possible, especially in mcp's where the docstrings become context for the agent.

MCP's should not return raw data structures that require the agent to inspect the output before it knows what it will be. They should return simple strings or structs that can be easily converted to complete JSON schema and shown to the agent via get_schema.

# Structure

## Skill Asset Isolation

Skills must not hardcode paths outside their own directory. External files are exposed to the skill via symlinks in `skills/{skill}/assets/`:

```
skills/scan/assets/portals.yml -> ../../../personal/portals.yml
skills/scan/assets/search.yml  -> ../../../personal/search.yml
```

Use symlinks from an external file to a file in the skill if a file is needed in more than one skill.

## Skill Bins

Executable scripts live in `skills/{skill}/bin/`. They must be self-contained, runnable directly, and accept all external paths as CLI options with sensible defaults.

### Python UV Scripts

Standalone scripts use uv inline script metadata so they run with no manual venv:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2", "pyyaml>=6", "typer>=0.12"]
# ///
```

We do this so that skills can be exported from the repo as self-contained units with no external setup.

ALSO add the dependencies to the root `pyproject.toml` if it exists so they are available in the venv for linting.
