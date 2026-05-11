#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "chromadb>=0.4",
#     "markdown-it-py>=3",
#     "rank_bm25>=0.2",
#     "sentence-transformers>=2.2",
#     "typer>=0.12",
# ]
# ///
"""
cross_file_checking.py — Find similar paragraphs across markdown files.

Uses hybrid search (BM25 + semantic embeddings) to detect near-duplicate
content that may indicate copy-paste documentation or contradictions.

Outputs pairs sorted by similarity score (highest first):
  file_a:line_a → file_b:line_b (0.92) - "snippet preview..."

Usage:
  uv run cross_file_checking.py                      # scan workspace
  uv run cross_file_checking.py --threshold 0.8      # looser threshold
  uv run cross_file_checking.py --brief              # omit snippets
  uv run cross_file_checking.py --model all-mpnet-base-v2  # better model
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from markdown_it import MarkdownIt
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

app = typer.Typer()

# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class Paragraph:
    """A paragraph extracted from a markdown file."""

    file_path: Path
    line_number: int
    text: str
    heading_context: str = ""

    @property
    def id(self) -> str:
        """Unique identifier for deduplication."""
        return f"{self.file_path}:{self.line_number}"

    def snippet(self, max_len: int = 60) -> str:
        """Return truncated preview of text."""
        text = self.text.replace("\n", " ").strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."


@dataclass
class SimilarityMatch:
    """A pair of similar paragraphs."""

    para_a: Paragraph
    para_b: Paragraph
    score: float  # Combined similarity score (0-1, higher = more similar)

    def format(self, brief: bool = False, root: Path | None = None) -> str:
        """Format as output line."""
        path_a = self.para_a.file_path
        path_b = self.para_b.file_path
        if root:
            try:
                path_a = path_a.relative_to(root)
                path_b = path_b.relative_to(root)
            except ValueError:
                pass

        line = f"{path_a}:{self.para_a.line_number} → {path_b}:{self.para_b.line_number} ({self.score:.2f})"
        if not brief:
            line += f' - "{self.para_a.snippet()}"'
        return line


# ── Markdown Parsing ─────────────────────────────────────────────────────────


def extract_paragraphs(file_path: Path, min_chars: int = 50) -> list[Paragraph]:
    """Extract paragraphs from a markdown file using markdown-it-py."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    md = MarkdownIt()
    tokens = md.parse(content)

    paragraphs: list[Paragraph] = []
    current_heading = ""

    for token in tokens:
        # Track heading context
        if token.type == "heading_open":
            # Next token should be heading content
            continue
        if token.type == "inline" and token.map:
            # Check if parent was heading
            pass

        if token.type == "heading_open":
            continue

        # Look for inline content within paragraphs
        if token.type == "inline" and token.content and token.map:
            line_start = token.map[0] + 1  # 1-indexed
            text = token.content.strip()

            # Skip short paragraphs
            if len(text) < min_chars:
                continue

            # Skip if it looks like a list item marker only
            if text.startswith(("-", "*", "+")) and len(text) < min_chars + 5:
                continue

            paragraphs.append(
                Paragraph(
                    file_path=file_path,
                    line_number=line_start,
                    text=text,
                    heading_context=current_heading,
                )
            )

        # Update heading context from heading tokens
        if token.type == "heading_open" and token.map:
            # Find the inline token that follows
            pass

    # Second pass: extract heading text for context
    i = 0
    current_heading = ""
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open" and i + 1 < len(tokens):
            next_token = tokens[i + 1]
            if next_token.type == "inline":
                current_heading = next_token.content
        elif token.type == "inline" and token.map:
            line_start = token.map[0] + 1
            # Update heading_context for matching paragraphs
            for para in paragraphs:
                if para.line_number == line_start:
                    para.heading_context = current_heading
        i += 1

    return paragraphs


def collect_markdown_files(root: Path, exclude: list[str] | None = None) -> list[Path]:
    """Collect all markdown files, respecting git if available. Skips symlinks."""
    exclude_dirs = set(exclude or [])
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            p = root / line
            if p.is_symlink() or not p.exists():
                continue
            parts = set(p.relative_to(root).parts[:-1])
            if parts & exclude_dirs:
                continue
            paths.append(p)
        return paths
    except (subprocess.CalledProcessError, FileNotFoundError):
        paths = []
        for p in root.rglob("*.md"):
            if p.is_symlink():
                continue
            parts = set(p.relative_to(root).parts[:-1])
            if parts & exclude_dirs:
                continue
            paths.append(p)
        return paths


# ── Similarity Search ────────────────────────────────────────────────────────


def build_bm25_index(paragraphs: list[Paragraph]) -> BM25Okapi:
    """Build BM25 index from paragraph texts."""
    tokenized = [p.text.lower().split() for p in paragraphs]
    return BM25Okapi(tokenized)


