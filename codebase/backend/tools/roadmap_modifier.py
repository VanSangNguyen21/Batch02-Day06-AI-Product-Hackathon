"""Roadmap modifier tool."""

from __future__ import annotations

from typing import Any, Dict

from .roadmap_data import clone_roadmap, load_default_roadmap


TOPIC_RULES = [
    {
        "keywords": ["python", "pandas", "numpy", "code", "lap trinh", "lập trình"],
        "phase_match": ["toán", "lập trình", "nền tảng", "python"],
        "icon": "🐍",
        "title": "Python thực hành theo mục tiêu chat",
        "desc": "Bổ sung bài tập Python/NumPy/Pandas bám sát yêu cầu mới trong chat.",
        "tags": ["Python", "Cá nhân hóa"],
        "time": "1 tuần",
    },
    {
        "keywords": ["math", "toán", "dai so", "đại số", "xác suất", "thống kê", "statistics"],
        "phase_match": ["toán", "nền tảng"],
        "icon": "➕",
        "title": "Ôn Toán nền tảng theo yêu cầu",
        "desc": "Củng cố đại số tuyến tính, xác suất và thống kê trước khi đi sâu vào ML.",
        "tags": ["Toán học", "Bổ trợ"],
        "time": "1 tuần",
    },
    {
        "keywords": ["machine learning", " ml", "supervised", "unsupervised", "model", "sklearn"],
        "phase_match": ["machine learning", "ml"],
        "icon": "📈",
        "title": "Mini-project Machine Learning",
        "desc": "Thêm mini-project huấn luyện, đánh giá và tinh chỉnh model theo chủ đề bạn hỏi.",
        "tags": ["ML", "Project"],
        "time": "1–2 tuần",
    },
    {
        "keywords": ["deep learning", "neural", "cnn", "transformer", "pytorch", "tensorflow"],
        "phase_match": ["deep learning", "neural"],
        "icon": "🧠",
        "title": "Deep Learning tập trung",
        "desc": "Bổ sung lộ trình thực hành neural networks/CNN/Transformer theo mục tiêu mới.",
        "tags": ["Deep Learning", "Thực hành"],
        "time": "2 tuần",
    },
    {
        "keywords": ["nlp", "llm", "language model", "transformer", "chatbot"],
        "phase_match": ["deep learning", "neural", "nlp"],
        "icon": "💬",
        "title": "NLP/LLM ứng dụng",
        "desc": "Thêm nhánh học NLP, embeddings, transformers và chatbot/LLM project.",
        "tags": ["NLP", "LLM"],
        "time": "2 tuần",
    },
    {
        "keywords": ["project", "dự án", "du an", "portfolio", "deploy", "triển khai"],
        "phase_match": ["dự án", "triển khai", "project"],
        "icon": "🚀",
        "title": "Dự án portfolio theo yêu cầu chat",
        "desc": "Chuyển yêu cầu mới thành một project cuối kỳ có demo, API/UI và báo cáo ngắn.",
        "tags": ["Project", "Portfolio"],
        "time": "1–2 tuần",
    },
]

DEFAULT_RULE = {
    "phase_match": ["dự án", "triển khai", "project"],
    "icon": "✨",
    "title": "Milestone cá nhân hóa từ chat",
    "desc": "Bổ sung nhiệm vụ học tập dựa trên yêu cầu mới bạn vừa nhập trong chat.",
    "tags": ["Cá nhân hóa"],
    "time": "1 tuần",
}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Modify the current roadmap according to the user's chat message."""
    msg = context["message"].lower()
    roadmap = clone_roadmap(context)
    phases = roadmap.setdefault("phases", [])
    if not phases:
        roadmap = load_default_roadmap()
        phases = roadmap.setdefault("phases", [])

    selected = next((rule for rule in TOPIC_RULES if any(k in msg for k in rule["keywords"])), DEFAULT_RULE)

    target_phase = phases[-1]
    for phase in phases:
        title = (phase.get("title") or "").lower()
        if any(k in title for k in selected["phase_match"]):
            target_phase = phase
            break

    milestones = target_phase.setdefault("milestones", [])
    slug = len(milestones) + 1
    target_phase_id = target_phase.get("id") or f"phase-{phases.index(target_phase) + 1}"
    new_id = f"{target_phase_id}-chat-{slug}"
    existing_titles = {str(item.get("title", "")).lower() for item in milestones}
    changed = selected["title"].lower() not in existing_titles
    changes = []

    if changed:
        milestones.append(
            {
                "id": new_id,
                "icon": selected["icon"],
                "status": "active",
                "title": selected["title"],
                "desc": selected["desc"],
                "tags": selected["tags"],
                "time": selected["time"],
            }
        )
        changes.append(f"Added milestone '{selected['title']}' to '{target_phase.get('title')}'.")
    else:
        changes.append(f"Milestone '{selected['title']}' already exists; roadmap kept unchanged.")

    roadmap["title"] = roadmap.get("title") or "Lộ trình học AI cá nhân hóa"
    roadmap["subtitle"] = "Đã cập nhật theo yêu cầu mới trong chat."
    return {
        "tool": "roadmap_modifier",
        "result": roadmap,
        "changed": changed,
        "changes": changes,
    }
