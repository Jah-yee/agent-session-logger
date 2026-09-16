"""Session recorder."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .store import Store


class Recorder:
    """Records an interactive agent session."""

    def __init__(self, session_id: str, agent: str = "claude-code", project: str = "."):
        self.session_id = session_id
        self.agent = agent
        self.store = Store(project)
        self.store.init_db()
        self.session_file = self.store.create_session(session_id, agent)
        self._recording = False
        self._messages = []

    def start(self):
        """Start recording."""
        self._recording = True
        self._start_time = time.time()

    def wait(self):
        """Wait for recording to complete (blocking)."""
        while self._recording:
            time.sleep(0.1)

    def stop(self):
        """Stop recording and save."""
        self._recording = False
        # Write all messages to JSONL
        with open(self.session_file, "w") as f:
            for msg in self._messages:
                f.write(json.dumps(msg) + "\n")

    def log_message(self, role: str, content: str, tool_calls: Optional[str] = None):
        """Log a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_calls": tool_calls,
        }
        self._messages.append(msg)
        self.store.append_message(self.session_id, role, content, tool_calls)

    def log_user(self, content: str):
        """Log a user message."""
        self.log_message("user", content)

    def log_assistant(self, content: str, tool_calls: Optional[str] = None):
        """Log an assistant message."""
        self.log_message("assistant", content, tool_calls)

    def log_tool_result(self, tool_name: str, result: str):
        """Log a tool result."""
        self.log_message("tool", result, tool_calls=tool_name)
