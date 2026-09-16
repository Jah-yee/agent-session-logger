"""Session exporter."""

from .store import Store


def export_session(session_id: str, project: str = ".") -> str:
    """Export a session as markdown."""
    store = Store(project)
    session = store.get_session(session_id)
    if not session:
        return f"# Error\n\nSession '{session_id}' not found."
    
    messages = store.get_messages(session_id)
    
    lines = [
        f"# Session: {session_id}",
        "",
        f"- **Agent:** {session['agent']}",
        f"- **Started:** {session['started_at']}",
        f"- **Project:** {session['project']}",
        f"- **Messages:** {len(messages)}",
        "",
        "---",
        "",
    ]
    
    for msg in messages:
        role = msg["role"].capitalize()
        lines.append(f"### {role}")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")
        if msg.get("tool_calls"):
            lines.append(f"*Tool: {msg['tool_calls']}*")
            lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)
