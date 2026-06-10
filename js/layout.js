// ============================================================
// js/layout.js — Sidebar + Topbar Renderer
// Civil Engineering Student Portal
// ============================================================

// ══ NAV DEFINITIONS ══════════════════════════════════════════
const NAV = {
  student: [
    { id: 'dashboard',      icon: '🏠', label: 'Dashboard',       href: 'student-dashboard.html' },
    { id: 'marks',          icon: '📊', label: 'My Marks',        href: 'student-marks.html' },
    { id: 'tests',          icon: '📝', label: 'Online Tests',     href: 'student-tests.html' },
    { id: 'notes',          icon: '📚', label: 'Lecture Notes',    href: 'student-notes.html' },
    { id: 'chatbot',        icon: '🤖', label: 'Chatbot',          href: 'student-chatbot.html' },
    { id: 'notifications',  icon: '🔔', label: 'Notifications',    href: 'student-notifications.html' },
  ],
  instructor: [
    { id: 'dashboard',   icon: '🏠', label: 'Dashboard',          href: 'instructor-dashboard.html' },
    { id: 'marks',       icon: '📊', label: 'Manage Marks',       href: 'instructor-marks.html' },
    { id: 'complaints',  icon: '📬', label: 'Complaints',         href: 'instructor-complaints.html' },
    { id: 'tests',       icon: '📝', label: 'Upload Questions',   href: 'instructor-tests.html' },
    { id: 'notes',       icon: '📚', label: 'Lecture Notes',      href: 'instructor-notes.html' },
    { id: 'notices',     icon: '📣', label: 'Send Notice',        href: 'instructor-notices.html' },
  ]
};

// ══ RENDER LAYOUT ═════════════════════════════════════════════
function renderLayout({ role, activePage, pageTitle, badges = {} }) {
  const session = role === 'student'
    ? Session.requireStudent()
    : Session.requireInstructor();
  if (!session) return;

  const navItems  = NAV[role] || [];
  const userInit  = initials(session.name || 'U');
  const userRole  = role === 'instructor' ? 'Instructor' : `Student · ${session.studentId || ''}`;
  const todayStr  = DateUtil.today();
  const activeLabel = navItems.find(n => n.id === activePage)?.label || pageTitle || 'Portal';

  // Build nav HTML
  const navHTML = navItems.map(item => {
    const badge = badges[item.id] ? `<span class="nav-badge">${badges[item.id]}</span>` : '';
    return `
      <button
        class="nav-item ${activePage === item.id ? 'active' : ''}"
        onclick="window.location.href='${item.href}'"
        title="${item.label}">
        <span class="nav-icon">${item.icon}</span>
        <span class="nav-label">${item.label}</span>
        ${badge}
      </button>`;
  }).join('');

  // Inject full layout into body
  document.body.innerHTML = `
    <!-- Sidebar overlay for mobile -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="closeSidebar()"></div>

    <!-- ══ SIDEBAR ══ -->
    <aside class="sidebar" id="sidebar">

      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="sidebar-logo-icon">🏛️</div>
        <div class="sidebar-logo-text">
          <div class="sidebar-logo-title">Civil Eng. Portal</div>
          <div class="sidebar-logo-sub">v${CONFIG.APP_VERSION}</div>
        </div>
      </div>

      <!-- User Info -->
      <div class="sidebar-user">
        <div class="sidebar-avatar">${userInit}</div>
        <div style="overflow:hidden;">
          <div class="sidebar-user-name">${session.name || 'User'}</div>
          <div class="sidebar-user-role">${userRole}</div>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <div class="nav-section">${role === 'instructor' ? 'Instructor Tools' : 'Student Menu'}</div>
        ${navHTML}
      </nav>

      <!-- Footer -->
      <div class="sidebar-footer">
        <a href="https://t.me/${CONFIG.TELEGRAM_BOT}" target="_blank" class="nav-item" style="color:rgba(255,255,255,.5);text-decoration:none;">
          <span class="nav-icon">✈️</span>
          <span class="nav-label">Telegram Bot</span>
        </a>
        <button class="nav-item" onclick="doLogout()" style="color:#f87171;margin-top:2px;">
          <span class="nav-icon">🚪</span>
          <span class="nav-label">Logout</span>
        </button>
      </div>
    </aside>

    <!-- ══ MAIN CONTENT ══ -->
    <div class="main-content" id="mainContent">

      <!-- Topbar -->
      <header class="topbar">
        <div class="topbar-left">
          <button class="hamburger" onclick="toggleSidebar()" aria-label="Menu">☰</button>
          <div>
            <div class="topbar-title">${activeLabel}</div>
            <div class="topbar-sub">${role === 'instructor' ? 'Instructor Portal' : 'Student Portal'}</div>
          </div>
        </div>
        <div class="topbar-right">
          <div class="topbar-date" id="topbarDate">${todayStr}</div>
          ${role === 'student' ? `
          <button class="btn btn-outline btn-sm" onclick="window.location.href='student-notifications.html'" title="Notifications">
            🔔
          </button>` : ''}
          <div class="topbar-avatar" onclick="toggleUserMenu()" title="${session.name}">
            ${userInit}
          </div>
        </div>
      </header>

      <!-- User dropdown menu -->
      <div class="user-menu" id="userMenu">
        <div class="user-menu-header">
          <div class="user-menu-avatar">${userInit}</div>
          <div>
            <div class="user-menu-name">${session.name}</div>
            <div class="user-menu-role">${userRole}</div>
          </div>
        </div>
        <div class="user-menu-divider"></div>
        <button class="user-menu-item" onclick="doLogout()">🚪 Logout</button>
      </div>

      <!-- Page Content -->
      <main class="page-content" id="pageContent">
        <!-- injected by each page -->
      </main>

    </div>
  ` + document.body.innerHTML;

  // Close user menu on outside click
  document.addEventListener('click', (e) => {
    const menu   = document.getElementById('userMenu');
    const avatar = document.querySelector('.topbar-avatar');
    if (menu && !menu.contains(e.target) && e.target !== avatar) {
      menu.classList.remove('show');
    }
  });
}

