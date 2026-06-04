/**
 * ============================================================
 * RAG Quiz Selection Module
 * Dynamic Quiz Selection based on User Profile
 * VinUni AI20k Batch 02 · Day 06
 * ============================================================
 */

'use strict';

/* ─── RAG QUIZ ENDPOINTS ──────────────────────────────────────── */
const RAG_ENDPOINTS = {
  selectQuiz: `${API_BASE}/api/select-quiz`,
  listQuizSets: `${API_BASE}/api/list-quiz-sets`,
  quizById: (id) => `${API_BASE}/api/quiz-by-id/${id}`,
};

/**
 * QuizSelector Module — Handles RAG-based quiz selection
 */
const QuizSelector = {
  /**
   * Select quiz based on user profile using RAG
   * @param {Object} userProfile - User profile data
   * @returns {Promise<Object>} - Selected quiz data
   */
  async selectQuizForUser(userProfile) {
    try {
      console.log('🎯 Selecting quiz for user profile:', userProfile);

      const request = {
        user_id: userProfile.userId || 'user_' + Date.now(),
        learning_goal: userProfile.goal_why || 'Learn AI',
        background: userProfile.goal_job || 'Student',
        current_level: this._inferLevel(userProfile.quiz_score || 0),
        target_role: userProfile.target_role || null,
        interests: userProfile.interests || null,
        use_semantic: true,
      };

      console.log('📤 Sending select-quiz request:', request);

      const response = await fetch(RAG_ENDPOINTS.selectQuiz, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to select quiz');
      }

      const data = await response.json();
      console.log('✅ Quiz selected:', {
        name: data.quiz_set_name,
        method: data.retrieval_method,
        score: data.similarity_score,
      });

      return data;
    } catch (error) {
      console.error('❌ Quiz selection error:', error);
      throw error;
    }
  },

  /**
   * Infer difficulty level from quiz score
   * @param {number} score - Quiz score (0-10)
   * @returns {string} - Level (beginner|intermediate|advanced|expert)
   */
  _inferLevel(score) {
    if (score <= 3) return 'beginner';
    if (score <= 6) return 'intermediate';
    if (score <= 8) return 'advanced';
    return 'expert';
  },

  /**
   * Get quiz by ID (direct access)
   * @param {string} quizId - Quiz set ID
   * @returns {Promise<Object>} - Quiz data
   */
  async getQuizById(quizId) {
    try {
      console.log(`📥 Fetching quiz: ${quizId}`);

      const response = await fetch(RAG_ENDPOINTS.quizById(quizId));

      if (!response.ok) {
        throw new Error(`Failed to fetch quiz: ${quizId}`);
      }

      return await response.json();
    } catch (error) {
      console.error('❌ Quiz fetch error:', error);
      throw error;
    }
  },

  /**
   * List all available quiz sets
   * @returns {Promise<Array>} - List of quiz sets
   */
  async listQuizSets() {
    try {
      console.log('📋 Listing all quiz sets');

      const response = await fetch(RAG_ENDPOINTS.listQuizSets);

      if (!response.ok) {
        throw new Error('Failed to list quiz sets');
      }

      const data = await response.json();
      console.log(`✅ Found ${data.total_sets} quiz sets`);

      return data.quiz_sets;
    } catch (error) {
      console.error('❌ Quiz list error:', error);
      throw error;
    }
  },

  /**
   * Format quiz data for display
   * @param {Object} quizData - Raw quiz data from API
   * @returns {Object} - Formatted quiz data
   */
  formatQuizData(quizData) {
    return {
      id: quizData.quiz_set_id,
      name: quizData.quiz_set_name,
      description: quizData.quiz_set_description,
      difficulty: quizData.difficulty,
      topics: quizData.topics,
      questions: quizData.questions.map((q) => ({
        id: q.id,
        text: q.text,
        options: q.options,
        correct: q.correct,
        explanation: q.explanation,
      })),
      metadata: {
        retrievalMethod: quizData.retrieval_method,
        similarityScore: quizData.similarity_score,
        goals: quizData.target_goals,
      },
    };
  },

  /**
   * Display quiz info toast
   * @param {Object} quizData - Quiz data from API
   */
  showQuizInfoToast(quizData) {
    const methodLabel = {
      semantic: '🎯 AI-matched',
      metadata: '📌 Category-matched',
      fallback: '📦 Default',
    }[quizData.retrieval_method] || 'Unknown';

    showToast(
      `${methodLabel} quiz selected: <strong>${quizData.quiz_set_name}</strong><br/>` +
      `Difficulty: ${quizData.difficulty} | Topics: ${quizData.topics.join(', ')}<br/>` +
      `Match score: ${(quizData.similarity_score * 100).toFixed(0)}%`,
      'info',
      5000
    );
  },
};

/**
 * Integration Point: Call this when user fills form but before quiz starts
 * @param {Object} userProfile - User profile from form
 */
async function initializeRAGQuiz(userProfile) {
  try {
    console.log('🚀 Initializing RAG quiz selection...');

    // Show loading toast
    showToast('🔍 Finding the perfect quiz for you...', 'info', 0);

    // Call RAG selector
    const selectedQuiz = await QuizSelector.selectQuizForUser(userProfile);

    // Hide loading toast
    document.querySelectorAll('.toast').forEach((t) => {
      if (t.textContent.includes('Finding')) t.remove();
    });

    // Show quiz info
    QuizSelector.showQuizInfoToast(selectedQuiz);

    // Format and store in AppState
    const formattedQuiz = QuizSelector.formatQuizData(selectedQuiz);

    // Store original quiz data for analysis
    AppState.selectedQuizData = selectedQuiz;

    return formattedQuiz;
  } catch (error) {
    console.error('❌ RAG initialization failed:', error);
    showToast(`❌ Quiz selection failed: ${error.message}. Using default quiz...`, 'error', 5000);

    // Fallback to default quiz
    return null;
  }
}

/**
 * Load default quiz (fallback)
 * @returns {Promise<Object>} - Default quiz data
 */
async function loadDefaultQuiz() {
  try {
    console.log('📦 Loading default quiz (fallback)...');
    return await QuizSelector.getQuizById('fund-001');
  } catch (error) {
    console.error('❌ Failed to load default quiz:', error);
    throw error;
  }
}

/**
 * Helper: Toast notification function (assuming it exists in app.js)
 * If not available, provide simple implementation
 */
if (typeof showToast === 'undefined') {
  window.showToast = function (message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<div class="toast-content">${message}</div>`;
    document.body.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => toast.remove(), duration);
    }

    return toast;
  };
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { QuizSelector, initializeRAGQuiz, loadDefaultQuiz };
}
