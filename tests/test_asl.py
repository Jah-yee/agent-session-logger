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
class TestFailedWriteDoesNotLockDatabase:
    """A failed write must not poison the database for the rest of the process.

    Regression tests for #19. Before the fix, `append_message` and
    `create_session` closed the connection only on the success path, so a
    failed INSERT left the connection open with an uncommitted transaction and
    a RESERVED lock on sessions.db. Every later write then raised
    `OperationalError: database is locked`.

    The trigger used here is a NOT NULL violation on `role` (or on
    `session_id` / a duplicate primary key) rather than on `content`:
    `content=None` is coerced to "" by the fix, so it no longer raises at all
    and would pass without exercising the transaction handling.
    """

    def _connection_states(self):
        """State of every reachable sqlite3 connection.

        Returns True for a connection with an open transaction, False for one
        that is still open but idle, and None for a closed one. `closing()`
        closes the connection on the way out, so probing it raises
        ProgrammingError -- which is how we tell "closed" from "still open".
        """
        import gc
        import sqlite3

        state = []
        for obj in gc.get_objects():
            if isinstance(obj, sqlite3.Connection):
                try:
                    state.append(obj.in_transaction)
                except sqlite3.ProgrammingError:
                    state.append(None)  # closed
        return state

    def test_failed_append_does_not_lock_database(self, store):
        """A rejected message is skipped; later valid messages still persist."""
        import sqlite3

        store.create_session("lock-1", "claude-code")
        store.append_message("lock-1", "user", "before")

        # role=None violates the NOT NULL constraint and is NOT coerced away.
        with pytest.raises(sqlite3.IntegrityError):
            store.append_message("lock-1", None, "bad role")

        # The whole point: the store is still writable, in this same process.
        store.append_message("lock-1", "user", "after")
        store.append_message("lock-1", "assistant", "after again")

        messages = store.get_messages("lock-1")
        assert [m["content"] for m in messages] == ["before", "after", "after again"]

    def test_failed_append_leaves_no_open_transaction(self, store):
        """No connection is left holding an uncommitted transaction."""
        import sqlite3

        store.create_session("lock-2", "claude-code")
        with pytest.raises(sqlite3.IntegrityError):
            store.append_message("lock-2", None, "bad role")

        # No connection may still be in a transaction (that is the lock).
        assert True not in self._connection_states()

    def test_failed_append_with_unknown_session_does_not_lock(self, store):
        """A write for a session id that violates NOT NULL is also safe.

        The `messages.session_id` column is declared but never enforced as a
        foreign key (#9), so this exercises the NOT NULL path specifically
        rather than the role path.
        """
        import sqlite3

        store.create_session("lock-3", "claude-code")
        with pytest.raises(sqlite3.IntegrityError):
            store.append_message(None, "user", "no session id")

        store.append_message("lock-3", "user", "still writable")
        assert len(store.get_messages("lock-3")) == 1

    def test_failed_create_session_does_not_lock_database(self, store):
        """create_session has the same shape and must not leak either."""
        import sqlite3

        store.create_session("dup", "claude-code")
        # Duplicate primary key -> IntegrityError mid-transaction.
        with pytest.raises(sqlite3.IntegrityError):
            store.create_session("dup", "claude-code")

        store.append_message("dup", "user", "after duplicate")
        assert len(store.get_messages("dup")) == 1

    def test_failed_create_session_leaves_no_open_transaction(self, store):
        import sqlite3

        store.create_session("dup", "claude-code")
        with pytest.raises(sqlite3.IntegrityError):
            store.create_session("dup", "claude-code")

        assert True not in self._connection_states()

    def test_failed_init_db_does_not_lock_database(self, tmp_project):
        """init_db issues several statements; a late failure must not leak.

        The final CREATE INDEX fails because `messages` is pre-created without
        a `session_id` column, so the abort happens after earlier DDL in the
        same transaction succeeded.

        Here the leak is a connection, not a lock: these are DDL statements, so
        sqlite3 never opens a write transaction for them and nothing is left
        holding a RESERVED lock. The connection is still dropped mid-statement,
        so the assertion is that no connection is left OPEN, which is what
        `closing()` guarantees and what the un-fixed code violates.
        """
        import sqlite3

        s = Store(str(tmp_project))
        s.asl_dir.mkdir(parents=True, exist_ok=True)
        s.sessions_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(s.db_path)
        conn.execute("CREATE TABLE messages (unrelated TEXT)")
        conn.commit()
        conn.close()

        with pytest.raises(sqlite3.OperationalError):
            s.init_db()

        # No connection left open by the failed init_db.
        assert False not in self._connection_states()

        # And the store is still usable.
        s.create_session("after-init", "codex")
        assert len(s.list_sessions()) == 1

    def test_repeated_failures_never_lock_the_database(self, store):
        """The failure is not one-shot: many failures in a row stay writable."""
        import sqlite3

        store.create_session("lock-many", "claude-code")
        for i in range(25):
            with pytest.raises(sqlite3.IntegrityError):
                store.append_message("lock-many", None, f"bad {i}")
        store.append_message("lock-many", "user", "still here")
        assert len(store.get_messages("lock-many")) == 1

    def test_none_content_is_recorded_as_empty_string(self, store):
        """An empty tool result is not an error: it records as "" (#19)."""
        store.create_session("none-content", "claude-code")
        store.append_message("none-content", "tool", None, tool_calls="Bash")

        messages = store.get_messages("none-content")
        assert len(messages) == 1
        assert messages[0]["content"] == ""
        assert messages[0]["tool_calls"] == "Bash"

    def test_recorder_session_survives_a_rejected_message(self, tmp_project):
        """The end-to-end scenario from #19, via the public Recorder API.

        `log_tool_result(name, None)` is an ordinary event, not an error, and
        the session must keep recording afterwards.
        """
        r = Recorder("rec-1", "claude-code", str(tmp_project))
        r.start()
        r.log_user("step 1")
        r.log_assistant("step 2")
        r.log_tool_result("Bash", None)
        r.log_user("step 3")
        r.log_assistant("step 4")

        contents = [m["content"] for m in r.store.get_messages("rec-1")]
        assert contents == ["step 1", "step 2", "", "step 3", "step 4"]

        r.stop()
        assert r.session_file.exists()


