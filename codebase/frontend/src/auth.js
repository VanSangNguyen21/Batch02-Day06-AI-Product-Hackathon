/**
 * ============================================================
 * auth.js — Authentication & session management (frontend)
 *
 * Provides:
 *   - AuthState: in-memory + localStorage copy of {token, user_id, role, expires_at}
 *   - login(user_id, apiKey?, roleHint?)  -> POST /api/auth/login
 *   - logout()                            -> POST /api/auth/logout
 *   - fetchWithAuth(url, opts)            -> auto-adds Authorization + handles 401
 *   - applyRoleGating()                   -> show/hide nav tabs by role
 *   - renderUserBadge()                   -> header pill with user_id + role
 *
 * Demo accounts:
 *   admin    : login normally, manually set role in db to 'admin'
 *   reviewer : login normally, manually set role in db to 'reviewer'
 *   premium  : login normally, manually set role in db to 'premium'
 *   student  : any new registration
 * ============================================================
 */
'use strict';

const AUTH_STORAGE_KEY = 'alpe_auth';

const AuthState = {
  token:      null,
  user_id:    null,
  role:       'guest',   // guest | student | premium | reviewer | admin
  expires_at: null,
  limits:     { rate_per_minute: 0, daily_cost_usd: 0 },
};

/* ─── Persistence ─────────────────────────────────────────── */
function _persist() {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
      token:      AuthState.token,
      user_id:    AuthState.user_id,
      role:       AuthState.role,
      expires_at: AuthState.expires_at,
      limits:     AuthState.limits,
    }));
  } catch (e) {
    console.warn('localStorage persist failed:', e);
  }
}

function _restore() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return false;
    const obj = JSON.parse(raw);
    if (!obj.token || !obj.expires_at) return false;
    if (new Date(obj.expires_at) <= new Date()) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return false;
    }
    Object.assign(AuthState, obj);
    return true;
  } catch (e) {
    return false;
  }
}

/* ─── Login / Logout ─────────────────────────────────────── */
async function login(username, password) {
  const body = { username, password };

  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Login failed (${res.status})`);
  }
  const data = await res.json();
  AuthState.token      = data.token;
  AuthState.user_id    = data.user_id;
  AuthState.role       = data.role;
  AuthState.expires_at = data.expires_at;
  AuthState.limits     = data.limits;
  _persist();
  return data;
}

async function registerAccount(username, password) {
  const body = { username, password };

  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Registration failed (${res.status})`);
  }
  const data = await res.json();
  AuthState.token      = data.token;
  AuthState.user_id    = data.user_id;
  AuthState.role       = data.role;
  AuthState.expires_at = data.expires_at;
  AuthState.limits     = data.limits;
  _persist();
  return data;
}

