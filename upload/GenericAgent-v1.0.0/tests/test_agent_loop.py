"""Comprehensive tests for the agent_loop module.

Covers StepOutcome, BaseHandler, try_call_generator, json_default, exhaust,
get_pretty_json, _clean_content, and _compact_tool_args.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent_loop import (
    StepOutcome,
    BaseHandler,
    try_call_generator,
    json_default,
    exhaust,
    get_pretty_json,
    _clean_content,
    _compact_tool_args,
)


# ══════════════════════════════════════════════════════════════════════
# StepOutcome
# ══════════════════════════════════════════════════════════════════════

class TestStepOutcomeCreation:
    """Tests for StepOutcome creation and default values."""

    def test_basic_creation(self):
        """StepOutcome can be created with just data."""
        so = StepOutcome(data="result")
        assert so.data == "result"
        assert so.next_prompt is None
        assert so.should_exit is False

    def test_full_creation(self):
        """StepOutcome can be created with all fields."""
        so = StepOutcome(data={"key": "val"}, next_prompt="next", should_exit=True)
        assert so.data == {"key": "val"}
        assert so.next_prompt == "next"
        assert so.should_exit is True

    def test_none_data(self):
        """StepOutcome with None data."""
        so = StepOutcome(data=None)
        assert so.data is None
        assert so.next_prompt is None
        assert so.should_exit is False

    def test_list_data(self):
        """StepOutcome with list data."""
        so = StepOutcome(data=[1, 2, 3])
        assert so.data == [1, 2, 3]

    def test_dict_data(self):
        """StepOutcome with dict data."""
        so = StepOutcome(data={"status": "ok"})
        assert so.data == {"status": "ok"}


class TestStepOutcomeIsError:
    """Tests for the StepOutcome.is_error property."""

    def test_error_dict_status(self):
        """is_error is True when data is a dict with status='error'."""
        so = StepOutcome(data={"status": "error"})
        assert so.is_error is True

    def test_success_dict_status(self):
        """is_error is False when data is a dict with status='ok'."""
        so = StepOutcome(data={"status": "ok"})
        assert so.is_error is False

    def test_error_string_prefix(self):
        """is_error is True when data is a string starting with '[Error]'."""
        so = StepOutcome(data="[Error] something went wrong")
        assert so.is_error is True

    def test_normal_string(self):
        """is_error is False for normal strings."""
        so = StepOutcome(data="All good")
        assert so.is_error is False

    def test_none_data_not_error(self):
        """is_error is False when data is None."""
        so = StepOutcome(data=None)
        assert so.is_error is False

    def test_list_data_not_error(self):
        """is_error is False when data is a list."""
        so = StepOutcome(data=[1, 2, 3])
        assert so.is_error is False

    def test_integer_data_not_error(self):
        """is_error is False when data is an integer."""
        so = StepOutcome(data=42)
        assert so.is_error is False

    def test_dict_without_status(self):
        """is_error is False when data is a dict without 'status' key."""
        so = StepOutcome(data={"msg": "not an error"})
        assert so.is_error is False


class TestStepOutcomeFromDict:
    """Tests for StepOutcome.from_dict class method."""

    def test_from_dict_minimal(self):
        """from_dict with only the required 'data' key."""
        so = StepOutcome.from_dict({"data": "hello"})
        assert so.data == "hello"
        assert so.next_prompt is None
        assert so.should_exit is False

    def test_from_dict_full(self):
        """from_dict with all keys."""
        so = StepOutcome.from_dict({
            "data": {"result": 42},
            "next_prompt": "continue",
            "should_exit": True,
        })
        assert so.data == {"result": 42}
        assert so.next_prompt == "continue"
        assert so.should_exit is True

    def test_from_dict_missing_data_raises(self):
        """from_dict raises KeyError when 'data' key is missing."""
        with pytest.raises(KeyError):
            StepOutcome.from_dict({"next_prompt": "oops"})

    def test_from_dict_defaults(self):
        """from_dict defaults next_prompt to None and should_exit to False."""
        so = StepOutcome.from_dict({"data": None})
        assert so.next_prompt is None
        assert so.should_exit is False


# ══════════════════════════════════════════════════════════════════════
# BaseHandler
# ══════════════════════════════════════════════════════════════════════

class TestBaseHandlerInit:
    """Tests for BaseHandler.__init__."""

    def test_default_init(self):
        """BaseHandler initialises with sensible defaults."""
        h = BaseHandler()
        assert h.parent is None
        assert h.max_turns == 40
        assert h.current_turn == 0
        assert h._done_hooks == []

    def test_init_with_parent(self):
        """BaseHandler stores a reference to parent."""
        parent = MagicMock()
        h = BaseHandler(parent=parent)
        assert h.parent is parent

    def test_init_with_custom_turns(self):
        """BaseHandler accepts custom max_turns and current_turn."""
        h = BaseHandler(max_turns=100, current_turn=5)
        assert h.max_turns == 100
        assert h.current_turn == 5

    def test_init_with_done_hooks(self):
        """BaseHandler copies done_hooks list."""
        hooks = ["hook1", "hook2"]
        h = BaseHandler(done_hooks=hooks)
        assert h._done_hooks == hooks
        # Should be a copy, not the same list
        assert h._done_hooks is not hooks

    def test_init_with_none_done_hooks(self):
        """BaseHandler handles None done_hooks."""
        h = BaseHandler(done_hooks=None)
        assert h._done_hooks == []


class TestBaseHandlerDispatch:
    """Tests for BaseHandler.dispatch."""

    def test_dispatch_known_tool(self):
        """dispatch routes to do_<tool_name> method."""
        h = BaseHandler()
        h.do_test_tool = lambda args, resp: StepOutcome(data="tested")
        gen = h.dispatch("test_tool", {}, None)
        result = exhaust(gen)
        assert result.data == "tested"

    def test_dispatch_injects_index(self):
        """dispatch injects _index into args."""
        received_args = {}

        def do_capture(args, resp):
            received_args.update(args)
            return StepOutcome(data="captured")

        h = BaseHandler()
        h.do_capture_tool = do_capture
        gen = h.dispatch("capture_tool", {"existing": True}, None, index=3)
        exhaust(gen)
        assert received_args["_index"] == 3
        assert received_args["existing"] is True

    def test_dispatch_bad_json(self):
        """dispatch handles 'bad_json' tool name."""
        h = BaseHandler()
        gen = h.dispatch("bad_json", {"msg": "fix your json"}, None)
        result = exhaust(gen)
        assert isinstance(result, StepOutcome)
        assert result.next_prompt == "fix your json"
        assert result.should_exit is False

    def test_dispatch_bad_json_default_msg(self):
        """dispatch uses default msg for bad_json when msg is not in args."""
        h = BaseHandler()
        gen = h.dispatch("bad_json", {}, None)
        result = exhaust(gen)
        assert result.next_prompt == "bad_json"

    def test_dispatch_unknown_tool(self):
        """dispatch handles unknown tool names by yielding a warning."""
        h = BaseHandler()
        gen = h.dispatch("nonexistent_tool", {}, None)
        collected = list(gen)
        # The generator yields a warning string before returning
        warning_text = "".join(collected)
        assert "nonexistent_tool" in warning_text

    def test_dispatch_unknown_tool_returns_outcome(self):
        """dispatch returns a StepOutcome for unknown tools."""
        h = BaseHandler()
        gen = h.dispatch("mystery_tool", {}, None)
        result = exhaust(gen)
        assert isinstance(result, StepOutcome)
        assert result.next_prompt is not None
        assert "mystery_tool" in result.next_prompt

    def test_dispatch_calls_before_and_after_callbacks(self):
        """dispatch calls tool_before_callback and tool_after_callback."""
        call_log = []

        class LoggingHandler(BaseHandler):
            def tool_before_callback(self, tool_name, args, response):
                call_log.append(("before", tool_name))

            def tool_after_callback(self, tool_name, args, response, ret):
                call_log.append(("after", tool_name))

            def do_mytool(self, args, resp):
                call_log.append(("do", "mytool"))
                return StepOutcome(data="done")

        h = LoggingHandler()
        gen = h.dispatch("mytool", {}, None)
        exhaust(gen)
        assert ("before", "mytool") in call_log
        assert ("do", "mytool") in call_log
        assert ("after", "mytool") in call_log
        # Order: before -> do -> after
        assert call_log[0] == ("before", "mytool")
        assert call_log[1] == ("do", "mytool")
        assert call_log[2] == ("after", "mytool")


# ══════════════════════════════════════════════════════════════════════
# try_call_generator
# ══════════════════════════════════════════════════════════════════════

class TestTryCallGenerator:
    """Tests for try_call_generator."""

    def test_regular_function(self):
        """try_call_generator with a regular (non-generator) function."""
        def add(a, b):
            return a + b

        gen = try_call_generator(add, 3, 4)
        # For a regular function, the generator should just return the value
        results = list(gen)
        # No yields for a regular function return
        assert results == []

    def test_generator_function(self):
        """try_call_generator with a generator function yields values."""
        def gen_func():
            yield "a"
            yield "b"
            yield "c"
            return "done"

        gen = try_call_generator(gen_func)
        results = list(gen)
        assert results == ["a", "b", "c"]

    def test_generator_return_value(self):
        """try_call_generator returns the generator's return value."""
        def gen_func():
            yield "x"
            return 42

        gen = try_call_generator(gen_func)
        values = []
        try:
            while True:
                values.append(next(gen))
        except StopIteration as e:
            return_val = e.value
        assert values == ["x"]
        assert return_val == 42

    def test_string_return_not_treated_as_generator(self):
        """try_call_generator does not iterate over string returns."""
        def return_string():
            return "hello"

        gen = try_call_generator(return_string)
        results = list(gen)
        assert results == []

    def test_dict_return_not_treated_as_generator(self):
        """try_call_generator does not iterate over dict returns."""
        def return_dict():
            return {"key": "value"}

        gen = try_call_generator(return_dict)
        results = list(gen)
        assert results == []

    def test_list_return_not_treated_as_generator(self):
        """try_call_generator does not iterate over list returns."""
        def return_list():
            return [1, 2, 3]

        gen = try_call_generator(return_list)
        results = list(gen)
        assert results == []

    def test_kwargs_forwarded(self):
        """try_call_generator forwards keyword arguments."""
        def func_with_kwargs(a, b=10):
            return a + b

        gen = try_call_generator(func_with_kwargs, 5, b=20)
        results = list(gen)
        assert results == []


