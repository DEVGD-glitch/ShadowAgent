"""plugins/tools/memory_search.py — Semantic memory search tool for GenericAgent.

Provides a ``memory_search`` tool that uses the RAG engine to search the
agent's accumulated knowledge with semantic similarity.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("plugins.tools.memory_search")

# Lazy RAG engine reference
_rag_engine = None


def _get_rag_engine():
    """Lazily initialize the RAG engine."""
    global _rag_engine
    if _rag_engine is not None:
        return _rag_engine

    try:
        from memory.vector import RAGEngine

        store_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "memory",
            "vector_store.json",
        )
        _rag_engine = RAGEngine(store_path=store_path)
        return _rag_engine
    except Exception as exc:
        logger.error("Failed to initialize RAG engine: %s", exc)
        return None


def do_memory_search(args: dict, response: Any) -> dict[str, Any]:
    """Search the agent's memory using semantic similarity.

    Uses vector embeddings to find relevant information from past
    conversations, SOPs, and indexed documents.  More powerful than
    keyword search because it understands meaning and context.

    Args (from LLM):
        query: The search query — what you're looking for.
        top_k: Number of results (1-10, default 3).
        category: Optional category filter ("sop", "conversation", "doc").

    Returns:
        dict with status, results, and context string.
    """
    query = args.get("query", "")
    if not query:
        return {"status": "error", "msg": "Query parameter is required"}

    top_k = min(max(args.get("top_k", 3), 1), 10)
    category = args.get("category")

    engine = _get_rag_engine()
    if engine is None:
        return {
            "status": "error",
            "msg": "RAG engine not available. Ensure memory/vector package is installed.",
        }

    try:
        results = engine.search(query, top_k=top_k, category=category)
    except Exception as exc:
        return {"status": "error", "msg": f"Search failed: {exc}"}

    if not results:
        return {
            "status": "success",
            "query": query,
            "count": 0,
            "results": [],
            "context": "",
        }

    formatted = []
    for doc, score in results:
        formatted.append({
            "text": doc.text[:500],
            "score": round(score, 3),
            "source": doc.metadata.get("source", ""),
            "category": doc.metadata.get("category", ""),
        })

    # Also build a context string for direct injection
    context = engine.build_context(query, top_k=top_k, category=category)

    return {
        "status": "success",
        "query": query,
        "count": len(formatted),
        "results": formatted,
        "context": context[:2000] if context else "",
    }


def do_memory_index(args: dict, response: Any) -> dict[str, Any]:
    """Index new content into the agent's semantic memory.

    Adds text or file content to the vector store for future semantic
    search.  Use this to build up the agent's knowledge base.

    Args (from LLM):
        text: Text content to index (use this OR file_path, not both).
        file_path: Path to a file to index (use this OR text, not both).
        category: Category for the content ("doc", "sop", "conversation", "general").
        source: Source identifier (e.g. "user_notes", "documentation").

    Returns:
        dict with status and number of chunks indexed.
    """
    text = args.get("text", "")
    file_path = args.get("file_path", "")
    category = args.get("category", "general")
    source = args.get("source", "user")

    if not text and not file_path:
        return {"status": "error", "msg": "Either 'text' or 'file_path' must be provided"}

    engine = _get_rag_engine()
    if engine is None:
        return {"status": "error", "msg": "RAG engine not available"}

    try:
        if file_path:
            chunks = engine.index_file(file_path, category=category)
        else:
            chunks = engine.index_text(text, source=source, category=category)

        # Auto-save after indexing
        engine.save()

        return {
            "status": "success",
            "chunks_indexed": chunks,
            "category": category,
        }
    except Exception as exc:
        return {"status": "error", "msg": f"Indexing failed: {exc}"}


# ── Register tools ────────────────────────────────────────────────────────

try:
    from tools import register_tool

    register_tool(
        name="memory_search",
        handler=do_memory_search,
        description=(
            "Search the agent's accumulated memory using semantic similarity. "
            "Finds relevant information from past conversations, SOPs, and "
            "indexed documents. Understands meaning, not just keywords."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (1-10).",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: sop, conversation, doc, general.",
                },
            },
            "required": ["query"],
        },
        category="memory",
        source="plugin",
    )

    register_tool(
        name="memory_index",
        handler=do_memory_index,
        description=(
            "Index new content into the agent's semantic memory for future "
            "search. Add text, files, or documents to build the knowledge base."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text content to index.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to a file to index.",
                },
                "category": {
                    "type": "string",
                    "description": "Category: doc, sop, conversation, general.",
                    "default": "general",
                },
                "source": {
                    "type": "string",
                    "description": "Source identifier.",
                    "default": "user",
                },
            },
        },
        category="memory",
        source="plugin",
    )

except ImportError:
    logger.debug("Tool registry not available, memory tools not registered")
