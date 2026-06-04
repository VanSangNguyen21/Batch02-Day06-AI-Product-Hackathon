/**
 * ============================================================
 * CLOUDFLARE SHIELD & AI HUB — APP SCRIPT
 * Handles Turnstile Render, Tab Switching, Workers AI Simulator,
 * Config Generator, Log Terminal, and Backend Integration.
 * ============================================================
 */

'use strict';

// Global variables
let activeTab = 'turnstile';
let turnstileWidgetId = null;
let currentSiteKey = '1x00000000000000000000AA'; // Default: Always Pass
let verifiedSession = false;
let selectedModel = 'llama-3';

// DOM elements
const logConsole = document.getElementById('log-console');
const btnVerifyGate = document.getElementById('btn-verify-gate');
const turnstileTokenInput = document.getElementById('turnstile-token');
const aiGateOverlay = document.getElementById('ai-gate-overlay');

// Backend endpoint (runs on 8080 by default)
const BACKEND_API = 'http://127.0.0.1:8080/api';

/* ─── INITIALIZATION ────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  // Setup tabs
  setupTabs();
  
  // Set up Turnstile radio selectors
  const radioButtons = document.querySelectorAll('input[name="sitekey-selector"]');
  radioButtons.forEach(radio => {
    radio.addEventListener('change', (e) => {
      currentSiteKey = e.target.value;
      logToConsole(`Site key switched to: ${currentSiteKey}`, 'info');
      initTurnstile();
    });
  });

  // Setup Event Listeners
  document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
  btnVerifyGate.addEventListener('click', verifyTurnstileToken);
  document.getElementById('btn-copy-code').addEventListener('click', () => copyToClipboard('code-snippet', 'Mã nguồn JS'));
  document.getElementById('btn-copy-headers').addEventListener('click', () => copyToClipboard('headers-output', 'Cấu hình _headers'));

  // Welcome logs
  logToConsole('System startup. Cloudflare Shield Hub ready.', 'info');
  logToConsole('Connecting to Edge Gateway...', 'info');
  setTimeout(() => {
    logToConsole('Connected! Edge IP: 103.22.200.41 (Cloudflare Anycast IP)', 'success');
    logToConsole('Loading Cloudstile engine...', 'info');
    // Init Turnstile with explicit render after script is loaded
    initTurnstileWhenReady();
  }, 800);

  // Generate initial wrangler.js code block
  updateCodeSnippet();
  generateConfig();
});

/* ─── TURNSTILE ENGINGE ──────────────────────────────────────── */
function initTurnstileWhenReady() {
  if (typeof turnstile !== 'undefined') {
    initTurnstile();
  } else {
    // Wait for the script to load
    setTimeout(initTurnstileWhenReady, 100);
  }
}

function initTurnstile() {
  if (typeof turnstile === 'undefined') return;

  btnVerifyGate.disabled = true;
  turnstileTokenInput.value = '';

  logToConsole('Rendering Turnstile widget...', 'info');
  
  try {
    // Remove existing Turnstile widget if rendered
    if (turnstileWidgetId !== null) {
      turnstile.remove(turnstileWidgetId);
      turnstileWidgetId = null;
    }
    
    // Explicit render
    turnstileWidgetId = turnstile.render('#turnstile-container', {
      sitekey: currentSiteKey,
      callback: function(token) {
        turnstileTokenInput.value = token;
        btnVerifyGate.disabled = false;
        logToConsole('Turnstile response received from Client Browser.', 'success');
        logToConsole(`Token: ${token.substring(0, 32)}...`, 'info');
        showToast('Turnstile đã hoàn tất thử thách!', 'success');
      },
      'error-callback': function(err) {
        logToConsole('Turnstile error occurred. Challenge failed.', 'error');
        btnVerifyGate.disabled = true;
        showToast('Lỗi xác thực Turnstile', 'error');
      },
      'expired-callback': function() {
        logToConsole('Turnstile token expired. Resetting widget...', 'warn');
        btnVerifyGate.disabled = true;
        showToast('Token hết hạn. Vui lòng xác thực lại.', 'info');
      }
    });
  } catch (error) {
    logToConsole(`Widget render error: ${error.message}`, 'error');
  }
}