async function logout(silent = false) {
  if (AuthState.token) {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${AuthState.token}` },
      });
    } catch (e) {
      if (!silent) console.warn('Logout request failed:', e);
    }
  }
  AuthState.token = null;
  AuthState.user_id = null;
  AuthState.role = 'guest';
  AuthState.expires_at = null;
  AuthState.limits = { rate_per_minute: 0, daily_cost_usd: 0 };
  try { localStorage.removeItem(AUTH_STORAGE_KEY); } catch (e) {}
}

async function refreshMe() {
  if (!AuthState.token) return null;
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { 'Authorization': `Bearer ${AuthState.token}` },
  });
  if (!res.ok) {
    if (res.status === 401) await logout(true);
    return null;
  }
  const data = await res.json();
  AuthState.role       = data.role;
  AuthState.expires_at = data.expires_at;
  AuthState.limits     = data.limits;
  _persist();
  return data;
}

/* ─── Authenticated fetch helper ──────────────────────────── */
async function fetchWithAuth(url, options = {}) {
  options.headers = options.headers || {};
  if (AuthState.token) {
    options.headers['Authorization'] = `Bearer ${AuthState.token}`;
  }
  if (AuthState.user_id) {
    options.headers['X-User-Id'] = AuthState.user_id;
  }
  const res = await fetch(url, options);

  // Auto-handle 401: clear session and show login modal
  if (res.status === 401) {
    await logout(true);
    showLoginModal('Phiên đã hết hạn. Vui lòng đăng nhập lại.');
    throw new Error('Unauthorized');
  }
  return res;
}

/* ─── Role gating (DOM) ──────────────────────────────────── */
/**
 * Tag any element with data-role="admin" / data-role-min="premium"
 * to control visibility based on the current role.
 *
 *   data-role           : comma-separated list of allowed roles
 *   data-role-min       : minimum role (hierarchical: guest < student < premium < reviewer < admin)
 */
const ROLE_RANK = { guest: 0, student: 1, premium: 2, reviewer: 3, admin: 4 };

function applyRoleGating() {
  document.querySelectorAll('[data-role]').forEach(el => {
    const allowed = (el.dataset.role || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    if (allowed.includes(AuthState.role)) {
      el.style.display = '';
      el.classList.remove('hidden');
    } else {
      el.style.display = 'none';
    }
  });
  document.querySelectorAll('[data-role-min]').forEach(el => {
    const minRank = ROLE_RANK[(el.dataset.roleMin || '').toLowerCase()] ?? 0;
    const myRank  = ROLE_RANK[AuthState.role] ?? 0;
    if (myRank >= minRank) {
      el.style.display = '';
      el.classList.remove('hidden');
    } else {
      el.style.display = 'none';
    }
  });
}

/* ─── User badge in header ───────────────────────────────── */
function renderUserBadge() {
  const badge = document.getElementById('user-badge');
  if (!badge) return;
  if (!AuthState.token) {
    badge.innerHTML = `<button class="btn-primary btn-sm" id="btn-open-login">Đăng nhập</button>`;
    document.getElementById('btn-open-login')?.addEventListener('click', () => showLoginModal());
    return;
  }
  const roleColor = {
    admin:    '#ef4444',
    reviewer: '#f59e0b',
    premium:  '#10b981',
    student:  '#3b82f6',
    guest:    '#6b7280',
  }[AuthState.role] || '#6b7280';
  badge.innerHTML = `
    <div class="user-pill" style="--role-color:${roleColor}">
      <span class="user-pill-dot"></span>
      <span class="user-pill-id">${escapeHtml(AuthState.user_id || '')}</span>
      <span class="user-pill-role">${AuthState.role}</span>
    </div>
    <button class="btn-ghost btn-sm" id="btn-logout" title="Đăng xuất">Đăng xuất</button>
  `;
  document.getElementById('btn-logout')?.addEventListener('click', async () => {
    await logout();
    renderUserBadge();
    applyRoleGating();
    showToast('Đã đăng xuất', 'info');
  });
}

/* ─── Login modal ─────────────────────────────────────────── */
function showLoginModal(message = '') {
  const modal = document.getElementById('modal-login');
  if (!modal) return;
  const errEl = document.getElementById('login-error');
  if (errEl) errEl.textContent = message;
  modal.classList.remove('hidden');
  setTimeout(() => document.getElementById('login-username')?.focus(), 100);
}

function hideLoginModal() {
  const modal = document.getElementById('modal-login');
  if (modal) modal.classList.add('hidden');
}

let isRegisterMode = false;

document.getElementById('auth-toggle-btn')?.addEventListener('click', (e) => {
  e.preventDefault();
  isRegisterMode = !isRegisterMode;
  
  const title = document.getElementById('modal-login-title');
  const btnSubmit = document.getElementById('btn-login-submit');
  const toggleText = document.getElementById('auth-toggle-text');
  const toggleBtn = document.getElementById('auth-toggle-btn');
  const errEl = document.getElementById('login-error');
  if(errEl) errEl.textContent = '';
  
  if (isRegisterMode) {
    title.textContent = 'Đăng ký';
    btnSubmit.textContent = 'Đăng ký';
    toggleText.textContent = 'Đã có tài khoản?';
    toggleBtn.textContent = 'Đăng nhập ngay';
  } else {
    title.textContent = 'Đăng nhập';
    btnSubmit.textContent = 'Đăng nhập';
    toggleText.textContent = 'Chưa có tài khoản?';
    toggleBtn.textContent = 'Đăng ký ngay';
  }
});

async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById('login-username')?.value?.trim();
  const password = document.getElementById('login-password')?.value?.trim();
  const errEl    = document.getElementById('login-error');
  const btn      = document.getElementById('btn-login-submit');

  if (!username || !password) {
    errEl.textContent = 'Vui lòng nhập Username và Mật khẩu';
    return;
  }
  
  if (isRegisterMode && password.length < 6) {
    errEl.textContent = 'Mật khẩu phải có ít nhất 6 ký tự';
    return;
  }

  errEl.textContent = '';
  btn.disabled = true;
  btn.textContent = isRegisterMode ? 'Đang đăng ký...' : 'Đang đăng nhập...';
  
  try {
    if (isRegisterMode) {
      await registerAccount(username, password);
    } else {
      await login(username, password);
    }
    
    hideLoginModal();
    renderUserBadge();
    applyRoleGating();
    await refreshMe();
    showToast(`Chào mừng ${AuthState.user_id} (${AuthState.role})`, 'success');
    document.getElementById('login-password').value = '';
    // Redirect to workspace if on landing page
    if (document.body.classList.contains('page-landing') || window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
      setTimeout(() => { window.location.href = 'main.html'; }, 800);
    }
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = isRegisterMode ? 'Đăng ký' : 'Đăng nhập';
  }
}

/* ─── Util ────────────────────────────────────────────────── */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/* Show toast if global helper exists; otherwise no-op */
function showToast(msg, type) {
  if (typeof window.showToast === 'function') return window.showToast(msg, type);
  if (typeof window.toast === 'function')     return window.toast(msg, type);
  console.log(`[${type || 'info'}] ${msg}`);
}