class TestSearchRendersMarkupVerbatim:
    """#21: session content is untrusted and must not reach Rich's markup parser.

    Regression tests for the `rich.markup.escape` commit bundled in this PR.
    """

    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, "-m", "asl.cli", *args],
            capture_output=True, text=True, timeout=60, env=env,
        )

    @pytest.fixture
    def cli_project(self, tmp_path):
        project = tmp_path / "cli_project"
        project.mkdir()
        s = Store(str(project))
        s.init_db()
        s.create_session("s1", "claude-code")
        return project

    def test_search_preserves_markup_in_snippet(self, cli_project):
        s = Store(str(cli_project))
        s.append_message(
            "s1", "user",
            "auth fix: see [the docs](https://example.com) for auth",
        )

        env = dict(os.environ, PYTHONPATH=str(cli_project))
        result = self._run("search", "auth", "--project", str(cli_project), env=env)

        assert result.returncode == 0, result.stderr
        # The link text must survive verbatim instead of being eaten as a tag.
        assert "[the docs](https://example.com)" in result.stdout

    def test_search_survives_unmatched_closing_tag(self, cli_project):
        """A stray [/] must not raise MarkupError and kill the command."""
        s = Store(str(cli_project))
        s.append_message("s1", "user", "closing tag [/notbold] in the transcript")

        env = dict(os.environ, PYTHONPATH=str(cli_project))
        result = self._run("search", "closing", "--project", str(cli_project), env=env)

        assert result.returncode == 0, result.stderr
        assert "[/notbold]" in result.stdout

    def test_search_does_not_rewrite_wrap_or_highlight(self, cli_project):
        """soft_wrap/highlight=False keep long snippets unwrapped."""
        s = Store(str(cli_project))
        long_line = "x" * 300
        s.append_message("s1", "user", f"needle {long_line}")

        env = dict(os.environ, PYTHONPATH=str(cli_project))
        result = self._run("search", "needle", "--project", str(cli_project), env=env)

        assert result.returncode == 0, result.stderr
        body = [ln for ln in result.stdout.splitlines() if "needle" in ln]
        assert body, result.stdout
        assert len(body[0]) > 100  # not rewrapped at 80 columns