"""Tests for ASL."""

import os
import tempfile
import pytest
from pathlib import Path

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
