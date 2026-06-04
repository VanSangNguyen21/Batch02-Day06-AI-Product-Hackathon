/**
 * ============================================================
 * AI LEARNING PATH PERSONALIZER — MAIN APPLICATION SCRIPT
 * VinUni Batch 02 · Day 05
 *
 * Architecture:
 *   - AppState: single source of truth
 *   - Tab system
 *   - Multi-step form + validation
 *   - Quiz engine (10 questions, scoring, confidence)
 *   - Chat interface + rate limiter
 *   - Roadmap renderer (tree from JSON)
 *   - Fallback / Failure / Correction modes
 *   - Toast notification system
 *   - API integration: /api/analyze, /api/chat, /api/feedback
 * ============================================================
 */

'use strict';

/* ─── API CONFIGURATION ──────────────────────────────────────── */
const API_BASE = (() => {
  const origin = window.location.origin;
  if (origin && origin !== 'null' && /^https?:\/\//.test(origin)) {
    return origin;
  }
  return localStorage.getItem('AI_PATH_API_BASE') || 'http://127.0.0.1:8000';
})();
const ENDPOINTS = {
  analyze:  `${API_BASE}/api/analyze`,
  chat:     `${API_BASE}/api/chat`,
  feedback: `${API_BASE}/api/feedback`,
  modelConfig: `${API_BASE}/api/model-config`,
  authMe:   `${API_BASE}/api/auth/me`,
  login:    `${API_BASE}/api/auth/login`,
  register: `${API_BASE}/api/auth/register`,
  logout:   `${API_BASE}/api/auth/logout`,
  progress: `${API_BASE}/api/progress`,
};

const LOCAL_AUTH_KEY = 'AI_PATH_LOCAL_AUTH_USER';

function getLocalAuthUser() {
  try {
    const raw = localStorage.getItem(LOCAL_AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    localStorage.removeItem(LOCAL_AUTH_KEY);
    return null;
  }
}

/* ─── INPUT SANITIZATION GUARDRAIL ──────────────────────────── */
/**
 * Basic frontend XSS / injection guardrail.
 * Strips script tags, HTML tags, and dangerous patterns.
 * @param {string} input - Raw user input
 * @returns {string} - Sanitized string
 */
function sanitizeInput(input) {
  if (typeof input !== 'string') return '';
  return input
    .replace(/<script[\s\S]*?<\/script>/gi, '') // Remove script blocks
    .replace(/<[^>]+>/g, '')                      // Strip HTML tags
    .replace(/javascript:/gi, '')                 // Remove JS protocol
    .replace(/on\w+\s*=/gi, '')                   // Remove event handlers
    .replace(/[<>]/g, (c) => c === '<' ? '&lt;' : '&gt;') // Encode angle brackets
    .trim()
    .substring(0, 1000);                          // Hard length limit
}

/* ─── APP STATE ──────────────────────────────────────────────── */
/**
 * Central state object — single source of truth.
 * Never mutate directly from UI handlers; use setState().
 */
const AppState = {
  // Form data
  userData: {
    goal_why:   '',
    goal_time:  '',
    goal_job:   '',
    goal_style: '',
  },

  // Quiz
  quiz: {
    currentIndex: 0,
    answers: [], // index → selected option index
    startTime:  null,
    endTime:    null,
    timerInterval: null,
  },

  // Results
  results: {
    score:       0,       // 0–10
    confidence:  0,       // 0–100
    level:       '',      // 'Beginner' | 'Intermediate' | 'Advanced'
    roadmap:     null,    // JSON roadmap data
    isFallback:  false,
    isFailure:   false,
    sessionId:   null,
  },

  // Chat
  chat: {
    history:        [],   // { role: 'user'|'ai', content: string, time: Date }
    rateLimit: {
      remaining:    5,
      max:          5,
      unlimited:    false,
      modelName:    '',
      provider:     '',
      resetAt:      null, // timestamp when limit resets
      countdown:    null, // setInterval ref
    },
    totalTokens:   0,
    totalCostUSD:  0,
    isLoading:     false,
  },

  // Milestones completion
  completedMilestones: new Set(),

  // UI state
  ui: {
    currentStep:   1,
    feedbackRating: 0,
    userId:         null,
    user:           null,
  },
};

/* ─── PROGRESS PERSISTENCE ──────────────────────────────────── */
const ProgressStore = {
  version: 1,
  saveTimer: null,

  key(userId) {
    return `AI_PATH_PROGRESS_V${this.version}_${userId}`;
  },

  save() {
    const userId = AppState.ui.userId;
    if (!userId) return;

    const payload = this.snapshot();
    localStorage.setItem(this.key(userId), JSON.stringify(payload));
    this.saveRemote(payload);
  },

  snapshot() {
    return {
      savedAt: Date.now(),
      userData: AppState.userData,
      quiz: {
        currentIndex: AppState.quiz.currentIndex,
        answers: AppState.quiz.answers,
        startTime: AppState.quiz.startTime,
        endTime: AppState.quiz.endTime,
      },
      results: AppState.results,
      chat: {
        history: AppState.chat.history,
        totalTokens: AppState.chat.totalTokens,
        totalCostUSD: AppState.chat.totalCostUSD,
      },
      completedMilestones: Array.from(AppState.completedMilestones),
      ui: {
        currentStep: AppState.ui.currentStep,
      },
    };
  },

  saveRemote(payload) {
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(async () => {
      try {
        await fetch(ENDPOINTS.progress, {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ progress: payload }),
        });
      } catch (err) {
        console.warn('[Progress] Remote save failed:', err.message);
      }
    }, 350);
  },

  loadLocal(userId) {
    try {
      const raw = localStorage.getItem(this.key(userId));
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  clear(userId = AppState.ui.userId) {
    if (userId) localStorage.removeItem(this.key(userId));
    fetch(ENDPOINTS.progress, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  },

  apply(saved) {
    AppState.userData = { ...AppState.userData, ...(saved.userData || {}) };
    AppState.quiz = {
      ...AppState.quiz,
      ...(saved.quiz || {}),
      timerInterval: null,
    };
    AppState.results = { ...AppState.results, ...(saved.results || {}) };
    AppState.chat = {
      ...AppState.chat,
      history: saved.chat?.history || [],
      totalTokens: saved.chat?.totalTokens || 0,
      totalCostUSD: saved.chat?.totalCostUSD || 0,
      isLoading: false,
    };
    AppState.completedMilestones = new Set(saved.completedMilestones || []);
    AppState.ui.currentStep = saved.ui?.currentStep || AppState.ui.currentStep;

    this.restoreInputs();
    this.restoreView();
    return true;
  },

  restore(userId) {
    const local = this.loadLocal(userId);
    const restored = local ? this.apply(local) : false;
    this.restoreRemote(userId, local);
    return restored;
  },

  async restoreRemote(userId, localProgress = null) {
    try {
      const response = await fetch(ENDPOINTS.progress, { credentials: 'include' });
      if (!response.ok) return;
      const data = await response.json();
      if (!data.has_progress || !data.progress) return;

      const remote = data.progress;
      const remoteIsNewer = !localProgress || (remote.savedAt || 0) > (localProgress.savedAt || 0);
      if (!remoteIsNewer) return;

      localStorage.setItem(this.key(userId), JSON.stringify(remote));
      this.apply(remote);
    } catch (err) {
      console.warn('[Progress] Remote restore failed:', err.message);
    }
  },

  restoreInputs() {
    const fields = {
      'goal-why': AppState.userData.goal_why,
      'goal-time': AppState.userData.goal_time,
      'goal-style': AppState.userData.goal_style,
      'goal-job': AppState.userData.goal_job,
    };

    Object.entries(fields).forEach(([id, value]) => {
      const el = $(id);
      if (!el) return;
      el.value = value || '';
      el.classList.toggle('has-value', Boolean(value));
    });
  },

  restoreView() {
    const hasResults = Boolean(AppState.results.roadmap);
    const hasQuizResult = Boolean(AppState.quiz.endTime || AppState.results.level || AppState.results.score);
    const formSection = $('form-section');
    const resultsSection = $('results-section');

    if (hasResults && !resultsSection) {
      goToWorkspace(false);
      return;
    }

    if (!hasResults && isWorkspacePage() && !hasQuizResult) {
      window.location.href = 'main.html';
      return;
    }

    if ((hasResults || (isWorkspacePage() && hasQuizResult)) && resultsSection) {
      if (formSection) formSection.classList.add('hidden');
      resultsSection.classList.remove('hidden');
      ResultsUI.renderExisting();
      return;
    }

    if (!formSection || !resultsSection) return;

    formSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    StepForm.goToStep(AppState.ui.currentStep || 1, { restartQuiz: false });
  },
};

/* ─── STATE HELPERS ──────────────────────────────────────────── */
function setState(path, value) {
  const keys = path.split('.');
  let obj = AppState;
  keys.slice(0, -1).forEach(k => { obj = obj[k]; });
  obj[keys[keys.length - 1]] = value;
}

/* --- DATA LOADING ------------------------------------------------ */
let QUIZ_QUESTIONS = [];
let QUIZ_QUESTION_BANK = [];
let DEFAULT_ROADMAP = null;
let STAR_LABELS = {};
let SCORE_LEVELS = [];

async function loadJsonData(path, label) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${label} HTTP ${response.status}`);
  return response.json();
}

async function loadAppData() {
  try {
    const data = await loadJsonData('src/app_data.json', 'App data');
    if (!data || !data.defaultRoadmap || !data.starLabels || !Array.isArray(data.scoreLevels)) {
      throw new Error('app_data.json is missing required fields');
    }

    DEFAULT_ROADMAP = data.defaultRoadmap;
    STAR_LABELS = data.starLabels;
    SCORE_LEVELS = data.scoreLevels;
  } catch (err) {
    console.error('[App Data] Could not load app_data.json:', err.message);
    DEFAULT_ROADMAP = null;
    STAR_LABELS = {};
    SCORE_LEVELS = [];
  }
}

function isValidQuestion(question) {
  return Boolean(
    question &&
    typeof question.text === 'string' &&
    Array.isArray(question.options) &&
    question.options.length >= 2 &&
    Number.isInteger(question.correct) &&
    question.correct >= 0 &&
    question.correct < question.options.length
  );
}

async function loadQuizQuestionBank() {
  try {
    const data = await loadJsonData('src/quiz_questions.json', 'Quiz bank');
    const topics = Array.isArray(data) ? data : data.topics;
    if (!Array.isArray(topics) || topics.length !== 10) {
      throw new Error('Quiz bank must contain exactly 10 topics');
    }

    const normalizedTopics = topics.map((variants, topicIndex) => {
      if (!Array.isArray(variants) || variants.length === 0) {
        throw new Error(`Topic ${topicIndex + 1} has no variants`);
      }
      const validVariants = variants.filter(isValidQuestion);
      if (validVariants.length === 0) {
        throw new Error(`Topic ${topicIndex + 1} has no valid variants`);
      }
      return validVariants;
    });

    QUIZ_QUESTION_BANK = normalizedTopics;
    QUIZ_QUESTIONS = normalizedTopics.map((variants, topicIndex) => cloneQuizQuestion(variants[0], topicIndex, 0));
  } catch (err) {
    console.error('[Quiz Bank] Could not load quiz_questions.json:', err.message);
    QUIZ_QUESTION_BANK = [];
    QUIZ_QUESTIONS = [];
  }
}

function cloneQuizQuestion(question, topicIndex, variantIndex) {
  return {
    ...question,
    id: `${topicIndex + 1}-${question.id || variantIndex + 1}`,
    options: question.options.map(option => ({ ...option })),
  };
}

let lastQuizSignature = '';

function buildRandomQuizQuestions() {
  if (!Array.isArray(QUIZ_QUESTION_BANK) || QUIZ_QUESTION_BANK.length === 0) {
    return [];
  }

  let selectedIndexes = [];
  let signature = '';

  for (let attempt = 0; attempt < 8; attempt += 1) {
    selectedIndexes = QUIZ_QUESTION_BANK.map(variants => Math.floor(Math.random() * variants.length));
    signature = selectedIndexes.join('-');
    if (signature !== lastQuizSignature) break;
  }

  lastQuizSignature = signature;
  return QUIZ_QUESTION_BANK.map((variants, topicIndex) => (
    cloneQuizQuestion(variants[selectedIndexes[topicIndex]], topicIndex, selectedIndexes[topicIndex])
  ));
}

/* --- DOM REFERENCES (cached on init) ---------------------------- */
const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

function isWorkspacePage() {
  return document.body.classList.contains('page-workspace');
}

function goToWorkspace(shouldAnalyze = false) {
  window.location.href = shouldAnalyze ? 'workspace.html?analyze=1' : 'workspace.html';
}

/* ─── TOAST SYSTEM ───────────────────────────────────────────── */
const Toast = {
  container: null,

  init() {
    this.container = $('toast-container');
  },

  /**
   * Show a toast notification.
   * @param {Object} opts - { title, message, type: 'success'|'error'|'warning'|'info', duration }
   */
  show({ title = '', message = '', type = 'info', duration = 4000 } = {}) {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${icons[type]}</span>
      <div class="toast-body">
        ${title    ? `<div class="toast-title">${title}</div>` : ''}
        ${message  ? `<div class="toast-message">${message}</div>` : ''}
      </div>
      <span class="toast-close" aria-label="Đóng">×</span>
    `;
    this.container.appendChild(el);

    // Close handler
    el.querySelector('.toast-close').addEventListener('click', () => this._remove(el));

    // Auto-remove
    const timer = setTimeout(() => this._remove(el), duration);
    el._timer = timer;
  },

  _remove(el) {
    clearTimeout(el._timer);
    el.classList.add('closing');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    // Fallback if animation doesn't fire
    setTimeout(() => el.remove(), 500);
  },

  success(title, message) { this.show({ title, message, type: 'success' }); },
  error(title, message)   { this.show({ title, message, type: 'error',   duration: 6000 }); },
  warning(title, message) { this.show({ title, message, type: 'warning' }); },
  info(title, message)    { this.show({ title, message, type: 'info' }); },
};

