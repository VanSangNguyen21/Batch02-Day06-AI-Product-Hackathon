"""Roadmap lookup tool."""

from __future__ import annotations

from typing import Any, Dict

from .roadmap_data import load_default_roadmap


def run(_: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact view of the app roadmap for model context."""
    roadmap = load_default_roadmap()
    phases = []
    for phase in roadmap.get("phases", [])[:4]:
        milestones = [
            {
                "title": item.get("title"),
                "desc": item.get("desc"),
                "tags": item.get("tags", []),
                "time": item.get("time"),
                "status": item.get("status"),
            }
            for item in phase.get("milestones", [])[:3]
        ]
        phases.append(
            {
                "title": phase.get("title"),
                "duration": phase.get("duration"),
                "milestones": milestones,
            }
        )
    return {
        "tool": "roadmap_lookup",
        "result": {
            "title": roadmap.get("title", "Lo trinh hoc AI co ban"),
            "subtitle": roadmap.get("subtitle", ""),
            "phases": phases,
        },
    }
