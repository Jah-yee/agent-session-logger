"""Session storage and database management."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class Store:
    """Manages session storage and SQLite database."""

    def __init__(self, project: str = "."):
        self.project_path = Path(project).resolve()
        self.asl_dir = self.project_path / ".asl"
        self.db_path = self.asl_dir / "sessions.db"
        self.sessions_dir = self.asl_dir / "sessions"

    def init_db(self):
        """Initialize the database and directories."""
        self.asl_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent TEXT NOT NULL,
                project TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                metadata TEXT,
                file_path TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tool_calls TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session 
            ON messages(session_id)
        """)
        conn.commit()
        conn.close()

    def create_session(self, session_id: str, agent: str) -> Path:
        """Create a new session file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{agent}_{session_id}.jsonl"
        session_file = self.sessions_dir / filename
        session_file.touch()
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO sessions (id, agent, project, started_at, file_path) VALUES (?, ?, ?, ?, ?)",
            (session_id, agent, str(self.project_path), datetime.utcnow().isoformat(), str(session_file))
        )
        conn.commit()
        conn.close()
        
        return session_file

    def append_message(self, session_id: str, role: str, content: str, tool_calls: Optional[str] = None):
        """Append a message to a session."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, datetime.utcnow().isoformat(), tool_calls)
        )
        conn.commit()
        conn.close()

    def list_sessions(self) -> list[dict]:
        """List all recorded sessions."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, agent, started_at FROM sessions ORDER BY started_at DESC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session details."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_messages(self, session_id: str) -> list[dict]:
        """Get all messages for a session."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