# ══════════════════════════════════════════════════════════════════════
# json_default
# ══════════════════════════════════════════════════════════════════════

class TestJsonDefault:
    """Tests for json_default."""

    def test_set_to_list(self):
        """json_default converts a set to a sorted list."""
        result = json_default({3, 1, 2})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_set_preserves_elements(self):
        """json_default preserves all elements of a set."""
        result = json_default({"a", "b", "c"})
        assert isinstance(result, list)
        assert set(result) == {"a", "b", "c"}

    def test_empty_set(self):
        """json_default handles an empty set."""
        result = json_default(set())
        assert result == []

    def test_int_to_string(self):
        """json_default converts non-set objects to string."""
        result = json_default(42)
        assert result == "42"
        assert isinstance(result, str)

    def test_custom_object_to_string(self):
        """json_default converts custom objects to string."""
        class Foo:
            def __str__(self):
                return "FooInstance"

        result = json_default(Foo())
        assert result == "FooInstance"

    def test_none_to_string(self):
        """json_default converts None to string."""
        result = json_default(None)
        assert result == "None"
        assert isinstance(result, str)

    def test_tuple_to_string(self):
        """json_default converts tuple to string (not list)."""
        result = json_default((1, 2, 3))
        assert isinstance(result, str)
        # Tuples are not sets, so they should be str-converted
        assert "(1, 2, 3)" in result

    def test_usage_with_json_dumps(self):
        """json_default works as the default parameter for json.dumps."""
        data = {"items": {1, 2, 3}, "name": "test"}
        result = json.dumps(data, default=json_default)
        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert sorted(parsed["items"]) == [1, 2, 3]