// ══ SIDEBAR CONTROLS ══════════════════════════════════════════
function toggleSidebar() {
  document.getElementById('sidebar')?.classList.toggle('open');
  document.getElementById('sidebarOverlay')?.classList.toggle('show');
}

function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebarOverlay')?.classList.remove('show');
}

// Close sidebar on nav click (mobile)
function navGo(href) {
  closeSidebar();
  window.location.href = href;
}

// ══ USER MENU ═════════════════════════════════════════════════
function toggleUserMenu() {
  document.getElementById('userMenu')?.classList.toggle('show');
}

// ══ LOGOUT ════════════════════════════════════════════════════
function doLogout() {
  Session.clear();
  Toast.info('Logged out.');
  setTimeout(() => window.location.href = 'index.html', 500);
}

// ══ INJECT PAGE CONTENT ═══════════════════════════════════════
// Call after renderLayout to set the page body
function setPageContent(html) {
  const pc = document.getElementById('pageContent');
  if (pc) {
    pc.innerHTML = html;
    pc.classList.add('page-section');
  }
}

// ══ LAYOUT CSS (injected once) ════════════════════════════════
(function injectLayoutStyles() {
  if (document.getElementById('layout-styles')) return;
  const style = document.createElement('style');
  style.id = 'layout-styles';
  style.textContent = `

    /* Topbar Avatar */
    .topbar-avatar {
      width: 34px; height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary-light), var(--accent));
      color: #fff;
      font-weight: 700;
      font-size: .82rem;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: var(--trans);
      flex-shrink: 0;
      user-select: none;
    }
    .topbar-avatar:hover {
      transform: scale(1.08);
      box-shadow: 0 2px 10px rgba(59,130,246,.4);
    }

    /* User Dropdown Menu */
    .user-menu {
      position: fixed;
      top: calc(var(--topbar-h) + 6px);
      right: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--r-md);
      box-shadow: var(--shadow-lg);
      z-index: 999;
      min-width: 200px;
      overflow: hidden;
      opacity: 0;
      pointer-events: none;
      transform: translateY(-8px) scale(.97);
      transition: all .18s var(--ease);
    }
    .user-menu.show {
      opacity: 1;
      pointer-events: all;
      transform: translateY(0) scale(1);
    }
    .user-menu-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 16px;
      background: var(--bg);
    }
    .user-menu-avatar {
      width: 36px; height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary-light), var(--accent));
      color: #fff;
      font-weight: 700;
      font-size: .85rem;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .user-menu-name { font-weight: 600; font-size: .86rem; }
    .user-menu-role { color: var(--text-muted); font-size: .72rem; }
    .user-menu-divider { height: 1px; background: var(--border); }
    .user-menu-item {
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 10px 16px;
      background: none;
      border: none;
      font-family: inherit;
      font-size: .84rem;
      color: var(--text);
      cursor: pointer;
      text-align: left;
      transition: var(--trans);
    }
    .user-menu-item:hover { background: var(--bg-hover); }
    .user-menu-item.danger { color: var(--danger); }
    .user-menu-item.danger:hover { background: var(--danger-light); }

    /* Nav label (hidden when collapsed) */
    .nav-label { flex: 1; }

    /* Sidebar scrollbar */
    .sidebar-nav { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.1) transparent; }

    /* Active nav item glow */
    .nav-item.active {
      background: var(--primary);
      box-shadow: 0 2px 12px rgba(59,130,246,.3);
    }

    /* Main content animation */
    #pageContent { animation: fadeUp .28s var(--ease); }

    /* Topbar shadow on scroll */
    .topbar.scrolled { box-shadow: var(--shadow-md); }

    /* Loading skeleton */
    .skeleton {
      background: linear-gradient(90deg, var(--bg) 25%, var(--border) 50%, var(--bg) 75%);
      background-size: 200% 100%;
      animation: shimmer 1.4s infinite;
      border-radius: var(--r-sm);
    }
    @keyframes shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    .skel-line { height: 14px; margin: 8px 0; }
    .skel-box  { height: 80px; margin: 8px 0; }

    /* Quick action buttons */
    .quick-actions {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px,1fr));
      gap: 10px;
    }
    .quick-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 16px 10px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--r-md);
      cursor: pointer;
      transition: var(--trans);
      font-family: inherit;
      font-size: .82rem;
      font-weight: 600;
      color: var(--text);
      text-align: center;
    }
    .quick-btn:hover {
      border-color: var(--primary-light);
      background: var(--primary-glow);
      color: var(--primary);
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }
    .quick-btn .qb-icon { font-size: 1.6rem; }

    /* Responsive adjustments */
    @media (max-width: 900px) {
      .user-menu { right: 12px; }
      .topbar-date { display: none; }
    }
  `;
  document.head.appendChild(style);
})();

// ══ TOPBAR SCROLL EFFECT ══════════════════════════════════════
window.addEventListener('scroll', () => {
  const topbar = document.querySelector('.topbar');
  if (topbar) topbar.classList.toggle('scrolled', window.scrollY > 10);
}, { passive: true });

// ══ SKELETON LOADER HELPER ════════════════════════════════════
function skeletonCard(lines = 3) {
  return `
    <div class="card">
      <div class="card-body">
        ${Array(lines).fill('<div class="skeleton skel-line"></div>').join('')}
        <div class="skeleton skel-box mt-12"></div>
      </div>
    </div>`;
}

function skeletonGrid(count = 4) {
  return `
    <div class="stats-grid">
      ${Array(count).fill(`
        <div class="stat-card">
          <div class="skeleton skel-line" style="width:40%;"></div>
          <div class="skeleton" style="height:32px;margin:8px 0;width:60%;"></div>
          <div class="skeleton skel-line" style="width:70%;"></div>
        </div>`).join('')}
    </div>`;
}

