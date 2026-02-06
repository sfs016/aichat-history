"""Export chat sessions to Markdown and JSON formats."""

import json
from datetime import datetime

from .core import Message, Session


def session_to_markdown(session: Session, messages: list[Message]) -> str:
    """Export a session and its messages as clean Markdown."""
    lines = [f"# {session.title}", ""]

    if session.project_path:
        lines.append(f"**Project:** {session.project_path}")
    lines.append(f"**Source:** {session.source}")
    if session.created:
        lines.append(f"**Created:** {session.created.isoformat()}")
    if session.updated:
        lines.append(f"**Updated:** {session.updated.isoformat()}")
    lines.append(f"**Messages:** {session.message_count}")
    lines.extend(["", "---", ""])

    for msg in messages:
        role_label = msg.role.capitalize()
        ts = ""
        if msg.timestamp:
            ts = f" ({msg.timestamp.strftime('%Y-%m-%d %H:%M')})"
        lines.append(f"## {role_label}{ts}")
        lines.append("")
        lines.append(msg.content)
        lines.extend(["", "---", ""])

    return "\n".join(lines)


def session_to_json(session: Session, messages: list[Message]) -> str:
    """Export a session and its messages as structured JSON."""
    data = {
        "session": {
            "id": session.id,
            "title": session.title,
            "source": session.source,
            "project_path": session.project_path,
            "message_count": session.message_count,
            "created": session.created.isoformat() if session.created else None,
            "updated": session.updated.isoformat() if session.updated else None,
        },
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "message_type": msg.message_type,
                "metadata": msg.metadata,
            }
            for msg in messages
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
