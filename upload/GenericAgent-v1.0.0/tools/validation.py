"""tools/validation.py — Pydantic-based tool argument validation.

Validates LLM tool-call arguments against the registered JSON Schema
*before* dispatching to the handler.  This catches malformed arguments
early and provides clear error messages that help the LLM self-correct.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tools.validation")

# ══════════════════════════════════════════════════════════════════════════════
#  i18n-aware boolean string sets
#  Covers multiple languages so that LLM responses in any supported language
#  are correctly coerced to Python booleans.
# ══════════════════════════════════════════════════════════════════════════════

# Affirmative / truthy strings across supported languages
_TRUTHY_STRINGS: frozenset[str] = frozenset({
    # English
    "true", "yes", "y", "1",
    # French
    "oui", "vrai",
    # Chinese
    "是", "对", "真", "好的",
    # Spanish / German / other common LLM outputs
    "sí", "si", "ja", "да",
})

# Negative / falsy strings across supported languages
_FALSY_STRINGS: frozenset[str] = frozenset({
    # English
    "false", "no", "n", "0",
    # French
    "non", "faux",
    # Chinese
    "否", "错", "假",
    # Spanish / German / other common LLM outputs
    "nein", "нет",
})

# ══════════════════════════════════════════════════════════════════════════════
#  Lightweight JSON Schema validator (no pydantic dependency required)
# ══════════════════════════════════════════════════════════════════════════════

# We implement a lightweight validator to avoid forcing a pydantic dependency.
# If pydantic is available, we use it for richer validation.


def _has_pydantic() -> bool:
    try:
        import pydantic  # noqa: F401
        return True
    except ImportError:
        return False


def validate_tool_args(
    tool_name: str,
    args: dict[str, Any],
    schema: dict[str, Any],
) -> Tuple[dict[str, Any], List[str]]:
    """Validate tool arguments against a JSON Schema.

    If validation fails, the errors are returned as human-readable strings
    that can be fed back to the LLM so it can correct its output.

    Parameters
    ----------
    tool_name : str
        Name of the tool being called.
    args : dict
        The arguments from the LLM's tool call.
    schema : dict
        JSON Schema for the tool's parameters.

    Returns
    -------
    tuple[dict, list[str]]
        A tuple of (coerced_args, error_messages).  If ``error_messages``
        is empty, validation passed.  ``coerced_args`` may contain type-
        coerced values (e.g. ``"5"`` → ``5`` when the schema says integer).
    """
    errors: List[str] = []
    coerced: dict[str, Any] = dict(args)

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # ── Check required fields ───────────────────────────────────────────
    for field_name in required:
        if field_name not in coerced:
            errors.append(f"Missing required parameter '{field_name}'")

    # ── Validate each present field ─────────────────────────────────────
    for key, value in list(coerced.items()):
        prop_schema = properties.get(key)
        if prop_schema is None:
            # Extra field — allowed unless additionalProperties is false
            if schema.get("additionalProperties") is False:
                errors.append(
                    f"Unknown parameter '{key}'. "
                    f"Allowed: {', '.join(sorted(properties.keys()))}"
                )
            continue

        # Type coercion + validation
        expected_type = prop_schema.get("type")
        if expected_type:
            coerced_value, coercion_err = _coerce_type(key, value, expected_type, prop_schema)
            if coercion_err:
                errors.append(coercion_err)
            else:
                coerced[key] = coerced_value

        # Enum validation
        enum_values = prop_schema.get("enum")
        if enum_values is not None and key in coerced:
            if coerced[key] not in enum_values:
                errors.append(
                    f"Parameter '{key}' must be one of {enum_values}, "
                    f"got {json.dumps(coerced[key], ensure_ascii=False)}"
                )

        # String constraints
        if isinstance(coerced.get(key), str):
            s = coerced[key]
            min_len = prop_schema.get("minLength")
            if min_len is not None and len(s) < min_len:
                errors.append(f"Parameter '{key}' must be at least {min_len} characters")

            max_len = prop_schema.get("maxLength")
            if max_len is not None and len(s) > max_len:
                errors.append(f"Parameter '{key}' must be at most {max_len} characters")

            pattern = prop_schema.get("pattern")
            if pattern and not re.search(pattern, s):
                errors.append(f"Parameter '{key}' must match pattern /{pattern}/")

        # Number constraints
        if isinstance(coerced.get(key), (int, float)):
            n = coerced[key]
            minimum = prop_schema.get("minimum")
            if minimum is not None and n < minimum:
                errors.append(f"Parameter '{key}' must be >= {minimum}")

            maximum = prop_schema.get("maximum")
            if maximum is not None and n > maximum:
                errors.append(f"Parameter '{key}' must be <= {maximum}")

    return coerced, errors


def _coerce_type(
    key: str,
    value: Any,
    expected_type: str,
    prop_schema: dict,
) -> Tuple[Any, Optional[str]]:
    """Attempt to coerce a value to the expected JSON Schema type.

    Returns (coerced_value, error_message).  If coercion fails, the
    original value is returned along with an error message.
    """
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }

    # Handle array and object types
    if expected_type == "array":
        if isinstance(value, list):
            return value, None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed, None
            except json.JSONDecodeError:
                pass
        return value, f"Parameter '{key}' must be an array, got {type(value).__name__}"

    if expected_type == "object":
        if isinstance(value, dict):
            return value, None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed, None
            except json.JSONDecodeError:
                pass
        return value, f"Parameter '{key}' must be an object, got {type(value).__name__}"

    # Scalar types
    target_type = type_map.get(expected_type)
    if target_type is None:
        return value, None  # Unknown type, pass through

    # Already correct type
    if isinstance(value, target_type) and not (expected_type == "integer" and isinstance(value, bool)):
        return value, None

    # Attempt coercion from string
    if isinstance(value, str):
        try:
            if expected_type == "integer":
                return int(value), None
            elif expected_type == "number":
                return float(value), None
            elif expected_type == "boolean":
                lower_val = value.lower()
                if lower_val in _TRUTHY_STRINGS:
                    return True, None
                elif lower_val in _FALSY_STRINGS:
                    return False, None
        except (ValueError, TypeError):
            pass

    # Boolean coercion from int
    if expected_type == "boolean" and isinstance(value, int):
        return bool(value), None

    return value, (
        f"Parameter '{key}' must be {expected_type}, "
        f"got {type(value).__name__}: {json.dumps(value, ensure_ascii=False)[:80]}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Integration with agent_loop
# ══════════════════════════════════════════════════════════════════════════════


def validate_and_coerce(
    tool_name: str,
    args: dict[str, Any],
    tools_schemas: list[dict],
) -> Tuple[dict[str, Any], List[str]]:
    """Validate tool arguments against the matching schema from the tools list.

    This is the main entry point for the agent loop integration.  It finds
    the schema for the given tool name, validates the args, and returns
    coerced args plus any error messages.

    Parameters
    ----------
    tool_name : str
        The tool being called.
    args : dict
        Raw arguments from the LLM.
    tools_schemas : list[dict]
        The full tools schema list (OpenAI format).

    Returns
    -------
    tuple[dict, list[str]]
        (coerced_args, error_messages)
    """
    # Find the matching schema
    param_schema = None

    # TOOLS_SCHEMA can be either a list of OpenAI function schemas
    # or a dict with a different structure (the original format)
    if isinstance(tools_schemas, list):
        for ts in tools_schemas:
            if isinstance(ts, dict):
                func = ts.get("function", {})
                if func.get("name") == tool_name:
                    param_schema = func.get("parameters", {})
                    break
    elif isinstance(tools_schemas, dict):
        # Original format: {"tool_name": {"type": "function", "function": {...}}}
        tool_entry = tools_schemas.get(tool_name, {})
        if isinstance(tool_entry, dict):
            func = tool_entry.get("function", tool_entry)
            if isinstance(func, dict):
                param_schema = func.get("parameters", {})

    if param_schema is None:
        # No schema found — pass through without validation
        return args, []

    return validate_tool_args(tool_name, args, param_schema)
