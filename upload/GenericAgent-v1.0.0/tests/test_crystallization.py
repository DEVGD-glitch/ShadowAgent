"""tests/test_crystallization.py — Tests for the automatic skill crystallization engine.

Tests cover:
1. Auto-crystallization trigger (should_crystallize)
2. L1 auto-sync (auto_sync_l1, auto_sync_l1_from_file)
3. Working checkpoint persistence (save/load/clear)
4. RAG auto-indexing (auto_index_to_rag, auto_index_text_to_rag)
5. MemoryWriteObserver
6. CrystallizationHook
7. Crystallization metrics
8. Integration with agent_loop and ga.py
"""

from __future__ import annotations

import json
import os
import tempfile
import textwrap
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_root(tmp_path):
    """Create a temporary project root with memory/ structure."""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(exist_ok=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(exist_ok=True)

    # Create L1 insight file
    l1_content = textwrap.dedent("""\
        # [Global Memory Insight]
        Browser special ops: tmwebdriver_sop(file upload/image search/PDF blob/...)
        Keyboard & Mouse: ljqCtrl_sop(no pyautogui/activate first)
        Read L2 or ls ../memory/ for L3 when needed
        L0(META-SOP): memory_management_sop
        L2: currently empty
        L3: memory_cleanup_sop(memory cleanup) | ui_detect.py | ocr_utils.py
        L4: L4_raw_sessions/

        [RULES]
        1. Search first: must use es for filename search
    """)
    (mem_dir / "global_mem_insight.txt").write_text(l1_content, encoding="utf-8")

    # Create L2 global memory
    (mem_dir / "global_mem.txt").write_text("# [Global Memory - L2]\n", encoding="utf-8")

    return tmp_path


@pytest.fixture
def crystallization_module():
    """Import the crystallization module."""
    from memory import crystallization
    # Reset metrics for each test
    crystallization.reset_crystallization_metrics()
    return crystallization


# ---------------------------------------------------------------------------
# 1. Auto-Crystallization Trigger Tests
# ---------------------------------------------------------------------------

class TestShouldCrystallize:

    def test_short_task_no_trigger(self, crystallization_module):
        """Tasks under 15 turns should NOT trigger crystallization."""
        assert crystallization_module.should_crystallize(5, {"result": "CURRENT_TASK_DONE"}) is False
        assert crystallization_module.should_crystallize(14, {"result": "CURRENT_TASK_DONE"}) is False

    def test_long_task_triggers_on_current_task_done(self, crystallization_module):
        """Tasks with 15+ turns and CURRENT_TASK_DONE should trigger."""
        assert crystallization_module.should_crystallize(15, {"result": "CURRENT_TASK_DONE"}) is True
        assert crystallization_module.should_crystallize(30, {"result": "CURRENT_TASK_DONE"}) is True

    def test_long_task_triggers_on_exited(self, crystallization_module):
        """Tasks with 15+ turns and EXITED should trigger."""
        assert crystallization_module.should_crystallize(15, {"result": "EXITED"}) is True

    def test_no_trigger_on_empty_exit_reason(self, crystallization_module):
        """No exit reason should not trigger."""
        assert crystallization_module.should_crystallize(20, {}) is False
        assert crystallization_module.should_crystallize(20, {"result": "UNKNOWN"}) is False

    def test_no_trigger_on_abort(self, crystallization_module):
        """User-aborted tasks should NOT trigger crystallization."""
        assert crystallization_module.should_crystallize(
            20, {"result": "CURRENT_TASK_DONE", "data": {"status": "aborted"}}
        ) is False

    def test_boundary_at_15_turns(self, crystallization_module):
        """Exactly 15 turns should trigger."""
        assert crystallization_module.should_crystallize(15, {"result": "CURRENT_TASK_DONE"}) is True

    def test_boundary_at_14_turns(self, crystallization_module):
        """14 turns should NOT trigger."""
        assert crystallization_module.should_crystallize(14, {"result": "CURRENT_TASK_DONE"}) is False


class TestGetCrystallizationPrompt:

    def test_prompt_contains_start_long_term_update(self, crystallization_module):
        """The prompt should instruct the LLM to call start_long_term_update."""
        prompt = crystallization_module.get_crystallization_prompt()
        assert "start_long_term_update" in prompt
        assert "15+ turns" in prompt

    def test_prompt_mentions_l0_l2_l3(self, crystallization_module):
        """The prompt should reference memory layers."""
        prompt = crystallization_module.get_crystallization_prompt()
        assert "L0" in prompt or "L1" in prompt
        assert "L2" in prompt
        assert "L3" in prompt


# ---------------------------------------------------------------------------
# 2. L1 Auto-Sync Tests
# ---------------------------------------------------------------------------

class TestL1AutoSync:

    def test_sync_adds_new_sop_to_l1(self, crystallization_module, project_root):
        """auto_sync_l1 should add a new SOP reference to the L1 file."""
        result = crystallization_module.auto_sync_l1(
            "stock_screening_sop.md",
            "stock screening with EXPMA",
            project_root=str(project_root),
        )
        assert result is True

        # Read L1 and verify the new SOP is referenced
        l1_path = project_root / "memory" / "global_mem_insight.txt"
        content = l1_path.read_text(encoding="utf-8")
        assert "stock_screening_sop.md" in content
        assert "stock screening with EXPMA" in content

    def test_sync_skips_existing_sop(self, crystallization_module, project_root):
        """auto_sync_l1 should skip if the SOP is already referenced."""
        # First sync
        crystallization_module.auto_sync_l1(
            "test_sop.md", "test description", project_root=str(project_root)
        )
        # Second sync should return False (already there)
        result = crystallization_module.auto_sync_l1(
            "test_sop.md", "test description", project_root=str(project_root)
        )
        assert result is False

    def test_sync_from_file(self, crystallization_module, project_root):
        """auto_sync_l1_from_file should extract description from file heading."""
        sop_path = project_root / "memory" / "my_new_sop.md"
        sop_path.write_text("# My New SOP\n\nThis is the content.", encoding="utf-8")

        result = crystallization_module.auto_sync_l1_from_file(
            str(sop_path), project_root=str(project_root)
        )
        assert result is True

        l1_content = (project_root / "memory" / "global_mem_insight.txt").read_text(encoding="utf-8")
        assert "my_new_sop.md" in l1_content

    def test_sync_handles_missing_l1(self, crystallization_module, tmp_path):
        """auto_sync_l1 should return False if L1 file doesn't exist."""
        result = crystallization_module.auto_sync_l1(
            "test.md", "test", project_root=str(tmp_path)
        )
        assert result is False

    def test_sync_from_file_generates_description_from_filename(self, crystallization_module, project_root):
        """When file has no heading, description should come from filename."""
        sop_path = project_root / "memory" / "email_automation_sop.md"
        sop_path.write_text("Just some content without a heading.", encoding="utf-8")

        result = crystallization_module.auto_sync_l1_from_file(
            str(sop_path), project_root=str(project_root)
        )
        assert result is True

        l1_content = (project_root / "memory" / "global_mem_insight.txt").read_text(encoding="utf-8")
        assert "email_automation_sop" in l1_content


# ---------------------------------------------------------------------------
# 3. Working Checkpoint Persistence Tests
# ---------------------------------------------------------------------------

class TestWorkingCheckpoint:

    def test_save_and_load(self, crystallization_module, project_root):
        """Save and load a working checkpoint."""
        key_info = "Python path: /usr/bin/python3, venv at ~/venv"
        related_sop = "python_setup_sop.md"

        saved = crystallization_module.save_working_checkpoint(
            key_info=key_info,
            related_sop=related_sop,
            project_root=str(project_root),
        )
        assert saved is True

        loaded = crystallization_module.load_working_checkpoint(
            project_root=str(project_root)
        )
        assert loaded["key_info"] == key_info
        assert loaded["related_sop"] == related_sop
        assert "timestamp" in loaded
        assert "saved_at" in loaded

    def test_load_nonexistent(self, crystallization_module, tmp_path):
        """Loading a nonexistent checkpoint should return empty dict."""
        result = crystallization_module.load_working_checkpoint(
            project_root=str(tmp_path)
        )
        assert result == {}

    def test_clear(self, crystallization_module, project_root):
        """Clear should remove the checkpoint file."""
        crystallization_module.save_working_checkpoint(
            key_info="test", project_root=str(project_root)
        )

        cleared = crystallization_module.clear_working_checkpoint(
            project_root=str(project_root)
        )
        assert cleared is True

        loaded = crystallization_module.load_working_checkpoint(
            project_root=str(project_root)
        )
        assert loaded == {}

    def test_survives_json_corruption(self, crystallization_module, project_root):
        """Loading a corrupted checkpoint file should return empty dict."""
        checkpoint_path = project_root / "temp" / "_working_checkpoint.json"
        checkpoint_path.write_text("{corrupted json", encoding="utf-8")

        result = crystallization_module.load_working_checkpoint(
            project_root=str(project_root)
        )
        assert result == {}

    def test_unicode_key_info(self, crystallization_module, project_root):
        """Checkpoint should handle Unicode (Chinese/French) key_info."""
        key_info = "配置路径：/用户/文档，François的设置"
        crystallization_module.save_working_checkpoint(
            key_info=key_info, project_root=str(project_root)
        )

        loaded = crystallization_module.load_working_checkpoint(
            project_root=str(project_root)
        )
        assert loaded["key_info"] == key_info


# ---------------------------------------------------------------------------
# 4. RAG Auto-Indexing Tests
# ---------------------------------------------------------------------------

class TestRAGAutoIndexing:

    def test_auto_index_nonexistent_file(self, crystallization_module):
        """Indexing a nonexistent file should return 0."""
        result = crystallization_module.auto_index_to_rag("/nonexistent/file.md")
        assert result == 0

    def test_auto_index_text_empty(self, crystallization_module):
        """Indexing empty text should return 0."""
        result = crystallization_module.auto_index_text_to_rag("")
        assert result == 0

    def test_auto_index_text_whitespace_only(self, crystallization_module):
        """Indexing whitespace-only text should return 0."""
        result = crystallization_module.auto_index_text_to_rag("   \n\n   ")
        assert result == 0

    def test_auto_index_handles_missing_rag(self, crystallization_module, tmp_path):
        """Should gracefully handle RAG engine not being available."""
        # This tests the import error path — since memory.vector may not
        # be fully configured in test environment, it should return 0
        test_file = tmp_path / "test_sop.md"
        test_file.write_text("# Test SOP\nContent here.", encoding="utf-8")

        # Should not raise an exception
        result = crystallization_module.auto_index_to_rag(str(test_file))
        assert isinstance(result, int)
        assert result >= 0


# ---------------------------------------------------------------------------
# 5. MemoryWriteObserver Tests
# ---------------------------------------------------------------------------

class TestMemoryWriteObserver:

    def test_identifies_sop_file(self, crystallization_module):
        """Observer should identify L3 SOP files correctly."""
        observer = crystallization_module.MemoryWriteObserver()

        assert observer.is_sop_file("/path/memory/stock_sop.md") is True
        assert observer.is_sop_file("/path/memory/skill-web.md") is True
        assert observer.is_sop_file("/path/memory/automation_skill.md") is True

    def test_rejects_l1_l2_l0_files(self, crystallization_module):
        """Observer should NOT identify L0/L1/L2 files as SOPs."""
        observer = crystallization_module.MemoryWriteObserver()

        assert observer.is_sop_file("/path/memory/global_mem_insight.txt") is False
        assert observer.is_sop_file("/path/memory/global_mem.txt") is False
        assert observer.is_sop_file("/path/memory/memory_management_sop.md") is False

    def test_rejects_l4_and_cache_files(self, crystallization_module):
        """Observer should NOT identify L4/cache files as SOPs."""
        observer = crystallization_module.MemoryWriteObserver()

        assert observer.is_sop_file("/path/memory/L4_raw_sessions/log.txt") is False
        assert observer.is_sop_file("/path/memory/vector_store.json") is False
        assert observer.is_sop_file("/path/memory/__pycache__/mod.pyc") is False

    def test_identifies_direct_memory_md_files(self, crystallization_module):
        """MD/PY files directly in memory/ should be identified as SOPs."""
        observer = crystallization_module.MemoryWriteObserver()

        assert observer.is_sop_file("/project/memory/my_tool.py") is True
        assert observer.is_sop_file("/project/memory/notes.md") is True

    def test_rejects_non_memory_files(self, crystallization_module):
        """Files outside memory/ should not be identified as SOPs."""
        observer = crystallization_module.MemoryWriteObserver()

        assert observer.is_sop_file("/project/src/main.py") is False
        assert observer.is_sop_file("/project/README.md") is False

    def test_on_memory_write_non_sop(self, crystallization_module, tmp_path):
        """on_memory_write should skip non-SOP files."""
        observer = crystallization_module.MemoryWriteObserver()

        result = observer.on_memory_write("/path/memory/global_mem.txt")
        assert result["l1_synced"] is False
        assert result["rag_indexed"] == 0

    def test_on_memory_write_sop_file(self, crystallization_module, project_root):
        """on_memory_write should sync L1 and index for SOP files."""
        observer = crystallization_module.MemoryWriteObserver()

        # Create a test SOP
        sop_path = project_root / "memory" / "test_new_sop.md"
        sop_path.write_text("# Test New SOP\nAutomated testing procedure.", encoding="utf-8")

        result = observer.on_memory_write(str(sop_path), project_root=str(project_root))
        assert result["l1_synced"] is True


# ---------------------------------------------------------------------------
# 6. CrystallizationHook Tests
# ---------------------------------------------------------------------------

class TestCrystallizationHook:

    def test_hook_triggers_once(self, crystallization_module):
        """Hook should trigger only once per task."""
        hook = crystallization_module.CrystallizationHook(min_turns=5)

        assert hook.should_trigger(10, {"result": "CURRENT_TASK_DONE"}) is True
        assert hook.should_trigger(10, {"result": "CURRENT_TASK_DONE"}) is False

    def test_hook_respects_min_turns(self, crystallization_module):
        """Hook should respect min_turns setting."""
        hook = crystallization_module.CrystallizationHook(min_turns=20)

        assert hook.should_trigger(15, {"result": "CURRENT_TASK_DONE"}) is False
        assert hook.should_trigger(20, {"result": "CURRENT_TASK_DONE"}) is True

    def test_hook_reset(self, crystallization_module):
        """Hook should be reusable after reset."""
        hook = crystallization_module.CrystallizationHook(min_turns=5)

        hook.should_trigger(10, {"result": "CURRENT_TASK_DONE"})
        hook.reset()
        assert hook.should_trigger(10, {"result": "CURRENT_TASK_DONE"}) is True

    def test_hook_get_prompt(self, crystallization_module):
        """Hook should return a non-empty prompt."""
        hook = crystallization_module.CrystallizationHook()
        prompt = hook.get_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ---------------------------------------------------------------------------
# 7. Crystallization Metrics Tests
# ---------------------------------------------------------------------------

class TestCrystallizationMetrics:

    def test_initial_metrics(self, crystallization_module):
        """Metrics should start at zero after reset."""
        crystallization_module.reset_crystallization_metrics()
        metrics = crystallization_module.get_crystallization_metrics()
        assert metrics.total_triggers == 0
        assert metrics.l1_syncs == 0
        assert metrics.rag_indexed == 0
        assert metrics.checkpoint_saves == 0

    def test_metrics_updated_on_checkpoint_save(self, crystallization_module, project_root):
        """Saving a checkpoint should increment metrics."""
        crystallization_module.reset_crystallization_metrics()

        crystallization_module.save_working_checkpoint(
            key_info="test", project_root=str(project_root)
        )

        metrics = crystallization_module.get_crystallization_metrics()
        assert metrics.checkpoint_saves >= 1

    def test_metrics_to_dict(self, crystallization_module):
        """Metrics should serialize to dict."""
        metrics = crystallization_module.get_crystallization_metrics()
        d = metrics.to_dict()
        assert "total_triggers" in d
        assert "l1_syncs" in d
        assert "rag_indexed" in d
        assert "checkpoint_saves" in d


# ---------------------------------------------------------------------------
# 8. Crystallization Event Logging Tests
# ---------------------------------------------------------------------------

class TestCrystallizationEventLogging:

    def test_log_creates_file(self, crystallization_module, project_root):
        """log_crystallization_event should create the log file."""
        crystallization_module.log_crystallization_event(
            "test_event",
            {"detail": "test"},
            project_root=str(project_root),
        )

        log_path = project_root / "temp" / "_crystallization_log.json"
        assert log_path.exists()

        events = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(events) == 1
        assert events[0]["event_type"] == "test_event"
        assert events[0]["details"]["detail"] == "test"

    def test_log_appends_events(self, crystallization_module, project_root):
        """Multiple log calls should append, not overwrite."""
        for i in range(3):
            crystallization_module.log_crystallization_event(
                f"event_{i}", {"i": i}, project_root=str(project_root)
            )

        log_path = project_root / "temp" / "_crystallization_log.json"
        events = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(events) == 3

    def test_log_caps_at_100_events(self, crystallization_module, project_root):
        """Log should keep only the last 100 events."""
        for i in range(110):
            crystallization_module.log_crystallization_event(
                f"event_{i}", {"i": i}, project_root=str(project_root)
            )

        log_path = project_root / "temp" / "_crystallization_log.json"
        events = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(events) == 100
        # Should keep the last 100 (events 10-109)
        assert events[0]["details"]["i"] == 10
        assert events[-1]["details"]["i"] == 109


# ---------------------------------------------------------------------------
# 9. Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_full_crystallization_flow(self, crystallization_module, project_root):
        """Test the full flow: trigger → checkpoint save → L1 sync → RAG index."""
        crystallization_module.reset_crystallization_metrics()

        # 1. Simulate a long task completing
        should_trigger = crystallization_module.should_crystallize(
            20, {"result": "CURRENT_TASK_DONE"}
        )
        assert should_trigger is True

        # 2. Save working checkpoint
        saved = crystallization_module.save_working_checkpoint(
            key_info="Installed Python 3.12, venv at ~/project/venv",
            related_sop="python_setup_sop.md",
            project_root=str(project_root),
        )
        assert saved is True

        # 3. Create a new SOP
        sop_path = project_root / "memory" / "python_setup_sop.md"
        sop_path.write_text(
            "# Python Setup SOP\n\nInstall Python 3.12 and create venv.",
            encoding="utf-8",
        )

        # 4. Auto-sync L1
        synced = crystallization_module.auto_sync_l1_from_file(
            str(sop_path), project_root=str(project_root)
        )
        assert synced is True

        # 5. Verify L1 contains the new SOP
        l1_content = (project_root / "memory" / "global_mem_insight.txt").read_text(encoding="utf-8")
        assert "python_setup_sop.md" in l1_content

        # 6. Verify checkpoint can be loaded
        loaded = crystallization_module.load_working_checkpoint(
            project_root=str(project_root)
        )
        assert "Installed Python 3.12" in loaded["key_info"]

        # 7. Verify metrics
        metrics = crystallization_module.get_crystallization_metrics()
        assert metrics.checkpoint_saves >= 1
        assert metrics.l1_syncs >= 1

    def test_observer_integration(self, crystallization_module, project_root):
        """Test MemoryWriteObserver with L1 sync and RAG indexing."""
        observer = crystallization_module.MemoryWriteObserver()

        # Create a new SOP
        sop_path = project_root / "memory" / "email_sop.md"
        sop_path.write_text(
            "# Email Automation SOP\n\nHow to send emails automatically.",
            encoding="utf-8",
        )

        result = observer.on_memory_write(str(sop_path), project_root=str(project_root))

        assert result["l1_synced"] is True
        # RAG indexing may or may not work depending on vector store availability
        assert isinstance(result["rag_indexed"], int)

        # Verify L1 was updated
        l1_content = (project_root / "memory" / "global_mem_insight.txt").read_text(encoding="utf-8")
        assert "email_sop.md" in l1_content
