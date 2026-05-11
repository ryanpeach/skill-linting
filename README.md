# skill-linting

A Claude Code plugin (and marketplace) that audits skills repos.

Bundles two skills:

- **`skill-linting`** — lints skill docs for structural issues: missing frontmatter, unlinked file paths, duplicated content, contradictions across docs.
- **`claude-safety`** — reviews `~/.claude/settings.json` for risky auto-allowed permissions.

## Install

In Claude Code:

```
/plugin marketplace add ryanpeach/skill-linting
/plugin install skill-linting@skill-linting
```

Then `/reload-plugins` (or restart Claude Code).

## Use

The `skill-linting` skill auto-activates when you ask Claude to lint or audit a skills repo. The `claude-safety` skill is invoked when reviewing Claude Code permission/settings safety.
