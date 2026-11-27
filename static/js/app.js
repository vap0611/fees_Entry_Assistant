/**
 * Fees Entry Assistant - Frontend Logic & Visual Engines (Mobile + Desktop)
 * Includes:
 * 1. Persistent Theme Engine (Light / Dark Mode + Mobile Status Bar Sync)
 * 2. Antigravity Particle Simulation (Touch + Mouse Responsive, Reduced-Motion Safe)
 * 3. Click Spark Burst Particle Engine
 * 4. Mobile Workspace Switcher (AI Chat <-> Live Sheet), Overflow Menu & Card View
 * 5. Live KPI Dashboard & Smooth Animated Counters
 * 6. Full Safety Pipeline (2-step Confirmation, 1-Click Undo, Duplicate Alert, Gap Detection, Activity Log)
 */

document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ==============================================================
  // 1. THEME ENGINE (LIGHT / DARK MODE)
  // ==============================================================
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  const themeIconSun = document.getElementById('theme-icon-sun');
  const themeIconMoon = document.getElementById('theme-icon-moon');
  const metaThemeColor = document.getElementById('meta-theme-color');

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
      if (themeIconSun) themeIconSun.classList.remove('hidden');
      if (themeIconMoon) themeIconMoon.classList.add('hidden');
      if (metaThemeColor) metaThemeColor.setAttribute('content', '#070b14');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('fees_assistant_theme', 'light');
      if (themeIconSun) themeIconSun.classList.add('hidden');
      if (themeIconMoon) themeIconMoon.classList.remove('hidden');
      if (metaThemeColor) metaThemeColor.setAttribute('content', '#f8fafc');
    }
    window.dispatchEvent(new CustomEvent('theme-change', { detail: { isDark } }));
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(!isDark);
    if (window.lucide) lucide.createIcons();
  }

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', toggleTheme);
  }

  initTheme();

  // ==============================================================
  // 2. ANTIGRAVITY PARTICLE SIMULATION BACKGROUND
  // ==============================================================
  function initAntigravityCanvas() {
    const canvas = document.getElementById('antigravity-canvas');
    if (!canvas || prefersReducedMotion) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let lastWidth = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let particles = [];
    let mouse = { x: -1000, y: -1000, active: false };
    let shockwaves = [];
    let animFrameId = null;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = width + 'px';
      canvas.style.height = height + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Avoid resetting particles on vertical-only resize (e.g., mobile keyboard open/close)
      if (lastWidth === 0 || Math.abs(width - lastWidth) > 15) {
        lastWidth = width;
        rebuildParticles();
      }
    }

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
      const maxCount = width < 640 ? 28 : 75;
      const count = Math.min(Math.floor((width * height) / 18000), maxCount);
      const palette = getPalette();
      particles = [];

      for (let i = 0; i < count; i++) {
        const col = palette[Math.floor(Math.random() * palette.length)];
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.45,
          vy: (Math.random() - 0.5) * 0.45,
          radius: Math.random() * 2.1 + 1.2,
          color: col,
          baseAlpha: Math.random() * 0.45 + 0.2,
          pulseSpeed: Math.random() * 0.02 + 0.01,
          pulse: Math.random() * Math.PI * 2
        });
      }
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

    window.addEventListener('touchstart', (e) => {
      if (e.touches && e.touches[0]) {
        mouse.x = e.touches[0].clientX;
        mouse.y = e.touches[0].clientY;
        mouse.active = true;
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (e.touches && e.touches[0]) {
        mouse.x = e.touches[0].clientX;
        mouse.y = e.touches[0].clientY;
        mouse.active = true;
      }
    }, { passive: true });

    window.addEventListener('touchend', () => {
      setTimeout(() => { mouse.active = false; }, 250);
    }, { passive: true });

    window.addEventListener('click', (e) => {
      shockwaves.push({
        x: e.clientX,
        y: e.clientY,
        radius: 5,
        maxRadius: Math.min(width, height) * 0.35,
        alpha: 0.55,
        speed: 4.5
      });
      if (shockwaves.length > 4) shockwaves.shift();
    });

    function draw() {
      ctx.clearRect(0, 0, width, height);

      const dark = isDarkTheme();
      const maxConnDist = width < 640 ? 80 : 95;
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
            const force = (1 - Math.abs(dist - sw.radius) / 25) * 1.4;
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

        p.vx *= 0.985;
        p.vy *= 0.985;
        p.vx += (Math.random() - 0.5) * 0.04;
        p.vy += (Math.random() - 0.5) * 0.04;

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
      } else {
        if (!animFrameId) animFrameId = requestAnimationFrame(draw);
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
    if (!canvas || prefersReducedMotion) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let sparks = [];
    let isRunning = false;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = window.innerWidth + 'px';
      canvas.style.height = window.innerHeight + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    window.addEventListener('resize', resize, { passive: true });
    resize();

    const sparkColors = [
      '#2563EB',
      '#F97316',
      '#EF4444',
      '#38BDF8',
      '#FBBF24',
      '#FFFFFF'
    ];

    window.addEventListener('click', (e) => {
      if (e.clientX === 0 && e.clientY === 0) return;
      const count = window.innerWidth < 640 ? 7 : 10;
      for (let i = 0; i < count; i++) {
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
  }

  initAntigravityCanvas();
  initClickSpark();

  // ==============================================================
  // 4. ANIMATED KPI COUNTER HELPERS
  // ==============================================================
  function animateValue(element, start, end, duration = 600, prefix = '', suffix = '') {
    if (!element) return;
    if (prefersReducedMotion) {
      element.textContent = `${prefix}${end.toLocaleString()}${suffix}`;
      return;
    }
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

  async function checkEngineStatus() {
    const kpiEngineMode = document.getElementById('kpi-engine-mode');
    if (!kpiEngineMode) return;

    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        if (data.gemini_enabled || data.has_gemini_key) {
          kpiEngineMode.innerHTML = `<span class="text-blue-600 dark:text-blue-400 font-bold">✨ Gemini AI</span>`;
        } else {
          kpiEngineMode.innerHTML = `<span class="text-orange-600 dark:text-orange-400 font-bold">⚡ Rule Engine</span>`;
        }
      } else {
        kpiEngineMode.textContent = 'Rule Engine';
      }
    } catch {
      kpiEngineMode.textContent = 'Rule Engine';
    }
  }

  checkEngineStatus();

  // ==============================================================
  // 5. DOM ELEMENTS & CORE REPOSITORY STATE
  // ==============================================================
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const btnSend = document.getElementById('btn-send');
  const messagesContainer = document.getElementById('messages-container');
  const typingIndicator = document.getElementById('typing-indicator');
  const btnClearChat = document.getElementById('btn-clear-chat');

  // Mobile Workspace Switcher & Overflow Menu Elements
  const mobileTabChat = document.getElementById('mobile-tab-chat');
  const mobileTabLedger = document.getElementById('mobile-tab-ledger');
  const mobileTabLedgerBadge = document.getElementById('mobile-tab-ledger-badge');
  const ledgerSection = document.getElementById('ledger-section');
  const chatSection = document.getElementById('chat-section');

  const btnMobileMore = document.getElementById('btn-mobile-more');
  const mobileMoreMenu = document.getElementById('mobile-more-menu');
  const btnMobileReset = document.getElementById('btn-mobile-reset');

  // Ledger View Switcher (Cards vs Table)
  const btnToggleLedgerView = document.getElementById('btn-toggle-ledger-view');
  const btnToggleLedgerViewDesktop = document.getElementById('btn-toggle-ledger-view-desktop');
  const iconLedgerView = document.getElementById('icon-ledger-view');
  const labelLedgerView = document.getElementById('label-ledger-view');
  const ledgerCardsView = document.getElementById('ledger-cards-view');
  const ledgerTableView = document.getElementById('ledger-table-view');
  const mobileMonthsBar = document.getElementById('mobile-months-bar');
  const mobileStudentCards = document.getElementById('mobile-student-cards');

  // Live Mock Table Elements
  const liveTableHeader = document.getElementById('live-table-header');
  const liveTableBody = document.getElementById('live-table-body');
  const btnResetTable = document.getElementById('btn-reset-table');

  // Activity Log Elements
  const btnOpenActivityLog = document.getElementById('btn-open-activity-log');
  const btnCloseActivityLog = document.getElementById('btn-close-activity-log');
  const btnCloseActivityLogFooter = document.getElementById('btn-close-activity-log-footer');
  const modalActivityLog = document.getElementById('modal-activity-log');
  const activityLogContainer = document.getElementById('activity-log-container');
  const headerLogCount = document.getElementById('header-log-count');

  // Add Student Modal Elements
  const btnOpenAddStudent = document.getElementById('btn-open-add-student');
  const btnCloseAddStudent = document.getElementById('btn-close-add-student');
  const btnCloseAddStudentFooter = document.getElementById('btn-close-add-student-footer');
  const modalAddStudent = document.getElementById('modal-add-student');
  const formAddStudent = document.getElementById('form-add-student');
  const inputNewStudentName = document.getElementById('input-new-student-name');
  const inputNewStudentStd = document.getElementById('input-new-student-std');
  const inputNewStudentSchool = document.getElementById('input-new-student-school');
  const inputNewStudentFee = document.getElementById('input-new-student-fee');
  const addStudentStatus = document.getElementById('add-student-status');
  const btnSaveNewStudent = document.getElementById('btn-save-new-student');

  // Table Search and Clear Elements
  const tableSearchInput = document.getElementById('table-search-input');
  const btnClearSearch = document.getElementById('btn-clear-search');
  const tableStudentCount = document.getElementById('table-student-count');

  // KPI Dashboard Metric Elements
  const kpiStudentsCount = document.getElementById('kpi-students-count');
  const kpiBaseFees = document.getElementById('kpi-base-fees');
  const kpiMonthsCount = document.getElementById('kpi-months-count');

  let lastUpdatedCell = null;
  let lastNewCol = null;
  let cachedTableData = null;
  let previousStudentCount = 0;
  let previousBaseFees = 0;
  let ledgerViewMode = window.innerWidth < 640 ? 'cards' : 'table';

  if (window.lucide) {
    lucide.createIcons();
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }, 50);
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    if (!text) return '';
    // Security Hardening: Escape HTML first to prevent Stored & Reflected XSS (CWE-79)
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
    let letter = "";
    idx += 1;
    while (idx > 0) {
      let rem = (idx - 1) % 26;
      letter = String.fromCharCode(65 + rem) + letter;
      idx = Math.floor((idx - 1) / 26);
    }
    return letter;
  }

  // ==============================================================
  // 5B. MOBILE WORKSPACE SWITCHER & OVERFLOW MENU
  // ==============================================================
  const ACTIVE_TAB_CLS = 'min-h-[38px] flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg text-xs font-bold transition cursor-pointer btn-primary-gradient shadow-sm';
  const INACTIVE_TAB_CLS = 'min-h-[38px] flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg text-xs font-bold transition cursor-pointer bg-white/80 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700';

  window.setMobileView = function(view) {
    if (!ledgerSection || !chatSection) return;

    if (view === 'ledger') {
      ledgerSection.classList.remove('hidden');
      ledgerSection.classList.add('flex');
      chatSection.classList.add('hidden');
      chatSection.classList.remove('flex');

      if (mobileTabLedger) mobileTabLedger.className = ACTIVE_TAB_CLS;
      if (mobileTabChat) mobileTabChat.className = INACTIVE_TAB_CLS;
    } else {
      chatSection.classList.remove('hidden');
      chatSection.classList.add('flex');
      ledgerSection.classList.add('hidden');
      ledgerSection.classList.remove('flex');

      if (mobileTabChat) mobileTabChat.className = ACTIVE_TAB_CLS;
      if (mobileTabLedger) mobileTabLedger.className = INACTIVE_TAB_CLS;
      scrollToBottom();
    }
    if (window.lucide) lucide.createIcons();
  };

  if (mobileTabChat) {
    mobileTabChat.addEventListener('click', () => window.setMobileView('chat'));
  }
  if (mobileTabLedger) {
    mobileTabLedger.addEventListener('click', () => window.setMobileView('ledger'));
  }

  // Mobile Overflow Menu
  function closeMobileMoreMenu() {
    if (mobileMoreMenu) mobileMoreMenu.classList.add('hidden');
    if (btnMobileMore) btnMobileMore.setAttribute('aria-expanded', 'false');
  }

  if (btnMobileMore && mobileMoreMenu) {
    btnMobileMore.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = mobileMoreMenu.classList.contains('hidden');
      mobileMoreMenu.classList.toggle('hidden', !willOpen);
      btnMobileMore.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
  }

  if (btnMobileReset && btnResetTable) {
    btnMobileReset.addEventListener('click', () => {
      closeMobileMoreMenu();
      btnResetTable.click();
    });
  }

  // Soft Keyboard Scroll Guard for Chat Input on Mobile
  if (chatInput) {
    chatInput.addEventListener('focus', () => {
      if (window.innerWidth < 768) {
        setTimeout(scrollToBottom, 280);
      }
    });
  }

  // Ledger Cards <-> Table Grid Switcher
  function applyLedgerViewMode() {
    if (!ledgerCardsView || !ledgerTableView) return;

    if (ledgerViewMode === 'cards') {
      ledgerCardsView.classList.remove('hidden');
      ledgerTableView.classList.add('hidden');
      if (labelLedgerView) labelLedgerView.textContent = 'Table';
      if (iconLedgerView) iconLedgerView.setAttribute('data-lucide', 'table-2');
      if (btnToggleLedgerViewDesktop) {
        btnToggleLedgerViewDesktop.innerHTML = `<i data-lucide="table-2" class="w-3 h-3 text-blue-500"></i><span>Table</span>`;
      }
    } else {
      ledgerTableView.classList.remove('hidden');
      ledgerCardsView.classList.add('hidden');
      if (labelLedgerView) labelLedgerView.textContent = 'Cards';
      if (iconLedgerView) iconLedgerView.setAttribute('data-lucide', 'layout-grid');
      if (btnToggleLedgerViewDesktop) {
        btnToggleLedgerViewDesktop.innerHTML = `<i data-lucide="layout-list" class="w-3 h-3 text-orange-500"></i><span>Cards</span>`;
      }
    }
    if (window.lucide) lucide.createIcons();
  }

  function toggleLedgerViewMode() {
    ledgerViewMode = ledgerViewMode === 'cards' ? 'table' : 'cards';
    applyLedgerViewMode();
  }

  if (btnToggleLedgerView) btnToggleLedgerView.addEventListener('click', toggleLedgerViewMode);
  if (btnToggleLedgerViewDesktop) btnToggleLedgerViewDesktop.addEventListener('click', toggleLedgerViewMode);

  applyLedgerViewMode();

  // ==============================================================
  // 6. LIVE LEDGER RENDERING (TABLE GRID + MOBILE CARDS)
  // ==============================================================

  function renderMobileCards(filteredStudents, months, query) {
    if (!mobileMonthsBar || !mobileStudentCards) return;

    // Render Month Columns Management Strip
    if (months.length === 0) {
      mobileMonthsBar.innerHTML = `<span class="text-[11px] text-slate-400">No active month columns</span>`;
    } else {
      mobileMonthsBar.innerHTML = `
        <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mr-1 flex-shrink-0">Columns:</span>
        ${months.map(m => {
          const isNewCol = lastNewCol === m;
          const badgeTone = isNewCol
            ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700 col-new'
            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700';
          return `
            <span class="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-semibold whitespace-nowrap flex-shrink-0 ${badgeTone}">
              <span>${escapeHtml(m)}</span>
              <button
                type="button"
                data-month="${escapeHtml(m)}"
                class="btn-delete-col text-slate-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 rounded-full active:scale-95 cursor-pointer"
                title="Delete column '${escapeHtml(m)}'"
                aria-label="Delete column ${escapeHtml(m)}"
              >
                <i data-lucide="x" class="w-3 h-3"></i>
              </button>
            </span>
          `;
        }).join('')}
      `;
    }

    if (filteredStudents.length === 0) {
      mobileStudentCards.innerHTML = `
        <div class="col-span-full p-6 text-center text-slate-400 dark:text-slate-500 text-xs">
          No students found matching "${escapeHtml(query)}".
        </div>
      `;
      return;
    }

    mobileStudentCards.innerHTML = filteredStudents.map(s => {
      const payments = s.payments || {};
      const monthPills = months.map(m => {
        const paid = payments[m];
        const isJustUpdated = lastUpdatedCell && lastUpdatedCell.student_id === s.id && lastUpdatedCell.month === m;
        const pulseCls = isJustUpdated ? 'cell-updated ring-2 ring-orange-400/70' : '';

        if (paid !== undefined && paid !== null && paid !== '') {
          return `
            <div class="flex flex-col px-2.5 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 ${pulseCls}">
              <span class="text-[9px] font-mono uppercase tracking-wider text-emerald-700/80 dark:text-emerald-400/80">${escapeHtml(m)}</span>
              <span class="text-xs font-mono font-bold text-emerald-800 dark:text-emerald-300">₹${Number(paid).toLocaleString()}</span>
            </div>
          `;
        }
        return `
          <div class="flex flex-col px-2.5 py-1.5 rounded-lg bg-slate-50/80 dark:bg-slate-900/60 border border-dashed border-slate-200 dark:border-slate-700/80">
            <span class="text-[9px] font-mono uppercase tracking-wider text-slate-400 dark:text-slate-500">${escapeHtml(m)}</span>
            <span class="text-xs font-mono text-slate-400 dark:text-slate-600">Unpaid</span>
          </div>
        `;
      }).join('');

      return `
        <article class="glass-card rounded-xl p-3 space-y-2.5 shadow-xs">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center space-x-1.5">
                <h3 class="text-sm font-bold text-slate-900 dark:text-white truncate">${escapeHtml(s.name)}</h3>
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 flex-shrink-0">Std ${escapeHtml(s.std || '—')}</span>
              </div>
              <p class="text-[11px] text-slate-500 dark:text-slate-400 truncate mt-0.5">${escapeHtml(s.school || 'School not set')}</p>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-[9px] uppercase tracking-wider text-slate-400 dark:text-slate-500 font-semibold">Base Fee</div>
              <div class="text-xs font-mono font-bold text-orange-600 dark:text-orange-400">₹${Number(s.monthly_fee).toLocaleString()}</div>
            </div>
          </div>

          <div class="grid grid-cols-2 min-[380px]:grid-cols-3 gap-1.5">
            ${monthPills}
          </div>

          <div class="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end">
            <button
              type="button"
              data-student-name="${escapeHtml(s.name)}"
              data-student-std="${escapeHtml(s.std || '')}"
              data-student-fee="${Number(s.monthly_fee) || 0}"
              class="btn-card-quick-pay min-h-[34px] px-3 py-1 rounded-lg text-[11px] font-bold bg-blue-50 dark:bg-blue-950/60 hover:bg-blue-100 dark:hover:bg-blue-900/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60 inline-flex items-center space-x-1 active:scale-95 cursor-pointer"
            >
              <i data-lucide="zap" class="w-3 h-3 text-orange-500"></i>
              <span>Quick Pay (₹${Number(s.monthly_fee).toLocaleString()})</span>
            </button>
          </div>
        </article>
      `;
    }).join('');
  }

  async function renderLiveMockTable(data = null) {
    try {
      if (!data && !cachedTableData) {
        const res = await fetch('/api/mock-table');
        data = await res.json();
      } else if (!data) {
        data = cachedTableData;
      }
      cachedTableData = data;

      const months = data.months || [];
      const students = data.students || [];
      const totalBase = data.total_base_fees || 0;

      // Update KPI Counter animations & Mobile Tab Badge
      if (mobileTabLedgerBadge) {
        mobileTabLedgerBadge.textContent = students.length;
      }
      if (kpiStudentsCount) {
        animateValue(kpiStudentsCount, previousStudentCount, students.length, 500);
        previousStudentCount = students.length;
      }
      if (kpiBaseFees) {
        animateValue(kpiBaseFees, previousBaseFees, totalBase, 500, '₹');
        previousBaseFees = totalBase;
      }
      if (kpiMonthsCount) {
        kpiMonthsCount.textContent = `${months.length} Active`;
      }

      if (tableStudentCount) {
        tableStudentCount.textContent = `${students.length} Students • ₹${totalBase.toLocaleString()}`;
      }

      let headerHtml = `
        <th class="p-2.5 sticky left-0 bg-slate-100 dark:bg-slate-900 z-10 border-r border-slate-200 dark:border-slate-800 min-w-[125px] text-slate-800 dark:text-slate-100">
          <div class="text-[9px] text-slate-400 dark:text-slate-500 font-mono font-medium">Col A</div>
          <div class="font-bold">Student Name</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 min-w-[60px] text-center text-slate-800 dark:text-slate-100">
          <div class="text-[9px] text-slate-400 dark:text-slate-500 font-mono font-medium">Col B</div>
          <div class="font-bold">Std</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 min-w-[110px] text-slate-800 dark:text-slate-100">
          <div class="text-[9px] text-slate-400 dark:text-slate-500 font-mono font-medium">Col C</div>
          <div class="font-bold">School</div>
        </th>
        <th class="p-2.5 border-r border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 text-right min-w-[90px] text-slate-800 dark:text-slate-100">
          <div class="text-[9px] text-slate-400 dark:text-slate-500 font-mono font-medium">Col D</div>
          <div class="font-bold">Base Fee</div>
        </th>
      `;

      months.forEach((m, idx) => {
        const colLetter = getColLetter(4 + idx);
        const isNewCol = (lastNewCol === m);
        const colBgClass = isNewCol 
          ? 'bg-amber-100 dark:bg-amber-950/60 col-new text-amber-900 dark:text-amber-300' 
          : 'bg-slate-50 dark:bg-slate-900/90 text-slate-800 dark:text-slate-100';

        headerHtml += `
          <th class="p-2.5 text-center border-r border-slate-200 dark:border-slate-800 min-w-[110px] group ${colBgClass}">
            <div class="flex items-center justify-between text-[9px] text-blue-600 dark:text-blue-400 font-mono font-bold mb-0.5">
              <span>Col ${colLetter}</span>
              <button 
                type="button" 
                data-month="${escapeHtml(m)}"
                class="btn-delete-col text-slate-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 rounded hover:bg-red-50 dark:hover:bg-red-950/40 transition active:scale-95 cursor-pointer" 
                title="Delete column '${escapeHtml(m)}'"
                aria-label="Delete column ${escapeHtml(m)}"
              >
                <i data-lucide="trash-2" class="w-3 h-3"></i>
              </button>
            </div>
            <div class="font-mono font-bold tracking-tight">${escapeHtml(m)}</div>
          </th>
        `;
      });
      liveTableHeader.innerHTML = headerHtml;

      const query = (tableSearchInput ? tableSearchInput.value : "").trim().toLowerCase();
      const filteredStudents = query 
        ? students.filter(s => 
            (s.name && s.name.toLowerCase().includes(query)) ||
            (s.school && s.school.toLowerCase().includes(query)) ||
            (s.std && String(s.std).toLowerCase().includes(query))
          )
        : students;

      if (tableStudentCount && query) {
        tableStudentCount.textContent = `Showing ${filteredStudents.length} of ${students.length}`;
      }

      if (filteredStudents.length === 0) {
        liveTableBody.innerHTML = `
          <tr>
            <td colspan="${4 + months.length}" class="p-6 text-center text-slate-400 dark:text-slate-500 font-sans text-xs">
              No students found matching "${escapeHtml(query)}".
            </td>
          </tr>
        `;
      } else {
        liveTableBody.innerHTML = filteredStudents.map(s => {
          const payments = s.payments || {};
          let rowHtml = `
            <tr class="hover:bg-blue-50/40 dark:hover:bg-slate-800/40 transition">
              <td class="p-2.5 font-bold text-slate-900 dark:text-slate-100 sticky left-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 shadow-xs font-sans">${escapeHtml(s.name)}</td>
              <td class="p-2.5 text-center text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 font-sans text-xs">${escapeHtml(s.std || '—')}</td>
              <td class="p-2.5 text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 font-sans text-xs">${escapeHtml(s.school || '—')}</td>
              <td class="p-2.5 text-right font-semibold text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-800 font-mono text-xs">₹${Number(s.monthly_fee).toLocaleString()}</td>
          `;

          months.forEach(m => {
            const paid = payments[m];
            const isJustUpdated = (lastUpdatedCell && lastUpdatedCell.student_id === s.id && lastUpdatedCell.month === m);
            const cellClass = isJustUpdated ? 'cell-updated' : '';

            if (paid !== undefined && paid !== null && paid !== "") {
              rowHtml += `<td class="p-2 text-center border-r border-slate-100 dark:border-slate-800/60 ${cellClass}">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 border border-emerald-300/40 dark:border-emerald-700/40 shadow-2xs">
                  ₹${Number(paid).toLocaleString()}
                </span>
              </td>`;
            } else {
              rowHtml += `<td class="p-2 text-center border-r border-slate-100 dark:border-slate-800/60 text-slate-300 dark:text-slate-600 font-sans text-xs">—</td>`;
            }
          });

          rowHtml += `</tr>`;
          return rowHtml;
        }).join('');
      }

      // Keep Mobile Card View synchronized with zero extra fetches
      renderMobileCards(filteredStudents, months, query);

      if (window.lucide) {
        lucide.createIcons();
      }

    } catch (e) {
      console.error('Error rendering live mock table:', e);
    }
  }

  // Search input and clear button handlers
  if (tableSearchInput) {
    tableSearchInput.addEventListener('input', () => {
      if (btnClearSearch) {
        btnClearSearch.classList.toggle('hidden', tableSearchInput.value.trim().length === 0);
      }
      renderLiveMockTable(cachedTableData);
    });
  }

  if (btnClearSearch) {
    btnClearSearch.addEventListener('click', () => {
      tableSearchInput.value = '';
      btnClearSearch.classList.add('hidden');
      tableSearchInput.focus();
      renderLiveMockTable(cachedTableData);
    });
  }

  // Event Delegation for Column Delete (Table Header + Mobile Month Strip)
  function handleDeleteColumnClick(e) {
    const btn = e.target.closest('.btn-delete-col');
    if (btn) {
      const month = btn.getAttribute('data-month');
      if (month) confirmDeleteColumn(month);
    }
  }

  if (liveTableHeader) liveTableHeader.addEventListener('click', handleDeleteColumnClick);
  if (mobileMonthsBar) mobileMonthsBar.addEventListener('click', handleDeleteColumnClick);

  // Event Delegation for Student Card Quick Pay Button
  if (mobileStudentCards) {
    mobileStudentCards.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-card-quick-pay');
      if (!btn) return;
      const name = btn.getAttribute('data-student-name') || '';
      const std = btn.getAttribute('data-student-std') || '';
      const fee = btn.getAttribute('data-student-fee') || '';
      const stdPart = std ? ` Std ${std}` : '';
      if (chatInput) {
        chatInput.value = `${name}${stdPart} paid ${fee}`;
        if (window.innerWidth < 768) {
          window.setMobileView('chat');
        }
        chatInput.focus();
      }
    });
  }

  // Reset Table Handler
  if (btnResetTable) {
    btnResetTable.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/mock-reset', { method: 'POST' });
        const data = await res.json();
        lastUpdatedCell = null;
        lastNewCol = null;
        if (tableSearchInput) {
          tableSearchInput.value = '';
          if (btnClearSearch) btnClearSearch.classList.add('hidden');
        }
        await renderLiveMockTable(data.table);
        await refreshActivityLog();
        const count = (data.table && data.table.students) ? data.table.students.length : 0;
        appendBotMessage(`🔄 **Database reset** to original seed state (${count} students).`, null, 'info');
      } catch (e) {
        alert('Error resetting table');
      }
    });
  }

  // ==============================================================
  // 7. CHAT INTERFACE & INTERACTIVE BOT MESSAGES
  // ==============================================================

  function appendUserMessage(text) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const wrapper = document.createElement('div');
    wrapper.className = 'message-user message-enter flex items-start justify-end space-x-2';
    
    wrapper.innerHTML = `
      <div class="message-user-bubble">
        <div class="flex items-center justify-between space-x-3 mb-1 text-[10px] text-blue-200">
          <span class="font-semibold uppercase tracking-wider">Admin</span>
          <span>${time}</span>
        </div>
        <p class="text-sm font-medium leading-relaxed">${escapeHtml(text)}</p>
      </div>
      <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-tr from-blue-600 via-orange-500 to-red-500 text-white flex items-center justify-center flex-shrink-0 text-xs shadow-sm">
        <i data-lucide="user" class="w-3.5 h-3.5 sm:w-4 sm:h-4"></i>
      </div>
    `;

    messagesContainer.appendChild(wrapper);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
  }

  function appendBotMessage(replyText, timestamp, status = 'success', extraConfig = {}) {
    const time = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const wrapper = document.createElement('div');
    wrapper.className = 'message-bot message-enter flex items-start space-x-2 sm:space-x-3';

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

    // Interactive Confirm / Cancel / Gap Option Buttons (Thumb-sized min-h-[38px])
    if (extraConfig.options && extraConfig.options.length > 0 && extraConfig.actionId) {
      buttonsHtml = `
        <div class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex flex-wrap gap-2 action-buttons-group">
          ${extraConfig.options.map(opt => {
            const isPrimary = opt.primary || opt.choice === 'confirm' || opt.choice === 'fill_gap' || opt.choice === 'confirm_duplicate';
            const btnClass = isPrimary 
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-xs font-semibold' 
              : 'bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium border border-slate-300 dark:border-slate-700';
            return `
              <button 
                onclick="handleActionChoice('${extraConfig.actionId}', '${opt.choice}', this)"
                class="min-h-[38px] px-3.5 py-2 rounded-lg text-xs transition active:scale-95 flex items-center space-x-1 cursor-pointer ${btnClass}"
              >
                ${opt.choice === 'confirm' ? '<i data-lucide="check" class="w-3.5 h-3.5 mr-0.5"></i>' : ''}
                ${opt.choice === 'cancel' ? '<i data-lucide="x" class="w-3.5 h-3.5 mr-0.5"></i>' : ''}
                <span>${escapeHtml(opt.label)}</span>
              </button>
            `;
          }).join('')}
        </div>
      `;
    }

    // Undo Button + Mobile Shortcut to Inspect Sheet
    if (extraConfig.entryId) {
      buttonsHtml = `
        <div class="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2">
          <button 
            id="btn-undo-${extraConfig.entryId}"
            onclick="handleUndoPayment('${extraConfig.entryId}', this)"
            class="min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-50 dark:bg-orange-950/40 hover:bg-orange-100 dark:hover:bg-orange-900/40 text-orange-800 dark:text-orange-300 border border-orange-200 dark:border-orange-800/80 transition active:scale-95 flex items-center space-x-1 cursor-pointer"
          >
            <i data-lucide="rotate-ccw" class="w-3.5 h-3.5 text-orange-600 dark:text-orange-400"></i>
            <span>Undo Entry</span>
          </button>
          <button
            type="button"
            onclick="setMobileView('ledger')"
            class="md:hidden min-h-[36px] px-2.5 py-1.5 rounded-lg text-[11px] font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800/60 flex items-center space-x-1 active:scale-95 cursor-pointer"
          >
            <span>View Sheet</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
          </button>
          <span class="hidden md:inline text-[10px] text-slate-400 dark:text-slate-500">Reverts this cell in sheet</span>
        </div>
      `;
    }

    wrapper.innerHTML = `
      <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full ${bgBadge} flex items-center justify-center flex-shrink-0 text-xs font-bold shadow-sm">
        <i data-lucide="${iconName}" class="w-3.5 h-3.5 sm:w-4 sm:h-4"></i>
      </div>
      <div class="message-bot-bubble bot-markdown text-xs sm:text-sm text-slate-800 dark:text-slate-100">
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

  // ==============================================================
  // 8. HANDLE CONFIRM / CANCEL / GAP ACTION CHOICES
  // ==============================================================

  window.handleActionChoice = async function(actionId, choice, btnElement) {
    const group = btnElement.closest('.action-buttons-group');
    if (group) {
      group.querySelectorAll('button').forEach(b => {
        b.disabled = true;
        b.classList.add('opacity-40', 'cursor-not-allowed');
      });
    }

    typingIndicator.classList.remove('hidden');
    scrollToBottom();

    try {
      let endpoint = '/api/action/confirm';
      let payload = { action_id: actionId, choice: choice };

      if (choice === 'cancel') {
        endpoint = '/api/action/cancel';
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      typingIndicator.classList.add('hidden');

      if (res.ok) {
        if (data.status === 'confirmation_required') {
          appendBotMessage(data.reply, data.timestamp, data.status, {
            actionId: data.action_id,
            options: data.options
          });
        } else {
          appendBotMessage(data.reply, data.timestamp, data.status, {
            entryId: data.entry_id
          });
        }

        if (data.table_updated && data.table) {
          lastUpdatedCell = data.updated_cell || null;
          await renderLiveMockTable(data.table);
        }
        await refreshActivityLog();
      } else {
        appendBotMessage(`⚠️ ${data.error || 'Failed to complete action.'}`, null, 'error');
      }
    } catch (err) {
      typingIndicator.classList.add('hidden');
      appendBotMessage('⚠️ Network error connecting to server.', null, 'error');
    }
  };

  // ==============================================================
  // 9. HANDLE UNDO PAYMENT
  // ==============================================================

  window.handleUndoPayment = async function(entryId, btnElement) {
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-slate-400"></i><span class="text-slate-400">Undone ✓</span>`;
      btnElement.className = "min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed flex items-center space-x-1";
    }

    typingIndicator.classList.remove('hidden');
    scrollToBottom();

    try {
      const res = await fetch('/api/action/undo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry_id: entryId })
      });

      const data = await res.json();
      typingIndicator.classList.add('hidden');

      if (res.ok) {
        appendBotMessage(data.reply, data.timestamp, data.status);
        if (data.table_updated && data.table) {
          lastUpdatedCell = null;
          await renderLiveMockTable(data.table);
        }
        await refreshActivityLog();
      } else {
        appendBotMessage(`⚠️ ${data.error || 'Failed to undo entry.'}`, null, 'error');
      }
    } catch (err) {
      typingIndicator.classList.add('hidden');
      appendBotMessage('⚠️ Network error during undo.', null, 'error');
    }
  };

  // ==============================================================
  // 10. CHAT FORM SUBMIT & PRESERVING MESSAGE ON NETWORK ERROR
  // ==============================================================

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
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: savedMessage })
      });

      const data = await response.json();
      typingIndicator.classList.add('hidden');
      btnSend.disabled = false;

      if (response.ok) {
        appendBotMessage(data.reply, data.timestamp, data.status, {
          actionId: data.action_id,
          options: data.options,
          entryId: data.entry_id
        });

        if (data.table_updated && data.table) {
          lastUpdatedCell = data.updated_cell || null;
          await renderLiveMockTable(data.table);
          await refreshActivityLog();
        }
      } else {
        appendBotMessage(`⚠️ ${data.error || 'Failed to process message.'}`, null, 'error');
      }
    } catch (err) {
      typingIndicator.classList.add('hidden');
      btnSend.disabled = false;

      chatInput.value = savedMessage;
      appendBotMessage('⚠️ **Connection error:** The server could not be reached. Your message was kept in the input box so you don\'t have to retype it.', null, 'error');
      chatInput.focus();
    }
  });

  // ==============================================================
  // 11. REPORT DOWNLOAD & COLUMN DELETION HANDLERS
  // ==============================================================

  window.triggerReportDownload = function() {
    window.location.href = '/api/export-csv';
  };

  window.confirmDeleteColumn = async function(monthName) {
    if (!monthName) return;
    const ok = confirm(`Are you sure you want to delete column "${monthName}" and all fee entries recorded in it?`);
    if (!ok) return;

    typingIndicator.classList.remove('hidden');
    scrollToBottom();

    try {
      const res = await fetch('/api/columns/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month_name: monthName })
      });

      const data = await res.json();
      typingIndicator.classList.add('hidden');

      if (res.ok && data.status === 'success') {
        appendBotMessage(data.reply, data.timestamp, 'warning');
        if (data.table) {
          lastUpdatedCell = null;
          await renderLiveMockTable(data.table);
        }
        await refreshActivityLog();
      } else {
        appendBotMessage(data.reply || `⚠️ Failed to delete column "${monthName}".`, null, 'error');
      }
    } catch (err) {
      typingIndicator.classList.add('hidden');
      appendBotMessage('⚠️ Network error while attempting to delete column.', null, 'error');
    }
  };

  window.simulateNetworkError = function() {
    chatInput.value = "Student Dummy has paid 2000";
    appendBotMessage('⚠️ **[Simulated Test] Connection error:** Server unreachable. Notice that your typed message has been safely preserved in the input box below!', null, 'warning');
    chatInput.focus();
  };

  window.useQuickPrompt = function(promptText) {
    if (window.innerWidth < 768) {
      window.setMobileView('chat');
    }
    chatInput.value = promptText;
    chatForm.dispatchEvent(new Event('submit'));
  };

  if (btnClearChat) {
    btnClearChat.addEventListener('click', () => {
      if (confirm('Clear the chat history screen?')) {
        const welcome = messagesContainer.firstElementChild;
        messagesContainer.innerHTML = '';
        if (welcome) messagesContainer.appendChild(welcome);
        scrollToBottom();
      }
    });
  }

  // ==============================================================
  // 12. ACTIVITY LOG (SESSION HISTORY)
  // ==============================================================

  async function refreshActivityLog() {
    try {
      const res = await fetch('/api/activity-log');
      const data = await res.json();
      const logs = data.log || [];

      if (headerLogCount) headerLogCount.textContent = logs.length;

      if (!activityLogContainer) return;

      if (logs.length === 0) {
        activityLogContainer.innerHTML = `
          <div class="p-8 text-center text-xs text-slate-400 dark:text-slate-500">
            No activity yet in this session.
          </div>
        `;
        return;
      }

      activityLogContainer.innerHTML = logs.map(item => {
        let badgeBg = 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300';
        if (item.status === 'Undone') badgeBg = 'bg-orange-100 dark:bg-orange-950/80 text-orange-800 dark:text-orange-300';
        if (item.status === 'Cancelled') badgeBg = 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300';
        if (item.status === 'Reset') badgeBg = 'bg-blue-100 dark:bg-blue-950/80 text-blue-800 dark:text-blue-300';

        return `
          <div class="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200/90 dark:border-slate-800 shadow-2xs space-y-1">
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-slate-900 dark:text-slate-100">${escapeHtml(item.student)}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded font-semibold ${badgeBg}">${escapeHtml(item.status)}</span>
            </div>
            <div class="text-[11px] text-slate-500 dark:text-slate-400 flex items-center space-x-2">
              <span>${escapeHtml(item.school)}</span>
              <span>•</span>
              <span class="font-mono text-slate-700 dark:text-slate-300">₹${Number(item.amount).toLocaleString()}</span>
              <span>•</span>
              <span class="font-mono font-medium text-blue-600 dark:text-blue-400">${escapeHtml(item.month)}</span>
            </div>
            <div class="text-[10px] text-slate-400 dark:text-slate-500 pt-0.5 flex items-center justify-between">
              <span>${escapeHtml(item.note || '')}</span>
              <span>${escapeHtml(item.time)}</span>
            </div>
          </div>
        `;
      }).join('');

    } catch (e) {
      console.error('Error refreshing activity log:', e);
    }
  }

  if (btnOpenActivityLog) {
    btnOpenActivityLog.addEventListener('click', () => {
      closeMobileMoreMenu();
      refreshActivityLog();
      if (modalActivityLog) modalActivityLog.classList.remove('hidden');
    });
  }
  if (btnCloseActivityLog) {
    btnCloseActivityLog.addEventListener('click', () => {
      if (modalActivityLog) modalActivityLog.classList.add('hidden');
    });
  }
  if (btnCloseActivityLogFooter) {
    btnCloseActivityLogFooter.addEventListener('click', () => {
      if (modalActivityLog) modalActivityLog.classList.add('hidden');
    });
  }

  // ==============================================================
  // 13. ADD NEW STUDENT MODAL LOGIC
  // ==============================================================

  if (btnOpenAddStudent) {
    btnOpenAddStudent.addEventListener('click', () => {
      closeMobileMoreMenu();
      if (addStudentStatus) addStudentStatus.classList.add('hidden');
      if (inputNewStudentName) inputNewStudentName.value = '';
      if (inputNewStudentStd) inputNewStudentStd.value = '';
      if (inputNewStudentSchool) inputNewStudentSchool.value = '';
      if (inputNewStudentFee) inputNewStudentFee.value = '';
      if (modalAddStudent) modalAddStudent.classList.remove('hidden');
      if (inputNewStudentName && window.innerWidth >= 640) {
        setTimeout(() => inputNewStudentName.focus(), 100);
      }
    });
  }

  if (btnCloseAddStudent) {
    btnCloseAddStudent.addEventListener('click', () => {
      if (modalAddStudent) modalAddStudent.classList.add('hidden');
    });
  }

  if (btnCloseAddStudentFooter) {
    btnCloseAddStudentFooter.addEventListener('click', () => {
      if (modalAddStudent) modalAddStudent.classList.add('hidden');
    });
  }

  if (formAddStudent) {
    formAddStudent.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = inputNewStudentName ? inputNewStudentName.value.trim() : '';
      const std = inputNewStudentStd ? inputNewStudentStd.value.trim() : '';
      const school = inputNewStudentSchool ? inputNewStudentSchool.value.trim() : '';
      const fee = inputNewStudentFee ? Number(inputNewStudentFee.value) : 0;

      if (!name) {
        alert('Please enter student name');
        return;
      }

      if (btnSaveNewStudent) btnSaveNewStudent.disabled = true;

      try {
        const res = await fetch('/api/students', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, std, school, monthly_fee: fee })
        });
        const data = await res.json();
        if (btnSaveNewStudent) btnSaveNewStudent.disabled = false;

        if (res.ok && data.status === 'success') {
          if (addStudentStatus) {
            addStudentStatus.className = 'p-2 rounded text-xs bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800';
            addStudentStatus.textContent = '✓ Student added successfully!';
            addStudentStatus.classList.remove('hidden');
          }

          setTimeout(() => {
            if (modalAddStudent) modalAddStudent.classList.add('hidden');
          }, 800);

          if (data.table) {
            await renderLiveMockTable(data.table);
          }
          await refreshActivityLog();
          appendBotMessage(data.reply, data.timestamp, 'success');
        } else {
          if (addStudentStatus) {
            addStudentStatus.className = 'p-2 rounded text-xs bg-red-50 dark:bg-red-950/60 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800';
            addStudentStatus.textContent = data.reply || 'Failed to add student.';
            addStudentStatus.classList.remove('hidden');
          }
        }
      } catch (err) {
        if (btnSaveNewStudent) btnSaveNewStudent.disabled = false;
        alert('Network error adding student.');
      }
    });
  }

  // Close modals & mobile overflow menu on outside click or Escape key
  window.addEventListener('click', (e) => {
    if (modalActivityLog && e.target === modalActivityLog) modalActivityLog.classList.add('hidden');
    if (modalAddStudent && e.target === modalAddStudent) modalAddStudent.classList.add('hidden');
    if (mobileMoreMenu && !mobileMoreMenu.classList.contains('hidden')) {
      const wrapper = document.getElementById('mobile-more-wrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        closeMobileMoreMenu();
      }
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modalActivityLog) modalActivityLog.classList.add('hidden');
      if (modalAddStudent) modalAddStudent.classList.add('hidden');
      closeMobileMoreMenu();
    }
  });

  // Initial table & log load
  renderLiveMockTable();
  refreshActivityLog();
});
