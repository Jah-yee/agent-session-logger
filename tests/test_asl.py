"""Tests for ASL."""

import os
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

import asl
from asl.store import Store
from asl.recorder import Recorder
from asl.searcher import Searcher
from asl.exporter import export_session


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    project = tmp_path / "test_project"
    project.mkdir()
    return project


@pytest.fixture
def store(tmp_project):
    """Create a Store instance."""
    s = Store(str(tmp_project))
    s.init_db()
    return s


class TestStore:
    def test_init_db(self, store):
        assert store.db_path.exists()
        assert store.sessions_dir.exists()

    def test_create_session(self, store):
        sf = store.create_session("test-123", "claude-code")
        assert sf.exists()
        assert "test-123" in sf.name

    def test_append_message(self, store):
        store.create_session("test-123", "claude-code")
        store.append_message("test-123", "user", "Hello")
        store.append_message("test-123", "assistant", "Hi there")
        
        messages = store.get_messages("test-123")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_list_sessions(self, store):
        store.create_session("test-1", "claude-code")
        store.create_session("test-2", "codex")
        
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_get_session(self, store):
        store.create_session("test-123", "claude-code")
        session = store.get_session("test-123")
        assert session is not None
        assert session["id"] == "test-123"
        assert session["agent"] == "claude-code"


class TestRecorder:
    def test_recorder_init(self, tmp_project):
        r = Recorder("test-session", "claude-code", str(tmp_project))
        assert r.session_id == "test-session"
        assert r.agent == "claude-code"

    def test_log_message(self, tmp_project):
        r = Recorder("test-session", "claude-code", str(tmp_project))
        r.start()
        r.log_user("Hello")
        r.log_assistant("Hi there")
        r.stop()
        
        messages = r.store.get_messages("test-session")
        assert len(messages) == 2


class TestSearcher:
    def test_search(self, store):
        store.create_session("test-123", "claude-code")
        store.append_message("test-123", "user", "How do I fix the auth bug?")
        store.append_message("test-123", "assistant", "Try using JWT tokens")
        
        searcher = Searcher(str(store.project_path))
        results = searcher.search("auth")
        assert len(results) >= 1

    def test_search_no_results(self, store):
        searcher = Searcher(str(store.project_path))
        results = searcher.search("nonexistent")
        assert len(results) == 0


class TestExporter:
    def test_export_session(self, store):
        store.create_session("test-123", "claude-code")
        store.append_message("test-123", "user", "Hello")
        store.append_message("test-123", "assistant", "Hi")
        
        md = export_session("test-123", str(store.project_path))
        assert "# Session: test-123" in md
        assert "Hello" in md
        assert "Hi" in md

    def test_export_nonexistent(self, store):
        md = export_session("nonexistent", str(store.project_path))
        assert "Error" in md


class TestModuleEntryPoint:
    """`python -m asl.cli` must reach the CLI. Regression test for #16.

    Without the ``__main__`` guard, runpy executes the module body for its
    side effects and falls off the end: exit status 0 and no output at all,
    for every subcommand and for ``--help``. The exit status alone cannot tell
    that apart from success, so assert on stdout and on click's usage error.
    """

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "asl.cli", *args],
            capture_output=True, text=True, timeout=30,
        )

    def test_help_prints_usage(self):
        result = self._run("--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        for command in ("record", "search", "export", "list", "init"):
            assert command in result.stdout

    def test_version_prints_version(self):
        result = self._run("--version")
        assert result.returncode == 0
        assert asl.__version__ in result.stdout

    def test_unknown_command_is_a_usage_error(self):
        result = self._run("no-such-command")
        assert result.returncode == 2
        assert "Usage:" in result.stderr
