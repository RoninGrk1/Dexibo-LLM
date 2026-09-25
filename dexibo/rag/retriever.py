"""Pure-Python TF-IDF retrieval over knowledge/ + market_knowledge concepts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dexibo.config import PROJECT_ROOT
from dexibo.tools.market_knowledge import CONCEPTS

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.I)
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "as",
        "at",
        "by",
        "with",
        "from",
        "that",
        "this",
        "it",
        "its",
        "not",
        "can",
        "may",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "if",
        "than",
        "into",
        "over",
        "also",
        "such",
        "when",
        "what",
        "how",
        "why",
        "which",
        "will",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "been",
        "was",
        "were",
        "but",
        "about",
        "only",
        "more",
        "most",
        "other",
        "some",
        "any",
        "all",
        "no",
        "nor",
        "so",
        "up",
        "out",
        "per",
    }
)


@dataclass(frozen=True)
class Chunk:
    """A retrievable text chunk."""

    doc_id: str
    title: str
    text: str
    source: str  # "knowledge" | "concept"


def tokenise(text: str) -> list[str]:
    """Lowercase alphanumeric tokens; split hyphens; keep tickers/numbers."""
    raw = (text or "").lower()
    # Split hyphenated compounds so "open-banking" → open, banking
    raw = raw.replace("-", " ").replace("/", " ")
    toks = [t for t in _TOKEN_RE.findall(raw)]
    out: list[str] = []
    for t in toks:
        if len(t) <= 1:
            continue
        if t in _STOP:
            continue
        out.append(t)
    return out


def _bigrams(tokens: list[str]) -> list[str]:
    return [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


def _knowledge_dir() -> Path:
    return PROJECT_ROOT / "knowledge"


def _load_knowledge_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    kdir = _knowledge_dir()
    if not kdir.is_dir():
        return chunks
    for path in sorted(kdir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = path.stem.replace("_", " ").title()
        for line in raw.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        # Split on ## headings into sub-chunks; keep whole doc as one if short
        parts = re.split(r"\n(?=## )", raw)
        if len(parts) <= 1 or len(raw) < 800:
            chunks.append(
                Chunk(
                    doc_id=path.stem,
                    title=title,
                    text=raw.strip(),
                    source="knowledge",
                )
            )
        else:
            for i, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue
                sub_title = title
                m = re.match(r"##\s+(.+)", part)
                if m:
                    sub_title = f"{title} — {m.group(1).strip()}"
                chunks.append(
                    Chunk(
                        doc_id=f"{path.stem}#{i}",
                        title=sub_title,
                        text=part,
                        source="knowledge",
                    )
                )
    return chunks


def _load_concept_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for concept in CONCEPTS:
        aliases = ", ".join(concept.get("aliases", []))
        text = (
            f"{concept['title']}\n"
            f"Aliases: {aliases}\n\n"
            f"{concept['summary']}"
        )
        chunks.append(
            Chunk(
                doc_id=f"concept:{concept['id']}",
                title=concept["title"],
                text=text,
                source="concept",
            )
        )
    return chunks


@lru_cache(maxsize=1)
def _corpus() -> tuple[list[Chunk], list[dict[str, float]], dict[str, float]]:
    """Return chunks, per-doc tf-idf vectors, and idf map."""
    chunks = _load_knowledge_chunks() + _load_concept_chunks()
    docs_tokens = [tokenise(c.text) for c in chunks]
    n = len(docs_tokens) or 1
    df: dict[str, int] = {}
    for toks in docs_tokens:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1
    idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}

    vectors: list[dict[str, float]] = []
    for toks in docs_tokens:
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        length = len(toks) or 1
        vec = {t: (cnt / length) * idf.get(t, 0.0) for t, cnt in tf.items()}
        vectors.append(vec)
    return chunks, vectors, idf


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # iterate smaller
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Return top-k scored chunks for *query* (TF-IDF cosine).

    Each item: {doc_id, title, text, source, score}.
    """
    q = (query or "").strip()
    if not q or k < 1:
        return []

    chunks, vectors, idf = _corpus()
    if not chunks:
        return []

    q_toks = tokenise(q)
    if not q_toks:
        return []

    tf: dict[str, int] = {}
    for t in q_toks:
        tf[t] = tf.get(t, 0) + 1
    qlen = len(q_toks)
    qvec = {t: (cnt / qlen) * idf.get(t, 0.0) for t, cnt in tf.items()}

    q_set = set(q_toks)
    q_bis = set(_bigrams(q_toks))

    scored: list[tuple[float, int]] = []
    for i, vec in enumerate(vectors):
        score = _cosine(qvec, vec)
        # Stronger title boost for overlapping tokens
        title_toks = set(tokenise(chunks[i].title))
        overlap = title_toks & q_set
        if overlap:
            score += 0.12 * len(overlap)
        # Bigram bonus against title + body tokens
        body_bis = set(_bigrams(tokenise(chunks[i].text[:1200])))
        title_bis = set(_bigrams(tokenise(chunks[i].title)))
        bi_hits = q_bis & (body_bis | title_bis)
        if bi_hits:
            score += 0.08 * len(bi_hits)
        # Tiny source preference for curated knowledge docs
        if chunks[i].source == "knowledge" and score > 0:
            score += 0.01
        if score > 0:
            scored.append((score, i))

    scored.sort(key=lambda x: (-x[0], chunks[x[1]].doc_id))
    out: list[dict[str, Any]] = []
    for score, i in scored[:k]:
        c = chunks[i]
        out.append(
            {
                "doc_id": c.doc_id,
                "title": c.title,
                "text": c.text,
                "source": c.source,
                "score": round(float(score), 6),
            }
        )
    return out


def format_retrieved_context(chunks: list[dict[str, Any]]) -> str:
    """Format chunks as a [Retrieved context] block for the model."""
    if not chunks:
        return ""
    parts = ["[Retrieved context]"]
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"### ({i}) {c['title']} [{c['source']}:{c['doc_id']}] "
            f"(score={c['score']})\n{c['text']}"
        )
    parts.append(
        "[/Retrieved context]\n"
        "Use the retrieved context to ground educational answers. "
        "Do not invent facts beyond it when uncertain."
    )
    return "\n\n".join(parts)


def clear_corpus_cache() -> None:
    """Reset cached corpus (useful after editing knowledge files)."""
    _corpus.cache_clear()
