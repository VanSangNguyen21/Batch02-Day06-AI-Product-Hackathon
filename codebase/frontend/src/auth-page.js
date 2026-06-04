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
const DEFAULT_ACCOUNT = {
  username: 'admin',
  password: 'admin',
  user: {
    user_id: 'local_admin',
    name: 'Admin',
    email: 'admin',
  },
};

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

function hasLocalSession() {
  return Boolean(localStorage.getItem(LOCAL_AUTH_KEY));
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
    if (hasLocalSession()) {
      window.location.href = 'main.html';
      return;
    }

    try {
      const response = await fetch(AUTH_ENDPOINTS.me, { credentials: 'include' });
      if (response.ok) window.location.href = 'main.html';
    } catch {
      // Stay on auth page when backend is offline.
    }
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
      username: sanitizeInput($('register-email').value),
      password: $('register-password').value,
    });
  },

  async submit(mode, payload) {
    const errorEl = mode === 'login' ? $('login-error') : $('register-error');
    errorEl.textContent = '';

    if (mode === 'login' && payload.username === DEFAULT_ACCOUNT.username && payload.password === DEFAULT_ACCOUNT.password) {
      saveLocalSession(DEFAULT_ACCOUNT.user);
      window.location.href = 'main.html';
      return;
    }

    try {
      const response = await fetch(mode === 'login' ? AUTH_ENDPOINTS.login : AUTH_ENDPOINTS.register, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Không thể xử lý yêu cầu.');
      }
      window.location.href = 'main.html';
    } catch (err) {
      errorEl.textContent = mode === 'login'
        ? 'Sai tài khoản hoặc mật khẩu. Tài khoản mặc định là admin/admin.'
        : err.message;
    }
  },
};

document.addEventListener('DOMContentLoaded', () => AuthPage.init());