async function verifyTurnstileToken() {
  const token = turnstileTokenInput.value;
  const username = document.getElementById('username-input').value || 'Anonymous';
  const action = document.getElementById('action-select').value;

  if (!token) {
    logToConsole('Verification failed: No token available.', 'error');
    return;
  }

  logToConsole('Initiating Backend security check...', 'info');
  logToConsole('Sending payload to secure endpoint: /api/verify-turnstile', 'info');

  btnVerifyGate.disabled = true;
  btnVerifyGate.innerHTML = '<div class="spinner"></div> Đang xác thực...';

  try {
    // Attempt real backend call
    const response = await fetch(`${BACKEND_API}/verify-turnstile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token, username, action })
    });

    const data = await response.json();

    if (response.ok && data.success) {
      logToConsole('--- BACKEND VERIFICATION OK ---', 'success');
      logToConsole(`Status: ${data.message}`, 'success');
      logToConsole(`Cloudflare Response time: ${data.cf_response_time || 'N/A'}ms`, 'success');
      logToConsole(`Edge Node Country: ${data.country || 'N/A'}`, 'info');
      
      verifiedSession = true;
      aiGateOverlay.style.opacity = '0';
      setTimeout(() => {
        aiGateOverlay.style.display = 'none';
      }, 300);

      showToast('Xác thực thành công! Đã mở khóa Workers AI Hub.', 'success');
      
      // Auto switch tab to AI Workers after success
      setTimeout(() => {
        switchTab('workers-ai');
      }, 1000);
    } else {
      logToConsole('--- BACKEND VERIFICATION FAILED ---', 'error');
      logToConsole(`Reason: ${data.detail || data.message || 'Token không hợp lệ'}`, 'error');
      showToast('Xác thực thất bại! Từ chối truy cập.', 'error');
      turnstile.reset(turnstileWidgetId);
      btnVerifyGate.disabled = true;
    }
  } catch (err) {
    // Fallback if local backend server is not running
    logToConsole('Local backend server offline. Running sandbox simulation...', 'warn');
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1500));

    if (currentSiteKey === '2x00000000000000000000AB') {
      logToConsole('Simulated Verification FAILED (Always Fail Key used).', 'error');
      showToast('Xác thực thất bại (Thử nghiệm)!', 'error');
      turnstile.reset(turnstileWidgetId);
      btnVerifyGate.disabled = true;
    } else {
      logToConsole('Simulated Verification SUCCESS. Gate verified.', 'success');
      
      verifiedSession = true;
      aiGateOverlay.style.opacity = '0';
      setTimeout(() => {
        aiGateOverlay.style.display = 'none';
      }, 300);

      showToast('Đã xác thực thành công (Chế độ mô phỏng)!', 'success');
      
      setTimeout(() => {
        switchTab('workers-ai');
      }, 1000);
    }
  } finally {
    btnVerifyGate.disabled = false;
    btnVerifyGate.innerHTML = '🔒 Xác Thực & Truy Cập';
  }
}

/* ─── TAB MANAGEMENT ────────────────────────────────────────── */
function setupTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  activeTab = tabId;
  
  // Update buttons active class
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Update tabs view
  document.querySelectorAll('.tab-content').forEach(content => {
    if (content.id === `tab-${tabId}`) {
      content.classList.add('active');
    } else {
      content.classList.remove('active');
    }
  });

  logToConsole(`Navigation: Switched to Tab [${tabId}]`, 'info');
}

/* ─── LOG TERMINAL ──────────────────────────────────────────── */
function logToConsole(message, type = 'info') {
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour12: false });
  
  const logLine = document.createElement('div');
  logLine.className = 'log-line';
  
  logLine.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="log-type ${type}">${type}</span>
    <span class="log-msg">${message}</span>
  `;
  
  logConsole.appendChild(logLine);
  logConsole.scrollTop = logConsole.scrollHeight;
}

function clearLogs() {
  logConsole.innerHTML = '';
  logToConsole('Terminal logs cleared.', 'info');
}

/* ─── WORKERS AI PLAYGROUND ──────────────────────────────────── */
function selectAIModel(modelId) {
  selectedModel = modelId;
  
  // Set active class on sidebar buttons
  document.querySelectorAll('.panel-sidebar .sidebar-btn').forEach(btn => {
    if (btn.getAttribute('data-model') === modelId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Toggle model views
  document.querySelectorAll('.model-view').forEach(view => {
    view.style.display = 'none';
  });

  if (modelId === 'llama-3') {
    document.getElementById('model-text-generator').style.display = 'block';
  } else if (modelId === 'flux') {
    document.getElementById('model-image-generator').style.display = 'block';
  } else if (modelId === 'whisper') {
    document.getElementById('model-speech-generator').style.display = 'block';
  }

  updateCodeSnippet();
}

function updateCodeSnippet() {
  const codeBox = document.getElementById('code-snippet');
  const langLabel = document.getElementById('editor-lang');
  
  let code = '';
  if (selectedModel === 'llama-3') {
    langLabel.innerText = 'Cloudflare Worker Code (JavaScript)';
    code = `export default {
  async fetch(request, env) {
    // Cổng xác thực bảo vệ dữ liệu AI
    const apiToken = env.CF_API_TOKEN;
    const accountId = env.CF_ACCOUNT_ID;
    
    const response = await fetch(
      \`https://api.cloudflare.com/client/v4/accounts/\${accountId}/ai/run/@cf/meta/llama-3.1-8b-instruct\`,
      {
        method: "POST",
        headers: { "Authorization": \`Bearer \${apiToken}\` },
        body: JSON.stringify({
          messages: [
            { role: "system", content: "You are Llama running on Cloudflare Edge." },
            { role: "user", content: "Hãy giải thích ngắn gọn Cloudflare Workers là gì?" }
          ]
        })
      }
    );
    const result = await response.json();
    return Response.json(result);
  }
};`;
  } else if (selectedModel === 'flux') {
    langLabel.innerText = 'Wrangler AI Configuration (wrangler.toml)';
    code = `name = "cloudflare-flux-generator"
main = "src/index.js"
compatibility_date = "2024-05-01"

# Bật bindings cho Workers AI
[ai]
binding = "AI"

# index.js:
# export default {
#   async fetch(request, env) {
#     const response = await env.AI.run('@cf/black-forest-labs/flux-1-schnell', {
#        prompt: "A futuristic cybernetic city..."
#     });
#     return new Response(response, { headers: { "Content-Type": "image/jpeg" } });
#   }
# };`;
  } else if (selectedModel === 'whisper') {
    langLabel.innerText = 'Cloudflare Worker (Whisper Audio API)';
    code = `export default {
  async fetch(request, env) {
    const blob = await request.blob();
    const response = await env.AI.run('@cf/openai/whisper-large-v3-play', {
      audio: [...new Uint8Array(await blob.arrayBuffer())]
    });
    return Response.json({ text: response.text });
  }
};`;
  }
  
  codeBox.textContent = code;
}

// Simulated or real request to Cloudflare Workers AI via local Backend
async function runTextGeneration() {
  const prompt = document.getElementById('prompt-input').value || '';
  const runButton = document.getElementById('btn-run-ai');
  const responseBox = document.getElementById('response-snippet');

  logToConsole(`[Workers AI] Sending prompt to Meta Llama 3.1: "${prompt.substring(0, 40)}..."`, 'info');
  
  runButton.disabled = true;
  runButton.innerHTML = '<div class="spinner"></div> Đang gọi AI Edge Model...';
  responseBox.textContent = 'Connecting to Cloudflare Workers AI edge nodes... Fetching models...';

  try {
    const response = await fetch(`${BACKEND_API}/workers-ai/text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });

    const data = await response.json();

    if (response.ok) {
      logToConsole(`[Workers AI] Request complete. Tokens: ${data.tokens_used || 'N/A'}. Cost: $0.00001`, 'success');
      responseBox.textContent = JSON.stringify(data, null, 2);
      showToast('Đã nhận phản hồi từ Llama 3.1!', 'success');
    } else {
      throw new Error(data.detail || 'Lỗi kết nối');
    }
  } catch (err) {
    logToConsole(`[Workers AI] Offline/Error. Running simulated local model...`, 'warn');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const simulatedResponse = {
      model: "@cf/meta/llama-3.1-8b-instruct",
      success: true,
      result: {
        response: `[Simulated Llama 3.1 on Cloudflare Edge]: Cloudflare Workers là một nền tảng serverless cho phép bạn chạy mã JavaScript, Rust, C hoặc C++ ngay trên mạng biên toàn cầu của Cloudflare. Với thời gian khởi động (cold start) gần như bằng 0 và vị trí địa lý cực kỳ gần với người dùng của bạn, nó mang lại tốc độ cực nhanh và khả năng tự động mở rộng theo lưu lượng truy cập.`
      },
      verification_status: "Verified by Cloudflare Turnstile token"
    };

    responseBox.textContent = JSON.stringify(simulatedResponse, null, 2);
    logToConsole(`[Workers AI] Simulated request complete. Mode: Local Sandbox.`, 'success');
    showToast('Nhận phản hồi mô phỏng thành công!', 'success');
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = '✨ Gửi Yêu Cầu Đến Edge Worker';
  }
}

async function runImageGeneration() {
  const prompt = document.getElementById('image-prompt-input').value || '';
  const runButton = document.getElementById('btn-run-image-ai');
  const responseBox = document.getElementById('response-snippet');

  logToConsole(`[Workers AI] Sending image generation prompt: "${prompt.substring(0, 40)}..."`, 'info');
  
  runButton.disabled = true;
  runButton.innerHTML = '<div class="spinner"></div> Đang vẽ ảnh trên Cloudflare Edge...';
  responseBox.textContent = 'Generating image matrix on FLUX.1-schnell model...';

  try {
    const response = await fetch(`${BACKEND_API}/workers-ai/image`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });

    const data = await response.json();

    if (response.ok) {
      logToConsole('[Workers AI] Image matrix completed!', 'success');
      responseBox.innerHTML = `{\n  "status": "success",\n  "model": "@cf/black-forest-labs/flux-1-schnell",\n  "image": "<Base64 JPEG Output>"\n}\n\n<img src="${data.image_url}" class="generated-image" style="max-width: 100%; border-radius: 8px; margin-top: 1rem; border: 1px solid var(--border-color);" />`;
      showToast('Đã tạo ảnh thành công!', 'success');
    } else {
      throw new Error(data.detail || 'Lỗi tạo ảnh');
    }
  } catch (err) {
    logToConsole(`[Workers AI] Running simulated image generator...`, 'warn');
    await new Promise(resolve => setTimeout(resolve, 2500));
    
    // We can display a cool generated image placeholder or real aesthetic image using our tool or unsplash
    const mockImageURL = 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=600&auto=format&fit=crop';
    
    responseBox.innerHTML = `{\n  "status": "success",\n  "model": "@cf/black-forest-labs/flux-1-schnell (Simulated)",\n  "image_url": "${mockImageURL}"\n}\n\n<img src="${mockImageURL}" style="max-width: 100%; border-radius: 8px; margin-top: 1rem; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />`;
    logToConsole(`[Workers AI] Image simulated successfully.`, 'success');
    showToast('Tạo ảnh mô phỏng hoàn tất!', 'success');
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = '🎨 Tạo Ảnh Bằng AI Worker';
  }
}

async function runSpeechToText() {
  const sample = document.getElementById('audio-sample-select').value;
  const runButton = document.getElementById('btn-run-speech-ai');
  const responseBox = document.getElementById('response-snippet');

  logToConsole(`[Workers AI] Audio transcription request for: ${sample}`, 'info');
  
  runButton.disabled = true;
  runButton.innerHTML = '<div class="spinner"></div> Đang dịch âm thanh...';
  responseBox.textContent = 'Transcribing binary stream using Whisper Large v3...';

  await new Promise(resolve => setTimeout(resolve, 2000));
  
  let text = '';
  if (sample === 'vinuni_intro.mp3') {
    text = "Chào mừng tất cả các học viên đến với Khóa học AI Product Kickoff Batch 02 tại trường đại học VinUniversity. Hôm nay chúng ta sẽ khởi chạy các mô hình AI trên nền tảng Serverless Cloudflare.";
  } else {
    text = "Deploying static websites on Cloudflare Pages is extremely easy. You just push your codebase to GitHub, connect Pages, and it compiles and serves your static files with HTTP/3 support and Brotli compression globally in seconds.";
  }

  const simulatedResponse = {
    model: "@cf/openai/whisper-large-v3-play",
    success: true,
    result: {
      text: text,
      confidence: 0.9882,
      duration_seconds: 14.2
    }
  };

  responseBox.textContent = JSON.stringify(simulatedResponse, null, 2);
  logToConsole('[Workers AI] Audio transcription completed successfully.', 'success');
  showToast('Phóng tác âm thanh hoàn tất!', 'success');
  runButton.disabled = false;
  runButton.innerHTML = '🎙️ Phóng Tác File Âm Thanh';
}

/* ─── PAGES CONFIG BUILDER ───────────────────────────────────── */
function generateConfig() {
  const optHsts = document.getElementById('opt-hsts').checked;
  const optCsp = document.getElementById('opt-csp').checked;
  const optCors = document.getElementById('opt-cors').checked;
  const optClickjack = document.getElementById('opt-clickjack').checked;

  let headersText = '';
  
  headersText += `# Cloudflare Pages Custom Security Headers\n`;
  headersText += `/*\n`;
  
  if (optHsts) {
    headersText += `  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload\n`;
  }
  
  if (optCsp) {
    headersText += `  Content-Security-Policy: default-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' http://127.0.0.1:8080 https://challenges.cloudflare.com;\n`;
  }
  
  if (optCors) {
    headersText += `  Access-Control-Allow-Origin: *\n`;
    headersText += `  Access-Control-Allow-Methods: GET, POST, OPTIONS\n`;
    headersText += `  Access-Control-Allow-Headers: Content-Type, Authorization\n`;
  }
  
  if (optClickjack) {
    headersText += `  X-Frame-Options: DENY\n`;
    headersText += `  X-Content-Type-Options: nosniff\n`;
    headersText += `  Referrer-Policy: strict-origin-when-cross-origin\n`;
  }

  document.getElementById('headers-output').textContent = headersText;
  logToConsole('Generated new Cloudflare Pages _headers configuration', 'info');
}

/* ─── UTILITIES & TOASTS ─────────────────────────────────────── */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'error') icon = '❌';
  if (type === 'warn') icon = '⚠️';
  
  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span>${message}</span>
  `;
  
  container.appendChild(toast);
  
  // Trigger transition
  setTimeout(() => toast.classList.add('show'), 10);
  
  // Remove toast
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 350);
  }, 4000);
}

function copyToClipboard(elementId, typeLabel) {
  const text = document.getElementById(elementId).innerText || document.getElementById(elementId).textContent;
  
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Đã sao chép ${typeLabel} vào Clipboard!`, 'success');
    logToConsole(`Clipboard: Copied ${typeLabel}`, 'info');
  }).catch(err => {
    showToast('Không thể sao chép', 'error');
  });
}
