"""Registry and orchestration helpers for local chat tools."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List

from . import learner_profile, progress_summary, resource_recommender, roadmap_lookup, roadmap_modifier

logger = logging.getLogger(__name__)

AVAILABLE_CHAT_TOOLS = [
    "learner_profile",
    "roadmap_lookup",
    "roadmap_modifier",
    "resource_recommender",
    "progress_summary",
]

TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "learner_profile": learner_profile.run,
    "roadmap_lookup": roadmap_lookup.run,
    "roadmap_modifier": roadmap_modifier.run,
    "resource_recommender": resource_recommender.run,
    "progress_summary": progress_summary.run,
}


def select_chat_tools(message: str) -> List[str]:
    """Choose useful local tools for a learner message."""
    msg = message.lower()
    tools = ["learner_profile"]
    modify_words = [
        "thêm", "them", "bổ sung", "bo sung", "sửa", "sua", "đổi", "doi",
        "cập nhật", "cap nhat", "modify", "change", "update", "add",
        "focus", "tập trung", "tap trung",
    ]
    roadmap_words = ["roadmap", "lộ trình", "lo trinh", "milestone", "bước", "buoc", "kế hoạch", "ke hoach"]
    topic_words = [
        "python", "pandas", "numpy", "machine learning", " ml", "deep learning",
        "neural", "cnn", "nlp", "llm", "project", "dự án", "du an", "toán", "thống kê",
    ]
    should_modify = any(k in msg for k in modify_words) and (
        any(k in msg for k in roadmap_words) or any(k in msg for k in topic_words)
    )
    if any(k in msg for k in roadmap_words) or should_modify:
        tools.append("roadmap_lookup")
    if should_modify:
        tools.append("roadmap_modifier")
    if any(k in msg for k in ["tài liệu", "tai lieu", "resource", "course", "khóa học", "khoa hoc", "sách", "sach", "python", "machine learning", "deep learning"]):
        tools.append("resource_recommender")
    if any(k in msg for k in ["tiến độ", "tien do", "đã học", "da hoc", "progress", "quiz"]):
        tools.append("progress_summary")
    if len(tools) == 1:
        tools.append("resource_recommender")
    return tools


def run_chat_tools(tool_names: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run selected local tools and return structured results."""
    results = []
    for name in tool_names:
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            results.append({"tool": name, "error": "tool_not_found"})
            continue
        try:
            results.append(tool(context))
        except Exception as exc:
            logger.error("Chat tool failed: %s", name, exc_info=True)
            results.append({"tool": name, "error": str(exc)})
    return results


def format_tool_context(tool_results: List[Dict[str, Any]]) -> str:
    """Format tool results as hidden model context."""
    return (
        "Ket qua app tools dung de ho tro tra loi. "
        "Hay dung du lieu nay lam ngu canh, khong nhac den chi tiet ky thuat noi bo.\n"
        f"{json.dumps(tool_results, ensure_ascii=False, indent=2)}"
    )