def find_similar_pairs(
    paragraphs: list[Paragraph],
    model_name: str,
    persist_dir: Path,
    threshold: float,
    top_k: int,
    bm25_weight: float = 0.3,
    quiet: bool = False,
) -> list[SimilarityMatch]:
    """Find similar paragraph pairs using hybrid search."""
    import chromadb

    if not paragraphs:
        return []

    # Load embedding model
    typer.echo(f"Loading model: {model_name}", err=True)
    model = SentenceTransformer(model_name)

    # Build BM25 index
    typer.echo("Building BM25 index...", err=True)
    bm25 = build_bm25_index(paragraphs)

    # Setup Chroma
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))

    # Use model name in collection to avoid conflicts
    collection_name = f"paragraphs_{model_name.replace('/', '_').replace('-', '_')}"

    # Delete existing collection to rebuild fresh
    try:
        client.delete_collection(collection_name)
    except (ValueError, Exception) as e:
        # Chroma raises different exceptions depending on version
        if (
            "not exist" not in str(e).lower()
            and "NotFoundError" not in type(e).__name__
        ):
            raise

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Generate embeddings
    typer.echo(f"Embedding {len(paragraphs)} paragraphs...", err=True)
    texts = [p.text for p in paragraphs]
    embeddings = model.encode(texts, show_progress_bar=not quiet)

    # Add to Chroma
    collection.add(
        ids=[p.id for p in paragraphs],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[
            {"file": str(p.file_path), "line": p.line_number} for p in paragraphs
        ],
    )

    # Find similar pairs
    typer.echo("Searching for similar pairs...", err=True)
    matches: list[SimilarityMatch] = []
    seen: set[frozenset[str]] = set()

    # Create paragraph lookup
    para_by_id = {p.id: p for p in paragraphs}

    for i, para in enumerate(
        typer.progressbar(paragraphs, label="Finding pairs")
        if not quiet
        else paragraphs
    ):
        # Query Chroma for nearest neighbors
        results = collection.query(
            query_embeddings=[embeddings[i].tolist()],
            n_results=min(top_k + 1, len(paragraphs)),  # +1 to account for self
            include=["distances"],
        )

        if (
            not results["ids"]
            or not results["ids"][0]
            or not results["distances"]
            or not results["distances"][0]
        ):
            continue

        # Get BM25 scores for this paragraph
        query_tokens = para.text.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)

        # Normalize BM25 scores to 0-1 range
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_normalized = [s / max_bm25 for s in bm25_scores]

        for j, (match_id, distance) in enumerate(
            zip(results["ids"][0], results["distances"][0])
        ):
            # Skip self-match
            if match_id == para.id:
                continue

            # Skip if already seen (bidirectional dedup)
            pair_key = frozenset([para.id, match_id])
            if pair_key in seen:
                continue
            seen.add(pair_key)

            # Convert cosine distance to similarity (Chroma returns distance, not similarity)
            semantic_sim = 1.0 - distance

            # Find BM25 score for this match
            match_para = para_by_id.get(match_id)
            if not match_para:
                continue

            match_idx = paragraphs.index(match_para)
            bm25_sim = bm25_normalized[match_idx]

            # Combine scores (weighted average)
            combined_score = (1 - bm25_weight) * semantic_sim + bm25_weight * bm25_sim

            if combined_score >= threshold:
                matches.append(
                    SimilarityMatch(
                        para_a=para,
                        para_b=match_para,
                        score=combined_score,
                    )
                )

    # Sort by score descending
    matches.sort(key=lambda m: m.score, reverse=True)

    return matches


# ── CLI ──────────────────────────────────────────────────────────────────────


@app.command()
def main(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Root directory to scan for markdown files.",
    ),
    threshold: float = typer.Option(
        0.9,
        "--threshold",
        "-t",
        help="Minimum similarity score (0-1) to report.",
    ),
    top_k: int = typer.Option(
        10,
        "--top-k",
        "-k",
        help="Number of nearest neighbors to consider per paragraph.",
    ),
    min_chars: int = typer.Option(
        50,
        "--min-chars",
        "-m",
        help="Minimum paragraph length in characters.",
    ),
    model: str = typer.Option(
        "all-MiniLM-L6-v2",
        "--model",
        help="Sentence transformer model name.",
    ),
    persist: Path = typer.Option(
        Path(".chroma"),
        "--persist",
        "-p",
        help="Directory for persistent Chroma database.",
    ),
    brief: bool = typer.Option(
        False,
        "--brief",
        "-b",
        help="Omit snippet previews in output.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress progress bars.",
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        "-x",
        help="Directory names to exclude (e.g. data personal).",
    ),
) -> None:
    """Find similar paragraphs across markdown files."""
    root = root.resolve()
    persist = persist.resolve() if not persist.is_absolute() else persist

    # Collect markdown files
    md_files = collect_markdown_files(root, exclude=exclude)
    typer.echo(f"Found {len(md_files)} markdown files", err=True)

    # Extract paragraphs
    all_paragraphs: list[Paragraph] = []
    if quiet:
        for md_file in md_files:
            paragraphs = extract_paragraphs(md_file, min_chars=min_chars)
            all_paragraphs.extend(paragraphs)
    else:
        with typer.progressbar(md_files, label="Extracting paragraphs") as progress:
            for md_file in progress:
                paragraphs = extract_paragraphs(md_file, min_chars=min_chars)
                all_paragraphs.extend(paragraphs)

    typer.echo(f"Extracted {len(all_paragraphs)} paragraphs", err=True)

    if not all_paragraphs:
        typer.echo("No paragraphs found to analyze.", err=True)
        return

    # Find similar pairs
    matches = find_similar_pairs(
        paragraphs=all_paragraphs,
        model_name=model,
        persist_dir=persist,
        threshold=threshold,
        top_k=top_k,
        quiet=quiet,
    )

    # Output results
    if not matches:
        typer.echo("No similar pairs found above threshold.", err=True)
        return

    typer.echo(f"\nFound {len(matches)} similar pairs:\n", err=True)
    for match in matches:
        typer.echo(match.format(brief=brief, root=root))


if __name__ == "__main__":
    app()
