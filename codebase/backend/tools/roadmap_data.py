"""Shared roadmap data helpers for local chat tools."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEBASE_DIR = os.path.dirname(BACKEND_DIR)
APP_DATA_PATH = os.path.join(CODEBASE_DIR, "frontend", "src", "app_data.json")


def load_default_roadmap() -> Dict[str, Any]:
    """Read the frontend default roadmap so chat tools use the same app data."""
    try:
        with open(APP_DATA_PATH, "r", encoding="utf-8") as data_file:
            data = json.load(data_file)
        roadmap = data.get("defaultRoadmap") or {}
        return roadmap if isinstance(roadmap, dict) else {}
    except Exception as exc:
        logger.warning("Could not load default roadmap tool data: %s", exc)
        return {}


def clone_roadmap(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy the current roadmap from context, falling back to default data."""
    roadmap = context.get("roadmap_data") or load_default_roadmap()
    return json.loads(json.dumps(roadmap, ensure_ascii=False))