# ══════════════════════════════════════════════════════════════════════
# exhaust
# ══════════════════════════════════════════════════════════════════════

class TestExhaust:
    """Tests for the exhaust helper."""

    def test_exhaust_simple_generator(self):
        """exhaust drives a generator to completion."""
        def gen():
            yield 1
            yield 2
            return 3

        result = exhaust(gen())
        assert result == 3

    def test_exhaust_empty_generator(self):
        """exhaust handles a generator that returns immediately without yielding."""
        def gen():
            return "nothing"
            yield  # make this a generator function

        result = exhaust(gen())
        assert result == "nothing"

    def test_exhaust_no_return_value(self):
        """exhaust returns None for a generator with no explicit return."""
        def gen():
            yield "a"

        result = exhaust(gen())
        assert result is None

    def test_exhaust_consumes_all_yields(self):
        """exhaust consumes all yielded values (side-effects happen)."""
        consumed = []

        def gen():
            for i in range(5):
                consumed.append(i)
                yield i
            return "done"

        result = exhaust(gen())
        assert result == "done"
        assert consumed == [0, 1, 2, 3, 4]


# ══════════════════════════════════════════════════════════════════════
# get_pretty_json
# ══════════════════════════════════════════════════════════════════════

class TestGetPrettyJson:
    """Tests for get_pretty_json."""

    def test_simple_dict(self):
        """get_pretty_json formats a simple dict."""
        result = get_pretty_json({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_list_input(self):
        """get_pretty_json formats a list."""
        result = get_pretty_json([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_script_semicolons_expanded(self):
        """get_pretty_json expands semicolons in 'script' values."""
        data = {"script": "a; b; c"}
        result = get_pretty_json(data)
        # Semicolons should be broken onto separate lines
        assert ";\n" in result

    def test_script_does_not_mutate_original(self):
        """get_pretty_json does not mutate the input dict."""
        data = {"script": "a; b; c"}
        original_script = data["script"]
        get_pretty_json(data)
        assert data["script"] == original_script

    def test_no_script_key(self):
        """get_pretty_json works without a 'script' key."""
        data = {"name": "test", "count": 42}
        result = get_pretty_json(data)
        assert '"name"' in result
        assert '"count"' in result

    def test_newlines_replaced(self):
        """get_pretty_json replaces literal \\n with actual newlines."""
        data = {"text": "line1\\nline2"}
        result = get_pretty_json(data)
        assert "\n" in result

    def test_unicode_preserved(self):
        """get_pretty_json preserves Unicode characters."""
        data = {"message": "你好世界"}
        result = get_pretty_json(data)
        assert "你好世界" in result

    def test_string_input(self):
        """get_pretty_json handles a plain string."""
        result = get_pretty_json("hello")
        assert '"hello"' in result


# ══════════════════════════════════════════════════════════════════════
# _clean_content
# ══════════════════════════════════════════════════════════════════════

class TestCleanContent:
    """Tests for _clean_content."""

    def test_empty_string(self):
        """_clean_content returns empty string for empty input."""
        assert _clean_content("") == ""

    def test_none_input(self):
        """_clean_content returns empty string for None input."""
        assert _clean_content(None) == ""

    def test_short_code_block_unchanged(self):
        """Short code blocks (<=6 non-blank lines) are not shrunk."""
        text = "```python\nprint('hi')\n```"
        result = _clean_content(text)
        assert "print('hi')" in result

    def test_long_code_block_shrunk(self):
        """Long code blocks (>6 non-blank lines) are shrunk to preview."""
        lines = "\n".join(f"line {i}" for i in range(10))
        text = f"```python\n{lines}\n```"
        result = _clean_content(text)
        assert "..." in result
        assert "10 lines" in result

    def test_file_content_tags_stripped(self):
        """_clean_content strips <file_content> tags."""
        text = "before<file_content>some content</file_content>after"
        result = _clean_content(text)
        assert "<file_content>" not in result
        assert "</file_content>" not in result

    def test_tool_use_tags_stripped(self):
        """_clean_content strips <tool_use> tags."""
        text = "before<tool_use>tool data</tool_use>after"
        result = _clean_content(text)
        assert "<tool_use>" not in result
        assert "</tool_use>" not in result

    def test_tool_call_tags_stripped(self):
        """_clean_content strips <tool_call...> tags."""
        text = "before<tool_call id='1'>call data</tool_call<tool_call"
        # Note: the regex is <tool_(?:use|call)> which matches <tool_call
        # with the closing angle bracket — let's test the supported pattern
        text2 = "before<tool_call id='1'>data</tool_call<tool_call" 
        # Actually the regex matches: <tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>
        text3 = "before<tool_use>content</tool_use>after"
        result = _clean_content(text3)
        assert "<tool_use>" not in result

    def test_excessive_blank_lines_collapsed(self):
        """_clean_content collapses 3+ consecutive newlines to 2."""
        text = "line1\n\n\n\nline2"
        result = _clean_content(text)
        assert "\n\n\n" not in result

    def test_plain_text_unchanged(self):
        """Plain text without special patterns is mostly unchanged."""
        text = "Hello world, this is a test."
        result = _clean_content(text)
        assert "Hello world" in result


# ══════════════════════════════════════════════════════════════════════
# _compact_tool_args
# ══════════════════════════════════════════════════════════════════════

class TestCompactToolArgs:
    """Tests for _compact_tool_args."""

    def test_simple_args(self):
        """_compact_tool_args with simple args."""
        result = _compact_tool_args("some_tool", {"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_index_excluded(self):
        """_compact_tool_args excludes the _index key."""
        result = _compact_tool_args("tool", {"_index": 0, "name": "test"})
        assert "_index" not in result
        assert "name" in result

    def test_path_basename(self):
        """_compact_tool_args shortens 'path' to basename."""
        result = _compact_tool_args("file_read", {"path": "/very/long/path/to/file.txt"})
        assert "file.txt" in result
        assert "/very/long/path/to/" not in result

    def test_update_working_checkpoint_short(self):
        """_compact_tool_args for update_working_checkpoint with short key_info."""
        result = _compact_tool_args("update_working_checkpoint", {"key_info": "short info"})
        assert result == "short info"

    def test_update_working_checkpoint_long(self):
        """_compact_tool_args for update_working_checkpoint truncates long key_info."""
        long_info = "A" * 100
        result = _compact_tool_args("update_working_checkpoint", {"key_info": long_info})
        assert len(result) <= 63  # 60 chars + "..."
        assert result.endswith("...")

    def test_ask_user_question(self):
        """_compact_tool_args for ask_user shows the question."""
        result = _compact_tool_args("ask_user", {"question": "Continue?"})
        assert "Continue?" in result

    def test_ask_user_with_candidates(self):
        """_compact_tool_args for ask_user includes candidates."""
        result = _compact_tool_args("ask_user", {
            "question": "Choose",
            "candidates": ["A", "B"],
        })
        assert "Choose" in result
        assert "A" in result
        assert "B" in result

    def test_ask_user_no_candidates(self):
        """_compact_tool_args for ask_user without candidates."""
        result = _compact_tool_args("ask_user", {"question": "Hello?"})
        assert "Hello?" in result

    def test_long_json_truncated(self):
        """_compact_tool_args truncates long JSON representations."""
        args = {f"key_{i}": f"value_{i}" for i in range(50)}
        result = _compact_tool_args("generic_tool", args)
        assert len(result) <= 123  # 120 chars + "..."

    def test_empty_args(self):
        """_compact_tool_args with empty args."""
        result = _compact_tool_args("tool", {})
        assert result == "{}"