/* ─── COST DISPLAY ───────────────────────────────────────────── */
const CostDisplay = {
  el:    null,
  label: null,

  init() {
    this.el    = $('cost-display');
    this.label = $('cost-label');
  },

  update(tokens, costUSD) {
    AppState.chat.totalTokens  += tokens;
    AppState.chat.totalCostUSD += costUSD;
    const total = AppState.chat.totalTokens;
    const cost  = AppState.chat.totalCostUSD.toFixed(4);
    if (this.label) this.label.textContent = `${total.toLocaleString()} tokens · $${cost}`;
    ProgressStore.save();
  },
};

/* ─── MODEL LIMIT POLICY ────────────────────────────────────── */
const ModelConfig = {
  async load() {
    try {
      const response = await fetch(ENDPOINTS.modelConfig, { credentials: 'include' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const rl = AppState.chat.rateLimit;

      rl.unlimited = Boolean(data.unlimited_questions || data.is_local);
      rl.modelName = data.model || '';
      rl.provider = data.provider || '';

      if (rl.unlimited) {
        rl.remaining = Infinity;
      } else {
        rl.max = data.question_limit || rl.max || 5;
        rl.remaining = rl.max;
      }

      if (typeof ChatUI !== 'undefined' && ChatUI._updateRateLimit) {
        ChatUI._updateRateLimit();
      }
    } catch (err) {
      console.warn('[Model Config] Using limited default policy:', err.message);
    }
  },
};

/* ─── AUTH UI ───────────────────────────────────────────────── */
const AuthUI = {
  currentMode: 'login',

  init() {
    this.authSection = $('auth-section');
    this.appContainer = $('app-container');
    this.accountMenu = $('account-menu');
    this.loginTab = $('auth-login-tab');
    this.registerTab = $('auth-register-tab');
    this.loginForm = $('login-form');
    this.registerForm = $('register-form');

    if (this.loginTab && this.registerTab && this.loginForm && this.registerForm) {
      this.loginTab.addEventListener('click', () => this.switchMode('login'));
      this.registerTab.addEventListener('click', () => this.switchMode('register'));
      this.loginForm.addEventListener('submit', (e) => this.handleLogin(e));
      this.registerForm.addEventListener('submit', (e) => this.handleRegister(e));
    }

    const logoutBtn = $('btn-logout');
    if (logoutBtn) logoutBtn.addEventListener('click', () => this.logout());
  },

  async checkSession() {
    const localUser = getLocalAuthUser();
    if (localUser) {
      this.showAuthenticated(localUser, false);
      return;
    }

    try {
      const response = await fetch(ENDPOINTS.authMe, { credentials: 'include' });
      if (!response.ok) throw new Error('not_authenticated');
      const data = await response.json();
      this.showAuthenticated(data.user, false);
    } catch {
      this.showUnauthenticated(false);
    }
  },

  switchMode(mode) {
    this.currentMode = mode;
    const isLogin = mode === 'login';
    this.loginTab.classList.toggle('active', isLogin);
    this.registerTab.classList.toggle('active', !isLogin);
    this.loginForm.classList.toggle('hidden', !isLogin);
    this.registerForm.classList.toggle('hidden', isLogin);
    $('login-error').textContent = '';
    $('register-error').textContent = '';
  },

  async handleLogin(event) {
    event.preventDefault();
    await this.submitAuth('login', {
      email: sanitizeInput($('login-email').value),
      password: $('login-password').value,
    });
  },

  async handleRegister(event) {
    event.preventDefault();
    await this.submitAuth('register', {
      name: sanitizeInput($('register-name').value),
      email: sanitizeInput($('register-email').value),
      password: $('register-password').value,
    });
  },

  async submitAuth(mode, payload) {
    const errorEl = mode === 'login' ? $('login-error') : $('register-error');
    errorEl.textContent = '';

    try {
      const response = await fetch(mode === 'login' ? ENDPOINTS.login : ENDPOINTS.register, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Không thể xử lý yêu cầu.');
      }

      this.showAuthenticated(data.user, true);
      Toast.success(mode === 'login' ? 'Đăng nhập thành công' : 'Tạo tài khoản thành công', 'Bạn có thể bắt đầu cá nhân hóa lộ trình.');
    } catch (err) {
      errorEl.textContent = err.message;
    }
  },

  showAuthenticated(user, shouldScroll = true) {
    AppState.ui.user = user;
    AppState.ui.userId = user.user_id;

    if (this.authSection) this.authSection.classList.add('hidden');
    if (this.appContainer) this.appContainer.classList.remove('hidden');
    if (this.accountMenu) this.accountMenu.classList.remove('hidden');

    if ($('account-name')) $('account-name').textContent = user.name;
    if ($('account-email')) $('account-email').textContent = user.email;
    if ($('account-avatar')) $('account-avatar').textContent = (user.name || user.email || 'U').trim().charAt(0).toUpperCase();

    const restored = ProgressStore.restore(user.user_id);

    if (shouldScroll) {
      const target = restored && AppState.results.roadmap ? $('results-section') : $('form-section');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  showUnauthenticated(shouldScroll = true) {
    AppState.ui.user = null;
    AppState.ui.userId = null;

    if (!this.authSection) {
      window.location.href = 'auth.html?mode=login';
      return;
    }

    this.authSection.classList.remove('hidden');
    if (this.appContainer) this.appContainer.classList.add('hidden');
    if (this.accountMenu) this.accountMenu.classList.add('hidden');
    if (shouldScroll) {
      this.authSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  async logout() {
    try {
      await fetch(ENDPOINTS.logout, { method: 'POST', credentials: 'include' });
    } finally {
      localStorage.removeItem(LOCAL_AUTH_KEY);
      SupportModal._resetSession({ keepAuth: false, silent: true, clearProgress: false });
      this.showUnauthenticated(true);
      Toast.info('Đã đăng xuất', 'Hẹn gặp lại bạn ở phiên học tiếp theo.');
    }
  },
};

/* ─── STEP FORM CONTROLLER ───────────────────────────────────── */
const StepForm = {
  step1El: null,
  step2El: null,
  ind1:    null,
  ind2:    null,
  line1:   null,

  init() {
    this.step1El = $('step-1');
    this.step2El = $('step-2');
    this.ind1    = $('step-ind-1');
    this.ind2    = $('step-ind-2');
    this.line1   = $('step-line-1');
    if (!$('goal-form') || !this.step1El || !this.step2El) return;

    // Form submission (Step 1 → Step 2)
    $('goal-form').addEventListener('submit', (e) => {
      e.preventDefault();
      this._submitStep1();
    });

    // Also mark selects as has-value for floating label
    ['goal-why', 'goal-time', 'goal-style', 'goal-job'].forEach(id => {
      const el = $(id);
      if (!el) return;
      el.addEventListener('change', () => {
        el.classList.toggle('has-value', el.value !== '');
      });
    });
  },

  _validateStep1() {
    let valid = true;
    const why   = $('goal-why').value;
    const time  = $('goal-time').value;
    const style = $('goal-style').value;
    const job   = $('goal-job').value;

    $('err-why').textContent   = why   ? '' : 'Vui lòng chọn mục đích học AI.';
    $('err-time').textContent  = time  ? '' : 'Vui lòng điền số tiếng học mỗi tuần.';
    $('err-style').textContent = style ? '' : 'Vui lòng chọn hình thức học ưa thích.';
    $('err-job').textContent   = job   ? '' : 'Vui lòng nhập công việc hiện tại.';

    // Kiểm tra số tiếng 1-40
    if (time) {
      const hours = parseInt(time, 10);
      if (isNaN(hours) || hours < 1 || hours > 40) {
        $('err-time').textContent = 'Thời gian học phải từ 1 đến 40 tiếng/tuần.';
        valid = false;
      }
    }

    if (!why || !time || !style || !job) valid = false;
    return valid;
  },

  _submitStep1() {
    if (!this._validateStep1()) return;

    // Save to state
    AppState.userData.goal_why   = sanitizeInput($('goal-why').value);
    AppState.userData.goal_time  = sanitizeInput($('goal-time').value);
    AppState.userData.goal_style = sanitizeInput($('goal-style').value);
    AppState.userData.goal_job   = sanitizeInput($('goal-job').value);
    ProgressStore.save();

    this.goToStep(2);
  },

  goToStep(step, { restartQuiz = true } = {}) {
    AppState.ui.currentStep = step;

    if (step === 1) {
      this.step1El.classList.remove('hidden');
      this.step2El.classList.add('hidden');
      this.ind1.classList.add('active');
      this.ind1.classList.remove('completed');
      this.ind2.classList.remove('active', 'completed');
      this.line1.classList.remove('active');
    } else if (step === 2) {
      this.step1El.classList.add('hidden');
      this.step2El.classList.remove('hidden');
      this.ind1.classList.remove('active');
      this.ind1.classList.add('completed');
      this.ind2.classList.add('active');
      this.line1.classList.add('active');
      if (restartQuiz) {
        Quiz.start();
      } else {
        Quiz.resume();
      }
    }
  },
};

/* ─── QUIZ ENGINE ────────────────────────────────────────────── */
const Quiz = {
  _timerEl:     null,
  _progressFill:null,
  _progressLabel:null,
  _cardEl:      null,
  _qNumber:     null,
  _qText:       null,
  _qOptions:    null,
  _qFeedback:   null,
  _dotsEl:      null,
  _prevBtn:     null,
  _nextBtn:     null,

  init() {
    this._timerEl      = $('quiz-time-display');
    this._progressFill = $('quiz-progress-fill');
    this._progressLabel= $('quiz-progress-label');
    this._cardEl       = $('question-card');
    this._qNumber      = $('q-number');
    this._qText        = $('q-text');
    this._qOptions     = $('q-options');
    this._qFeedback    = $('q-feedback');
    this._dotsEl       = $('quiz-dots');
    this._prevBtn      = $('btn-quiz-prev');
    this._nextBtn      = $('btn-quiz-next');
    if (!this._cardEl || !this._qOptions || !this._prevBtn || !this._nextBtn) return;

    this._prevBtn.addEventListener('click', () => this._navigate(-1));
  },

  start() {
    QUIZ_QUESTIONS = buildRandomQuizQuestions();
    if (QUIZ_QUESTIONS.length === 0) {
      Toast.error('Không tải được câu hỏi', 'Kiểm tra file src/quiz_questions.json rồi tải lại trang.');
      return;
    }

    AppState.quiz.currentIndex = 0;
    AppState.quiz.answers      = new Array(QUIZ_QUESTIONS.length).fill(null);
    AppState.quiz.startTime    = Date.now();
    AppState.quiz.endTime      = null;

    // Build dots
    this._buildDots();

    // Render first question
    this._renderQuestion(0);

    // Start timer
    this._startTimer();

    Toast.info('Bài kiểm tra bắt đầu!', '10 câu hỏi về nền tảng AI. Chọn đáp án tốt nhất!');
    ProgressStore.save();
  },

  resume() {
    this._buildDots();
    const index = Math.min(AppState.quiz.currentIndex || 0, QUIZ_QUESTIONS.length - 1);
    this._renderQuestion(index);
    if (!AppState.quiz.endTime) {
      if (!AppState.quiz.startTime) AppState.quiz.startTime = Date.now();
      this._startTimer();
    }
  },

  _startTimer() {
    if (AppState.quiz.timerInterval) clearInterval(AppState.quiz.timerInterval);
    AppState.quiz.timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - AppState.quiz.startTime) / 1000);
      const m = Math.floor(elapsed / 60).toString().padStart(1, '0');
      const s = (elapsed % 60).toString().padStart(2, '0');
      if (this._timerEl) this._timerEl.textContent = `${m}:${s}`;
    }, 1000);
  },

  _buildDots() {
    this._dotsEl.innerHTML = QUIZ_QUESTIONS.map((_, i) => `
      <div class="quiz-dot" id="qdot-${i}" title="Câu ${i + 1}" data-index="${i}"></div>
    `).join('');

    this._dotsEl.querySelectorAll('.quiz-dot').forEach(dot => {
      dot.addEventListener('click', () => {
        const idx = parseInt(dot.dataset.index);
        this._navigate(idx - AppState.quiz.currentIndex);
      });
    });
  },

  _updateDots() {
    QUIZ_QUESTIONS.forEach((q, i) => {
      const dot = $(`qdot-${i}`);
      if (!dot) return;
      dot.className = 'quiz-dot';
      if (i === AppState.quiz.currentIndex) { dot.classList.add('active'); return; }
      const answer = AppState.quiz.answers[i];
      if (answer === null) return;
      if (answer === q.correct) dot.classList.add('correct');
      else dot.classList.add('wrong');
    });
  },

  _renderQuestion(index) {
    const q = QUIZ_QUESTIONS[index];
    const selected = AppState.quiz.answers[index];

    // Animate card
    this._cardEl.style.animation = 'none';
    requestAnimationFrame(() => {
      this._cardEl.style.animation = 'slideUp 0.3s ease both';
    });

    this._qNumber.textContent = `Câu ${index + 1}`;
    this._qText.textContent   = q.text;

    // Render options
    this._qOptions.innerHTML = q.options.map((opt, i) => `
      <button
        class="option-btn ${selected !== null ? (i === q.correct ? 'correct' : (selected === i ? 'wrong' : '')) : (selected === i ? 'selected' : '')}"
        data-index="${i}"
        ${selected !== null ? 'disabled' : ''}
        aria-pressed="${selected === i}"
      >
        <span class="opt-label">${opt.label}</span>
        <span>${opt.text}</span>
      </button>
    `).join('');

    // Attach click handlers (only if not already answered)
    if (selected === null) {
      this._qOptions.querySelectorAll('.option-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          this._selectAnswer(index, parseInt(btn.dataset.index));
        });
      });
    }

    // Show feedback if already answered
    if (selected !== null) {
      const isCorrect = (selected === q.correct);
      this._qFeedback.className = `question-feedback ${isCorrect ? 'correct' : 'wrong'}`;
      this._qFeedback.textContent = isCorrect
        ? `✓ Chính xác! ${q.explanation}`
        : `✗ Sai. Đáp án đúng: ${q.options[q.correct].text}. ${q.explanation}`;
    } else {
      this._qFeedback.className = 'question-feedback';
      this._qFeedback.textContent = '';
    }

    // Update progress
    const answered = AppState.quiz.answers.filter(a => a !== null).length;
    const pct = ((index + 1) / QUIZ_QUESTIONS.length) * 100;
    this._progressFill.style.width  = `${pct}%`;
    this._progressLabel.textContent = `Câu ${index + 1} / ${QUIZ_QUESTIONS.length}`;

    // Update nav buttons
    this._prevBtn.disabled = (index === 0);
    this._nextBtn.disabled = (selected === null && index < QUIZ_QUESTIONS.length - 1);

    // Last question check
    const isLast = (index === QUIZ_QUESTIONS.length - 1);
    if (isLast && selected !== null) {
      this._nextBtn.innerHTML = `
        Nộp bài
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      `;
      this._nextBtn.onclick = () => this._submitQuiz();
      this._nextBtn.disabled = false;
    } else {
      this._nextBtn.innerHTML = `
        Câu tiếp
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      `;
      this._nextBtn.onclick = () => this._navigate(1);
    }

    this._updateDots();
  },

  _selectAnswer(questionIndex, optionIndex) {
    AppState.quiz.answers[questionIndex] = optionIndex;
    ProgressStore.save();

    // Re-render to show correct/wrong states
    this._renderQuestion(questionIndex);

    // Enable next button
    this._nextBtn.disabled = false;
  },

  _navigate(delta) {
    const next = AppState.quiz.currentIndex + delta;
    if (next < 0 || next >= QUIZ_QUESTIONS.length) return;
    AppState.quiz.currentIndex = next;
    this._renderQuestion(next);
    ProgressStore.save();
  },

  _submitQuiz() {
    // Clear timer
    if (AppState.quiz.timerInterval) {
      clearInterval(AppState.quiz.timerInterval);
      AppState.quiz.timerInterval = null;
    }
    AppState.quiz.endTime = Date.now();

    // Calculate score
    const score = AppState.quiz.answers.reduce((acc, ans, i) => {
      return acc + (ans === QUIZ_QUESTIONS[i].correct ? 1 : 0);
    }, 0);

    AppState.results.score = score;

    // Determine level
    const levelInfo = SCORE_LEVELS.find(l => score >= l.min && score <= l.max) || SCORE_LEVELS[0] || { badge: 'Beginner' };
    AppState.results.level = levelInfo.badge;

    // Calculate confidence (0–100)
    // Base: (score/10) * 80 + 20 (min 20%)
    // Reduce if many unanswered (shouldn't happen but guard)
    const answered = AppState.quiz.answers.filter(a => a !== null).length;
    const totalQuestions = QUIZ_QUESTIONS.length;
    const base = (score / totalQuestions) * 80 + 20;
    const completionFactor = answered / totalQuestions;
    AppState.results.confidence = Math.round(base * completionFactor);

    // Determine fallback mode
    AppState.results.isFallback = AppState.results.confidence < 80;

    Toast.success('Nộp bài thành công!', `Điểm của bạn: ${score}/10. Đang phân tích lộ trình...`);

    // Transition to results
    ResultsUI.show();
  },
};

