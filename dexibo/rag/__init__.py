"""Lightweight fintech RAG (TF-IDF, no heavy ML deps)."""

from dexibo.rag.retriever import format_retrieved_context, retrieve

__all__ = ["retrieve", "format_retrieved_context"]
