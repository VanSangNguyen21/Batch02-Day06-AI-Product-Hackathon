"""Resource recommender tool."""

from __future__ import annotations

from typing import Any, Dict


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest learning resources based on the user's topic."""
    msg = context["message"].lower()
    if any(k in msg for k in ["python", "pandas", "numpy", "code", "lap trinh", "lập trình"]):
        topic = "python"
        resources = [
            "Kaggle Learn Python",
            "Python for Everybody",
            "Automate the Boring Stuff with Python",
        ]
    elif any(k in msg for k in ["deep learning", "neural", "cnn", "transformer", "pytorch", "tensorflow"]):
        topic = "deep_learning"
        resources = [
            "fast.ai Practical Deep Learning",
            "DeepLearning.AI Neural Networks",
            "PyTorch Tutorials",
        ]
    elif any(k in msg for k in ["machine learning", "ml", "sklearn", "scikit", "model"]):
        topic = "machine_learning"
        resources = [
            "Machine Learning Specialization - Andrew Ng",
            "Google ML Crash Course",
            "Hands-On ML - Aurelien Geron",
        ]
    else:
        topic = "ai_foundation"
        resources = ["Google AI Essentials", "Kaggle Learn", "Elements of AI"]
    return {"tool": "resource_recommender", "result": {"topic": topic, "resources": resources}}