/* ─── RESULTS UI ─────────────────────────────────────────────── */
const ResultsUI = {
  show() {
    // Hide form section
    if ($('form-section')) $('form-section').classList.add('hidden');

    // Show results
    const resultsEl = $('results-section');
    if (!resultsEl) {
      ProgressStore.save();
      goToWorkspace(true);
      return;
    }
    resultsEl.classList.remove('hidden');

    // Update confidence meter
    this._animateConfidence();

    // Update score
    if ($('score-display')) $('score-display').textContent = `${AppState.results.score} / 10`;
    const levelInfo = SCORE_LEVELS.find(l => AppState.results.score >= l.min && AppState.results.score <= l.max);
    if ($('score-level')) $('score-level').textContent = levelInfo ? levelInfo.label : '—';

    // Show fallback alert if needed
    if (AppState.results.isFallback && $('fallback-alert')) {
      if ($('fallback-alert')) $('fallback-alert').classList.remove('hidden');
    }

    // Load roadmap (with loading state)
    Roadmap.loadSkeleton();

    // Call API analyze
    this._callAnalyzeAPI();

    // Setup chat welcome message
    ChatUI.init();
    ProgressStore.save();

    // Smooth scroll to results
    resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  renderExisting() {
    this._animateConfidence();
    if ($('score-display')) $('score-display').textContent = `${AppState.results.score} / 10`;
    const levelInfo = SCORE_LEVELS.find(l => AppState.results.score >= l.min && AppState.results.score <= l.max);
    if ($('score-level')) $('score-level').textContent = levelInfo ? levelInfo.label : (AppState.results.level || '--');

    if ($('fallback-alert')) $('fallback-alert').classList.toggle('hidden', !AppState.results.isFallback);
    if ($('failure-alert')) $('failure-alert').classList.toggle('hidden', !AppState.results.isFailure);

    if (AppState.results.roadmap) {
      Roadmap.render(AppState.results.roadmap);
    }

    if ($('cost-label')) {
      $('cost-label').textContent = `${AppState.chat.totalTokens.toLocaleString()} tokens · $${AppState.chat.totalCostUSD.toFixed(4)}`;
    }

    ChatUI.init({ restoreHistory: true });
    requestAnimationFrame(() => ChatUI.scrollToBottom());
  },

  _animateConfidence() {
    const conf = AppState.results.confidence;
    const fill = $('confidence-fill');
    const val  = $('confidence-value');
    const badge    = $('confidence-badge');
    const badgeText= $('confidence-badge-text');
    if (!badge) return;
    const badgeDot = badge.querySelector('.badge-dot');

    // Animate fill with delay
    requestAnimationFrame(() => {
      setTimeout(() => {
        if (fill) fill.style.width = `${conf}%`;
        if (val)  val.textContent  = `${conf}%`;
      }, 300);
    });

    // Set badge
    if (conf >= 80) {
      if (badgeDot) badgeDot.style.background = 'var(--color-success)';
      if (badgeText) badgeText.textContent = 'Độ tự tin cao — lộ trình cá nhân hóa';
      badge.innerHTML = `<span class="badge-dot" style="background:var(--color-success);width:8px;height:8px;border-radius:999px;animation:pulse 2s infinite"></span> <span>Độ tự tin cao</span>`;
    } else if (conf >= 50) {
      badge.innerHTML = `<span class="badge-dot" style="background:var(--color-warning);width:8px;height:8px;border-radius:999px;animation:pulse 2s infinite"></span> <span>Độ tự tin trung bình — lộ trình cơ bản</span>`;
    } else {
      badge.innerHTML = `<span class="badge-dot" style="background:var(--color-error);width:8px;height:8px;border-radius:999px;animation:pulse 2s infinite"></span> <span>Độ tự tin thấp — cần thêm thông tin</span>`;
    }
  },

  async _callAnalyzeAPI() {
    if (!AppState.results.sessionId) {
      AppState.results.sessionId = `session_${Date.now()}`;
    }

    const payload = {
      user_id:          AppState.ui.userId || 'guest_user',
      session_id:       AppState.results.sessionId,
      goal_description: `Mục đích học AI: ${AppState.userData.goal_why}. Hình thức học ưa thích: ${AppState.userData.goal_style}.`,
      quiz_answers:     AppState.quiz.answers,
      time_per_week:    `${AppState.userData.goal_time} tiếng/tuần`,
      current_job:      AppState.userData.goal_job || 'none',
      background:       AppState.userData.goal_style || 'none',
      quiz_score:       AppState.results.score,
    };

    // Helper to convert backend milestones to frontend phases
    const convertMilestonesToPhases = (milestones) => {
      if (!milestones || milestones.length === 0) return [];
      
      let phases = [];
      const beginnerMs = milestones.filter(m => m.difficulty === 'beginner');
      const intermediateMs = milestones.filter(m => m.difficulty === 'intermediate');
      const advancedMs = milestones.filter(m => m.difficulty === 'advanced');
      
      let phaseNum = 1;
      if (beginnerMs.length > 0) {
        phases.push({
          id: 'phase-beginner',
          number: phaseNum++,
          title: 'Giai đoạn khởi đầu (Beginner)',
          duration: '2-4 tuần',
          milestones: beginnerMs.map((m, idx) => ({
            id: `m-beg-${idx}`,
            icon: m.milestone_title.match(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/u)?.[0] || '🌱',
            status: idx === 0 ? 'active' : 'locked',
            title: m.milestone_title.replace(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/gu, '').trim() || m.milestone_title,
            desc: m.description,
            tags: ['Cơ bản', m.difficulty],
            time: m.duration,
            links: m.resource_links || []
          }))
        });
      }
      
      if (intermediateMs.length > 0) {
        phases.push({
          id: 'phase-intermediate',
          number: phaseNum++,
          title: 'Giai đoạn phát triển (Intermediate)',
          duration: '3-5 tuần',
          milestones: intermediateMs.map((m, idx) => ({
            id: `m-int-${idx}`,
            icon: m.milestone_title.match(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/u)?.[0] || '⚡',
            status: 'locked',
            title: m.milestone_title.replace(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/gu, '').trim() || m.milestone_title,
            desc: m.description,
            tags: ['Trung cấp', m.difficulty],
            time: m.duration,
            links: m.resource_links || []
          }))
        });
      }
      
      if (advancedMs.length > 0) {
        phases.push({
          id: 'phase-advanced',
          number: phaseNum++,
          title: 'Giai đoạn nâng cao (Advanced)',
          duration: '4-8 tuần',
          milestones: advancedMs.map((m, idx) => ({
            id: `m-adv-${idx}`,
            icon: m.milestone_title.match(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/u)?.[0] || '🚀',
            status: 'locked',
            title: m.milestone_title.replace(/[\p{Emoji_Presentation}\p{Emoji}\u2700-\u27BF]/gu, '').trim() || m.milestone_title,
            desc: m.description,
            tags: ['Nâng cao', m.difficulty],
            time: m.duration,
            links: m.resource_links || []
          }))
        });
      }
      return phases;
    };

    try {
      const response = await fetch(ENDPOINTS.analyze, {
        method:  'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();

      // Extract confidence
      if (typeof data.confidence_score === 'number') {
        AppState.results.confidence = Math.round(data.confidence_score * 100);
        this._animateConfidence();
      }

      // Update cost info
      if (data.cost_info) {
        const totalTokens = (data.cost_info.input_tokens || 0) + (data.cost_info.output_tokens || 0);
        const costUsd = data.cost_info.calculated_cost || 0.0;
        CostDisplay.update(totalTokens, costUsd);
      }

      // Handle paths based on path_type
      const pathType = data.path_type || 'happy';
      
      if (pathType === 'happy') {
        // Happy Path: full personalized roadmap
        const phases = convertMilestonesToPhases(data.milestones || []);
        AppState.results.roadmap = {
          title: 'Lộ trình học AI cá nhân hóa',
          subtitle: data.personalization_notes || 'Được thiết kế riêng cho mục tiêu của bạn.',
          phases: phases
        };
        AppState.results.isFallback = false;
        AppState.results.isFailure = false;
        
        if ($('fallback-alert')) $('fallback-alert').classList.add('hidden');
        if ($('failure-alert')) $('failure-alert').classList.add('hidden');
        
        // Render
        Roadmap.render(AppState.results.roadmap);
        ProgressStore.save();
        Toast.success('Lộ trình đã sẵn sàng!', 'AI đã phân tích xong và tạo lộ trình phù hợp cho bạn.');
        
      } else if (pathType === 'low_conf') {
        // Low Confidence: lock custom edits, load baseline roadmap
        AppState.results.isFallback = true;
        AppState.results.isFailure = false;
        AppState.results.roadmap = DEFAULT_ROADMAP;
        
        if ($('fallback-alert')) $('fallback-alert').classList.remove('hidden');
        if ($('failure-alert')) $('failure-alert').classList.add('hidden');
        
        // Render baseline VinUni roadmap
        Roadmap.render(DEFAULT_ROADMAP);
        ProgressStore.save();
        
        // Proactive Chatbot suggestion
        setTimeout(() => {
          ChatUI._appendMessage('ai', 'Mình nhận thấy nền tảng Toán của bạn cần được củng cố thêm trước khi học Deep Learning, bạn có muốn mình bổ sung 1 tuần học bổ trợ Toán không?');
        }, 1500);
        
        Toast.warning('Lộ trình cơ bản kích hoạt', 'Độ tự tin AI trung bình. Lộ trình nền tảng đã được tải.');
        
      } else {
        // Failure path / Fallback if score < 50%
        throw new Error('AI Confidence too low or Failure mode triggered');
      }

    } catch (err) {
      console.warn('[Analyze API] Error / Failure Path triggered:', err.message);

      // Failure mode — use default roadmap
      AppState.results.isFailure = true;
      AppState.results.roadmap   = DEFAULT_ROADMAP;
      AppState.results.isFallback = true;

      // Show friendly warning alerts
      if ($('failure-alert')) $('failure-alert').classList.remove('hidden');
      if ($('fallback-alert')) $('fallback-alert').classList.remove('hidden');

      Roadmap.render(DEFAULT_ROADMAP);
      ProgressStore.save();

      Toast.warning('Dùng lộ trình mặc định', 'Hệ thống đang bận tối ưu cấu trúc, vui lòng đợi trong giây lát.');
    }
  },
};

/* ─── ROADMAP RENDERER ───────────────────────────────────────── */
const Roadmap = {
  treeEl:   null,
  skeletonEl: null,

  init() {
    this.treeEl    = $('roadmap-tree');
    this.skeletonEl = $('roadmap-skeleton');

    if ($('btn-export-roadmap')) $('btn-export-roadmap').addEventListener('click', () => this.exportAsText());
    if ($('btn-retry')) $('btn-retry').addEventListener('click', () => {
      if ($('failure-alert')) $('failure-alert').classList.add('hidden');
      ResultsUI._callAnalyzeAPI();
    });
  },

  loadSkeleton() {
    if (this.skeletonEl) this.skeletonEl.classList.remove('hidden');
  },

  render(roadmapData) {
    if (!this.treeEl) return;

    // Hide skeleton
    if (this.skeletonEl) this.skeletonEl.classList.add('hidden');

    // Update meta
    const titleEl = $('roadmap-title');
    const subtitleEl = $('roadmap-subtitle');
    if (titleEl && roadmapData.title)    titleEl.textContent    = roadmapData.title;
    if (subtitleEl && roadmapData.subtitle) subtitleEl.textContent = roadmapData.subtitle;

    // Clear existing content (except skeleton)
    const existingPhases = this.treeEl.querySelectorAll('.roadmap-phase');
    existingPhases.forEach(el => el.remove());

    // Build phases
    const phases = roadmapData.phases || [];
    phases.forEach((phase, phaseIdx) => {
      const phaseEl = this._buildPhase(phase, phaseIdx);
      this.treeEl.appendChild(phaseEl);
    });
  },

  _buildPhase(phase, phaseIdx) {
    const el = document.createElement('div');
    el.className = 'roadmap-phase';
    el.style.animationDelay = `${phaseIdx * 0.12}s`;

    el.innerHTML = `
      <div class="roadmap-phase-header">
        <div class="phase-number">${phase.number || phaseIdx + 1}</div>
        <div>
          <div class="phase-title">${phase.title || 'Giai đoạn ' + (phaseIdx + 1)}</div>
          <div class="phase-duration">⏱ ${phase.duration || ''}</div>
        </div>
        <div class="phase-line"></div>
      </div>
      <div class="milestones-list" id="milestones-${phase.id || phaseIdx}"></div>
    `;

    const listEl = el.querySelector('.milestones-list');
    const milestones = phase.milestones || [];

    milestones.forEach((ms, msIdx) => {
      const card = this._buildMilestone(ms, msIdx);
      listEl.appendChild(card);
    });

    return el;
  },

  _buildMilestone(ms, msIdx) {
    // Check if completed via state
    const isCompleted = AppState.completedMilestones.has(ms.id);
    const status = isCompleted ? 'completed' : (ms.status || 'locked');

    const el = document.createElement('div');
    el.className = `milestone-card ${status}`;
    el.dataset.id = ms.id;
    el.style.animationDelay = `${msIdx * 0.08}s`;

    const linksHtml = (ms.links && ms.links.length > 0) ? `
      <div class="milestone-links">
        ${ms.links.map(link => {
          let label = 'Tài liệu học';
          if (link.includes('coursera.org')) label = 'Coursera';
          else if (link.includes('kaggle.com')) label = 'Kaggle';
          else if (link.includes('elementsofai.com')) label = 'Elements of AI';
          else if (link.includes('promptingguide.ai')) label = 'Prompting Guide';
          else if (link.includes('deeplearning.ai')) label = 'DeepLearning.AI';
          else if (link.includes('youtube.com') || link.includes('youtu.be')) label = 'Video';
          
          return `<a href="${link}" target="_blank" rel="noopener noreferrer" class="milestone-link-btn" title="${link}">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            ${label}
          </a>`;
        }).join('')}
      </div>
    ` : '';

    el.innerHTML = `
      <div class="milestone-node"></div>
      <div class="milestone-icon">${ms.icon || '📌'}</div>
      <div class="milestone-body">
        <div class="milestone-title">${ms.title || 'Milestone'}</div>
        <div class="milestone-desc">${ms.desc || ''}</div>
        ${linksHtml}
        <div class="milestone-meta">
          ${(ms.tags || []).map(tag => `<span class="milestone-tag">${tag}</span>`).join('')}
          ${ms.time ? `<span class="milestone-time">⏱ ${ms.time}</span>` : ''}
        </div>
      </div>
      <button class="milestone-check" title="${isCompleted ? 'Đã hoàn thành' : 'Đánh dấu hoàn thành'}" aria-label="Toggle hoàn thành">
        ${isCompleted ? '✓' : ''}
      </button>
    `;

    // Toggle completion (not for locked milestones)
    if (status !== 'locked') {
      const checkBtn = el.querySelector('.milestone-check');
      checkBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleMilestone(ms.id, el, checkBtn);
      });

      // Click on card to expand / mark active
      el.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        if (!el.classList.contains('locked')) {
          el.classList.toggle('active');
        }
      });
    }

    return el;
  },

  _toggleMilestone(id, cardEl, checkBtn) {
    const wasCompleted = AppState.completedMilestones.has(id);

    if (wasCompleted) {
      AppState.completedMilestones.delete(id);
      cardEl.classList.remove('completed');
      cardEl.querySelector('.milestone-node').style.cssText = '';
      checkBtn.textContent = '';
      checkBtn.title = 'Đánh dấu hoàn thành';
    } else {
      AppState.completedMilestones.add(id);
      cardEl.classList.remove('active', 'locked');
      cardEl.classList.add('completed');
      checkBtn.textContent = '✓';
      checkBtn.title = 'Đã hoàn thành';
      Toast.success('Hoàn thành!', `Bạn đã hoàn thành: ${cardEl.querySelector('.milestone-title').textContent}`);
    }
    ProgressStore.save();
  },

  exportAsText() {
    const roadmap = AppState.results.roadmap || DEFAULT_ROADMAP;
    let text = `# ${roadmap.title}\n`;
    text += `${roadmap.subtitle}\n\n`;
    text += `Người học: ${AppState.userData.goal_why || 'N/A'}\n`;
    text += `Thời gian học: ${AppState.userData.goal_time || 'N/A'} / tuần\n`;
    text += `Điểm quiz: ${AppState.results.score}/10 | Level: ${AppState.results.level}\n\n`;
    text += `${'='.repeat(60)}\n\n`;

    (roadmap.phases || []).forEach((phase, pi) => {
      text += `## Giai đoạn ${phase.number || pi + 1}: ${phase.title}\n`;
      text += `⏱ Thời gian: ${phase.duration}\n\n`;
      (phase.milestones || []).forEach((ms, mi) => {
        const done = AppState.completedMilestones.has(ms.id) ? '[✓]' : '[ ]';
        text += `  ${done} ${ms.icon} ${ms.title}\n`;
        text += `     ${ms.desc}\n`;
        text += `     Tags: ${(ms.tags || []).join(', ')} | ${ms.time}\n\n`;
      });
    });

    text += `\n---\nXuất lúc: ${new Date().toLocaleString('vi-VN')}\nAI Learning Path Personalizer | VinUni`;

    // Download
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = 'lo-trinh-hoc-ai.txt';
    a.click();
    URL.revokeObjectURL(url);

    Toast.success('Đã xuất!', 'Lộ trình đã được tải về máy của bạn.');
  },
};

