"""
====================================================
  RAG Quiz Retriever
  Semantic Search for Intelligent Question Selection
  VinUni AI20k Batch 02 · Day 06
====================================================
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Lazy import để avoid loading model nếu không cần
_embedder = None


def get_embedder():
    """
    Lazy load sentence-transformers embedder.
    Sử dụng model nhẹ cho performance.
    """
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("🔄 Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Embedder loaded successfully")
        except ImportError:
            logger.error("❌ sentence-transformers not installed. Install via pip.")
            raise
    return _embedder


class QuizRAGRetriever:
    """
    RAG Retriever để chọn bộ câu hỏi phù hợp dựa trên semantic similarity.
    
    Flow:
    1. Parse user profile (goal + background)
    2. Embed user profile + quiz set metadata
    3. Compute cosine similarity
    4. Rank quiz sets
    5. Return top N quiz sets
    """

    def __init__(self):
        """Khởi tạo retriever"""
        self.embedder = get_embedder()
        self.quiz_embeddings_cache = {}  # Cache embeddings để tránh tính toán lại

    def embed_text(self, text: str) -> np.ndarray:
        """Embed một đoạn text"""
        if not text or not isinstance(text, str):
            logger.warning(f"⚠️ Invalid text for embedding: {text}")
            return np.zeros(384)  # all-MiniLM output dimension
        
        try:
            embedding = self.embedder.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"❌ Error embedding text: {e}")
            return np.zeros(384)

    def get_quiz_embedding(self, quiz_set) -> np.ndarray:
        """Lấy hoặc tính embedding của quiz set (với caching)"""
        if quiz_set.set_id in self.quiz_embeddings_cache:
            return self.quiz_embeddings_cache[quiz_set.set_id]
        
        embedding = self.embed_text(quiz_set.embedding_text)
        self.quiz_embeddings_cache[quiz_set.set_id] = embedding
        return embedding

    def build_user_profile_text(
        self,
        learning_goal: str,
        background: str,
        current_level: str,
        target_role: Optional[str] = None,
        interests: Optional[List[str]] = None
    ) -> str:
        """
        Xây dựng text profile của user để embedding.
        
        Args:
            learning_goal: Mục tiêu học tập (vd: "Learn Deep Learning")
            background: Background (vd: "Software engineer with 5 years experience")
            current_level: Trình độ hiện tại (vd: "intermediate")
            target_role: Target role (vd: "ML Engineer")
            interests: Danh sách topics quan tâm
        """
        profile_parts = [
            learning_goal,
            background,
            f"current level: {current_level}",
        ]
        
        if target_role:
            profile_parts.append(f"target role: {target_role}")
        
        if interests:
            profile_parts.append(f"interests: {', '.join(interests)}")
        
        return " ".join(profile_parts)

    def retrieve_quiz_sets(
        self,
        quiz_sets: List,  # List of QuizSet objects
        learning_goal: str,
        background: str,
        current_level: str,
        target_role: Optional[str] = None,
        interests: Optional[List[str]] = None,
        top_k: int = 1,
        min_similarity: float = 0.3  # Minimum similarity threshold
    ) -> Tuple[List, List[float]]:
        """
        Retrieve quiz sets dựa trên user profile.
        
        Returns:
            (list of selected quiz sets, list of similarity scores)
        """
        # Build user profile text
        user_profile = self.build_user_profile_text(
            learning_goal,
            background,
            current_level,
            target_role,
            interests
        )
        
        logger.info(f"📝 User profile: {user_profile}")
        
        # Embed user profile
        user_embedding = self.embed_text(user_profile)
        
        # Compute similarity với tất cả quiz sets
        similarities = []
        for quiz_set in quiz_sets:
            quiz_embedding = self.get_quiz_embedding(quiz_set)
            
            # Cosine similarity
            similarity = cosine_similarity(
                user_embedding.reshape(1, -1),
                quiz_embedding.reshape(1, -1)
            )[0][0]
            
            similarities.append((quiz_set, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by min_similarity và take top_k
        selected = [
            (quiz_set, sim) for quiz_set, sim in similarities
            if sim >= min_similarity
        ][:top_k]
        
        # Log results
        logger.info(f"🔍 Retrieved {len(selected)} quiz sets")
        for quiz_set, sim in selected:
            logger.info(f"  - {quiz_set.name}: {sim:.3f}")
        
        if not selected:
            logger.warning(f"⚠️ No quiz sets found with similarity >= {min_similarity}")
            logger.info("Returning top 1 anyway as fallback")
            selected = similarities[:1]
        
        quiz_sets_result = [qs for qs, _ in selected]
        scores = [sim for _, sim in selected]
        
        return quiz_sets_result, scores

    def retrieve_quiz_set_by_metadata(
        self,
        quiz_sets: List,
        difficulty: Optional[str] = None,
        topics: Optional[List[str]] = None,
        goals: Optional[List[str]] = None
    ) -> List:
        """
        Fallback method: Retrieve quiz sets dựa trên metadata matching.
        
        Dùng khi semantic similarity không đủ hoặc muốn hardcoded logic.
        """
        filtered = quiz_sets
        
        if difficulty:
            filtered = [q for q in filtered if q.difficulty == difficulty]
        
        if topics:
            filtered = [
                q for q in filtered
                if any(t in q.topics for t in topics)
            ]
        
        if goals:
            filtered = [
                q for q in filtered
                if any(g in q.target_goals for g in goals)
            ]
        
        return filtered


# Global retriever instance
_retriever = None


def get_retriever() -> QuizRAGRetriever:
    """Lấy global retriever instance (singleton)"""
    global _retriever
    if _retriever is None:
        _retriever = QuizRAGRetriever()
    return _retriever


def select_quiz_for_user(
    quiz_sets: List,
    learning_goal: str,
    background: str,
    current_level: str,
    target_role: Optional[str] = None,
    interests: Optional[List[str]] = None,
    use_semantic: bool = True,
    top_k: int = 1
) -> Tuple[Optional, float]:
    """
    Main function: Chọn 1 quiz set phù hợp cho user.
    
    Returns:
        (selected_quiz_set, similarity_score)
    """
    retriever = get_retriever()
    
    try:
        if use_semantic:
            selected_sets, scores = retriever.retrieve_quiz_sets(
                quiz_sets,
                learning_goal,
                background,
                current_level,
                target_role,
                interests,
                top_k
            )
            
            if selected_sets:
                return selected_sets[0], scores[0]
        
        # Fallback to metadata matching
        logger.info("📌 Falling back to metadata matching")
        # Infer difficulty từ current_level
        difficulty_map = {
            "beginner": "easy",
            "intermediate": "medium",
            "advanced": "hard",
            "expert": "hard"
        }
        difficulty = difficulty_map.get(current_level.lower(), "mixed")
        
        filtered = retriever.retrieve_quiz_set_by_metadata(
            quiz_sets,
            difficulty=difficulty
        )
        
        if filtered:
            return filtered[0], 0.5  # Default score
        
        # Last resort: return first quiz set
        logger.warning("⚠️ No quiz set matched, returning default")
        return quiz_sets[0] if quiz_sets else None, 0.3
    
    except Exception as e:
        logger.error(f"❌ Error in select_quiz_for_user: {e}")
        return quiz_sets[0] if quiz_sets else None, 0.0
