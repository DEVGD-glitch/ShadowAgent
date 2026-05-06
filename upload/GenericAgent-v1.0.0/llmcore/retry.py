"""Retry with exponential backoff and jitter for LLM requests.

Provides :func:`_stream_with_retry` which wraps HTTP requests with
configurable retry logic and typed exception raising.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any, Generator

import requests

from .utils import (
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMStreamInterruptedError,
    logger,
)

if TYPE_CHECKING:
    from .sessions import BaseSession


def _stream_with_retry(
    sess: BaseSession,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    parse_fn: Any,
) -> Generator[str, None, list[dict[str, Any]]]:
    """Stream from the LLM with exponential backoff and jitter.

    Improvements over the original:
    - Exponential backoff: 1 s, 2 s, 4 s, 8 s, 16 s (capped at 30 s)
    - Random jitter (0-50 % of base delay) to avoid thundering-herd retries
    - Respects the ``Retry-After`` header when present
    - Raises typed LLM exceptions when max retries are exceeded

    Yields text chunks and returns the list of content blocks.
    """
    _RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504, 529}

    def _delay(resp: Any, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        base_delay = min(30.0, 1.0 * (2 ** attempt))
        jitter = random.uniform(0, 0.5 * base_delay)
        try:
            ra = float((resp.headers or {}).get("retry-after"))
        except (TypeError, ValueError):
            ra = None
        return max(0.5, ra if ra is not None else base_delay + jitter)

    for attempt in range(sess.max_retries + 1):
        streamed = False
        try:
            with requests.post(url, headers=headers, json=payload, stream=sess.stream,
                               timeout=(sess.connect_timeout, sess.read_timeout), proxies=sess.proxies, verify=sess.verify) as r:
                if r.status_code >= 400:
                    if r.status_code in _RETRYABLE and attempt < sess.max_retries:
                        d = _delay(r, attempt)
                        logger.warning("[LLM Retry] HTTP %d, retry in %.1fs (%d/%d)",
                                       r.status_code, d, attempt + 1, sess.max_retries + 1)
                        time.sleep(d); continue
                    try:
                        body = r.text.strip()[:500]
                    except Exception:
                        logger.debug("Failed to read response body for error reporting")
                        body = ""
                    err = f"!!!Error: HTTP {r.status_code}" + (f": {body}" if body else "")
                    # Raise typed exception for non-retryable HTTP errors
                    if r.status_code == 429:
                        raise LLMRateLimitError(err, details={"status_code": r.status_code, "body": body})
                    yield err
                    return [{"type": "text", "text": err}]
                gen = parse_fn(r)
                try:
                    while True:
                        streamed = True; yield next(gen)
                except StopIteration as e:
                    return e.value or []
        except (LLMRateLimitError, LLMError):
            raise  # Re-raise our typed exceptions
        except (requests.Timeout, requests.ConnectionError) as e:
            err = f"!!!Error: {type(e).__name__}"
            if attempt < sess.max_retries:
                d = _delay(None, attempt)
                logger.warning("[LLM Retry] %s, retry in %.1fs (%d/%d)",
                               type(e).__name__, d, attempt + 1, sess.max_retries + 1)
                # Don't yield the error during retries — it confuses users who
                # see a partial error message before the request eventually succeeds.
                time.sleep(d); continue
            # All retries exhausted -- raise typed exception
            raise LLMConnectionError(err, details={"error_type": type(e).__name__}) from e
        except Exception as e:
            err_msg = (f"Stream abnormally interrupted: {type(e).__name__}: {e}"
                       if streamed else f"!!!Error: {type(e).__name__}: {e}")
            err = f"\n\n[!!! {err_msg} !!!]" if streamed else f"!!!Error: {type(e).__name__}: {e}"
            logger.error("LLM stream error: %s", err_msg)
            if streamed:
                raise LLMStreamInterruptedError(err_msg, details={"partial": streamed}) from e
            raise LLMResponseError(err_msg, details={"error_type": type(e).__name__}) from e
    # Should not reach here, but as a safety net:
    err = "!!!Error: Max retries exceeded"
    yield err
    return [{"type": "text", "text": err}]