/* ─── CHAT UI ────────────────────────────────────────────────── */
const ChatUI = {
  messagesEl:  null,
  inputEl:     null,
  sendBtn:     null,
  charCount:   null,
  rlLabel:     null,
  rlFill:      null,
  rlTimer:     null,
  rlCountdown: null,

  init({ restoreHistory = false } = {}) {
    this.messagesEl  = $('chat-messages');
    this.inputEl     = $('chat-input');
    this.sendBtn     = $('btn-send');
    this.charCount   = $('char-count');
    this.rlLabel     = $('rate-limit-label');
    this.rlFill      = $('rate-limit-fill');
    this.rlTimer     = $('rate-limit-timer');
    this.rlCountdown = $('rl-countdown');

    if (!this.messagesEl || !this.inputEl || !this.sendBtn || !this.charCount) return;

    if (this._initialized) {
      if (restoreHistory) this._renderHistory();
      this._updateRateLimit();
      return;
    }
    this._initialized = true;

    if (restoreHistory && AppState.chat.history.length) {
      this._renderHistory();
    } else {
      this._addWelcomeMessage();
    }

    // Event listeners
    this.inputEl.addEventListener('input', () => this._onInputChange());
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    this.sendBtn.addEventListener('click', () => this.sendMessage());

    // Auto-resize textarea
    this.inputEl.addEventListener('input', () => {
      this.inputEl.style.height = 'auto';
      this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 120) + 'px';
    });

    this._updateRateLimit();
  },

  _renderHistory() {
    if (!this.messagesEl) return;
    this.messagesEl.innerHTML = '';
    (AppState.chat.history || []).forEach(msg => {
      this._appendMessage(msg.role, msg.content, true);
    });
  },

  _onInputChange() {
    const len = this.inputEl.value.length;
    this.charCount.textContent = `${len}/500`;
    this.charCount.classList.toggle('near-limit', len > 400 && len <= 490);
    this.charCount.classList.toggle('at-limit',   len > 490);
  },

  _addWelcomeMessage() {
    const score = AppState.results.score;
    const level = AppState.results.level;
    const name  = AppState.userData.goal_job
      ? ` (${AppState.userData.goal_job})`
      : '';

    const welcome = `Chào mừng bạn${name}! 🎉

Tôi đã phân tích kết quả quiz của bạn:
• **Điểm số**: ${score}/10 — *${level}*
• **Mục tiêu**: ${AppState.userData.goal_why || 'Học AI'}
• **Thời gian học**: ${AppState.userData.goal_time || 'N/A'}/tuần

Lộ trình học của bạn đã được tạo ở khung **Lộ trình học** bên phải. Hãy hỏi tôi bất cứ điều gì về lộ trình, tài nguyên học tập, hoặc các chủ đề AI bạn quan tâm! 🚀`;

    this._appendMessage('ai', welcome);
  },

  _appendMessage(role, content, skipState = false) {
    if (!this.messagesEl) return;

    const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const isUser = (role === 'user');
    const avatar = isUser ? '👤' : '🤖';

    const el = document.createElement('div');
    el.className = `msg ${role}`;

    // Convert **bold** and *italic* markdown
    const formatted = this._formatContent(content);

    el.innerHTML = `
      <div class="msg-avatar" aria-hidden="true">${avatar}</div>
      <div>
        <div class="msg-bubble">${formatted}</div>
        <div class="msg-time">${now}</div>
      </div>
    `;

    this.messagesEl.appendChild(el);
    this.scrollToBottom();

    // Save to history
    if (!skipState) {
      AppState.chat.history.push({ role, content, time: new Date() });
      ProgressStore.save();
    }

    return el;
  },

  _formatContent(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:3px">$1</code>')
      .replace(/\n/g, '<br>');
  },

  _showTyping() {
    const el = document.createElement('div');
    el.className = 'msg ai';
    el.id = 'typing-indicator';
    el.innerHTML = `
      <div class="msg-avatar" aria-hidden="true">🤖</div>
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  },

  _removeTyping() {
    const el = $('typing-indicator');
    if (el) el.remove();
  },

  scrollToBottom() {
    if (this.messagesEl) {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }
  },

  _updateRateLimit() {
    const rl = AppState.chat.rateLimit;
    if (rl.unlimited) {
      if (this.rlLabel) {
        this.rlLabel.textContent = `Không giới hạn câu hỏi${rl.modelName ? ` · ${rl.modelName}` : ''}`;
      }
      if (this.rlFill) {
        this.rlFill.style.width = '100%';
        this.rlFill.style.background = 'var(--color-success)';
      }
      return;
    }

    const pct = (rl.remaining / rl.max) * 100;

    if (this.rlLabel) {
      this.rlLabel.textContent = `${rl.remaining} tin nhắn còn lại`;
    }
    if (this.rlFill) {
      this.rlFill.style.width = `${pct}%`;
      // Color shifts: green → yellow → red
      const hue = (pct / 100) * 120;
      this.rlFill.style.background = `hsl(${hue}, 80%, 55%)`;
    }
  },

  _startRateLimitCountdown() {
    const rl = AppState.chat.rateLimit;
    rl.resetAt = Date.now() + 60000; // 60s window

    if (this.rlTimer) this.rlTimer.classList.remove('hidden');
    if (this.rlLabel) this.rlLabel.textContent = 'Giới hạn đạt';

    rl.countdown = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((rl.resetAt - Date.now()) / 1000));
      if (this.rlCountdown) this.rlCountdown.textContent = remaining;

      if (remaining <= 0) {
        clearInterval(rl.countdown);
        rl.remaining = rl.max;
        rl.resetAt   = null;
        if (this.rlTimer) this.rlTimer.classList.add('hidden');
        this._updateRateLimit();
        this.sendBtn.disabled  = false;
        this.inputEl.disabled  = false;
        Toast.info('Có thể gửi tiếp!', 'Giới hạn tin nhắn đã được làm mới.');
      }
    }, 1000);
  },

  async sendMessage() {
    const raw = this.inputEl.value.trim();
    if (!raw) return;

    const rl = AppState.chat.rateLimit;

    // Rate limit check
    if (!rl.unlimited && rl.remaining <= 0) {
      Toast.warning('Đã đạt giới hạn', 'Bạn chỉ có thể gửi 5 tin nhắn/phút. Vui lòng chờ.');
      return;
    }

    if (AppState.chat.isLoading) return;

    // Sanitize
    const content = sanitizeInput(raw);
    if (!content) return;

    // Clear input
    this.inputEl.value = '';
    this.inputEl.style.height = 'auto';
    this._onInputChange();

    // Append user message
    this._appendMessage('user', content);

    // Decrement rate limit for non-local models only.
    if (!rl.unlimited) {
      rl.remaining -= 1;
      this._updateRateLimit();
    }

    if (!rl.unlimited && rl.remaining <= 0) {
      this.sendBtn.disabled = true;
      this.inputEl.disabled = true;
      this._startRateLimitCountdown();
    }

    // Show typing indicator
    AppState.chat.isLoading = true;
    this.sendBtn.disabled   = true;
    const typingEl = this._showTyping();

    try {
      const response = await fetch(ENDPOINTS.chat, {
        method:  'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          user_id:            AppState.ui.userId || 'guest_user',
          message:            content,
          session_id:         AppState.results.sessionId || `session_${Date.now()}`,
          quiz_completed:     true,
          questions_answered: AppState.quiz.answers.filter(a => a !== null).length,
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      this._removeTyping();
      this._appendMessage('ai', data.response || data.message || 'Xin lỗi, tôi không thể trả lời lúc này.');

      // Update cost
      if (data.tokens_used) {
        const totalTokens = data.tokens_used.total || 0;
        const costUsd = data.cost ? (data.cost.request_cost_usd || 0.0) : 0.0;
        CostDisplay.update(totalTokens, costUsd);
      }

    } catch (err) {
      console.warn('[Chat API] Error:', err.message);
      this._removeTyping();

      // Fallback response
      const fallbackMsg = this._generateFallbackResponse(content);
      this._appendMessage('ai', fallbackMsg);

      Toast.warning('Chế độ offline', 'Không kết nối được API. Đang dùng phản hồi cục bộ.');
    } finally {
      AppState.chat.isLoading = false;
      // Re-enable send if rate limit allows
      if (rl.unlimited || rl.remaining > 0) {
        this.sendBtn.disabled = false;
        this.inputEl.disabled = false;
      }
    }
  },

  /**
   * Fallback AI response when API is unavailable.
   * Keyword-based simple response generator (Vietnamese).
   */
  _generateFallbackResponse(userMsg) {
    const msg = userMsg.toLowerCase();

    if (msg.includes('neural') || msg.includes('deep learning') || msg.includes('dl')) {
      return `Deep Learning là tập con của Machine Learning sử dụng nhiều lớp mạng nơ-ron. Trong lộ trình của bạn, phần này nằm ở **Giai đoạn 3**.

Tài nguyên gợi ý:
• 📖 "Deep Learning" - Goodfellow et al. (miễn phí online)
• 🎥 fast.ai - Practical Deep Learning for Coders
• 🔗 PyTorch hoặc TensorFlow 2.x`;
    }

    if (msg.includes('python') || msg.includes('lập trình')) {
      return `Để học Python cho AI/ML, bạn nên bắt đầu với:

1. **Python cơ bản**: Variables, loops, functions, OOP
2. **NumPy**: Tính toán ma trận hiệu quả
3. **Pandas**: Xử lý dữ liệu dạng bảng
4. **Matplotlib/Seaborn**: Trực quan hóa dữ liệu

Tài nguyên: Kaggle Learn (miễn phí), CS50P của Harvard`;
    }

    if (msg.includes('bao lâu') || msg.includes('thời gian') || msg.includes('how long')) {
      const time = AppState.userData.goal_time || '4-7 giờ';
      return `Với lịch học **${time}/tuần**, dự kiến bạn cần khoảng:

• Giai đoạn 1 (Nền tảng): 4–6 tuần
• Giai đoạn 2 (ML cơ bản): 6–8 tuần  
• Giai đoạn 3 (Deep Learning): 8–10 tuần
• Giai đoạn 4 (Dự án thực tế): 4–6 tuần

**Tổng cộng: ~6–9 tháng** nếu học đều đặn.`;
    }

    if (msg.includes('tài liệu') || msg.includes('sách') || msg.includes('course') || msg.includes('khóa')) {
      return `📚 **Tài nguyên học AI được khuyến nghị:**

**Miễn phí:**
• Coursera - Machine Learning Specialization (Andrew Ng)
• fast.ai - Practical Deep Learning
• Google ML Crash Course
• Kaggle Learn

**Sách:**
• "Hands-On Machine Learning" - Aurélien Géron
• "Pattern Recognition and Machine Learning" - Bishop

**Cộng đồng Việt:**
• Forum AIViVN (aivietnam.ai)
• GDSC Vietnam các trường đại học`;
    }

    if (msg.includes('roadmap') || msg.includes('lộ trình') || msg.includes('bước')) {
      return `Lộ trình học AI của bạn đã được tạo trong tab **Lộ trình học** 🗺️

Lộ trình gồm 4 giai đoạn chính, từ nền tảng toán học đến triển khai dự án thực tế. Bạn có thể:
• Click vào các milestone để xem chi tiết
• Đánh dấu hoàn thành các bước đã học
• Xuất lộ trình ra file text

Bạn muốn tìm hiểu thêm về giai đoạn nào?`;
    }

    // Default response
    return `Cảm ơn câu hỏi của bạn! 🤔

Hiện tại tôi đang ở chế độ offline nên không thể tra cứu thông tin chi tiết. Tuy nhiên, dựa trên lộ trình học của bạn (Level: **${AppState.results.level}**), tôi khuyến nghị:

• Tập trung vào các milestone đang **active** trong lộ trình
• Thực hành coding mỗi ngày, dù chỉ 30 phút
• Tham gia cộng đồng AI Việt Nam để hỏi đáp

Hãy thử hỏi lại khi kết nối được API nhé! 🚀`;
  },
};

/* ─── FEEDBACK MODAL ─────────────────────────────────────────── */
const FeedbackModal = {
  init() {
    const modal = $('modal-feedback');
    const overlay = modal;

    // Open
    $('btn-feedback').addEventListener('click', () => {
      modal.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    });

    // Close
    $('modal-feedback-close').addEventListener('click', () => this.close());
    $('btn-feedback-cancel').addEventListener('click',  () => this.close());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) this.close();
    });

    // Stars
    const starBtns = $$('.star-btn');
    starBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const rating = parseInt(btn.dataset.rating);
        AppState.ui.feedbackRating = rating;

        // Update star appearances
        starBtns.forEach(b => {
          b.classList.toggle('active', parseInt(b.dataset.rating) <= rating);
        });

        $('star-label-text').textContent = STAR_LABELS[rating] || '';
        $('btn-feedback-submit').disabled = false;
      });
    });

    // Submit
    $('btn-feedback-submit').addEventListener('click', () => this.submit());
  },

  close() {
    $('modal-feedback').classList.add('hidden');
    document.body.style.overflow = '';
  },

  async submit() {
    const rating  = AppState.ui.feedbackRating;
    const comment = sanitizeInput($('feedback-comment').value);

    if (!rating) {
      Toast.warning('Chưa chọn sao', 'Vui lòng chọn số sao trước khi gửi.');
      return;
    }

    // Map chat history to backend role naming: 'user' / 'assistant'
    const chatHistoryMapped = (AppState.chat.history || []).map(msg => ({
      role: msg.role === 'ai' ? 'assistant' : 'user',
      content: msg.content
    }));

    const payload = {
      user_id:          AppState.ui.userId || 'guest_user',
      session_id:       AppState.results.sessionId || `session_${Date.now()}`,
      rating:           rating,
      comment:          comment || '',
      roadmap_data:     AppState.results.roadmap,
      chat_history:     chatHistoryMapped,
      confidence_score: (AppState.results.confidence || 0) / 100.0,
      report:           rating <= 2,
    };

    try {
      const response = await fetch(ENDPOINTS.feedback, {
        method:  'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      Toast.success('Cảm ơn!', `Đánh giá ${rating}⭐ của bạn đã được ghi nhận. Phản hồi này giúp AI học tốt hơn!`);
      this.close();

    } catch (err) {
      console.warn('[Feedback API]', err.message);
      Toast.success('Cảm ơn!', `Đã ghi nhận đánh giá ${rating}⭐ của bạn. (Sẽ đồng bộ khi có kết nối)`);
      this.close();
    }
  },
};

/* ─── SUPPORT MODAL ──────────────────────────────────────────── */
const SupportModal = {
  init() {
    const modal = $('modal-support');

    // Open
    $('btn-support').addEventListener('click', () => {
      modal.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    });

    // Close
    ['modal-support-close', 'btn-support-close-main'].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener('click', () => this.close());
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });

    // Reset session
    $('btn-reset-session').addEventListener('click', () => {
      if (confirm('Bạn có chắc muốn xoá toàn bộ dữ liệu và bắt đầu lại?')) {
        this._resetSession();
      }
    });

    // Rollback to default roadmap
    $('btn-rollback').addEventListener('click', () => {
      AppState.results.roadmap   = DEFAULT_ROADMAP;
      AppState.results.isFallback = true;
      AppState.results.isFailure  = false;
      if ($('failure-alert')) $('failure-alert').classList.add('hidden');
      if ($('fallback-alert')) $('fallback-alert').classList.remove('hidden');
      Roadmap.render(DEFAULT_ROADMAP);
      Toast.info('Đã khôi phục', 'Lộ trình mặc định đã được hiển thị.');
      this.close();
    });
  },

  close() {
    $('modal-support').classList.add('hidden');
    document.body.style.overflow = '';
  },

  _resetSession({ keepAuth = true, silent = false, clearProgress = true } = {}) {
    const currentUser = AppState.ui.user;
    const currentUserId = AppState.ui.userId;
    if (clearProgress && currentUserId) ProgressStore.clear(currentUserId);

    // Reset state
    AppState.userData          = { goal_why: '', goal_time: '', goal_job: '', goal_style: '' };
    AppState.quiz              = { currentIndex: 0, answers: new Array(QUIZ_QUESTIONS.length).fill(null), startTime: null, endTime: null, timerInterval: null };
    AppState.results           = { score: 0, confidence: 0, level: '', roadmap: null, isFallback: false, isFailure: false, sessionId: null };
    AppState.chat              = {
      history: [],
      rateLimit: {
        remaining: 5,
        max: 5,
        unlimited: false,
        modelName: '',
        provider: '',
        resetAt: null,
        countdown: null,
      },
      totalTokens: 0,
      totalCostUSD: 0,
      isLoading: false,
    };
    AppState.completedMilestones = new Set();
    AppState.ui                = {
      currentStep: 1,
      feedbackRating: 0,
      user: keepAuth ? currentUser : null,
      userId: keepAuth ? currentUserId : null,
    };

    // Reset cost display
    if ($('cost-label')) $('cost-label').textContent = '0 tokens · $0.000';
    ModelConfig.load();

    // Show form, hide results
    if (keepAuth && $('form-section')) $('form-section').classList.remove('hidden');
    if ($('results-section')) $('results-section').classList.add('hidden');
    if ($('failure-alert')) $('failure-alert').classList.add('hidden');
    if ($('fallback-alert')) $('fallback-alert').classList.add('hidden');

    // Reset step form
    if ($('goal-form')) {
      $('goal-form').reset();
      StepForm.goToStep(1);
    }

    // Clear chat messages
    if ($('chat-messages')) $('chat-messages').innerHTML = '';

    this.close();
    if (!silent) Toast.info('Đặt lại thành công', 'Phiên làm việc đã được xoá. Bắt đầu lại từ đầu!');

    // Scroll to top
    if (!silent) window.scrollTo({ top: 0, behavior: 'smooth' });
  },
};

/* ─── HERO CTA ───────────────────────────────────────────────── */
function initHeroCTA() {
  const heroStartBtn = $('hero-start-btn');
  if (!heroStartBtn) return;

  heroStartBtn.addEventListener('click', () => {
    if (!AppState.ui.userId) {
      $('auth-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
      setTimeout(() => $('login-email').focus(), 600);
      return;
    }
    const formSection = $('form-section');
    formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => {
      $('goal-why').focus();
    }, 600);
  });
}

/* ─── ANIMATION OBSERVERS ────────────────────────────────────── */
function initScrollAnimations() {
  if (!window.IntersectionObserver) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  $$('.form-card, .roadmap-phase, .milestone-card').forEach(el => {
    el.style.animationPlayState = 'paused';
    observer.observe(el);
  });
}

/* ─── KEYBOARD SHORTCUTS ─────────────────────────────────────── */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Escape closes modals
    if (e.key === 'Escape') {
      $('modal-feedback').classList.add('hidden');
      $('modal-support').classList.add('hidden');
      document.body.style.overflow = '';
    }
  });
}

/* ─── ACCESSIBILITY: Focus trap in modals ────────────────────── */
function trapFocus(modalEl) {
  const focusable = modalEl.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];

  modalEl.addEventListener('keydown', function handler(e) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
    }
  });
}

/* ─── RESULTS SECTION: Hide initially ───────────────────────── */
function ensureResultsHidden() {
  const resultsSection = $('results-section');
  if (resultsSection) resultsSection.classList.add('hidden');
}

const WorkspacePage = {
  init() {
    if (!isWorkspacePage()) return;

    const hasQuizResult = Boolean(AppState.quiz.endTime || AppState.results.level || AppState.results.score);
    if (!hasQuizResult && !AppState.results.roadmap) {
      window.location.href = 'main.html';
      return;
    }

    if ($('results-section')) $('results-section').classList.remove('hidden');

    const shouldAnalyze = new URLSearchParams(window.location.search).get('analyze') === '1';
    if (shouldAnalyze || !AppState.results.roadmap) {
      Roadmap.loadSkeleton();
      ResultsUI._callAnalyzeAPI().finally(() => {
        if (window.history.replaceState) {
          window.history.replaceState({}, document.title, 'workspace.html');
        }
      });
    }
  },
};

/* ─── MAIN INIT ──────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 AI Learning Path Personalizer — Initializing...');
  console.log('   VinUni Batch 02 | Day 05');

  await Promise.all([
    loadAppData(),
    loadQuizQuestionBank(),
  ]);

  // Core systems
  Toast.init();
  CostDisplay.init();
  AuthUI.init();

  // UI components
  StepForm.init();
  Quiz.init();
  Roadmap.init();
  FeedbackModal.init();
  SupportModal.init();
  initHeroCTA();
  initKeyboardShortcuts();

  // Ensure results are hidden on load
  ensureResultsHidden();
  await AuthUI.checkSession();
  WorkspacePage.init();
  ModelConfig.load();

  // Trap focus in modals
  if ($('modal-feedback')) trapFocus($('modal-feedback'));
  if ($('modal-support')) trapFocus($('modal-support'));

  // Rate limit UI init
  ChatUI._updateRateLimit = function() {
    const rl = AppState.chat.rateLimit;
    if (rl.unlimited) {
      const rlLabel = $('rate-limit-label');
      const rlFill  = $('rate-limit-fill');
      if (rlLabel) rlLabel.textContent = `Không giới hạn câu hỏi${rl.modelName ? ` · ${rl.modelName}` : ''}`;
      if (rlFill) {
        rlFill.style.width = '100%';
        rlFill.style.background = 'var(--color-success)';
      }
      return;
    }

    const pct = (rl.remaining / rl.max) * 100;
    const rlLabel = $('rate-limit-label');
    const rlFill  = $('rate-limit-fill');
    if (rlLabel) rlLabel.textContent = `${rl.remaining} tin nhắn còn lại`;
    if (rlFill) {
      rlFill.style.width = `${pct}%`;
      const hue = (pct / 100) * 120;
      rlFill.style.background = `hsl(${hue}, 80%, 55%)`;
    }
  };

  console.log('✅ All systems initialized.');
  Toast.info('Chào mừng!', 'Sẵn sàng tạo lộ trình học AI cá nhân hóa của bạn.');
});

/* ─── EXPOSE FOR DEBUGGING (dev only) ───────────────────────── */
if (typeof window !== 'undefined') {
  window.__APP__ = {
    AppState,
    Quiz,
    Roadmap,
    ChatUI,
    Toast,
    getDefaultRoadmap: () => DEFAULT_ROADMAP,
    getQuizQuestions: () => QUIZ_QUESTIONS,
    getQuizQuestionBank: () => QUIZ_QUESTION_BANK,
  };
}
