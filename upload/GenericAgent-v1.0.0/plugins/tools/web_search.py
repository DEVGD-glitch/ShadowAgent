"""plugins/tools/web_search.py — Web search tool for GenericAgent.

Provides a ``web_search`` tool that queries the web via multiple backends:
1. DuckDuckGo API (no key required, default)
2. SearXNG (self-hosted, optional)
3. Custom search API (configurable)

The tool returns structured results with titles, URLs, and snippets.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional
from urllib.parse import quote_plus

logger = logging.getLogger("plugins.tools.web_search")


def _search_duckduckgo(query: str, num_results: int = 8) -> list[dict]:
    """Search using DuckDuckGo Instant Answer API (no key required).

    Returns a list of result dicts with 'title', 'url', 'snippet' keys.
    """
    results = []
    try:
        import requests

        # DuckDuckGo HTML search
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Try the lite version for cleaner results
        url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            # Parse HTML results
            import re
            text = response.text

            # Extract result links and snippets
            link_pattern = r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
            snippet_pattern = r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>'

            links = re.findall(link_pattern, text, re.DOTALL)
            snippets = re.findall(snippet_pattern, text, re.DOTALL)

            for i, (link_url, link_title) in enumerate(links[:num_results]):
                # Clean HTML from title
                clean_title = re.sub(r'<[^>]+>', '', link_title).strip()
                clean_url = link_url.strip()

                # Skip ad/tracking URLs
                if any(skip in clean_url for skip in ["duckduckgo.com", "javascript:", "//ad."]):
                    continue

                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

                results.append({
                    "title": clean_title,
                    "url": clean_url,
                    "snippet": snippet[:300],
                })

    except ImportError:
        logger.warning("requests library not available for web search")
    except Exception as exc:
        logger.error("DuckDuckGo search failed: %s", exc)

    return results


def _search_searxng(query: str, num_results: int = 8, base_url: str = "") -> list[dict]:
    """Search using a SearXNG instance.

    Parameters
    ----------
    base_url : str
        SearXNG instance URL (e.g. ``"http://localhost:8080"``).
    """
    if not base_url:
        base_url = os.environ.get("GA_SEARXNG_URL", "")

    if not base_url:
        return []

    results = []
    try:
        import requests

        response = requests.get(
            f"{base_url}/search",
            params={"q": query, "format": "json", "limit": num_results},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            for item in data.get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300],
                })

    except Exception as exc:
        logger.error("SearXNG search failed: %s", exc)

    return results


def _search_custom_api(query: str, num_results: int = 8) -> list[dict]:
    """Search using a custom search API (e.g. SerpAPI, Google Custom Search).

    Configured via environment variables:
    - ``GA_SEARCH_API_KEY`` — API key
    - ``GA_SEARCH_API_URL`` — API endpoint
    - ``GA_SEARCH_ENGINE_ID`` — Search engine ID (for Google)
    """
    api_key = os.environ.get("GA_SEARCH_API_KEY", "")
    api_url = os.environ.get("GA_SEARCH_API_URL", "")

    if not api_key or not api_url:
        return []

    results = []
    try:
        import requests

        params = {
            "q": query,
            "num": num_results,
            "key": api_key,
        }

        engine_id = os.environ.get("GA_SEARCH_ENGINE_ID", "")
        if engine_id:
            params["cx"] = engine_id

        response = requests.get(api_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Handle Google Custom Search format
            for item in data.get("items", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", "")[:300],
                })

    except Exception as exc:
        logger.error("Custom API search failed: %s", exc)

    return results


def do_web_search(args: dict, response: Any) -> dict[str, Any]:
    """Search the web for information.

    Queries multiple search backends and returns structured results
    with titles, URLs, and snippets.  Useful for research, fact-checking,
    and finding up-to-date information.

    Args (from LLM):
        query: The search query string.
        num_results: Number of results to return (1-20, default 5).

    Returns:
        dict with status and results list.
    """
    query = args.get("query", "")
    if not query:
        return {"status": "error", "msg": "Query parameter is required"}

    num_results = min(max(args.get("num_results", 5), 1), 20)

    # Try backends in order of preference
    results = []

    # 1. SearXNG (if configured)
    results = _search_searxng(query, num_results)

    # 2. Custom API (if configured)
    if not results:
        results = _search_custom_api(query, num_results)

    # 3. DuckDuckGo (fallback, no key required)
    if not results:
        results = _search_duckduckgo(query, num_results)

    if not results:
        return {
            "status": "error",
            "msg": "No search results found. Check internet connection or configure GA_SEARXNG_URL.",
        }

    return {
        "status": "success",
        "query": query,
        "count": len(results),
        "results": results,
    }


# ── Register the tool ─────────────────────────────────────────────────────

try:
    from tools import register_tool

    register_tool(
        name="web_search",
        handler=do_web_search,
        description=(
            "Search the web for information. Returns a list of results with "
            "titles, URLs, and snippets. Use this to find current information, "
            "research topics, look up documentation, or fact-check claims."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific for better results.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-20).",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
        category="search",
        source="plugin",
    )
except ImportError:
    logger.debug("Tool registry not available, web_search not registered")
