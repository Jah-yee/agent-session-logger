"""Session search and indexing."""

import sqlite3
from pathlib import Path
from typing import Optional

from .store import Store


def _like_escape(term: str, escape: str = "\\") -> str:
    """Escape LIKE metacharacters (% and _) in a search term.

    Without escaping, unescaped % matches any sequence of characters and _
    matches any single character, causing false positives when users search
    for identifiers or patterns that legitimately contain these characters.
    """
    for ch in (escape, "%", "_"):
        term = term.replace(ch, escape + ch)
    return term


class Indexer:
    """Indexes session content for search."""

    def __init__(self, project: str = "."):
        self.store = Store(project)
        self.store.init_db()

    def index_session(self, session_id: str):
        """Index a session's content for full-text search."""
        messages = self.store.get_messages(session_id)
        conn = sqlite3.connect(self.store.db_path)
        
        # Create FTS5 table if not exists
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                session_id,
                role,
                content,
                content=messages,
                content_rowid=id
            )
        """)
        
        # Index messages
        for msg in messages:
            conn.execute(
                "INSERT INTO messages_fts (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, msg["role"], msg["content"])
            )
        
        conn.commit()
        conn.close()


class Searcher:
    """Searches across recorded sessions."""

    def __init__(self, project: str = "."):
        self.store = Store(project)
        self.store.init_db()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search sessions by keyword."""
        conn = sqlite3.connect(self.store.db_path)
        conn.row_factory = sqlite3.Row
        
        # LIKE search with escaped metacharacters so that % and _ are matched
        # as literal characters (fixes false positives when searching for
        # identifiers, file paths, or printf-style format strings).
        escaped = _like_escape(query)
        rows = conn.execute("""
            SELECT DISTINCT s.id as session_id, s.started_at as timestamp,
                   substr(m.content, 1, 200) as snippet
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE m.content LIKE ? ESCAPE '\\'
            ORDER BY s.started_at DESC
            LIMIT ?
        """, (f"%{escaped}%", limit)).fetchall()
        
        conn.close()
        return [dict(row) for row in rows]

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Get a summary of a session."""
        session = self.store.get_session(session_id)
        if not session:
            return None
        messages = self.store.get_messages(session_id)
        return {
            "session": session,
            "message_count": len(messages),
            "user_messages": len([m for m in messages if m["role"] == "user"]),
            "assistant_messages": len([m for m in messages if m["role"] == "assistant"]),
        }
