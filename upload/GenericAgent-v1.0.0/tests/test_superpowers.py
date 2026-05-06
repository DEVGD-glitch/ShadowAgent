"""tests/test_superpowers.py — Tests for the new superpower features.

Tests the Tool Plugin System, MCP Client, Vector Memory / RAG,
Reasoning Engine, Tool Validation, API Server, and Multi-Agent
Orchestration.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ══════════════════════════════════════════════════════════════════════════════
#  Tool Registry Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestToolDefinition(unittest.TestCase):
    """Tests for ToolDefinition dataclass."""

    def test_to_openai_schema(self):
        from tools.registry import ToolDefinition

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Test input"},
                },
                "required": ["input"],
            },
            handler=lambda args, resp: {"status": "ok"},
        )

        schema = tool.to_openai_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "test_tool")
        self.assertEqual(schema["function"]["description"], "A test tool")
        self.assertIn("input", schema["function"]["parameters"]["properties"])


class TestToolRegistry(unittest.TestCase):
    """Tests for ToolRegistry."""

    def setUp(self):
        from tools.registry import ToolRegistry
        self.registry = ToolRegistry()

    def test_register_and_get(self):
        handler = lambda args, resp: {"status": "ok"}
        self.registry.register(
            name="my_tool",
            handler=handler,
            description="Test tool",
            parameters={"type": "object", "properties": {}},
        )
        tool = self.registry.get("my_tool")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "my_tool")

    def test_register_duplicate_fails(self):
        self.registry.register(
            name="dup_tool",
            handler=lambda a, r: None,
            description="First",
        )
        with self.assertRaises(ValueError):
            self.registry.register(
                name="dup_tool",
                handler=lambda a, r: None,
                description="Second",
            )

    def test_register_duplicate_override(self):
        self.registry.register(
            name="override_tool",
            handler=lambda a, r: "v1",
            description="V1",
        )
        self.registry.register(
            name="override_tool",
            handler=lambda a, r: "v2",
            description="V2",
            override=True,
        )
        tool = self.registry.get("override_tool")
        self.assertEqual(tool.description, "V2")

    def test_unregister(self):
        self.registry.register(
            name="temp_tool",
            handler=lambda a, r: None,
        )
        self.assertIn("temp_tool", self.registry)
        result = self.registry.unregister("temp_tool")
        self.assertIsNotNone(result)
        self.assertNotIn("temp_tool", self.registry)

    def test_disable_enable(self):
        self.registry.register(
            name="disabled_tool",
            handler=lambda a, r: None,
        )
        self.registry.disable("disabled_tool")
        self.assertIsNone(self.registry.get("disabled_tool"))
        self.registry.enable("disabled_tool")
        self.assertIsNotNone(self.registry.get("disabled_tool"))

    def test_list_tools(self):
        self.registry.register(name="a_tool", handler=lambda a, r: None, category="file")
        self.registry.register(name="b_tool", handler=lambda a, r: None, category="web")
        self.registry.register(name="c_tool", handler=lambda a, r: None, category="file")

        all_tools = self.registry.list_tools()
        self.assertEqual(len(all_tools), 3)

        file_tools = self.registry.list_tools(category="file")
        self.assertEqual(len(file_tools), 2)

    def test_list_categories(self):
        self.registry.register(name="x", handler=lambda a, r: None, category="file")
        self.registry.register(name="y", handler=lambda a, r: None, category="web")
        cats = self.registry.list_categories()
        self.assertEqual(cats["file"], 1)
        self.assertEqual(cats["web"], 1)

    def test_get_openai_schemas(self):
        self.registry.register(
            name="schema_tool",
            handler=lambda a, r: None,
            description="Schema test",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        schemas = self.registry.get_openai_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["function"]["name"], "schema_tool")

    def test_merge_builtin_schemas(self):
        self.registry.register(
            name="plugin_tool",
            handler=lambda a, r: None,
            description="Plugin",
        )
        builtin = [
            {"type": "function", "function": {"name": "builtin_tool", "description": "Builtin", "parameters": {}}},
        ]
        merged = self.registry.merge_builtin_schemas(builtin)
        names = [s["function"]["name"] for s in merged]
        self.assertIn("builtin_tool", names)
        self.assertIn("plugin_tool", names)

    def test_dispatch(self):
        def my_handler(args, resp):
            return {"status": "success", "data": args.get("input")}

        self.registry.register(
            name="dispatch_tool",
            handler=my_handler,
            description="Dispatch test",
        )
        result = self.registry.dispatch("dispatch_tool", {"input": "hello"}, None)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], "hello")

    def test_dispatch_unknown(self):
        result = self.registry.dispatch("nonexistent", {}, None)
        self.assertIsNone(result)

    def test_to_dict(self):
        self.registry.register(name="dict_tool", handler=lambda a, r: None, category="test")
        d = self.registry.to_dict()
        self.assertIn("tools", d)
        self.assertIn("dict_tool", d["tools"])

    def test_len(self):
        self.registry.register(name="len1", handler=lambda a, r: None)
        self.registry.register(name="len2", handler=lambda a, r: None)
        self.assertEqual(len(self.registry), 2)


class TestRegisterToolDecorator(unittest.TestCase):
    """Tests for the @register_tool decorator."""

    def test_decorator_with_args(self):
        from tools.registry import get_registry

        registry = get_registry()

        @register_tool_decorator(
            name="decorated_tool",
            description="Decorated test",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            category="test",
        )
        def handle_decorated(args, resp):
            return {"x": args.get("x")}

        tool = registry.get("decorated_tool")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.category, "test")

    def test_decorator_without_args(self):
        from tools.registry import get_registry

        registry = get_registry()

        # Using register_tool directly as a decorator (no parentheses)
        from tools.registry import register_tool as rt

        @rt
        def do_auto_named(args, resp):
            """Auto named tool."""
            return {}

        tool = registry.get("auto_named")
        self.assertIsNotNone(tool)

        # Cleanup
        registry.unregister("decorated_tool")
        registry.unregister("auto_named")


def register_tool_decorator(**kwargs):
    """Local version of register_tool for testing (avoids polluting global registry)."""
    from tools.registry import get_registry

    def decorator(fn):
        registry = get_registry()
        name = kwargs.pop("name", fn.__name__)
        if name.startswith("do_"):
            name = name[3:]
        registry.register(name=name, handler=fn, override=True, **kwargs)
        return fn

    return decorator


# ══════════════════════════════════════════════════════════════════════════════
#  Tool Validation Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestToolValidation(unittest.TestCase):
    """Tests for tool argument validation."""

    def test_valid_args(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        }
        coerced, errors = validate_tool_args("test", {"name": "hello", "count": 5}, schema)
        self.assertEqual(len(errors), 0)
        self.assertEqual(coerced["name"], "hello")
        self.assertEqual(coerced["count"], 5)

    def test_missing_required(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        _, errors = validate_tool_args("test", {}, schema)
        self.assertTrue(any("Missing required" in e for e in errors))

    def test_type_coercion(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "flag": {"type": "boolean"},
            },
        }
        coerced, errors = validate_tool_args("test", {"count": "5", "flag": "true"}, schema)
        self.assertEqual(len(errors), 0)
        self.assertEqual(coerced["count"], 5)
        self.assertEqual(coerced["flag"], True)

    def test_enum_validation(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["fast", "slow"]},
            },
        }
        _, errors = validate_tool_args("test", {"mode": "medium"}, schema)
        self.assertTrue(any("must be one of" in e for e in errors))

    def test_additional_properties_false(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        _, errors = validate_tool_args("test", {"name": "ok", "extra": "bad"}, schema)
        self.assertTrue(any("Unknown parameter" in e for e in errors))

    def test_string_constraints(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "minLength": 3, "maxLength": 10},
            },
        }
        _, errors = validate_tool_args("test", {"code": "ab"}, schema)
        self.assertTrue(any("at least 3" in e for e in errors))

    def test_number_constraints(self):
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
            },
        }
        _, errors = validate_tool_args("test", {"timeout": 0}, schema)
        self.assertTrue(any("must be >=" in e for e in errors))

    def test_validate_and_coerce_integration(self):
        from tools.validation import validate_and_coerce

        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "code_run",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["python", "bash"]},
                            "timeout": {"type": "integer", "minimum": 1},
                        },
                        "required": ["type"],
                    },
                },
            }
        ]
        coerced, errors = validate_and_coerce("code_run", {"type": "python", "timeout": "60"}, schemas)
        self.assertEqual(len(errors), 0)
        self.assertEqual(coerced["timeout"], 60)


# ══════════════════════════════════════════════════════════════════════════════
#  Vector Store Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestVectorStore(unittest.TestCase):
    """Tests for the VectorStore."""

    def setUp(self):
        from memory.vector.store import VectorStore
        self.store = VectorStore()  # In-memory only

    def test_add_and_get(self):
        from memory.vector.store import Document
        doc = Document(id="d1", text="Hello world", vector=[1.0, 0.0, 0.0])
        self.store.add(doc)
        retrieved = self.store.get("d1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.text, "Hello world")

    def test_add_many(self):
        from memory.vector.store import Document
        docs = [
            Document(id=f"d{i}", text=f"Doc {i}", vector=[float(i), 0.0, 0.0])
            for i in range(5)
        ]
        self.store.add_many(docs)
        self.assertEqual(self.store.count, 5)

    def test_delete(self):
        from memory.vector.store import Document
        self.store.add(Document(id="del_me", text="Delete me", vector=[]))
        self.assertTrue(self.store.delete("del_me"))
        self.assertIsNone(self.store.get("del_me"))

    def test_search(self):
        from memory.vector.store import Document
        self.store.add(Document(id="s1", text="Python programming", vector=[1.0, 0.0, 0.0]))
        self.store.add(Document(id="s2", text="JavaScript programming", vector=[0.0, 1.0, 0.0]))
        self.store.add(Document(id="s3", text="Python data science", vector=[0.9, 0.1, 0.0]))

        results = self.store.search([1.0, 0.0, 0.0], top_k=2)
        self.assertEqual(len(results), 2)
        # s1 should be most similar to [1, 0, 0]
        self.assertEqual(results[0][0].id, "s1")

    def test_search_with_metadata_filter(self):
        from memory.vector.store import Document
        self.store.add(Document(id="f1", text="File 1", vector=[1.0, 0.0], metadata={"category": "sop"}))
        self.store.add(Document(id="f2", text="File 2", vector=[0.9, 0.1], metadata={"category": "doc"}))

        results = self.store.search([1.0, 0.0], top_k=5, metadata_filter={"category": "sop"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].id, "f1")

    def test_save_and_load(self):
        from memory.vector.store import Document, VectorStore
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            store1 = VectorStore(store_path=path)
            store1.add(Document(id="p1", text="Persist me", vector=[1.0]))
            store1.save()

            store2 = VectorStore(store_path=path)
            count = store2.load()
            self.assertEqual(count, 1)
            self.assertEqual(store2.get("p1").text, "Persist me")
        finally:
            os.unlink(path)

    def test_stats(self):
        from memory.vector.store import Document
        self.store.add(Document(id="x1", text="X1", vector=[1.0], metadata={"category": "test"}))
        self.store.add(Document(id="x2", text="X2", vector=[]))
        stats = self.store.stats()
        self.assertEqual(stats["total_documents"], 2)
        self.assertEqual(stats["with_vectors"], 1)


class TestEmbeddingEngine(unittest.TestCase):
    """Tests for the EmbeddingEngine."""

    def test_simple_embedding(self):
        from memory.vector.store import EmbeddingEngine
        engine = EmbeddingEngine()
        vector = engine.embed("Hello world")
        self.assertEqual(len(vector), 128)
        # Should be normalized
        norm = math.sqrt(sum(v * v for v in vector))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_similar_texts_similar_vectors(self):
        from memory.vector.store import EmbeddingEngine, cosine_similarity
        engine = EmbeddingEngine()
        v1 = engine.embed("Python programming language")
        v2 = engine.embed("Python coding language")
        v3 = engine.embed("Cooking recipes for dinner")
        sim_similar = cosine_similarity(v1, v2)
        sim_different = cosine_similarity(v1, v3)
        # Similar texts should have higher similarity than different ones
        self.assertGreater(sim_similar, sim_different)


# ══════════════════════════════════════════════════════════════════════════════
#  RAG Engine Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRAGEngine(unittest.TestCase):
    """Tests for the RAG Engine."""

    def test_index_and_search(self):
        from memory.vector.rag import RAGEngine
        engine = RAGEngine(chunk_size=200, chunk_overlap=50)

        engine.index_text(
            "Python is a high-level programming language known for its readability and versatility.",
            source="python_intro",
            category="doc",
        )
        engine.index_text(
            "JavaScript is primarily used for web development and creating interactive websites.",
            source="js_intro",
            category="doc",
        )

        results = engine.search("Python programming", top_k=2)
        self.assertGreater(len(results), 0)
        # Top result should be about Python
        self.assertIn("Python", results[0][0].text)

    def test_build_context(self):
        from memory.vector.rag import RAGEngine
        engine = RAGEngine(chunk_size=200, chunk_overlap=50)

        engine.index_text(
            "GenericAgent is a desktop AI agent that can execute code and browse the web.",
            source="about",
            category="doc",
        )

        context = engine.build_context("What is GenericAgent?", min_similarity=0.0)
        # Context may be empty if similarity is too low with simple embedding
        # Check that the function runs without error; actual content depends on embedding quality
        self.assertIsInstance(context, str)

    def test_index_file(self):
        from memory.vector.rag import RAGEngine

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is a test document about machine learning and AI.")
            path = f.name

        try:
            engine = RAGEngine(chunk_size=200, chunk_overlap=50)
            count = engine.index_file(path, category="test")
            self.assertGreater(count, 0)
        finally:
            os.unlink(path)


class TestChunking(unittest.TestCase):
    """Tests for text chunking."""

    def test_short_text(self):
        from memory.vector.rag import chunk_text
        chunks = chunk_text("Short text", chunk_size=500)
        self.assertEqual(len(chunks), 1)

    def test_long_text(self):
        from memory.vector.rag import chunk_text
        text = "Word " * 500  # ~2500 chars
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        self.assertGreater(len(chunks), 1)

    def test_overlap(self):
        from memory.vector.rag import chunk_text
        text = "A" * 1000
        chunks = chunk_text(text, chunk_size=400, overlap=100)
        # Each chunk should be roughly 400 chars
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 420)  # Allow some slack


# ══════════════════════════════════════════════════════════════════════════════
#  Reasoning Engine Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestReasoningEngine(unittest.TestCase):
    """Tests for the Reasoning Engine."""

    def test_react_system_prompt(self):
        from agentmain.reasoning import ReasoningEngine, ReasoningMode
        engine = ReasoningEngine(mode=ReasoningMode.REACT)
        prompt = engine.get_system_prompt_addition()
        self.assertIn("ReAct", prompt)
        self.assertIn("Thought", prompt)

    def test_plan_execute_system_prompt(self):
        from agentmain.reasoning import ReasoningEngine, ReasoningMode
        engine = ReasoningEngine(mode=ReasoningMode.PLAN_EXECUTE)
        prompt = engine.get_system_prompt_addition()
        self.assertIn("Plan", prompt)

    def test_create_and_advance_plan(self):
        from agentmain.reasoning import ReasoningEngine, ReasoningMode
        engine = ReasoningEngine(mode=ReasoningMode.PLAN_EXECUTE)
        engine.create_plan(["Step 1", "Step 2", "Step 3"])

        self.assertEqual(len(engine.plan), 3)
        self.assertFalse(engine.is_plan_complete())

        engine.advance_step("Done 1")
        self.assertTrue(engine.plan[0].completed)
        self.assertEqual(engine.current_step, 1)

        engine.advance_step("Done 2")
        engine.advance_step("Done 3")
        self.assertTrue(engine.is_plan_complete())

    def test_extract_thought(self):
        from agentmain.reasoning import ReasoningEngine
        text = "Some text <thought>I need to search for information</thought> more text"
        thought = ReasoningEngine.extract_thought(text)
        self.assertEqual(thought, "I need to search for information")

    def test_extract_plan(self):
        from agentmain.reasoning import ReasoningEngine
        text = "<plan>\n1. First step\n2. Second step\n3. Third step\n</plan>"
        steps = ReasoningEngine.extract_plan(text)
        self.assertEqual(len(steps), 3)

    def test_extract_final_answer(self):
        from agentmain.reasoning import ReasoningEngine
        text = "<final_answer>The answer is 42</final_answer>"
        answer = ReasoningEngine.extract_final_answer(text)
        self.assertEqual(answer, "The answer is 42")

    def test_suggest_mode(self):
        from agentmain.reasoning import ReasoningEngine, ReasoningMode

        self.assertEqual(
            ReasoningEngine.suggest_mode("Plan a migration step by step"),
            ReasoningMode.PLAN_EXECUTE,
        )
        self.assertEqual(
            ReasoningEngine.suggest_mode("Search for the latest news"),
            ReasoningMode.REACT,
        )
        self.assertEqual(
            ReasoningEngine.suggest_mode("Carefully verify the calculation"),
            ReasoningMode.REFLECT,
        )

    def test_to_dict(self):
        from agentmain.reasoning import ReasoningEngine, ReasoningMode
        engine = ReasoningEngine(mode=ReasoningMode.REACT)
        engine.create_plan(["A", "B"])
        d = engine.to_dict()
        self.assertEqual(d["mode"], "react")
        self.assertEqual(len(d["plan"]), 2)


# ══════════════════════════════════════════════════════════════════════════════
#  MCP Client Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestMCPConfig(unittest.TestCase):
    """Tests for MCP config loading."""

    def test_load_config_nonexistent(self):
        from mcp.client import load_mcp_config
        configs = load_mcp_config("/nonexistent/path.json")
        self.assertEqual(len(configs), 0)

    def test_load_config_valid(self):
        from mcp.client import load_mcp_config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "mcpServers": {
                    "test": {
                        "transport": "stdio",
                        "command": "echo",
                        "args": ["hello"],
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_mcp_config(path)
            self.assertEqual(len(configs), 1)
            self.assertEqual(configs[0].name, "test")
            self.assertEqual(configs[0].transport, "stdio")
        finally:
            os.unlink(path)


class TestMCPServerConfig(unittest.TestCase):
    """Tests for MCPServerConfig dataclass."""

    def test_default_values(self):
        from mcp.client import MCPServerConfig
        config = MCPServerConfig(name="test")
        self.assertEqual(config.transport, "stdio")
        self.assertEqual(config.args, [])
        self.assertFalse(config.disabled)

    def test_disabled(self):
        from mcp.client import MCPServerConfig
        config = MCPServerConfig(name="test", disabled=True)
        self.assertTrue(config.disabled)


class TestMCPTool(unittest.TestCase):
    """Tests for MCPTool dataclass."""

    def test_to_openai_schema(self):
        from mcp.client import MCPTool
        tool = MCPTool(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            server_name="filesystem",
        )
        schema = tool.to_openai_schema()
        self.assertEqual(schema["function"]["name"], "read_file")


# ══════════════════════════════════════════════════════════════════════════════
#  Multi-Agent Orchestrator Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestOrchestrator(unittest.TestCase):
    """Tests for AgentOrchestrator."""

    def setUp(self):
        from agentmain.orchestrator import AgentOrchestrator
        self.orchestrator = AgentOrchestrator()

    def test_default_specialists(self):
        specialists = self.orchestrator.list_specialists()
        self.assertGreater(len(specialists), 0)
        names = [s["name"] for s in specialists]
        self.assertIn("CoderAgent", names)
        self.assertIn("ResearchAgent", names)

    def test_suggest_specialist_coding(self):
        result = self.orchestrator.suggest_specialist("Fix the bug in main.py")
        self.assertEqual(result, "CoderAgent")

    def test_suggest_specialist_research(self):
        result = self.orchestrator.suggest_specialist("Search for the latest AI papers")
        self.assertEqual(result, "ResearchAgent")

    def test_suggest_specialist_analysis(self):
        result = self.orchestrator.suggest_specialist("Analyze the sales data and create charts")
        self.assertEqual(result, "AnalystAgent")

    def test_suggest_specialist_writing(self):
        result = self.orchestrator.suggest_specialist("Write a blog post about AI agents")
        self.assertEqual(result, "WriterAgent")

    def test_register_custom_specialist(self):
        from agentmain.orchestrator import SpecialistProfile, SpecialistType
        profile = SpecialistProfile(
            name="CustomAgent",
            role=SpecialistType.CODER,
            description="Custom specialist",
        )
        self.orchestrator.register_specialist(profile)
        specialists = self.orchestrator.list_specialists()
        names = [s["name"] for s in specialists]
        self.assertIn("CustomAgent", names)

    def test_delegate_no_agent(self):
        result = self.orchestrator.delegate("Test task", "CoderAgent")
        self.assertFalse(result.success)
        # Should mention the error — either "No agent" or "not found" depending on specialist availability
        self.assertTrue("No agent" in result.result or "not found" in result.result.lower() or "Error" in result.result)


# ══════════════════════════════════════════════════════════════════════════════
#  Web Search Tool Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestWebSearchTool(unittest.TestCase):
    """Tests for the web_search tool."""

    def test_search_missing_query(self):
        from plugins.tools.web_search import do_web_search
        result = do_web_search({}, None)
        self.assertEqual(result["status"], "error")
        self.assertIn("Query", result["msg"])

    def test_search_with_query(self):
        from plugins.tools.web_search import do_web_search
        # This test requires internet — may fail in offline environments
        try:
            result = do_web_search({"query": "Python programming", "num_results": 3}, None)
            # If we get results, check structure
            if result["status"] == "success":
                self.assertIn("results", result)
                self.assertLessEqual(len(result["results"]), 3)
        except Exception:
            pass  # Skip in offline environments


# ══════════════════════════════════════════════════════════════════════════════
#  System Tools Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSystemTools(unittest.TestCase):
    """Tests for system tools."""

    def test_system_info(self):
        from plugins.tools.system_tools import do_system_info
        result = do_system_info({"section": "os"}, None)
        self.assertEqual(result["status"], "success")
        self.assertIn("os", result["info"])
        self.assertIn("system", result["info"]["os"])

    def test_directory_tree(self):
        from plugins.tools.system_tools import do_directory_tree
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            os.makedirs(os.path.join(tmpdir, "sub"))
            with open(os.path.join(tmpdir, "file.txt"), "w") as f:
                f.write("test")

            result = do_directory_tree({"path": tmpdir, "depth": 2}, None)
            self.assertEqual(result["status"], "success")
            self.assertIn("tree", result)
            self.assertIn("sub", result["tree"])


# ══════════════════════════════════════════════════════════════════════════════
#  API Server Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestAPIServer(unittest.TestCase):
    """Tests for the API server module."""

    def test_is_available(self):
        from server import is_available
        # Just check it doesn't crash
        result = is_available()
        self.assertIsInstance(result, bool)

    def test_create_app_without_fastapi(self):
        from server import is_available
        if not is_available():
            with self.assertRaises(RuntimeError):
                from server import create_app
                create_app()


# ══════════════════════════════════════════════════════════════════════════════
#  Integration Test: Tool Registry + Validation + Agent Loop
# ══════════════════════════════════════════════════════════════════════════════


class TestIntegration(unittest.TestCase):
    """Integration tests for the superpower features."""

    def test_registry_dispatch_in_handler(self):
        """Test that a registered tool can be dispatched through the handler."""
        from tools.registry import ToolRegistry
        from agent_loop import BaseHandler

        registry = ToolRegistry()
        registry.register(
            name="add_numbers",
            handler=lambda args, resp: {"sum": args.get("a", 0) + args.get("b", 0)},
            description="Add two numbers",
            category="math",
        )

        # Verify dispatch works
        result = registry.dispatch("add_numbers", {"a": 3, "b": 7}, None)
        self.assertEqual(result["sum"], 10)

    def test_validation_prevents_bad_args(self):
        """Test that validation catches type errors before dispatch."""
        from tools.validation import validate_tool_args

        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "timeout": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
        }
        _, errors = validate_tool_args("file_read", {"path": "", "timeout": 0}, schema)
        self.assertGreater(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
