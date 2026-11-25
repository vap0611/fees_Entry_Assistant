/**
 * Fees Entry Assistant - Complete Frontend Application
 * Features:
 * - Auth Portal (Login, Register, Initial Admin Setup, TOTP 2FA, Password Recovery, Lockout UI)
 * - Role-Based UI Controls (Admin, Staff, Read-Only Viewer) & CSRF-Protected API Client
 * - Theme Engine (Light / Dark Mode) + Antigravity Particles + Click Spark Effects
 * - Interactive Spreadsheet Ledger (360 Student Inspector, Direct Cell Payment Edit, Search/Filter, Totals)
 * - Conversational NLU Chat (Payment Modes, 2-Step Confirmation, Gap/Duplicate Alerts, 1-Click Undo)
 * - Revenue Analytics & Pending Defaulters Dashboard + Audit & Security Logs + Printable Receipts
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==============================================================
  // GLOBAL APPLICATION STATE
  // ==============================================================
  const state = {
    authenticated: false,
    needsSetup: false,
    allowSelfRegistration: true,
    csrfToken: '',
    user: null,
    currentView: 'ledger',
    cachedTableData: null,
    lastUpdatedCell: null,
    lastNewCol: null,
    previousStudentCount: 0,
    previousBaseFees: 0,
    previousCollected: 0,
    challengeToken: null,
    lastRecoveryCodes: [],
    activeStudentDetailId: null,
    confirmCallback: null,
    auditSubtab: 'ledger'
  };

  // ==============================================================
  // 1. THEME ENGINE (LIGHT / DARK MODE)
  // ==============================================================
  function initTheme() {
    const savedTheme = localStorage.getItem('fees_assistant_theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = savedTheme ? savedTheme === 'dark' : prefersDark;
    applyTheme(isDark);
  }

  function applyTheme(isDark) {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('fees_assistant_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('fees_assistant_theme', 'light');
    }
    window.dispatchEvent(new CustomEvent('theme-change', { detail: { isDark } }));
    if (window.lucide) lucide.createIcons();
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(!isDark);
  }

  document.querySelectorAll('.theme-toggle-trigger').forEach(btn => {
    btn.addEventListener('click', toggleTheme);
  });

  initTheme();

  // ==============================================================
  // 2. ANTIGRAVITY PARTICLE SIMULATION BACKGROUND
  // ==============================================================
  function initAntigravityCanvas() {
    const canvas = document.getElementById('antigravity-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = window.devicePixelRatio || 1;
    let particles = [];
    const mouse = { x: -1000, y: -1000, active: false };
    const shockwaves = [];
    let animFrameId = null;

    function isDarkTheme() {
      return document.documentElement.classList.contains('dark');
    }

    function getPalette() {
      if (isDarkTheme()) {
        return [
          { r: 59, g: 130, b: 246 },
          { r: 249, g: 115, b: 22 },
          { r: 239, g: 68, b: 68 },
          { r: 255, g: 255, b: 255 },
          { r: 96, g: 165, b: 250 }
        ];
      }
      return [
        { r: 37, g: 99, b: 235 },
        { r: 234, g: 88, b: 12 },
        { r: 220, g: 38, b: 38 },
        { r: 79, g: 70, b: 229 },
        { r: 14, g: 165, b: 233 }
      ];
    }

    function rebuildParticles() {
      const count = Math.min(Math.floor((width * height) / 18000), 75);
      const palette = getPalette();
      particles = [];
      for (let i = 0; i < count; i++) {
        const col = palette[Math.floor(Math.random() * palette.length)];
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.45,
          vy: (Math.random() - 0.5) * 0.45,
          radius: Math.random() * 2.2 + 1.2,
          color: col,
          baseAlpha: Math.random() * 0.45 + 0.2,
          pulseSpeed: Math.random() * 0.02 + 0.01,
          pulse: Math.random() * Math.PI * 2
        });
      }
    }

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      rebuildParticles();
    }

    window.addEventListener('resize', resize, { passive: true });
    window.addEventListener('theme-change', rebuildParticles);

    window.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
    }, { passive: true });

    window.addEventListener('mouseleave', () => {
      mouse.active = false;
      mouse.x = -1000;
      mouse.y = -1000;
    });

    window.addEventListener('click', (e) => {
      shockwaves.push({
        x: e.clientX,
        y: e.clientY,
        radius: 5,
        maxRadius: Math.min(width, height) * 0.35,
        alpha: 0.6,
        speed: 4.5
      });
      if (shockwaves.length > 5) shockwaves.shift();
    });

    function draw() {
      ctx.clearRect(0, 0, width, height);
      const dark = isDarkTheme();
      const maxConnDist = 95;
      const maxConnDistSq = maxConnDist * maxConnDist;

      for (let s = shockwaves.length - 1; s >= 0; s--) {
        const sw = shockwaves[s];
        sw.radius += sw.speed;
        sw.alpha *= 0.96;

        ctx.beginPath();
        ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
        ctx.strokeStyle = dark
          ? `rgba(249, 115, 22, ${sw.alpha * 0.4})`
          : `rgba(37, 99, 235, ${sw.alpha * 0.3})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        for (let i = 0; i < particles.length; i++) {
          const p = particles[i];
          const dx = p.x - sw.x;
          const dy = p.y - sw.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (Math.abs(dist - sw.radius) < 25 && dist > 1) {
            const force = (1 - Math.abs(dist - sw.radius) / 25) * 1.5;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
          }
        }

        if (sw.alpha < 0.02 || sw.radius > sw.maxRadius) {
          shockwaves.splice(s, 1);
        }
      }

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        if (mouse.active) {
          const mdx = p.x - mouse.x;
          const mdy = p.y - mouse.y;
          const mdistSq = mdx * mdx + mdy * mdy;
          const repulseRadius = 110;
          if (mdistSq < repulseRadius * repulseRadius && mdistSq > 1) {
            const mdist = Math.sqrt(mdistSq);
            const force = (1 - mdist / repulseRadius) * 0.35;
            p.vx += (mdx / mdist) * force;
            p.vy += (mdy / mdist) * force;
          }
        }

        p.vx = p.vx * 0.985 + (Math.random() - 0.5) * 0.04;
        p.vy = p.vy * 0.985 + (Math.random() - 0.5) * 0.04;
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;
        if (p.y < -10) p.y = height + 10;
        if (p.y > height + 10) p.y = -10;

        p.pulse += p.pulseSpeed;
        const currentAlpha = p.baseAlpha + Math.sin(p.pulse) * 0.15;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color.r}, ${p.color.g}, ${p.color.b}, ${Math.max(0.05, currentAlpha)})`;
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const cdx = p.x - p2.x;
          const cdy = p.y - p2.y;
          const cdistSq = cdx * cdx + cdy * cdy;
          if (cdistSq < maxConnDistSq) {
            const dist = Math.sqrt(cdistSq);
            const lineAlpha = (1 - dist / maxConnDist) * (dark ? 0.22 : 0.15);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = dark
              ? `rgba(148, 163, 184, ${lineAlpha})`
              : `rgba(100, 116, 139, ${lineAlpha})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }
      animFrameId = requestAnimationFrame(draw);
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        if (animFrameId) cancelAnimationFrame(animFrameId);
        animFrameId = null;
      } else if (!animFrameId) {
        animFrameId = requestAnimationFrame(draw);
      }
    });

    resize();
    animFrameId = requestAnimationFrame(draw);
  }

  // ==============================================================
  // 3. CLICK SPARK BURST ENGINE
  // ==============================================================
  function initClickSpark() {
    const canvas = document.getElementById('spark-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const sparks = [];
    let isRunning = false;
    let dpr = window.devicePixelRatio || 1;
    const sparkColors = ['#2563EB', '#F97316', '#EF4444', '#38BDF8', '#FBBF24', '#FFFFFF'];

    function resize() {
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    window.addEventListener('resize', resize, { passive: true });
    resize();

    function updateSparks() {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx;
        s.y += s.vy;
        s.vx *= 0.94;
        s.vy *= 0.94;
        s.alpha -= s.decay;
        s.radius *= 0.96;

        if (s.alpha <= 0 || s.radius <= 0.2) {
          sparks.splice(i, 1);
          continue;
        }
        ctx.save();
        ctx.globalAlpha = Math.max(0, s.alpha);
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      if (sparks.length > 0) {
        requestAnimationFrame(updateSparks);
      } else {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        isRunning = false;
      }
    }

    window.addEventListener('click', (e) => {
      for (let i = 0; i < 10; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3.5 + 1.5;
        sparks.push({
          x: e.clientX,
          y: e.clientY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          color: sparkColors[Math.floor(Math.random() * sparkColors.length)],
          radius: Math.random() * 2 + 1.5,
          alpha: 1,
          decay: Math.random() * 0.04 + 0.03
        });
      }
      if (!isRunning) {
        isRunning = true;
        requestAnimationFrame(updateSparks);
      }
    });
  }

  initAntigravityCanvas();
  initClickSpark();

  // ==============================================================
  // 4. SHARED UI UTILITIES (ESCAPING, TOASTS, MODALS, COUNTERS)
  // ==============================================================
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    if (!text) return '';
    const safe = escapeHtml(text);
    return safe
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code class="bg-slate-100 dark:bg-slate-800 text-blue-600 dark:text-blue-400 px-1 py-0.5 rounded font-mono text-xs border border-slate-200 dark:border-slate-700">$1</code>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n• /g, '<br>• ')
      .replace(/\n/g, '<br>');
  }

  function getColLetter(idx) {
    let letter = '';
    idx += 1;
    while (idx > 0) {
      const rem = (idx - 1) % 26;
      letter = String.fromCharCode(65 + rem) + letter;
      idx = Math.floor((idx - 1) / 26);
    }
    return letter;
  }

  function animateValue(element, start, end, duration = 450, prefix = '', suffix = '') {
    if (!element) return;
    const startTime = performance.now();
    const diff = end - start;
    function step(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + diff * ease);
      element.textContent = `${prefix}${current.toLocaleString()}${suffix}`;
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        element.textContent = `${prefix}${end.toLocaleString()}${suffix}`;
      }
    }
    requestAnimationFrame(step);
  }

  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const palette = {
      success: 'bg-emerald-600 text-white border-emerald-400/50',
      error: 'bg-red-600 text-white border-red-400/50',
      warning: 'bg-orange-500 text-white border-orange-300/50',
      info: 'bg-blue-600 text-white border-blue-400/50'
    };
    const icons = {
      success: 'check-circle-2',
      error: 'alert-octagon',
      warning: 'alert-triangle',
      info: 'info'
    };

    const toast = document.createElement('div');
    toast.className = `toast-enter pointer-events-auto flex items-center space-x-2.5 px-3.5 py-2.5 rounded-xl border shadow-xl text-xs font-semibold ${palette[type] || palette.info}`;
    toast.innerHTML = `
      <i data-lucide="${icons[type] || 'info'}" class="w-4 h-4 flex-shrink-0"></i>
      <span class="flex-1 leading-snug">${escapeHtml(message)}</span>
    `;
    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 260);
    }, 3600);
  }

  // Styled Confirm Dialog
  const modalConfirmDialog = document.getElementById('modal-confirm-dialog');
  const confirmDialogTitle = document.getElementById('confirm-dialog-title');
  const confirmDialogMessage = document.getElementById('confirm-dialog-message');
  const btnConfirmCancel = document.getElementById('btn-confirm-dialog-cancel');
  const btnConfirmOk = document.getElementById('btn-confirm-dialog-ok');

  function showConfirmDialog(title, message, onConfirm) {
    if (!modalConfirmDialog) {
      if (window.confirm(message)) onConfirm();
      return;
    }
    confirmDialogTitle.textContent = title;
    confirmDialogMessage.textContent = message;
    state.confirmCallback = onConfirm;
    modalConfirmDialog.classList.remove('hidden');
  }

  if (btnConfirmCancel) {
    btnConfirmCancel.addEventListener('click', () => {
      state.confirmCallback = null;
      modalConfirmDialog.classList.add('hidden');
    });
  }

  if (btnConfirmOk) {
    btnConfirmOk.addEventListener('click', () => {
      const cb = state.confirmCallback;
      state.confirmCallback = null;
      modalConfirmDialog.classList.add('hidden');
      if (cb) cb();
    });
  }

  // Generic Modal Open/Close helpers
  function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('hidden');
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  }

  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.getAttribute('data-close-modal')));
  });

  window.addEventListener('click', (e) => {
    const modalIds = [
      'modal-add-student', 'modal-student-detail', 'modal-cell-payment',
      'modal-add-month', 'modal-security', 'modal-users', 'modal-receipt', 'modal-confirm-dialog'
    ];
    modalIds.forEach(id => {
      const el = document.getElementById(id);
      if (el && e.target === el) closeModal(id);
    });
    const dropdown = document.getElementById('user-dropdown');
    const menuBtn = document.getElementById('btn-user-menu');
    if (dropdown && menuBtn && !menuBtn.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      [
        'modal-add-student', 'modal-student-detail', 'modal-cell-payment',
        'modal-add-month', 'modal-security', 'modal-users', 'modal-receipt', 'modal-confirm-dialog'
      ].forEach(closeModal);
      const dropdown = document.getElementById('user-dropdown');
      if (dropdown) dropdown.classList.add('hidden');
    }
  });

  // ==============================================================
  // 5. CSRF-AWARE API CLIENT
  // ==============================================================
  async function apiFetch(url, options = {}) {
    const opts = { ...options };
    const method = (opts.method || 'GET').toUpperCase();
    const headers = new Headers(opts.headers || {});

    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
      opts.body = JSON.stringify(opts.body);
    }

    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && state.csrfToken) {
      headers.set('X-CSRF-Token', state.csrfToken);
    }

    opts.headers = headers;
    const response = await fetch(url, opts);

    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (response.status === 401 && data.code === 'AUTH_REQUIRED' && state.authenticated) {
      state.authenticated = false;
      state.user = null;
      showToast('Session expired. Please sign in again.', 'warning');
      renderAuthOrApp();
    }

    return { ok: response.ok, status: response.status, data };
  }

  // ==============================================================
  // 6. AUTHENTICATION PORTAL & ACCOUNT LIFECYCLE
  // ==============================================================
  const authScreen = document.getElementById('auth-screen');
  const appShell = document.getElementById('app-shell');
  const authSetupBanner = document.getElementById('auth-setup-banner');
  const authTabsBar = document.getElementById('auth-tabs-bar');
  const tabAuthLogin = document.getElementById('tab-auth-login');
  const tabAuthRegister = document.getElementById('tab-auth-register');
  const tabAuthRecover = document.getElementById('tab-auth-recover');
  const formLogin = document.getElementById('form-login');
  const formRegister = document.getElementById('form-register');
  const formRecover = document.getElementById('form-recover');
  const form2fa = document.getElementById('form-2fa');

  function switchAuthTab(tab) {
    [tabAuthLogin, tabAuthRegister, tabAuthRecover].forEach(t => {
      if (!t) return;
      t.classList.remove('nav-tab-active');
      t.classList.add('text-slate-600', 'dark:text-slate-400');
    });
    [formLogin, formRegister, formRecover, form2fa].forEach(f => f && f.classList.add('hidden'));
    if (authTabsBar) authTabsBar.classList.remove('hidden');

    if (tab === 'login') {
      tabAuthLogin.classList.add('nav-tab-active');
      tabAuthLogin.classList.remove('text-slate-600', 'dark:text-slate-400');
      formLogin.classList.remove('hidden');
    } else if (tab === 'register') {
      tabAuthRegister.classList.add('nav-tab-active');
      tabAuthRegister.classList.remove('text-slate-600', 'dark:text-slate-400');
      formRegister.classList.remove('hidden');
    } else if (tab === 'recover') {
      tabAuthRecover.classList.add('nav-tab-active');
      tabAuthRecover.classList.remove('text-slate-600', 'dark:text-slate-400');
      formRecover.classList.remove('hidden');
    } else if (tab === '2fa') {
      if (authTabsBar) authTabsBar.classList.add('hidden');
      form2fa.classList.remove('hidden');
    }
    if (window.lucide) lucide.createIcons();
  }

  if (tabAuthLogin) tabAuthLogin.addEventListener('click', () => switchAuthTab('login'));
  if (tabAuthRegister) tabAuthRegister.addEventListener('click', () => switchAuthTab('register'));
  if (tabAuthRecover) tabAuthRecover.addEventListener('click', () => switchAuthTab('recover'));

  const linkGotoRecover = document.getElementById('link-goto-recover');
  if (linkGotoRecover) linkGotoRecover.addEventListener('click', () => switchAuthTab('recover'));

  const btnTwofaBack = document.getElementById('btn-twofa-back');
  if (btnTwofaBack) {
    btnTwofaBack.addEventListener('click', () => {
      state.challengeToken = null;
      switchAuthTab('login');
    });
  }

  // Password eye toggles
  document.querySelectorAll('.pw-eye-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-toggle-pw');
      const input = document.getElementById(targetId);
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
    });
  });

  // Password strength meter
  const regPassword = document.getElementById('reg-password');
  const regStrengthLabel = document.getElementById('reg-strength-label');
  if (regPassword) {
    regPassword.addEventListener('input', () => {
      const val = regPassword.value;
      let score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val)) score++;
      if (/[a-z]/.test(val)) score++;
      if (/\d/.test(val)) score++;

      const colors = ['bg-red-500', 'bg-orange-500', 'bg-blue-500', 'bg-emerald-500'];
      const labels = [
        'Very weak — needs 8+ chars, A-Z, a-z, 0-9',
        'Weak — add uppercase, lowercase & digits',
        'Moderate — almost meets all requirements',
        'Strong password ready!'
      ];
      document.querySelectorAll('.pw-bar').forEach((bar, i) => {
        bar.className = `pw-bar rounded-full transition-colors ${i < score ? colors[score - 1] : 'bg-slate-200 dark:bg-slate-800'}`;
      });
      if (regStrengthLabel) {
        regStrengthLabel.textContent = val ? labels[Math.max(0, score - 1)] : 'Requires 8+ chars, uppercase, lowercase & digit';
      }
    });
  }

  function applyRolePermissions() {
    const role = (state.user && state.user.role) || 'viewer';
    const isAdmin = role === 'admin';
    const canWrite = role === 'admin' || role === 'staff';

    document.querySelectorAll('.role-admin-only').forEach(el => {
      el.classList.toggle('hidden', !isAdmin);
    });
    document.querySelectorAll('.role-write-only').forEach(el => {
      el.classList.toggle('hidden', !canWrite);
    });

    const viewerBanner = document.getElementById('viewer-readonly-banner');
    if (viewerBanner) viewerBanner.classList.toggle('hidden', canWrite);

    const rolePill = document.getElementById('header-role-pill');
    if (rolePill) {
      rolePill.textContent = role.toUpperCase();
      if (isAdmin) {
        rolePill.className = 'text-[9px] px-1.5 py-0.5 rounded-full font-extrabold uppercase tracking-wider bg-gradient-to-r from-blue-600 to-orange-500 text-white';
      } else if (role === 'staff') {
        rolePill.className = 'text-[9px] px-1.5 py-0.5 rounded-full font-extrabold uppercase tracking-wider bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800';
      } else {
        rolePill.className = 'text-[9px] px-1.5 py-0.5 rounded-full font-extrabold uppercase tracking-wider bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300';
      }
    }

    if (state.user) {
      const displayName = state.user.full_name || state.user.username;
      const initials = displayName.split(/\s+/).map(p => p[0]).slice(0, 2).join('').toUpperCase() || 'U';
      const elInitials = document.getElementById('user-avatar-initials');
      const elDisp = document.getElementById('user-display-name');
      const elDropName = document.getElementById('dropdown-user-fullname');
      const elDropMeta = document.getElementById('dropdown-user-meta');
      if (elInitials) elInitials.textContent = initials;
      if (elDisp) elDisp.textContent = displayName;
      if (elDropName) elDropName.textContent = displayName;
      if (elDropMeta) elDropMeta.textContent = `@${state.user.username} • ${role.toUpperCase()}`;
    }
  }

  async function renderAuthOrApp() {
    if (state.authenticated && state.user) {
      authScreen.classList.add('hidden');
      appShell.classList.remove('hidden');
      applyRolePermissions();
      await Promise.all([checkEngineStatus(), renderLiveMockTable(), refreshActivityLog()]);
      switchWorkspaceView('ledger');
    } else {
      appShell.classList.add('hidden');
      authScreen.classList.remove('hidden');

      if (authSetupBanner) {
        authSetupBanner.classList.toggle('hidden', !state.needsSetup);
      }

      const regDisabledNotice = document.getElementById('reg-disabled-notice');
      const btnRegSubmit = document.getElementById('btn-reg-submit');
      const btnRegLabel = document.getElementById('btn-reg-label');

      if (state.needsSetup) {
        if (regDisabledNotice) regDisabledNotice.classList.add('hidden');
        if (btnRegSubmit) btnRegSubmit.disabled = false;
        if (btnRegLabel) btnRegLabel.textContent = 'Create Admin Account & Enter';
        switchAuthTab('register');
      } else {
        const regAllowed = state.allowSelfRegistration;
        if (regDisabledNotice) regDisabledNotice.classList.toggle('hidden', regAllowed);
        if (btnRegSubmit) btnRegSubmit.disabled = !regAllowed;
        if (btnRegLabel) btnRegLabel.textContent = 'Create Staff Account';
        switchAuthTab('login');
      }
    }
    if (window.lucide) lucide.createIcons();
  }

  async function bootstrapAuth() {
    const res = await apiFetch('/api/auth/status');
    if (res.ok) {
      state.csrfToken = res.data.csrf_token || '';
      state.authenticated = Boolean(res.data.authenticated);
      state.needsSetup = Boolean(res.data.needs_setup);
      state.allowSelfRegistration = Boolean(res.data.allow_self_registration);
      state.user = res.data.user || null;
    }
    await renderAuthOrApp();
  }

  function showRecoveryCodesModal(codes) {
    state.lastRecoveryCodes = codes || [];
    const grid = document.getElementById('recovery-codes-grid');
    if (grid) {
      grid.innerHTML = state.lastRecoveryCodes.map(c =>
        `<div class="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100">${escapeHtml(c)}</div>`
      ).join('');
    }
    openModal('modal-recovery-codes');
  }

  const btnCopyCodes = document.getElementById('btn-copy-recovery-codes');
  if (btnCopyCodes) {
    btnCopyCodes.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(state.lastRecoveryCodes.join('\n'));
        showToast('Recovery codes copied to clipboard!', 'success');
      } catch {
        showToast('Could not access clipboard. Download .TXT instead.', 'warning');
      }
    });
  }

  const btnDownloadCodes = document.getElementById('btn-download-recovery-codes');
  if (btnDownloadCodes) {
    btnDownloadCodes.addEventListener('click', () => {
      const content = [
        'FEES ENTRY ASSISTANT - BACKUP RECOVERY CODES',
        `Account: ${state.user ? state.user.username : ''}`,
        'Keep these safe. Each code works once for password reset or 2FA fallback.',
        '',
        ...state.lastRecoveryCodes
      ].join('\n');
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'fees_assistant_recovery_codes.txt';
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  const btnCloseRecCodes = document.getElementById('btn-close-recovery-codes');
  if (btnCloseRecCodes) {
    btnCloseRecCodes.addEventListener('click', () => closeModal('modal-recovery-codes'));
  }

  // Handle Login Form
  if (formLogin) {
    formLogin.addEventListener('submit', async (e) => {
      e.preventDefault();
      const loginErr = document.getElementById('login-error');
      const btn = document.getElementById('btn-login-submit');
      if (loginErr) loginErr.classList.add('hidden');
      if (btn) btn.disabled = true;

      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: {
          identifier: document.getElementById('login-identifier').value.trim(),
          password: document.getElementById('login-password').value,
          remember_me: document.getElementById('login-remember').checked
        }
      });

      if (btn) btn.disabled = false;

      if (res.ok && res.data.status === '2fa_required') {
        state.challengeToken = res.data.challenge_token;
        document.getElementById('twofa-code').value = '';
        switchAuthTab('2fa');
        document.getElementById('twofa-code').focus();
        return;
      }

      if (res.ok && res.data.status === 'success') {
        state.authenticated = true;
        state.user = res.data.user;
        state.csrfToken = res.data.csrf_token;
        state.needsSetup = false;
        document.getElementById('login-password').value = '';
        showToast(`Welcome back, ${state.user.full_name || state.user.username}!`, 'success');
        await renderAuthOrApp();
      } else if (loginErr) {
        loginErr.textContent = res.data.error || 'Authentication failed.';
        loginErr.classList.remove('hidden');
      }
    });
  }

  // Handle 2FA Verification Form
  if (form2fa) {
    form2fa.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errBox = document.getElementById('twofa-error');
      if (errBox) errBox.classList.add('hidden');

      const res = await apiFetch('/api/auth/login/2fa', {
        method: 'POST',
        body: {
          challenge_token: state.challengeToken,
          code: document.getElementById('twofa-code').value.trim()
        }
      });

      if (res.ok && res.data.status === 'success') {
        state.challengeToken = null;
        state.authenticated = true;
        state.user = res.data.user;
        state.csrfToken = res.data.csrf_token;
        showToast(res.data.used_recovery_code ? 'Signed in using recovery code!' : '2FA verified!', 'success');
        await renderAuthOrApp();
      } else if (errBox) {
        errBox.textContent = res.data.error || 'Invalid 2FA code.';
        errBox.classList.remove('hidden');
      }
    });
  }

  // Handle Registration Form
  if (formRegister) {
    formRegister.addEventListener('submit', async (e) => {
      e.preventDefault();
      const regErr = document.getElementById('reg-error');
      const btn = document.getElementById('btn-reg-submit');
      if (regErr) regErr.classList.add('hidden');
      if (btn) btn.disabled = true;

      const res = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: {
          full_name: document.getElementById('reg-fullname').value.trim(),
          username: document.getElementById('reg-username').value.trim(),
          email: document.getElementById('reg-email').value.trim(),
          password: document.getElementById('reg-password').value
        }
      });

      if (btn) btn.disabled = false;

      if (res.ok && res.data.status === 'success') {
        state.authenticated = true;
        state.needsSetup = false;
        state.user = res.data.user;
        state.csrfToken = res.data.csrf_token;
        document.getElementById('reg-password').value = '';
        await renderAuthOrApp();
        showToast(res.data.message || 'Account created!', 'success');
        if (res.data.recovery_codes && res.data.recovery_codes.length) {
          showRecoveryCodesModal(res.data.recovery_codes);
        }
      } else if (regErr) {
        regErr.textContent = res.data.error || 'Registration failed.';
        regErr.classList.remove('hidden');
      }
    });
  }

  // Handle Password Recovery Form
  if (formRecover) {
    formRecover.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errBox = document.getElementById('rec-error');
      const okBox = document.getElementById('rec-success');
      errBox.classList.add('hidden');
      okBox.classList.add('hidden');

      const res = await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        body: {
          identifier: document.getElementById('rec-identifier').value.trim(),
          recovery_code: document.getElementById('rec-code').value.trim(),
          new_password: document.getElementById('rec-new-password').value
        }
      });

      if (res.ok && res.data.status === 'success') {
        okBox.textContent = res.data.message;
        okBox.classList.remove('hidden');
        document.getElementById('rec-code').value = '';
        document.getElementById('rec-new-password').value = '';
        showToast('Password reset! Sign in with your new password.', 'success');
      } else {
        errBox.textContent = res.data.error || 'Failed to reset password.';
        errBox.classList.remove('hidden');
      }
    });
  }

  // User Menu & Logout Controls
  const btnUserMenu = document.getElementById('btn-user-menu');
  const userDropdown = document.getElementById('user-dropdown');
  if (btnUserMenu && userDropdown) {
    btnUserMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      userDropdown.classList.toggle('hidden');
    });
  }

  const btnLogout = document.getElementById('btn-logout');
  if (btnLogout) {
    btnLogout.addEventListener('click', async () => {
      userDropdown.classList.add('hidden');
      const res = await apiFetch('/api/auth/logout', { method: 'POST' });
      state.authenticated = false;
      state.user = null;
      state.csrfToken = res.data.csrf_token || '';
      showToast('Signed out securely.', 'info');
      await renderAuthOrApp();
    });
  }

  const btnLogoutAll = document.getElementById('btn-logout-all');
  if (btnLogoutAll) {
    btnLogoutAll.addEventListener('click', () => {
      userDropdown.classList.add('hidden');
      showConfirmDialog('Sign Out All Devices?', 'This invalidates all active browser sessions across every device.', async () => {
        const res = await apiFetch('/api/auth/logout-all', { method: 'POST' });
        state.authenticated = false;
        state.user = null;
        state.csrfToken = res.data.csrf_token || '';
        showToast('All active sessions invalidated.', 'info');
        await renderAuthOrApp();
      });
    });
  }

  // ==============================================================
  // 7. WORKSPACE VIEW SWITCHING (LEDGER / ANALYTICS / AUDIT)
  // ==============================================================
  function switchWorkspaceView(view) {
    state.currentView = view;
    const views = {
      ledger: document.getElementById('view-ledger'),
      analytics: document.getElementById('view-analytics'),
      audit: document.getElementById('view-audit')
    };

    Object.entries(views).forEach(([name, el]) => {
      if (el) el.classList.toggle('hidden', name !== view);
    });

    document.querySelectorAll('.nav-view-btn').forEach(btn => {
      const active = btn.getAttribute('data-view') === view;
      btn.classList.toggle('nav-tab-active', active);
      btn.classList.toggle('text-slate-600', !active);
      btn.classList.toggle('dark:text-slate-400', !active);
    });

    if (view === 'analytics') loadAnalytics();
    if (view === 'audit') loadAuditView();
    if (window.lucide) lucide.createIcons();
  }

  document.querySelectorAll('.nav-view-btn').forEach(btn => {
    btn.addEventListener('click', () => switchWorkspaceView(btn.getAttribute('data-view')));
  });

  const kpiPendingPill = document.getElementById('kpi-pending-pill');
  if (kpiPendingPill) {
    kpiPendingPill.addEventListener('click', () => switchWorkspaceView('analytics'));
  }

  // ==============================================================
  // 8. LIVE LEDGER TABLE, SEARCH, FILTERS & TOTALS FOOTER
  // ==============================================================
  const tableSearchInput = document.getElementById('table-search-input');
  const btnClearSearch = document.getElementById('btn-clear-search');
  const tableStatusFilter = document.getElementById('table-status-filter');
  const tableSchoolFilter = document.getElementById('table-school-filter');
  const tableStudentCount = document.getElementById('table-student-count');
  const liveTableHeader = document.getElementById('live-table-header');
  const liveTableBody = document.getElementById('live-table-body');
  const liveTableFooter = document.getElementById('live-table-footer');
  const tableScrollContainer = document.getElementById('table-scroll-container');
  const btnToggleTableHeight = document.getElementById('btn-toggle-table-height');

  let isTableExpanded = false;
  if (btnToggleTableHeight && tableScrollContainer) {
    btnToggleTableHeight.addEventListener('click', () => {
      isTableExpanded = !isTableExpanded;
      if (isTableExpanded) {
        tableScrollContainer.classList.remove('max-h-48', 'sm:max-h-60');
        tableScrollContainer.classList.add('max-h-[58vh]');
      } else {
        tableScrollContainer.classList.add('max-h-48', 'sm:max-h-60');
        tableScrollContainer.classList.remove('max-h-[58vh]');
      }
    });
  }

  async function checkEngineStatus() {
    const kpiEngineMode = document.getElementById('kpi-engine-mode');
    if (!kpiEngineMode) return;
    const res = await apiFetch('/api/config');
    if (res.ok) {
      if (res.data.has_gemini_key || res.data.gemini_mode === 'gemini_api') {
        kpiEngineMode.innerHTML = '<span class="text-blue-600 dark:text-blue-400 font-bold">✨ Gemini AI</span>';
      } else {
        kpiEngineMode.innerHTML = '<span class="text-orange-600 dark:text-orange-400 font-bold">⚡ Rule Engine</span>';
      }
    }
  }

  function updateKPIBar(data) {
    const activeStudents = data.active_students ?? (data.students ? data.students.length : 0);
    const totalBase = data.total_base_fees || 0;
    const focusCollected = data.focus_collected || 0;
    const months = data.months || [];

    const kpiStudentsCount = document.getElementById('kpi-students-count');
    const kpiBaseFees = document.getElementById('kpi-base-fees');
    const kpiFocusMonthLabel = document.getElementById('kpi-focus-month-label');
    const kpiFocusCollected = document.getElementById('kpi-focus-collected');
    const kpiCollectionRate = document.getElementById('kpi-collection-rate');
    const kpiPendingCount = document.getElementById('kpi-pending-count');
    const kpiMonthsCount = document.getElementById('kpi-months-count');

    if (kpiStudentsCount) {
      animateValue(kpiStudentsCount, state.previousStudentCount, activeStudents, 450);
      state.previousStudentCount = activeStudents;
    }
    if (kpiBaseFees) {
      animateValue(kpiBaseFees, state.previousBaseFees, totalBase, 450, '₹');
      state.previousBaseFees = totalBase;
    }
    if (kpiFocusMonthLabel) {
      kpiFocusMonthLabel.textContent = data.focus_month ? `${data.focus_month}:` : 'Collected:';
    }
    if (kpiFocusCollected) {
      animateValue(kpiFocusCollected, state.previousCollected, focusCollected, 450, '₹');
      state.previousCollected = focusCollected;
    }
    if (kpiCollectionRate) {
      kpiCollectionRate.textContent = `${data.collection_rate || 0}%`;
    }
    if (kpiPendingCount) {
      kpiPendingCount.textContent = data.pending_count ?? 0;
    }
    if (kpiMonthsCount) {
      kpiMonthsCount.textContent = `${months.length} Active`;
    }
  }

  function populateSchoolFilter(students) {
    if (!tableSchoolFilter) return;
    const current = tableSchoolFilter.value;
    const schools = [...new Set(students.map(s => s.school).filter(Boolean))].sort();
    tableSchoolFilter.innerHTML = '<option value="">All Schools</option>' +
      schools.map(sch => `<option value="${escapeHtml(sch)}">${escapeHtml(sch)}</option>`).join('');
    if (schools.includes(current)) {
      tableSchoolFilter.value = current;
    }
  }

  async function renderLiveMockTable(data = null) {
    try {
      if (!data) {
        const res = await apiFetch('/api/mock-table');
        if (!res.ok) return;
        data = res.data;
      }
      state.cachedTableData = data;
      updateKPIBar(data);

      const months = data.months || [];
      const students = data.students || [];
      const focusMonth = data.focus_month || (months.length ? months[months.length - 1] : null);
      const isAdmin = state.user && state.user.role === 'admin';
      const canWrite = state.user && (state.user.role === 'admin' || state.user.role === 'staff');

      populateSchoolFilter(students);

      if (tableStudentCount) {
        tableStudentCount.textContent = `${students.length} Students • ₹${(data.total_base_fees || 0).toLocaleString()}`;
      }

      // Header HTML
      let headerHtml = `
        <th class="p-2.5 sticky left-0 bg-slate-100 dark:bg-slate-900 z-20 border-r border-slate-200 dark:border-slate-800 min-w-[140px]">
          <div class="text-[9px] text-slate-400 font-mono font-medium">Col A</div>
          <div class="font-bold">Student Name</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 min-w-[56px] text-center">
          <div class="text-[9px] text-slate-400 font-mono font-medium">Col B</div>
          <div class="font-bold">Std</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 min-w-[115px]">
          <div class="text-[9px] text-slate-400 font-mono font-medium">Col C</div>
          <div class="font-bold">School</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 text-right min-w-[88px]">
          <div class="text-[9px] text-slate-400 font-mono font-medium">Col D</div>
          <div class="font-bold">Base Fee</div>
        </th>
      `;

      months.forEach((m, idx) => {
        const colLetter = getColLetter(4 + idx);
        const isNewCol = (state.lastNewCol === m);
        const colBgClass = isNewCol
          ? 'bg-amber-100 dark:bg-amber-950/60 col-new text-amber-900 dark:text-amber-300'
          : 'bg-slate-50 dark:bg-slate-900/95 text-slate-800 dark:text-slate-100';

        const deleteBtn = isAdmin
          ? `<button type="button" data-month="${escapeHtml(m)}" class="btn-delete-col text-slate-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 rounded hover:bg-red-50 dark:hover:bg-red-950/40 transition cursor-pointer" title="Delete column '${escapeHtml(m)}'" aria-label="Delete column ${escapeHtml(m)}"><i data-lucide="trash-2" class="w-3 h-3"></i></button>`
          : '';

        headerHtml += `
          <th class="p-2.5 text-center border-r border-slate-200 dark:border-slate-800 min-w-[118px] group ${colBgClass}">
            <div class="flex items-center justify-between text-[9px] text-blue-600 dark:text-blue-400 font-mono font-bold mb-0.5">
              <span>Col ${colLetter}</span>
              ${deleteBtn}
            </div>
            <div class="font-mono font-bold tracking-tight">${escapeHtml(m)}</div>
          </th>
        `;
      });
      liveTableHeader.innerHTML = headerHtml;

      // Filtering
      const query = (tableSearchInput ? tableSearchInput.value : '').trim().toLowerCase();
      const statusMode = tableStatusFilter ? tableStatusFilter.value : 'all';
      const schoolFilter = tableSchoolFilter ? tableSchoolFilter.value : '';

      const filteredStudents = students.filter(s => {
        const stStatus = s.status || 'active';
        if (statusMode === 'all' && stStatus !== 'active') return false;
        if (statusMode === 'inactive' && stStatus !== 'inactive') return false;
        if (statusMode === 'paid') {
          if (stStatus !== 'active') return false;
          const paidAmt = focusMonth ? (s.payments || {})[focusMonth] : null;
          if (!(paidAmt > 0)) return false;
        }
        if (statusMode === 'pending') {
          if (stStatus !== 'active') return false;
          const paidAmt = focusMonth ? (s.payments || {})[focusMonth] : null;
          if (paidAmt > 0) return false;
        }
        if (schoolFilter && s.school !== schoolFilter) return false;
        if (query) {
          const hit = (s.name && s.name.toLowerCase().includes(query)) ||
                      (s.school && s.school.toLowerCase().includes(query)) ||
                      (s.std && String(s.std).toLowerCase().includes(query)) ||
                      (s.guardian_phone && s.guardian_phone.toLowerCase().includes(query));
          if (!hit) return false;
        }
        return true;
      });

      if (tableStudentCount && (query || statusMode !== 'all' || schoolFilter)) {
        tableStudentCount.textContent = `Showing ${filteredStudents.length} of ${students.length}`;
      }

      if (filteredStudents.length === 0) {
        liveTableBody.innerHTML = `
          <tr>
            <td colspan="${4 + months.length}" class="p-6 text-center text-slate-400 dark:text-slate-500 font-sans text-xs">
              No students match the current filter.
            </td>
          </tr>
        `;
      } else {
        liveTableBody.innerHTML = filteredStudents.map(s => {
          const payments = s.payments || {};
          const metaMap = s.payments_meta || {};
          const isInactive = (s.status || 'active') === 'inactive';

          let rowHtml = `
            <tr class="hover:bg-blue-50/40 dark:hover:bg-slate-800/40 transition ${isInactive ? 'opacity-55' : ''}">
              <td class="p-2.5 sticky left-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 font-sans">
                <button type="button" data-student-id="${s.id}" class="btn-open-student text-left font-bold text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 hover:underline flex items-center space-x-1.5 cursor-pointer">
                  <span>${escapeHtml(s.name)}</span>
                  ${isInactive ? '<span class="text-[9px] px-1 py-0.2 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">INACTIVE</span>' : ''}
                </button>
              </td>
              <td class="p-2.5 text-center text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 font-sans text-xs">${escapeHtml(s.std || '—')}</td>
              <td class="p-2.5 text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 font-sans text-xs truncate max-w-[140px]">${escapeHtml(s.school || '—')}</td>
              <td class="p-2.5 text-right font-semibold text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-800 font-mono text-xs">₹${Number(s.monthly_fee).toLocaleString()}</td>
          `;

          months.forEach(m => {
            const paid = payments[m];
            const meta = metaMap[m] || {};
            const isJustUpdated = (state.lastUpdatedCell && state.lastUpdatedCell.student_id === s.id && state.lastUpdatedCell.month === m);
            const cellClass = isJustUpdated ? 'cell-updated' : '';
            const clickableAttrs = canWrite
              ? `data-cell-sid="${s.id}" data-cell-sname="${escapeHtml(s.name)}" data-cell-month="${escapeHtml(m)}" data-cell-amount="${paid || s.monthly_fee}" data-cell-paid="${paid ? '1' : '0'}" data-cell-mode="${escapeHtml(meta.payment_mode || 'Cash')}" data-cell-note="${escapeHtml(meta.note || '')}"`
              : '';

            if (paid !== undefined && paid !== null && paid !== '') {
              const modeTag = meta.payment_mode ? `<span class="text-[9px] opacity-75 ml-1">${escapeHtml(meta.payment_mode === 'Bank Transfer' ? 'Bank' : meta.payment_mode)}</span>` : '';
              const tooltip = meta.recorded_by ? `Recorded by ${meta.recorded_by}` : 'Click to edit';
              rowHtml += `
                <td class="p-1.5 text-center border-r border-slate-100 dark:border-slate-800/60 ${cellClass}">
                  <button type="button" ${clickableAttrs} title="${escapeHtml(tooltip)}" class="${canWrite ? 'cell-pay-btn cursor-pointer hover:scale-105' : 'cursor-default'} inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-bold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 border border-emerald-300/50 dark:border-emerald-700/50 transition">
                    ₹${Number(paid).toLocaleString()}${modeTag}
                  </button>
                </td>
              `;
            } else {
              rowHtml += `
                <td class="p-1.5 text-center border-r border-slate-100 dark:border-slate-800/60">
                  <button type="button" ${clickableAttrs} class="${canWrite ? 'cell-pay-btn cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 px-2.5 py-0.5 rounded-lg' : 'cursor-default'} text-slate-300 dark:text-slate-600 font-sans text-xs transition">
                    ${canWrite ? '—' : '—'}
                  </button>
                </td>
              `;
            }
          });

          rowHtml += '</tr>';
          return rowHtml;
        }).join('');
      }

      // Totals Summary Footer Row
      if (liveTableFooter) {
        const filteredBaseTotal = filteredStudents.reduce((acc, s) => acc + (s.status !== 'inactive' ? Number(s.monthly_fee || 0) : 0), 0);
        let footerHtml = `
          <tr>
            <td class="p-2 sticky left-0 bg-slate-100 dark:bg-slate-900 z-10 border-r border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-sans">TOTAL (${filteredStudents.length})</td>
            <td class="p-2 border-r border-slate-200 dark:border-slate-800"></td>
            <td class="p-2 border-r border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-sans">Expected Base</td>
            <td class="p-2 text-right border-r border-slate-200 dark:border-slate-800 text-blue-700 dark:text-blue-300">₹${filteredBaseTotal.toLocaleString()}</td>
        `;
        months.forEach(m => {
          const sumM = filteredStudents.reduce((acc, s) => acc + Number((s.payments || {})[m] || 0), 0);
          const pct = filteredBaseTotal > 0 ? Math.round((sumM / filteredBaseTotal) * 100) : 0;
          footerHtml += `
            <td class="p-2 text-center border-r border-slate-200 dark:border-slate-800 text-emerald-700 dark:text-emerald-300">
              ₹${sumM.toLocaleString()} <span class="text-[9px] text-slate-500 dark:text-slate-400">(${pct}%)</span>
            </td>
          `;
        });
        footerHtml += '</tr>';
        liveTableFooter.innerHTML = footerHtml;
      }

      if (window.lucide) lucide.createIcons();
    } catch (e) {
      console.error('Error rendering table:', e);
    }
  }

  // Table Filters & Search
  if (tableSearchInput) {
    tableSearchInput.addEventListener('input', () => {
      if (btnClearSearch) btnClearSearch.classList.toggle('hidden', !tableSearchInput.value.trim());
      renderLiveMockTable(state.cachedTableData);
    });
  }
  if (btnClearSearch) {
    btnClearSearch.addEventListener('click', () => {
      tableSearchInput.value = '';
      btnClearSearch.classList.add('hidden');
      tableSearchInput.focus();
      renderLiveMockTable(state.cachedTableData);
    });
  }
  if (tableStatusFilter) {
    tableStatusFilter.addEventListener('change', () => renderLiveMockTable(state.cachedTableData));
  }
  if (tableSchoolFilter) {
    tableSchoolFilter.addEventListener('change', () => renderLiveMockTable(state.cachedTableData));
  }

  // Table Click Delegation (Delete Col, Student 360, Quick Cell Pay)
  if (liveTableHeader) {
    liveTableHeader.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-delete-col');
      if (btn) {
        const month = btn.getAttribute('data-month');
        if (month) confirmDeleteColumn(month);
      }
    });
  }

  if (liveTableBody) {
    liveTableBody.addEventListener('click', (e) => {
      const studentBtn = e.target.closest('.btn-open-student');
      if (studentBtn) {
        openStudentDetailModal(Number(studentBtn.getAttribute('data-student-id')));
        return;
      }
      const cellBtn = e.target.closest('.cell-pay-btn');
      if (cellBtn) {
        openCellPaymentModal({
          studentId: Number(cellBtn.getAttribute('data-cell-sid')),
          studentName: cellBtn.getAttribute('data-cell-sname'),
          month: cellBtn.getAttribute('data-cell-month'),
          amount: Number(cellBtn.getAttribute('data-cell-amount')),
          isPaid: cellBtn.getAttribute('data-cell-paid') === '1',
          mode: cellBtn.getAttribute('data-cell-mode') || 'Cash',
          note: cellBtn.getAttribute('data-cell-note') || ''
        });
      }
    });
  }

  // ==============================================================
  // 9. STUDENT 360 DETAIL MODAL, DIRECT CELL PAYMENT & ADD MONTH
  // ==============================================================
  function openCellPaymentModal({ studentId, studentName, month, amount, isPaid, mode = 'Cash', note = '' }) {
    document.getElementById('cell-pay-student-id').value = studentId;
    document.getElementById('cell-pay-month').value = month;
    document.getElementById('cell-pay-subtitle').textContent = `${studentName} • ${month}`;
    document.getElementById('cell-pay-amount').value = amount || '';
    document.getElementById('cell-pay-mode').value = mode || 'Cash';
    document.getElementById('cell-pay-note').value = note || '';

    const clearBtn = document.getElementById('btn-cell-pay-clear');
    if (clearBtn) clearBtn.classList.toggle('hidden', !isPaid);
    openModal('modal-cell-payment');
    setTimeout(() => document.getElementById('cell-pay-amount').focus(), 80);
  }

  const formCellPayment = document.getElementById('form-cell-payment');
  if (formCellPayment) {
    formCellPayment.addEventListener('submit', async (e) => {
      e.preventDefault();
      const sid = Number(document.getElementById('cell-pay-student-id').value);
      const month = document.getElementById('cell-pay-month').value;
      const amount = Number(document.getElementById('cell-pay-amount').value);
      const payment_mode = document.getElementById('cell-pay-mode').value;
      const note = document.getElementById('cell-pay-note').value.trim();

      const res = await apiFetch('/api/payments', {
        method: 'POST',
        body: { student_id: sid, month_header: month, amount, payment_mode, note }
      });
      if (res.ok && res.data.status === 'success') {
        closeModal('modal-cell-payment');
        state.lastUpdatedCell = res.data.updated_cell;
        await renderLiveMockTable(res.data.table);
        await refreshActivityLog();
        if (!document.getElementById('modal-student-detail').classList.contains('hidden')) {
          await openStudentDetailModal(sid);
        }
        if (state.currentView === 'analytics') await loadAnalytics();
        showToast(`Saved ₹${amount.toLocaleString()} (${payment_mode}) for ${month}`, 'success');
      } else {
        showToast(res.data.reply || res.data.error || 'Failed to save payment.', 'error');
      }
    });
  }

  const btnCellPayClear = document.getElementById('btn-cell-pay-clear');
  if (btnCellPayClear) {
    btnCellPayClear.addEventListener('click', () => {
      const sid = Number(document.getElementById('cell-pay-student-id').value);
      const month = document.getElementById('cell-pay-month').value;
      showConfirmDialog('Clear Payment Entry?', `Clear the recorded payment for ${month}?`, async () => {
        const res = await apiFetch('/api/payments', {
          method: 'DELETE',
          body: { student_id: sid, month_header: month }
        });
        if (res.ok && res.data.status === 'success') {
          closeModal('modal-cell-payment');
          await renderLiveMockTable(res.data.table);
          await refreshActivityLog();
          if (!document.getElementById('modal-student-detail').classList.contains('hidden')) {
            await openStudentDetailModal(sid);
          }
          showToast('Payment cell cleared.', 'warning');
        } else {
          showToast(res.data.reply || 'Failed to clear cell.', 'error');
        }
      });
    });
  }

  // Student 360 Modal
  const tabStudentHistory = document.getElementById('tab-student-history');
  const tabStudentEdit = document.getElementById('tab-student-edit');
  const historyPanel = document.getElementById('student-detail-history-panel');
  const formEditStudent = document.getElementById('form-edit-student');

  function switchStudentModalTab(tab) {
    if (tab === 'history') {
      tabStudentHistory.classList.add('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
      tabStudentHistory.classList.remove('border-transparent', 'text-slate-500');
      tabStudentEdit.classList.remove('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
      tabStudentEdit.classList.add('border-transparent', 'text-slate-500');
      historyPanel.classList.remove('hidden');
      formEditStudent.classList.add('hidden');
    } else {
      tabStudentEdit.classList.add('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
      tabStudentEdit.classList.remove('border-transparent', 'text-slate-500');
      tabStudentHistory.classList.remove('border-blue-600', 'text-blue-600', 'dark:text-blue-400');
      tabStudentHistory.classList.add('border-transparent', 'text-slate-500');
      formEditStudent.classList.remove('hidden');
      historyPanel.classList.add('hidden');
    }
  }

  if (tabStudentHistory) tabStudentHistory.addEventListener('click', () => switchStudentModalTab('history'));
  if (tabStudentEdit) tabStudentEdit.addEventListener('click', () => switchStudentModalTab('edit'));

  async function openStudentDetailModal(studentId) {
    const res = await apiFetch(`/api/students/${studentId}`);
    if (!res.ok) {
      showToast('Failed to load student details.', 'error');
      return;
    }

    const { student, history, total_paid, paid_months_count, pending_months_count } = res.data;
    state.activeStudentDetailId = student.id;
    const canWrite = state.user && (state.user.role === 'admin' || state.user.role === 'staff');

    document.getElementById('student-detail-title').textContent = student.name;
    document.getElementById('student-detail-subtitle').textContent =
      `Std ${student.std || '—'} • ${student.school || 'No School'} • Base Fee: ₹${Number(student.monthly_fee).toLocaleString()}/mo`;

    // Populate Edit Form
    document.getElementById('edit-student-id').value = student.id;
    document.getElementById('edit-student-name').value = student.name;
    document.getElementById('edit-student-std').value = student.std || '';
    document.getElementById('edit-student-school').value = student.school || '';
    document.getElementById('edit-student-fee').value = student.monthly_fee;
    document.getElementById('edit-student-status').value = student.status || 'active';
    document.getElementById('edit-student-phone').value = student.guardian_phone || '';
    document.getElementById('edit-student-notes').value = student.notes || '';

    // Populate History Panel
    const phoneLink = student.guardian_phone
      ? `<a href="tel:${escapeHtml(student.guardian_phone)}" class="text-blue-600 dark:text-blue-400 hover:underline font-mono">${escapeHtml(student.guardian_phone)}</a>`
      : '<span class="text-slate-400">Not set</span>';

    historyPanel.innerHTML = `
      <div class="grid grid-cols-3 gap-2.5 text-center">
        <div class="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/70 dark:border-emerald-900">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase">Total Paid</p>
          <p class="text-base font-extrabold font-mono text-emerald-700 dark:text-emerald-300">₹${Number(total_paid).toLocaleString()}</p>
        </div>
        <div class="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200/70 dark:border-blue-900">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase">Paid Cycles</p>
          <p class="text-base font-extrabold font-mono text-blue-700 dark:text-blue-300">${paid_months_count}</p>
        </div>
        <div class="p-3 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200/70 dark:border-red-900">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase">Pending Cycles</p>
          <p class="text-base font-extrabold font-mono text-red-700 dark:text-red-300">${pending_months_count}</p>
        </div>
      </div>

      <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800 text-xs flex flex-wrap gap-4 justify-between">
        <div><span class="text-slate-400 font-bold">Guardian Phone:</span> ${phoneLink}</div>
        <div><span class="text-slate-400 font-bold">Notes:</span> <span class="text-slate-700 dark:text-slate-300">${escapeHtml(student.notes || 'None')}</span></div>
      </div>

      <div class="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden text-xs">
        ${history.map(item => {
          if (item.status === 'paid') {
            return `
              <div class="p-3 flex items-center justify-between bg-white dark:bg-slate-900/50">
                <div>
                  <span class="font-mono font-bold text-slate-900 dark:text-white">${escapeHtml(item.month)}</span>
                  <span class="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold">₹${Number(item.amount).toLocaleString()} • ${escapeHtml(item.payment_mode)}</span>
                  <p class="text-[10px] text-slate-400 mt-0.5">By ${escapeHtml(item.recorded_by)} ${item.note ? '• ' + escapeHtml(item.note) : ''}</p>
                </div>
                <div class="flex items-center space-x-1.5">
                  <button type="button" class="btn-receipt px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-300 font-bold hover:bg-blue-100 cursor-pointer" data-rmonth="${escapeHtml(item.month)}" data-ramount="${item.amount}" data-rmode="${escapeHtml(item.payment_mode)}" data-rentry="${escapeHtml(item.entry_id)}" data-rdate="${escapeHtml(item.paid_at)}">Receipt</button>
                  ${canWrite ? `<button type="button" class="btn-detail-pay px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-semibold cursor-pointer" data-dmonth="${escapeHtml(item.month)}" data-damount="${item.amount}" data-dpaid="1" data-dmode="${escapeHtml(item.payment_mode)}" data-dnote="${escapeHtml(item.note)}">Edit</button>` : ''}
                </div>
              </div>
            `;
          }
          return `
            <div class="p-3 flex items-center justify-between bg-slate-50/60 dark:bg-slate-900/20">
              <div>
                <span class="font-mono font-bold text-slate-700 dark:text-slate-300">${escapeHtml(item.month)}</span>
                <span class="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 font-bold">Pending</span>
              </div>
              ${canWrite ? `<button type="button" class="btn-detail-pay px-3 py-1 rounded-lg btn-primary-gradient font-bold cursor-pointer" data-dmonth="${escapeHtml(item.month)}" data-damount="${student.monthly_fee}" data-dpaid="0">Pay ₹${Number(student.monthly_fee).toLocaleString()}</button>` : ''}
            </div>
          `;
        }).join('')}
      </div>
    `;

    // Bind dynamic buttons in history panel
    historyPanel.querySelectorAll('.btn-detail-pay').forEach(btn => {
      btn.addEventListener('click', () => {
        openCellPaymentModal({
          studentId: student.id,
          studentName: student.name,
          month: btn.getAttribute('data-dmonth'),
          amount: Number(btn.getAttribute('data-damount')),
          isPaid: btn.getAttribute('data-dpaid') === '1',
          mode: btn.getAttribute('data-dmode') || 'Cash',
          note: btn.getAttribute('data-dnote') || ''
        });
      });
    });

    historyPanel.querySelectorAll('.btn-receipt').forEach(btn => {
      btn.addEventListener('click', () => {
        openReceiptModal({
          student,
          month: btn.getAttribute('data-rmonth'),
          amount: Number(btn.getAttribute('data-ramount')),
          mode: btn.getAttribute('data-rmode'),
          entryId: btn.getAttribute('data-rentry'),
          date: btn.getAttribute('data-rdate')
        });
      });
    });

    switchStudentModalTab('history');
    openModal('modal-student-detail');
  }

  function openReceiptModal({ student, month, amount, mode, entryId, date }) {
    const content = document.getElementById('receipt-content');
    if (content) {
      content.innerHTML = `
        <div class="flex justify-between py-1"><span class="text-slate-500">Receipt ID:</span><span class="font-mono font-bold">#${escapeHtml(entryId || 'LEDGER')}</span></div>
        <div class="flex justify-between py-1"><span class="text-slate-500">Student Name:</span><span class="font-bold">${escapeHtml(student.name)}</span></div>
        <div class="flex justify-between py-1"><span class="text-slate-500">Class / School:</span><span>Std ${escapeHtml(student.std || '—')} • ${escapeHtml(student.school || '—')}</span></div>
        <div class="flex justify-between py-1"><span class="text-slate-500">Billing Cycle:</span><span class="font-mono font-bold">${escapeHtml(month)}</span></div>
        <div class="flex justify-between py-1"><span class="text-slate-500">Payment Mode:</span><span class="font-bold">${escapeHtml(mode)}</span></div>
        <div class="flex justify-between py-1"><span class="text-slate-500">Recorded At:</span><span class="font-mono">${escapeHtml(date || new Date().toLocaleDateString())}</span></div>
        <div class="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center text-sm">
          <span class="font-bold">Total Amount Received:</span>
          <span class="text-lg font-extrabold font-mono text-emerald-600 dark:text-emerald-400">₹${Number(amount).toLocaleString()}</span>
        </div>
      `;
    }
    openModal('modal-receipt');
  }

  const btnPrintReceipt = document.getElementById('btn-print-receipt');
  if (btnPrintReceipt) btnPrintReceipt.addEventListener('click', () => window.print());

  if (formEditStudent) {
    formEditStudent.addEventListener('submit', async (e) => {
      e.preventDefault();
      const sid = Number(document.getElementById('edit-student-id').value);
      const res = await apiFetch(`/api/students/${sid}`, {
        method: 'PATCH',
        body: {
          name: document.getElementById('edit-student-name').value.trim(),
          std: document.getElementById('edit-student-std').value.trim(),
          school: document.getElementById('edit-student-school').value.trim(),
          monthly_fee: Number(document.getElementById('edit-student-fee').value),
          status: document.getElementById('edit-student-status').value,
          guardian_phone: document.getElementById('edit-student-phone').value.trim(),
          notes: document.getElementById('edit-student-notes').value.trim()
        }
      });

      if (res.ok && res.data.status === 'success') {
        showToast('Student profile updated!', 'success');
        await renderLiveMockTable(res.data.table);
        await refreshActivityLog();
        await openStudentDetailModal(sid);
      } else {
        showToast(res.data.reply || res.data.error || 'Failed to update student.', 'error');
      }
    });
  }

  const btnDeleteStudent = document.getElementById('btn-delete-student');
  if (btnDeleteStudent) {
    btnDeleteStudent.addEventListener('click', () => {
      const sid = Number(document.getElementById('edit-student-id').value);
      const sname = document.getElementById('edit-student-name').value;
      showConfirmDialog('Delete Student?', `Permanently delete ${sname} and all recorded payments from the database?`, async () => {
        const res = await apiFetch(`/api/students/${sid}`, { method: 'DELETE' });
        if (res.ok && res.data.status === 'success') {
          closeModal('modal-student-detail');
          await renderLiveMockTable(res.data.table);
          await refreshActivityLog();
          showToast(`Deleted student ${sname}`, 'warning');
        } else {
          showToast(res.data.reply || res.data.error || 'Failed to delete student.', 'error');
        }
      });
    });
  }

  // Add Student Modal
  const btnOpenAddStudent = document.getElementById('btn-open-add-student');
  const formAddStudent = document.getElementById('form-add-student');
  if (btnOpenAddStudent) {
    btnOpenAddStudent.addEventListener('click', () => {
      ['input-new-student-name', 'input-new-student-std', 'input-new-student-school',
        'input-new-student-fee', 'input-new-student-phone', 'input-new-student-notes'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      const st = document.getElementById('add-student-status');
      if (st) st.classList.add('hidden');
      openModal('modal-add-student');
      setTimeout(() => document.getElementById('input-new-student-name').focus(), 80);
    });
  }

  if (formAddStudent) {
    formAddStudent.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('btn-save-new-student');
      if (btn) btn.disabled = true;

      const res = await apiFetch('/api/students', {
        method: 'POST',
        body: {
          name: document.getElementById('input-new-student-name').value.trim(),
          std: document.getElementById('input-new-student-std').value.trim(),
          school: document.getElementById('input-new-student-school').value.trim(),
          monthly_fee: Number(document.getElementById('input-new-student-fee').value),
          guardian_phone: document.getElementById('input-new-student-phone').value.trim(),
          notes: document.getElementById('input-new-student-notes').value.trim()
        }
      });

      if (btn) btn.disabled = false;

      if (res.ok && res.data.status === 'success') {
        closeModal('modal-add-student');
        await renderLiveMockTable(res.data.table);
        await refreshActivityLog();
        appendBotMessage(res.data.reply, res.data.timestamp, 'success');
        showToast('New student enrolled!', 'success');
      } else {
        const st = document.getElementById('add-student-status');
        if (st) {
          st.className = 'p-2.5 rounded-xl text-xs bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800';
          st.textContent = res.data.reply || res.data.error || 'Failed to add student.';
          st.classList.remove('hidden');
        }
      }
    });
  }

  // Add Month Modal
  const btnOpenAddMonth = document.getElementById('btn-open-add-month');
  const formAddMonth = document.getElementById('form-add-month');
  const btnSuggestNextMonth = document.getElementById('btn-suggest-next-month');

  function computeNextMonthLabel() {
    const months = (state.cachedTableData && state.cachedTableData.months) || [];
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (!months.length) {
      const now = new Date();
      return `${monthNames[now.getMonth()]} ${now.getFullYear()}`;
    }
    const last = months[months.length - 1];
    const parts = last.split(/\s+/);
    const idx = monthNames.findIndex(m => m.toLowerCase() === (parts[0] || '').toLowerCase());
    const yr = parseInt(parts[1], 10);
    if (idx !== -1 && !Number.isNaN(yr)) {
      return idx === 11 ? `Jan ${yr + 1}` : `${monthNames[idx + 1]} ${yr}`;
    }
    return '';
  }

  if (btnOpenAddMonth) {
    btnOpenAddMonth.addEventListener('click', () => {
      document.getElementById('input-add-month').value = computeNextMonthLabel();
      openModal('modal-add-month');
    });
  }
  if (btnSuggestNextMonth) {
    btnSuggestNextMonth.addEventListener('click', () => {
      document.getElementById('input-add-month').value = computeNextMonthLabel();
    });
  }
  if (formAddMonth) {
    formAddMonth.addEventListener('submit', async (e) => {
      e.preventDefault();
      const month_name = document.getElementById('input-add-month').value.trim();
      const res = await apiFetch('/api/columns', { method: 'POST', body: { month_name } });
      if (res.ok && res.data.status === 'success') {
        state.lastNewCol = res.data.month_header;
        closeModal('modal-add-month');
        await renderLiveMockTable(res.data.table);
        await refreshActivityLog();
        showToast(`Created column "${res.data.month_header}"`, 'success');
      } else {
        showToast(res.data.reply || res.data.error || 'Invalid month format.', 'error');
      }
    });
  }

  function confirmDeleteColumn(monthName) {
    showConfirmDialog(
      `Delete Column "${monthName}"?`,
      `This will permanently remove column "${monthName}" and clear all fee payments recorded inside it.`,
      async () => {
        const res = await apiFetch('/api/columns/delete', {
          method: 'POST',
          body: { month_name: monthName }
        });
        if (res.ok && res.data.status === 'success') {
          state.lastUpdatedCell = null;
          await renderLiveMockTable(res.data.table);
          await refreshActivityLog();
          appendBotMessage(res.data.reply, res.data.timestamp, 'warning');
          showToast(`Deleted column ${monthName}`, 'warning');
        } else {
          showToast(res.data.reply || res.data.error || 'Failed to delete column.', 'error');
        }
      }
    );
  }

  // Reset Table (Admin Only)
  const btnResetTable = document.getElementById('btn-reset-table');
  if (btnResetTable) {
    btnResetTable.addEventListener('click', () => {
      showConfirmDialog(
        'Reset Entire Ledger?',
        'Resets all students, month columns, and payments back to the seed CSV. User accounts remain intact.',
        async () => {
          const res = await apiFetch('/api/mock-reset', { method: 'POST' });
          if (res.ok && res.data.status === 'success') {
            state.lastUpdatedCell = null;
            state.lastNewCol = null;
            if (tableSearchInput) tableSearchInput.value = '';
            if (btnClearSearch) btnClearSearch.classList.add('hidden');
            await renderLiveMockTable(res.data.table);
            await refreshActivityLog();
            showToast('Ledger database reset to seed CSV!', 'info');
          } else {
            showToast(res.data.error || 'Reset failed.', 'error');
          }
        }
      );
    });
  }

  // ==============================================================
  // 10. CHAT INTERFACE & SAFETY PIPELINE
  // ==============================================================
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const btnSend = document.getElementById('btn-send');
  const messagesContainer = document.getElementById('messages-container');
  const typingIndicator = document.getElementById('typing-indicator');
  const btnClearChat = document.getElementById('btn-clear-chat');

  function scrollToBottom() {
    setTimeout(() => {
      if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 50);
  }

  function appendUserMessage(text) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const wrapper = document.createElement('div');
    wrapper.className = 'message-user message-enter flex items-start justify-end space-x-2';
    const actorName = (state.user && (state.user.full_name || state.user.username)) || 'Admin';

    wrapper.innerHTML = `
      <div class="message-user-bubble">
        <div class="flex items-center justify-between space-x-3 mb-1 text-[10px] text-blue-200">
          <span class="font-semibold uppercase tracking-wider">${escapeHtml(actorName)}</span>
          <span>${time}</span>
        </div>
        <p class="text-sm font-medium leading-relaxed">${escapeHtml(text)}</p>
      </div>
      <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 via-orange-500 to-red-500 text-white flex items-center justify-center flex-shrink-0 text-xs shadow-sm">
        <i data-lucide="user" class="w-4 h-4"></i>
      </div>
    `;

    messagesContainer.appendChild(wrapper);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
  }

  function appendBotMessage(replyText, timestamp, status = 'success', extraConfig = {}) {
    const time = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const wrapper = document.createElement('div');
    wrapper.className = 'message-bot message-enter flex items-start space-x-3';

    let bgBadge = 'bg-blue-600 text-white';
    let iconName = 'bot';
    if (status === 'warning' || status === 'duplicate_warning' || status === 'gap_warning') {
      bgBadge = 'bg-orange-100 dark:bg-orange-950/80 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-800';
      iconName = 'alert-triangle';
    } else if (status === 'info' || status === 'confirmation_required') {
      bgBadge = 'bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800';
      iconName = 'help-circle';
    } else if (status === 'error') {
      bgBadge = 'bg-red-100 dark:bg-red-950/80 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800';
      iconName = 'alert-circle';
    }

    let buttonsHtml = '';
    if (extraConfig.options && extraConfig.options.length > 0 && extraConfig.actionId) {
      buttonsHtml = `
        <div class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex flex-wrap gap-2 action-buttons-group">
          ${extraConfig.options.map(opt => {
            const isPrimary = opt.primary || opt.choice === 'confirm' || opt.choice === 'fill_gap' || opt.choice === 'confirm_duplicate';
            const btnClass = isPrimary
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-xs font-semibold'
              : 'bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium border border-slate-300 dark:border-slate-700';
            return `
              <button type="button" data-action-id="${escapeHtml(extraConfig.actionId)}" data-choice="${escapeHtml(opt.choice)}" class="btn-action-choice px-3.5 py-1.5 rounded-lg text-xs transition active:scale-95 flex items-center space-x-1 cursor-pointer ${btnClass}">
                ${opt.choice === 'confirm' ? '<i data-lucide="check" class="w-3.5 h-3.5 mr-0.5"></i>' : ''}
                ${opt.choice === 'cancel' ? '<i data-lucide="x" class="w-3.5 h-3.5 mr-0.5"></i>' : ''}
                <span>${escapeHtml(opt.label)}</span>
              </button>
            `;
          }).join('')}
        </div>
      `;
    }

    if (extraConfig.entryId) {
      buttonsHtml = `
        <div class="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <button type="button" data-undo-id="${escapeHtml(extraConfig.entryId)}" class="btn-undo-entry px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-50 dark:bg-orange-950/40 hover:bg-orange-100 dark:hover:bg-orange-900/40 text-orange-800 dark:text-orange-300 border border-orange-200 dark:border-orange-800/80 transition active:scale-95 flex items-center space-x-1 cursor-pointer">
            <i data-lucide="rotate-ccw" class="w-3.5 h-3.5 text-orange-600 dark:text-orange-400"></i>
            <span>Undo Entry</span>
          </button>
          <span class="text-[10px] text-slate-400 dark:text-slate-500">Reverts cell (#${escapeHtml(extraConfig.entryId)})</span>
        </div>
      `;
    }

    wrapper.innerHTML = `
      <div class="w-8 h-8 rounded-full ${bgBadge} flex items-center justify-center flex-shrink-0 text-xs font-bold shadow-sm">
        <i data-lucide="${iconName}" class="w-4 h-4"></i>
      </div>
      <div class="message-bot-bubble bot-markdown text-sm text-slate-800 dark:text-slate-100">
        <div class="flex items-center justify-between mb-1 text-[10px] text-slate-400 dark:text-slate-500">
          <span class="font-bold text-xs text-blue-600 dark:text-blue-400">Fees Assistant</span>
          <span>${time}</span>
        </div>
        <div>${formatMarkdown(replyText)}</div>
        ${buttonsHtml}
      </div>
    `;

    messagesContainer.appendChild(wrapper);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
  }

  // Event delegation for Action Choice & Undo buttons in chat
  if (messagesContainer) {
    messagesContainer.addEventListener('click', async (e) => {
      const choiceBtn = e.target.closest('.btn-action-choice');
      if (choiceBtn) {
        const actionId = choiceBtn.getAttribute('data-action-id');
        const choice = choiceBtn.getAttribute('data-choice');
        const group = choiceBtn.closest('.action-buttons-group');
        if (group) {
          group.querySelectorAll('button').forEach(b => {
            b.disabled = true;
            b.classList.add('opacity-40', 'cursor-not-allowed');
          });
        }
        typingIndicator.classList.remove('hidden');
        scrollToBottom();

        const endpoint = choice === 'cancel' ? '/api/action/cancel' : '/api/action/confirm';
        const res = await apiFetch(endpoint, { method: 'POST', body: { action_id: actionId, choice } });
        typingIndicator.classList.add('hidden');

        if (res.ok) {
          if (res.data.status === 'confirmation_required') {
            appendBotMessage(res.data.reply, res.data.timestamp, res.data.status, {
              actionId: res.data.action_id,
              options: res.data.options
            });
          } else {
            appendBotMessage(res.data.reply, res.data.timestamp, res.data.status, { entryId: res.data.entry_id });
          }
          if (res.data.table_updated && res.data.table) {
            state.lastUpdatedCell = res.data.updated_cell || null;
            await renderLiveMockTable(res.data.table);
          }
          await refreshActivityLog();
        } else {
          appendBotMessage(`⚠️ ${res.data.error || 'Action failed.'}`, null, 'error');
        }
        return;
      }

      const undoBtn = e.target.closest('.btn-undo-entry');
      if (undoBtn) {
        const entryId = undoBtn.getAttribute('data-undo-id');
        undoBtn.disabled = true;
        undoBtn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5 text-slate-400"></i><span class="text-slate-400">Undone ✓</span>';
        undoBtn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed flex items-center space-x-1';

        typingIndicator.classList.remove('hidden');
        const res = await apiFetch('/api/action/undo', { method: 'POST', body: { entry_id: entryId } });
        typingIndicator.classList.add('hidden');

        if (res.ok) {
          appendBotMessage(res.data.reply, res.data.timestamp, res.data.status);
          if (res.data.table_updated && res.data.table) {
            state.lastUpdatedCell = null;
            await renderLiveMockTable(res.data.table);
          }
          await refreshActivityLog();
        } else {
          appendBotMessage(`⚠️ ${res.data.error || 'Undo failed.'}`, null, 'error');
        }
      }
    });
  }

  if (chatForm) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const message = chatInput.value.trim();
      if (!message) return;

      const savedMessage = message;
      appendUserMessage(message);
      chatInput.value = '';
      btnSend.disabled = true;
      typingIndicator.classList.remove('hidden');
      scrollToBottom();

      try {
        const res = await apiFetch('/api/chat', { method: 'POST', body: { message: savedMessage } });
        typingIndicator.classList.add('hidden');
        btnSend.disabled = false;

        if (res.ok) {
          appendBotMessage(res.data.reply, res.data.timestamp, res.data.status, {
            actionId: res.data.action_id,
            options: res.data.options,
            entryId: res.data.entry_id
          });
          if (res.data.table_updated && res.data.table) {
            state.lastUpdatedCell = res.data.updated_cell || null;
            await renderLiveMockTable(res.data.table);
            await refreshActivityLog();
          }
        } else {
          appendBotMessage(`⚠️ ${res.data.reply || res.data.error || 'Failed to process message.'}`, null, 'error');
        }
      } catch {
        typingIndicator.classList.add('hidden');
        btnSend.disabled = false;
        chatInput.value = savedMessage;
        appendBotMessage('⚠️ **Connection error:** Server unreachable. Message preserved in input box.', null, 'error');
        chatInput.focus();
      }
    });
  }

  document.querySelectorAll('.quick-prompt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (chatInput && chatForm) {
        chatInput.value = btn.getAttribute('data-quick-prompt');
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });
  });

  if (btnClearChat) {
    btnClearChat.addEventListener('click', () => {
      showConfirmDialog('Clear Chat Screen?', 'Clears the visible chat stream without modifying saved SQLite payments.', () => {
        const welcome = messagesContainer.firstElementChild;
        messagesContainer.innerHTML = '';
        if (welcome) messagesContainer.appendChild(welcome);
        scrollToBottom();
      });
    });
  }

  // ==============================================================
  // 11. ANALYTICS & PENDING DEFAULTERS VIEW
  // ==============================================================
  const analyticsMonthSelect = document.getElementById('analytics-month-select');
  const btnRefreshAnalytics = document.getElementById('btn-refresh-analytics');

  async function loadAnalytics(selectedMonth = null) {
    const queryMonth = selectedMonth || (analyticsMonthSelect ? analyticsMonthSelect.value : '');
    const url = queryMonth ? `/api/analytics?month=${encodeURIComponent(queryMonth)}` : '/api/analytics';
    const res = await apiFetch(url);
    if (!res.ok) return;

    const { summary, months, monthly_breakdown, school_breakdown, payment_mode_breakdown, pending_students } = res.data.analytics;

    if (analyticsMonthSelect) {
      analyticsMonthSelect.innerHTML = months.map(m =>
        `<option value="${escapeHtml(m)}" ${m === summary.focus_month ? 'selected' : ''}>${escapeHtml(m)}</option>`
      ).join('');
    }

    // 4 Summary Cards with SVG Circular Ring
    const cardsContainer = document.getElementById('analytics-cards-container');
    const radius = 22;
    const circ = 2 * Math.PI * radius;
    const offset = circ - ((summary.focus_rate || 0) / 100) * circ;

    if (cardsContainer) {
      cardsContainer.innerHTML = `
        <div class="glass-card electric-glow rounded-2xl p-4 flex items-center justify-between">
          <div>
            <p class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">${escapeHtml(summary.focus_month)} Collected</p>
            <p class="text-xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400 mt-1">₹${Number(summary.focus_collected).toLocaleString()}</p>
            <p class="text-[11px] text-slate-500 mt-0.5">of ₹${Number(summary.focus_expected).toLocaleString()} target</p>
          </div>
          <svg class="w-14 h-14 flex-shrink-0" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r="${radius}" stroke="currentColor" stroke-width="5" fill="transparent" class="text-slate-200 dark:text-slate-800" />
            <circle cx="28" cy="28" r="${radius}" stroke="currentColor" stroke-width="5" fill="transparent" stroke-dasharray="${circ}" stroke-dashoffset="${offset}" stroke-linecap="round" class="progress-ring-circle text-blue-600 dark:text-blue-400" />
            <text x="28" y="32" text-anchor="middle" class="fill-slate-800 dark:fill-white text-[11px] font-bold font-mono">${Math.round(summary.focus_rate)}%</text>
          </svg>
        </div>

        <div class="glass-card rounded-2xl p-4">
          <p class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">Pending Due (${escapeHtml(summary.focus_month)})</p>
          <p class="text-xl font-extrabold font-mono text-red-600 dark:text-red-400 mt-1">₹${Number(summary.focus_pending_amount).toLocaleString()}</p>
          <p class="text-[11px] text-slate-500 mt-0.5">${summary.pending_count} of ${summary.active_students} active unpaid</p>
        </div>

        <div class="glass-card rounded-2xl p-4">
          <p class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">All-Time Collected</p>
          <p class="text-xl font-extrabold font-mono text-blue-600 dark:text-blue-400 mt-1">₹${Number(summary.total_collected_all).toLocaleString()}</p>
          <p class="text-[11px] text-slate-500 mt-0.5">Across ${months.length} billing cycles</p>
        </div>

        <div class="glass-card rounded-2xl p-4">
          <p class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">Student Roster</p>
          <p class="text-xl font-extrabold font-mono text-orange-600 dark:text-orange-400 mt-1">${summary.active_students} Active</p>
          <p class="text-[11px] text-slate-500 mt-0.5">${summary.inactive_students} Inactive • ₹${Number(summary.total_base_fees).toLocaleString()}/mo base</p>
        </div>
      `;
    }

    // Monthly Bar Chart
    const monthlyChart = document.getElementById('analytics-monthly-chart');
    if (monthlyChart) {
      monthlyChart.innerHTML = monthly_breakdown.map(m => `
        <div class="space-y-1 text-xs">
          <div class="flex justify-between font-mono">
            <span class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(m.month)}</span>
            <span class="text-slate-600 dark:text-slate-400">₹${Number(m.collected).toLocaleString()} / ₹${Number(m.expected).toLocaleString()} (${m.rate}% • ${m.paid_students} paid)</span>
          </div>
          <div class="w-full h-2.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
            <div class="h-full rounded-full bg-gradient-to-r from-blue-600 via-orange-500 to-red-500 transition-all duration-500" style="width: ${Math.min(100, m.rate)}%"></div>
          </div>
        </div>
      `).join('');
    }

    // Payment Mode Share
    const modeChart = document.getElementById('analytics-mode-chart');
    if (modeChart) {
      const modeTotal = payment_mode_breakdown.reduce((acc, m) => acc + m.total, 0);
      if (payment_mode_breakdown.length === 0) {
        modeChart.innerHTML = '<p class="text-xs text-slate-400 text-center py-6">No recorded payments yet.</p>';
      } else {
        modeChart.innerHTML = payment_mode_breakdown.map(m => {
          const pct = modeTotal > 0 ? Math.round((m.total / modeTotal) * 100) : 0;
          return `
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(m.mode)} <span class="text-[10px] text-slate-400">(${m.count})</span></span>
                <span class="font-mono font-bold text-blue-600 dark:text-blue-400">₹${Number(m.total).toLocaleString()} (${pct}%)</span>
              </div>
              <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                <div class="h-full rounded-full bg-orange-500" style="width: ${pct}%"></div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // School Breakdown
    const schoolList = document.getElementById('analytics-school-list');
    if (schoolList) {
      schoolList.innerHTML = school_breakdown.map(sch => `
        <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800">
          <div>
            <p class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(sch.school)}</p>
            <p class="text-[11px] text-slate-500">${sch.students} students</p>
          </div>
          <div class="text-right font-mono">
            <p class="font-bold text-slate-900 dark:text-white">₹${Number(sch.base_total).toLocaleString()}/mo</p>
            <p class="text-[10px] text-emerald-600 dark:text-emerald-400">Paid: ₹${Number(sch.collected_total).toLocaleString()}</p>
          </div>
        </div>
      `).join('');
    }

    // Pending Defaulters List
    const pendingBadge = document.getElementById('analytics-pending-badge');
    const pendingList = document.getElementById('analytics-pending-list');
    const canWrite = state.user && (state.user.role === 'admin' || state.user.role === 'staff');

    if (pendingBadge) pendingBadge.textContent = `${pending_students.length} Unpaid`;
    if (pendingList) {
      if (pending_students.length === 0) {
        pendingList.innerHTML = '<p class="text-xs text-emerald-600 dark:text-emerald-400 font-bold text-center py-8">🎉 All active students have paid for ' + escapeHtml(summary.focus_month) + '!</p>';
      } else {
        pendingList.innerHTML = pending_students.map(p => `
          <div class="py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div>
              <p class="font-bold text-slate-900 dark:text-white">${escapeHtml(p.name)} <span class="text-[11px] font-normal text-slate-500">(Std ${escapeHtml(p.std || '—')} • ${escapeHtml(p.school || '—')})</span></p>
              <p class="text-[11px] text-slate-400">Last paid: ${escapeHtml(p.last_paid_month)} ${p.guardian_phone ? '• Tel: ' + escapeHtml(p.guardian_phone) : ''}</p>
            </div>
            <div class="flex items-center space-x-2">
              <span class="font-mono font-bold text-red-600 dark:text-red-400">Due: ₹${Number(p.monthly_fee).toLocaleString()}</span>
              ${canWrite ? `<button type="button" class="btn-pending-pay px-3 py-1 rounded-lg btn-primary-gradient text-xs font-bold cursor-pointer" data-psid="${p.id}" data-psname="${escapeHtml(p.name)}" data-pmonth="${escapeHtml(summary.focus_month)}" data-pamount="${p.monthly_fee}">Pay Now</button>` : ''}
            </div>
          </div>
        `).join('');

        pendingList.querySelectorAll('.btn-pending-pay').forEach(btn => {
          btn.addEventListener('click', () => {
            openCellPaymentModal({
              studentId: Number(btn.getAttribute('data-psid')),
              studentName: btn.getAttribute('data-psname'),
              month: btn.getAttribute('data-pmonth'),
              amount: Number(btn.getAttribute('data-pamount')),
              isPaid: false
            });
          });
        });
      }
    }
    if (window.lucide) lucide.createIcons();
  }

  if (analyticsMonthSelect) analyticsMonthSelect.addEventListener('change', () => loadAnalytics(analyticsMonthSelect.value));
  if (btnRefreshAnalytics) btnRefreshAnalytics.addEventListener('click', () => loadAnalytics());

  // ==============================================================
  // 12. AUDIT TRAIL & SECURITY LOGS VIEW
  // ==============================================================
  const headerLogCount = document.getElementById('header-log-count');
  const auditSubLedger = document.getElementById('audit-subtab-ledger');
  const auditSubSecurity = document.getElementById('audit-subtab-security');
  const auditLedgerPanel = document.getElementById('audit-ledger-panel');
  const auditSecurityPanel = document.getElementById('audit-security-panel');
  const auditSearchInput = document.getElementById('audit-search-input');
  const auditStatusFilter = document.getElementById('audit-status-filter');
  const btnRefreshAudit = document.getElementById('btn-refresh-audit');

  async function refreshActivityLog() {
    const res = await apiFetch('/api/activity-log?limit=150');
    if (!res.ok) return;
    const logs = res.data.log || [];
    if (headerLogCount) headerLogCount.textContent = logs.length;
    if (state.currentView === 'audit' && state.auditSubtab === 'ledger') {
      renderAuditLedgerRows(logs);
    }
  }

  function renderAuditLedgerRows(logs) {
    const tbody = document.getElementById('audit-ledger-body');
    if (!tbody) return;
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="p-6 text-center text-slate-400">No matching audit entries.</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(item => {
      let badgeBg = 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300';
      if (item.status === 'Undone' || item.status === 'Col Deleted' || item.status === 'Deleted') {
        badgeBg = 'bg-red-100 dark:bg-red-950/80 text-red-800 dark:text-red-300';
      } else if (item.status === 'Cancelled' || item.status === 'Updated') {
        badgeBg = 'bg-orange-100 dark:bg-orange-950/80 text-orange-800 dark:text-orange-300';
      } else if (item.status === 'Reset' || item.status === 'Added' || item.status === 'Col Added') {
        badgeBg = 'bg-blue-100 dark:bg-blue-950/80 text-blue-800 dark:text-blue-300';
      }
      return `
        <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
          <td class="p-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">${escapeHtml(item.time)}</td>
          <td class="p-3 font-mono font-bold text-blue-600 dark:text-blue-400">@${escapeHtml(item.actor || 'System')}</td>
          <td class="p-3 font-bold text-slate-900 dark:text-slate-100">${escapeHtml(item.student)}</td>
          <td class="p-3 font-mono text-slate-600 dark:text-slate-300">${escapeHtml(item.month)}</td>
          <td class="p-3 text-right font-mono font-bold">₹${Number(item.amount || 0).toLocaleString()}</td>
          <td class="p-3"><span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${badgeBg}">${escapeHtml(item.status)}</span></td>
          <td class="p-3 text-slate-500 dark:text-slate-400">${escapeHtml(item.note)}</td>
        </tr>
      `;
    }).join('');
  }

  async function loadAuditView() {
    if (state.auditSubtab === 'security' && state.user && state.user.role === 'admin') {
      const res = await apiFetch('/api/auth/logs?limit=150');
      const tbody = document.getElementById('audit-security-body');
      if (res.ok && tbody) {
        const logs = res.data.logs || [];
        tbody.innerHTML = logs.map(l => `
          <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
            <td class="p-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">${escapeHtml(l.created_at)}</td>
            <td class="p-3 font-mono font-bold text-slate-900 dark:text-slate-100">${escapeHtml(l.username)}</td>
            <td class="p-3 font-mono text-xs">${escapeHtml(l.event_type)}</td>
            <td class="p-3 font-mono text-slate-500">${escapeHtml(l.ip_address)}</td>
            <td class="p-3"><span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${l.success ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300' : 'bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300'}">${l.success ? 'OK' : 'DENIED'}</span></td>
            <td class="p-3 text-slate-500 dark:text-slate-400">${escapeHtml(l.detail)}</td>
          </tr>
        `).join('');
      }
      return;
    }

    const q = auditSearchInput ? auditSearchInput.value.trim() : '';
    const st = auditStatusFilter ? auditStatusFilter.value : '';
    const params = new URLSearchParams({ limit: '150' });
    if (q) params.set('search', q);
    if (st) params.set('status', st);
    const res = await apiFetch(`/api/activity-log?${params.toString()}`);
    if (res.ok) renderAuditLedgerRows(res.data.log || []);
  }

  if (auditSubLedger && auditSubSecurity) {
    auditSubLedger.addEventListener('click', () => {
      state.auditSubtab = 'ledger';
      auditSubLedger.className = 'px-3.5 py-1.5 rounded-xl text-xs font-bold nav-tab-active cursor-pointer';
      auditSubSecurity.className = 'role-admin-only px-3.5 py-1.5 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 cursor-pointer';
      auditLedgerPanel.classList.remove('hidden');
      auditSecurityPanel.classList.add('hidden');
      loadAuditView();
    });

    auditSubSecurity.addEventListener('click', () => {
      state.auditSubtab = 'security';
      auditSubSecurity.className = 'role-admin-only px-3.5 py-1.5 rounded-xl text-xs font-bold nav-tab-active cursor-pointer';
      auditSubLedger.className = 'px-3.5 py-1.5 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 cursor-pointer';
      auditSecurityPanel.classList.remove('hidden');
      auditLedgerPanel.classList.add('hidden');
      loadAuditView();
    });
  }

  if (auditSearchInput) auditSearchInput.addEventListener('input', loadAuditView);
  if (auditStatusFilter) auditStatusFilter.addEventListener('change', loadAuditView);
  if (btnRefreshAudit) btnRefreshAudit.addEventListener('click', loadAuditView);

  // ==============================================================
  // 13. ACCOUNT SECURITY & 2FA SETTINGS MODAL
  // ==============================================================
  const btnOpenSecurityModal = document.getElementById('btn-open-security-modal');

  async function refreshSecurityModal() {
    const res = await apiFetch('/api/auth/me');
    if (!res.ok) return;
    const { user, security } = res.data;
    document.getElementById('sec-profile-fullname').value = user.full_name || '';
    document.getElementById('sec-profile-email').value = user.email || '';
    document.getElementById('sec-profile-role').textContent = (user.role || '').toUpperCase();
    document.getElementById('sec-last-login').textContent = `Signed in as @${user.username} • Last login: ${security.last_login_at || 'Now'}`;
    document.getElementById('sec-recovery-remaining').textContent = security.recovery_codes_remaining;

    const badge = document.getElementById('sec-totp-status-badge');
    const setupBox = document.getElementById('sec-2fa-setup-box');
    const activeBox = document.getElementById('sec-2fa-active-box');
    const enrollPanel = document.getElementById('sec-2fa-enrollment');

    if (security.totp_enabled) {
      badge.textContent = 'Enabled';
      badge.className = 'text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300';
      setupBox.classList.add('hidden');
      activeBox.classList.remove('hidden');
    } else {
      badge.textContent = 'Disabled';
      badge.className = 'text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300';
      setupBox.classList.remove('hidden');
      activeBox.classList.add('hidden');
      if (enrollPanel) enrollPanel.classList.add('hidden');
    }
  }

  if (btnOpenSecurityModal) {
    btnOpenSecurityModal.addEventListener('click', async () => {
      if (userDropdown) userDropdown.classList.add('hidden');
      await refreshSecurityModal();
      openModal('modal-security');
    });
  }

  const formProfileUpdate = document.getElementById('form-profile-update');
  if (formProfileUpdate) {
    formProfileUpdate.addEventListener('submit', async (e) => {
      e.preventDefault();
      const res = await apiFetch('/api/auth/me', {
        method: 'PATCH',
        body: {
          full_name: document.getElementById('sec-profile-fullname').value.trim(),
          email: document.getElementById('sec-profile-email').value.trim()
        }
      });
      if (res.ok && res.data.status === 'success') {
        state.user = res.data.user;
        applyRolePermissions();
        showToast('Profile saved!', 'success');
      } else {
        showToast(res.data.error || 'Failed to update profile.', 'error');
      }
    });
  }

  const formChangePassword = document.getElementById('form-change-password');
  if (formChangePassword) {
    formChangePassword.addEventListener('submit', async (e) => {
      e.preventDefault();
      const res = await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: {
          current_password: document.getElementById('sec-curr-password').value,
          new_password: document.getElementById('sec-new-password').value
        }
      });
      if (res.ok && res.data.status === 'success') {
        state.csrfToken = res.data.csrf_token;
        document.getElementById('sec-curr-password').value = '';
        document.getElementById('sec-new-password').value = '';
        showToast('Password updated! Other sessions signed out.', 'success');
      } else {
        showToast(res.data.error || 'Password change failed.', 'error');
      }
    });
  }

  const btnSetup2fa = document.getElementById('btn-setup-2fa');
  if (btnSetup2fa) {
    btnSetup2fa.addEventListener('click', async () => {
      const res = await apiFetch('/api/auth/2fa/setup', { method: 'POST' });
      if (res.ok && res.data.status === 'success') {
        document.getElementById('sec-2fa-secret-display').textContent = res.data.secret;
        document.getElementById('sec-2fa-otpauth-uri').textContent = res.data.otpauth_uri;
        document.getElementById('sec-2fa-verify-code').value = '';
        document.getElementById('sec-2fa-enrollment').classList.remove('hidden');
      }
    });
  }

  const btnCopy2faSecret = document.getElementById('btn-copy-2fa-secret');
  if (btnCopy2faSecret) {
    btnCopy2faSecret.addEventListener('click', async () => {
      const txt = document.getElementById('sec-2fa-secret-display').textContent;
      try {
        await navigator.clipboard.writeText(txt);
        showToast('2FA key copied!', 'success');
      } catch {
        showToast('Select and copy manually.', 'warning');
      }
    });
  }

  const btnVerify2fa = document.getElementById('btn-verify-2fa');
  if (btnVerify2fa) {
    btnVerify2fa.addEventListener('click', async () => {
      const code = document.getElementById('sec-2fa-verify-code').value.trim();
      const res = await apiFetch('/api/auth/2fa/verify', { method: 'POST', body: { code } });
      if (res.ok && res.data.status === 'success') {
        state.user = res.data.user;
        await refreshSecurityModal();
        showToast('2FA enabled!', 'success');
        if (res.data.recovery_codes) showRecoveryCodesModal(res.data.recovery_codes);
      } else {
        showToast(res.data.error || 'Invalid 2FA verification code.', 'error');
      }
    });
  }

  const btnDisable2fa = document.getElementById('btn-disable-2fa');
  if (btnDisable2fa) {
    btnDisable2fa.addEventListener('click', async () => {
      const pw = document.getElementById('sec-disable-2fa-pw').value;
      const res = await apiFetch('/api/auth/2fa/disable', { method: 'POST', body: { password: pw } });
      if (res.ok && res.data.status === 'success') {
        state.user = res.data.user;
        document.getElementById('sec-disable-2fa-pw').value = '';
        await refreshSecurityModal();
        showToast('2FA disabled.', 'warning');
      } else {
        showToast(res.data.error || 'Could not disable 2FA.', 'error');
      }
    });
  }

  const btnRegenRecovery = document.getElementById('btn-regen-recovery');
  if (btnRegenRecovery) {
    btnRegenRecovery.addEventListener('click', async () => {
      const pw = document.getElementById('sec-regen-pw').value;
      const res = await apiFetch('/api/auth/recovery-codes/regenerate', { method: 'POST', body: { password: pw } });
      if (res.ok && res.data.status === 'success') {
        document.getElementById('sec-regen-pw').value = '';
        await refreshSecurityModal();
        showRecoveryCodesModal(res.data.recovery_codes);
      } else {
        showToast(res.data.error || 'Password verification failed.', 'error');
      }
    });
  }

  // ==============================================================
  // 14. ADMIN USER MANAGEMENT MODAL
  // ==============================================================
  const btnOpenUsersModal = document.getElementById('btn-open-users-modal');
  const toggleSelfReg = document.getElementById('toggle-self-reg');
  const formAdminCreateUser = document.getElementById('form-admin-create-user');

  function renderUsersTable(users) {
    const tbody = document.getElementById('users-table-body');
    if (!tbody) return;
    tbody.innerHTML = users.map(u => {
      const isMe = state.user && state.user.id === u.id;
      const statusBadge = u.is_locked
        ? '<span class="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 font-bold text-[10px]">Locked</span>'
        : (u.is_active
          ? '<span class="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">Active</span>'
          : '<span class="px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-600 font-bold text-[10px]">Disabled</span>');

      return `
        <tr>
          <td class="p-2.5">
            <p class="font-bold text-slate-900 dark:text-white">${escapeHtml(u.full_name)} ${isMe ? '<span class="text-[10px] text-blue-500">(You)</span>' : ''}</p>
            <p class="text-[11px] font-mono text-slate-500">@${escapeHtml(u.username)} • ${escapeHtml(u.email || '')}</p>
          </td>
          <td class="p-2.5">
            <select data-uid="${u.id}" class="admin-role-select bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2 py-1 text-xs font-bold" ${isMe ? 'disabled' : ''}>
              <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
              <option value="staff" ${u.role === 'staff' ? 'selected' : ''}>Staff</option>
              <option value="viewer" ${u.role === 'viewer' ? 'selected' : ''}>Viewer</option>
            </select>
          </td>
          <td class="p-2.5">
            <span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${u.totp_enabled ? 'bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}">${u.totp_enabled ? '2FA On' : 'Password'}</span>
          </td>
          <td class="p-2.5">${statusBadge}</td>
          <td class="p-2.5 text-right space-x-1">
            ${u.is_locked ? `<button type="button" data-uid="${u.id}" class="btn-unlock-user px-2 py-1 rounded-lg bg-orange-100 text-orange-700 font-bold text-[10px] cursor-pointer">Unlock</button>` : ''}
            ${!isMe ? `<button type="button" data-uid="${u.id}" data-active="${u.is_active ? '1' : '0'}" class="btn-toggle-user px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold text-[10px] cursor-pointer">${u.is_active ? 'Disable' : 'Enable'}</button>` : ''}
            ${!isMe ? `<button type="button" data-uid="${u.id}" data-uname="${escapeHtml(u.username)}" class="btn-delete-user px-2 py-1 rounded-lg bg-red-50 dark:bg-red-950/60 text-red-600 font-bold text-[10px] cursor-pointer">Del</button>` : ''}
          </td>
        </tr>
      `;
    }).join('');
  }

  async function refreshUsersModal() {
    const res = await apiFetch('/api/users');
    if (!res.ok) return;
    if (toggleSelfReg) toggleSelfReg.checked = Boolean(res.data.allow_self_registration);
    renderUsersTable(res.data.users || []);
  }

  if (btnOpenUsersModal) {
    btnOpenUsersModal.addEventListener('click', async () => {
      if (userDropdown) userDropdown.classList.add('hidden');
      await refreshUsersModal();
      openModal('modal-users');
    });
  }

  if (toggleSelfReg) {
    toggleSelfReg.addEventListener('change', async () => {
      const res = await apiFetch('/api/settings/auth', {
        method: 'PATCH',
        body: { allow_self_registration: toggleSelfReg.checked }
      });
      if (res.ok) {
        state.allowSelfRegistration = res.data.allow_self_registration;
        showToast(`Self-registration ${toggleSelfReg.checked ? 'enabled' : 'disabled'}`, 'info');
      }
    });
  }

  const usersTableBody = document.getElementById('users-table-body');
  if (usersTableBody) {
    usersTableBody.addEventListener('change', async (e) => {
      const sel = e.target.closest('.admin-role-select');
      if (sel) {
        const uid = Number(sel.getAttribute('data-uid'));
        const res = await apiFetch(`/api/users/${uid}`, { method: 'PATCH', body: { role: sel.value } });
        if (res.ok) {
          renderUsersTable(res.data.users);
          showToast('Role updated.', 'success');
        } else {
          showToast(res.data.error || 'Could not update role.', 'error');
          refreshUsersModal();
        }
      }
    });

    usersTableBody.addEventListener('click', async (e) => {
      const unlockBtn = e.target.closest('.btn-unlock-user');
      if (unlockBtn) {
        const uid = Number(unlockBtn.getAttribute('data-uid'));
        const res = await apiFetch(`/api/users/${uid}`, { method: 'PATCH', body: { unlock: true } });
        if (res.ok) {
          renderUsersTable(res.data.users);
          showToast('Account unlocked.', 'success');
        }
        return;
      }

      const toggleBtn = e.target.closest('.btn-toggle-user');
      if (toggleBtn) {
        const uid = Number(toggleBtn.getAttribute('data-uid'));
        const active = toggleBtn.getAttribute('data-active') === '1';
        const res = await apiFetch(`/api/users/${uid}`, { method: 'PATCH', body: { is_active: !active } });
        if (res.ok) {
          renderUsersTable(res.data.users);
          showToast(`Account ${!active ? 'enabled' : 'disabled'}.`, 'info');
        }
        return;
      }

      const delBtn = e.target.closest('.btn-delete-user');
      if (delBtn) {
        const uid = Number(delBtn.getAttribute('data-uid'));
        const uname = delBtn.getAttribute('data-uname');
        showConfirmDialog('Delete User?', `Permanently delete @${uname}?`, async () => {
          const res = await apiFetch(`/api/users/${uid}`, { method: 'DELETE' });
          if (res.ok) {
            renderUsersTable(res.data.users);
            showToast(`Removed @${uname}`, 'warning');
          } else {
            showToast(res.data.error || 'Delete failed.', 'error');
          }
        });
      }
    });
  }

  if (formAdminCreateUser) {
    formAdminCreateUser.addEventListener('submit', async (e) => {
      e.preventDefault();
      const res = await apiFetch('/api/users', {
        method: 'POST',
        body: {
          full_name: document.getElementById('admin-new-fullname').value.trim(),
          username: document.getElementById('admin-new-username').value.trim(),
          email: document.getElementById('admin-new-email').value.trim(),
          password: document.getElementById('admin-new-password').value,
          role: document.getElementById('admin-new-role').value
        }
      });
      if (res.ok && res.data.status === 'success') {
        formAdminCreateUser.reset();
        renderUsersTable(res.data.users);
        showToast(res.data.message, 'success');
      } else {
        showToast(res.data.error || 'Failed to create member.', 'error');
      }
    });
  }

  // Boot application
  bootstrapAuth();
});
