"""Learner profile tool."""

from __future__ import annotations

from typing import Any, Dict


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return learner/session metadata for chat grounding."""
    return {
        "tool": "learner_profile",
        "result": {
            "user_id": context["user_id"],
            "quiz_completed": context["quiz_completed"],
            "questions_answered": context["questions_answered"],
            "model": context["model_name"],
            "provider": context["provider"],
        },
    }
