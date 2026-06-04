"""Progress summary tool."""

from __future__ import annotations

from typing import Any, Dict


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize recent chat history and quiz progress."""
    history = context.get("history") or []
    return {
        "tool": "progress_summary",
        "result": {
            "history_messages": len(history),
            "quiz_completed": context["quiz_completed"],
            "questions_answered": context["questions_answered"],
        },
    }
