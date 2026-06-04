'use strict';

const API_BASE = (() => {
  const origin = window.location.origin;
  if (origin && origin !== 'null' && /^https?:\/\//.test(origin)) return origin;
  return localStorage.getItem('AI_PATH_API_BASE') || 'http://127.0.0.1:8000';
})();

const AUTH_ENDPOINTS = {
  me: `${API_BASE}/api/auth/me`,
  login: `${API_BASE}/api/auth/login`,
  register: `${API_BASE}/api/auth/register`,
};

const LOCAL_AUTH_KEY = 'AI_PATH_LOCAL_AUTH_USER';

const $ = (id) => document.getElementById(id);

function sanitizeInput(input) {
  if (typeof input !== 'string') return '';
  return input
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .replace(/[<>]/g, (c) => c === '<' ? '&lt;' : '&gt;')
    .trim()
    .substring(0, 1000);
}

function saveLocalSession(user) {
  localStorage.setItem(LOCAL_AUTH_KEY, JSON.stringify(user));
}

function getLocalSession() {
  try {
    const raw = localStorage.getItem(LOCAL_AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    localStorage.removeItem(LOCAL_AUTH_KEY);
    return null;
  }
}

function normalizeAuthUser(data = {}, fallback = {}) {
  const rawUser = data.user || data;
  const userId = rawUser.user_id || rawUser.username || fallback.username || fallback.email || 'student';
  return {
    user_id: userId,
    name: rawUser.name || fallback.name || userId,
    email: rawUser.email || fallback.email || userId,
    role: rawUser.role || data.role || 'student',
    token: data.token || rawUser.token || null,
    expires_at: data.expires_at || rawUser.expires_at || null,
    limits: data.limits || rawUser.limits || null,
  };
}

async function fetchWithSavedToken(url, options = {}) {
  const session = getLocalSession();
  const headers = new Headers(options.headers || {});
  if (session?.token) headers.set('Authorization', `Bearer ${session.token}`);
  return fetch(url, { ...options, headers });
}

const AuthPage = {
  init() {
    this.loginTab = $('auth-login-tab');
    this.registerTab = $('auth-register-tab');
    this.loginForm = $('login-form');
    this.registerForm = $('register-form');

    this.loginTab.addEventListener('click', () => this.switchMode('login'));
    this.registerTab.addEventListener('click', () => this.switchMode('register'));
    this.loginForm.addEventListener('submit', (event) => this.handleLogin(event));
    this.registerForm.addEventListener('submit', (event) => this.handleRegister(event));

    const mode = new URLSearchParams(window.location.search).get('mode');
    this.switchMode(mode === 'register' ? 'register' : 'login');
    this.checkExistingSession();
  },

  async checkExistingSession() {
    const session = getLocalSession();
    if (session?.token) {
      try {
        const response = await fetchWithSavedToken(AUTH_ENDPOINTS.me);
        if (response.ok) {
          const data = await response.json().catch(() => ({}));
          saveLocalSession(normalizeAuthUser(data, session));
          window.location.href = 'workspace.html';
          return;
        }
      } catch {
        // Continue to login screen.
      }
      localStorage.removeItem(LOCAL_AUTH_KEY);
    }

    localStorage.removeItem(LOCAL_AUTH_KEY);
  },

  switchMode(mode) {
    const isLogin = mode === 'login';
    this.loginTab.classList.toggle('active', isLogin);
    this.registerTab.classList.toggle('active', !isLogin);
    this.loginForm.classList.toggle('hidden', !isLogin);
    this.registerForm.classList.toggle('hidden', isLogin);
    $('login-error').textContent = '';
    $('register-error').textContent = '';
    document.title = `${isLogin ? 'Đăng nhập' : 'Đăng ký'} | AI Learning Path Personalizer`;
  },

  async handleLogin(event) {
    event.preventDefault();
    await this.submit('login', {
      username: sanitizeInput($('login-email').value),
      email: sanitizeInput($('login-email').value),
      password: $('login-password').value,
    });
  },

  async handleRegister(event) {
    event.preventDefault();
    await this.submit('register', {
      name: sanitizeInput($('register-name').value),
      email: sanitizeInput($('register-email').value),
      password: $('register-password').value,
    });
  },

  async submit(mode, payload) {
    const errorEl = mode === 'login' ? $('login-error') : $('register-error');
    errorEl.textContent = '';

    try {
      const username = payload.username || payload.email || payload.name;
      const response = await fetch(mode === 'login' ? AUTH_ENDPOINTS.login : AUTH_ENDPOINTS.register, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password: payload.password,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Không thể xử lý yêu cầu.');
      }
      saveLocalSession(normalizeAuthUser(data, payload));
      window.location.href = 'workspace.html';
    } catch (err) {
      errorEl.textContent = mode === 'login'
        ? 'Sai tài khoản hoặc mật khẩu. Tài khoản mặc định là admin/admin123.'
        : err.message;
    }
  },
};

document.addEventListener('DOMContentLoaded', () => AuthPage.init());
