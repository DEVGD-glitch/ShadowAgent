"""plugins/tools/skill_search_tool.py — Skill Search tool for GenericAgent.

Exposes the 105K+ external skill library as an agent tool, enabling the LLM
to search for existing skills that can be reused or adapted for current tasks.

The skill search engine connects to an external API hosted at
``http://www.fudankw.cn:58787`` (configurable via ``SKILL_SEARCH_API``
environment variable).  It supports environment-aware search that considers
the user's OS, shell, runtimes, and tools.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("plugins.tools.skill_search_tool")


def do_skill_search(args: dict, response: Any) -> dict[str, Any]:
    """Search the 105K+ skill library for reusable skills.

    Finds existing skills that match the current task or problem.  Skills
    are ranked by relevance, quality (clarity, completeness, actionability),
    and compatibility with the current environment.

    Args (from LLM):
        query: What kind of skill you're looking for.
        category: Optional category filter (e.g. "web", "data", "system", "automation").
        top_k: Number of results to return (1-20, default 5).

    Returns:
        dict with status, results, and formatted skill summaries.
    """
    query = args.get("query", "")
    if not query:
        return {"status": "error", "msg": "Query parameter is required"}

    top_k = min(max(args.get("top_k", 5), 1), 20)
    category = args.get("category")

    try:
        # Import from the skill_search package in memory/
        import sys
        import os

        # Add skill_search path if not already importable
        skill_search_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "memory", "skill_search",
        )
        if skill_search_dir not in sys.path:
            sys.path.insert(0, skill_search_dir)

        from skill_search import search, detect_environment, SkillSearchError

    except ImportError:
        return {
            "status": "error",
            "msg": "Skill search engine not available. The memory/skill_search/ package is required.",
        }

    try:
        env = detect_environment()
        results = search(query, env=env, category=category, top_k=top_k)
    except SkillSearchError as exc:
        return {
            "status": "error",
            "msg": f"Skill search API error: {exc}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "msg": f"Skill search failed: {exc}",
        }

    if not results:
        return {
            "status": "success",
            "query": query,
            "count": 0,
            "results": [],
            "message": "No matching skills found. Try a different query or category.",
        }

    formatted = []
    for r in results:
        skill = r.skill
        entry = {
            "name": skill.name or skill.key,
            "category": skill.category,
            "description": skill.description or skill.one_line_summary,
            "tags": skill.tags[:5] if skill.tags else [],
            "quality_score": round(skill.quality_score, 1),
            "relevance": round(r.relevance, 2),
            "final_score": round(r.final_score, 2),
            "os_compatible": skill.os if skill.os else "any",
            "runtimes": skill.runtimes[:3] if skill.runtimes else [],
            "safety": {
                "blast_radius": skill.blast_radius,
                "data_exposure": skill.data_exposure,
                "autonomous_safe": skill.autonomous_safe,
            },
        }
        if skill.github_url:
            entry["github_url"] = skill.github_url
        formatted.append(entry)

    # Build a concise text summary for the LLM
    summary_lines = [f"Found {len(formatted)} skills matching '{query}':\n"]
    for i, entry in enumerate(formatted, 1):
        summary_lines.append(
            f"{i}. **{entry['name']}** (score: {entry['final_score']})\n"
            f"   Category: {entry['category']} | Tags: {', '.join(entry['tags'])}\n"
            f"   {entry['description']}\n"
            f"   Safety: blast={entry['safety']['blast_radius']}, "
            f"data={entry['safety']['data_exposure']}, "
            f"auto_safe={entry['safety']['autonomous_safe']}"
        )
    summary = "\n".join(summary_lines)

    return {
        "status": "success",
        "query": query,
        "count": len(formatted),
        "results": formatted,
        "summary": summary,
    }


# ── Register tool ─────────────────────────────────────────────────────────

try:
    from tools import register_tool

    register_tool(
        name="skill_search",
        handler=do_skill_search,
        description=(
            "Search the 105K+ skill library for reusable skills that match "
            "the current task.  Finds existing skills ranked by relevance and "
            "quality, with environment compatibility checks.  Use this BEFORE "
            "attempting complex tasks from scratch — chances are someone has "
            "already solved it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What kind of skill you're looking for (e.g. 'send email', 'web scraping', 'stock analysis').",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: web, data, system, automation, communication, etc.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (1-20).",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
        category="knowledge",
        source="plugin",
    )

except ImportError:
    logger.debug("Tool registry not available, skill_search tool not registered")
