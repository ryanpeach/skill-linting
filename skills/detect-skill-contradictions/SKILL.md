---
description: Find paragraphs that are near-duplicates across markdown files in a skills repo so you can fix duplication or genuine contradictions between docs.
---

# Detect Skill Contradictions

Two skill docs that say similar-but-not-identical things are the most common source of skill rot: one drifts, the other stays, and the agent reads both. This skill finds those pairs so you can collapse, reword, or cross-link them.

## Run the checker

[`./bin/cross_file_checking.py`](./bin/cross_file_checking.py) uses hybrid search (BM25 + sentence-transformer embeddings) to surface paragraph pairs above a similarity threshold:

```
uv run skills/detect-skill-contradictions/bin/cross_file_checking.py
```

Useful flags:

- `--threshold 0.8` — loosen the match threshold (default `0.9`)
- `--brief` — omit snippet previews
- `--exclude <dir>` — skip directories (e.g. `data`, `personal`)
- `--model all-mpnet-base-v2` — swap in a heavier embedding model

Output is one line per pair, sorted by score:

```
file_a:line_a → file_b:line_b (0.92) - "snippet preview..."
```

## Build a todo list from the output before triaging

Run the script first and turn its output into a TodoWrite list — one todo per reported pair. Each pair requires a human-judgment decision (duplication vs. contradiction vs. acceptable overlap), so a checklist is the right granularity. Mark each todo completed only after you've resolved that pair (edited the docs, added a cross-link, or explicitly decided to leave it).

This matters because:

- The script's similarity report scrolls out of context quickly once you start editing files.
- Pairs are independent decisions — batching invites either rubber-stamping or losing track.
- Some pairs cascade: collapsing duplication in one file can resolve several pending pairs, and a todo list makes that easy to spot and check off together.

## Triage each pair

For every pair the script reports, classify it as one of:

### Duplication

The same rule restated. Pick the canonical home, delete the copy, and replace it with a markdown link to the canonical paragraph.

### Contradiction

The two paragraphs disagree on a rule, default, or recommendation. Decide which one is right, fix the other, and ideally collapse into a single source of truth.

### Acceptable overlap

Two skills genuinely need to mention the same concept (e.g. both reference the same external standard). Leave the wording alone but make sure each link points at the canonical definition rather than re-deriving it.

## When the script misses or over-reports

If a pair you'd consider a contradiction is below threshold, lower `--threshold` rather than rewriting the script. If the script flags pairs that are clearly fine (boilerplate frontmatter, shared headers, license text), add them to an `--exclude` directory or shorten the snippet so they fall under `--min-chars`. Only change the script itself when an entire category of false positive or negative shows up repeatedly.
