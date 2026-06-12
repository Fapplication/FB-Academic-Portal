// ============================================================
// js/config.js — API Wrapper, Session, Utilities
// Civil Engineering Student Portal
// ============================================================

// ══ CONFIGURATION ════════════════════════════════════════════
const CONFIG = {
  // ⚠️ Replace with your deployed Google Apps Script Web App URL
  API_URL: 'https://script.google.com/macros/s/AKfycbyov_ffNcgMZYP_-fzlLfs9HiCl_XFud1vFbIMC_VmU_DHk0r6wemzzXYAN6EHhdjGZ-g/exec',

  // Telegram Bot
  TELEGRAM_BOT: 'FBResultPortalBot',

  // App Info
  APP_NAME:    'Civil Eng. Portal',
  APP_VERSION: '2.0.0',
};

// ══ API WRAPPER ═══════════════════════════════════════════════
const API = {

  async call(action, params = {}) {
    try {
      const allParams = { action, ...params };

      // Build query string — GAS works best with GET + query params
      const qs = Object.entries(allParams)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => {
          const val = typeof v === 'object' ? JSON.stringify(v) : String(v);
          return encodeURIComponent(k) + '=' + encodeURIComponent(val);
        })
        .join('&');

      const url = CONFIG.API_URL + '?' + qs;

      const res = await fetch(url, {
        method: 'GET',
        redirect: 'follow',
      });

      if (!res.ok) throw new Error('HTTP ' + res.status);

      const text = await res.text();

      // Guard against HTML error pages from GAS
      const trimmed = text.trim();
      if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
        console.error('Non-JSON from server:', trimmed.substring(0, 300));
        return {
          success: false,
          message: 'Server error. Check your Apps Script deployment settings.'
        };
      }

      return JSON.parse(trimmed);

    } catch (err) {
      console.error('API call failed:', err);

      if (err.message.includes('Failed to fetch') ||
          err.message.includes('NetworkError')) {
        return {
          success: false,
          message: 'Cannot reach the server. Make sure your Apps Script URL is correct in js/config.js and deployed as "Anyone" access.'
        };
      }

      return { success: false, message: 'Error: ' + err.message };
    }
  },

  // ── AUTH ───────────────────────────────────────────────────
  checkID: (studentId) =>
    API.call('checkAuthorizedID', { studentId }),

  sendOTP: (studentId, purpose = 'RESET') =>
    API.call('sendOTP', { studentId, purpose }),

  verifyOTP: (studentId, otp) =>
    API.call('verifyOTP', { studentId, otp }),

  register: (data) =>
    API.call('registerStudent', data),

  loginStudent: (studentId, password) =>
    API.call('loginStudent', { studentId, password }),

  loginInstructor: (username, password) =>
    API.call('loginInstructor', { username, password }),

  // ── STUDENT ────────────────────────────────────────────────
  // MODIFIED: Added courseId parameter to fetch marks from specific tabs dynamically
  getMarks: (studentId, courseId = '') =>
    API.call('getMarks', { studentId, courseId }),

  submitComplaint: (data) =>
    API.call('submitComplaint', data),

  getLectureNotes: (courseId = '') =>
    API.call('getLectureNotes', { courseId }),

  getOnlineTests: (courseId = '') =>
    API.call('getOnlineTests', { courseId }),

  submitTestResult: (data) =>
    API.call('submitTestResult', data),

  chatbot: (message, studentId) =>
    API.call('chatbot', { message, studentId }),

  getNotices: () =>
    API.call('getNotices'),

  // ── COURSES & ASSESSMENTS (dynamic) ───────────────────────
  getCourses: () =>
    API.call('getCourses'),

  getCourseAssessments: (courseId) =>
    API.call('getCourseAssessments', { courseId }),

  // ── INSTRUCTOR ─────────────────────────────────────────────
  getDashboard: () =>
    API.call('getDashboard'),

  getAllStudents: (courseId) =>
    API.call('getAllStudents', { courseId }),

  getStudentMarks: (courseId) =>
    API.call('getStudentMarks', { courseId }),

  updateMark: (data) =>
    API.call('updateMark', data),

  addCourse: (data) =>
    API.call('addCourse', data),

  updateCourse: (data) =>
    API.call('updateCourse', data),

  deleteCourse: (courseId) =>
    API.call('deleteCourse', { courseId }),

  addAssessment: (data) =>
    API.call('addAssessment', data),

  updateAssessment: (data) =>
    API.call('updateAssessment', data),

  deleteAssessment: (assessmentId) =>
    API.call('deleteAssessment', { assessmentId }),

  uploadQuestion: (data) =>
    API.call('uploadQuestion', data),

  deleteQuestion: (questionId) =>
    API.call('deleteQuestion', { questionId }),

  uploadLectureNote: (data) =>
    API.call('uploadLectureNote', data),

  deleteLectureNote: (noteId) =>
    API.call('deleteLectureNote', { noteId }),

  sendNotice: (data) =>
    API.call('sendNotice', data),

  getComplaints: () =>
    API.call('getComplaints'),

  resolveComplaint: (data) =>
    API.call('resolveComplaint', data),

  getAuthorizedIDs: () =>
    API.call('getAuthorizedIDs'),

  addAuthorizedID: (data) =>
    API.call('addAuthorizedID', data),

  getTestResults: (courseId) =>
    API.call('getTestResults', { courseId }),
};

// ══ SESSION MANAGER ═══════════════════════════════════════════
const Session = {
  _key: 'cep_session',

  get() {
    try {
      return JSON.parse(localStorage.getItem(this._key) || 'null');
    } catch { return null; }
  },

  set(data) {
    localStorage.setItem(this._key, JSON.stringify({
      ...data,
      _ts: Date.now()
    }));
  },

  clear() {
    localStorage.removeItem(this._key);
  },

  isStudent() {
    const s = this.get();
    return s && s.role === 'student';
  },

  isInstructor() {
    const s = this.get();
    return s && s.role === 'instructor';
  },

  requireStudent() {
    const s = this.get();
    if (!s || s.role !== 'student') {
      window.location.href = 'index.html';
      return null;
    }
    // Session timeout: 8 hours
    if (Date.now() - s._ts > 8 * 60 * 60 * 1000) {
      this.clear();
      window.location.href = 'index.html';
      return null;
    }
    return s;
  },

  requireInstructor() {
    const s = this.get();
    if (!s || s.role !== 'instructor') {
      window.location.href = 'index.html';
      return null;
    }
    if (Date.now() - s._ts > 8 * 60 * 60 * 1000) {
      this.clear();
      window.location.href = 'index.html';
      return null;
    }
    return s;
  },

  refresh() {
    const s = this.get();
    if (s) this.set(s);
  }
};

// ══ TOAST NOTIFICATIONS ════════════════════════════════════════
const Toast = {
  _container: null,

  _getContainer() {
    if (!this._container) {
      this._container = document.createElement('div');
      this._container.className = 'toast-container';
      document.body.appendChild(this._container);
    }
    return this._container;
  },

  show(message, type = 'info', duration = 3500) {
    const container = this._getContainer();
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ'}</span>
      <span>${message}</span>
    `;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('show'));
    });

    // Animate out
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 400);
    }, duration);
  },

  success: (m, d) => Toast.show(m, 'success', d),
  error:   (m, d) => Toast.show(m, 'error',    d),
  warning: (m, d) => Toast.show(m, 'warning', d),
  info:    (m, d) => Toast.show(m, 'info',     d),
};

// ══ LOADER (button loading state) ══════════════════════════════
const Loader = {
  show(el, text = 'Loading...') {
    if (!el) return;
    el._orig     = el.innerHTML;
    el._disabled = el.disabled;
    el.disabled  = true;
    el.innerHTML = `<span class="spinner"></span>${text}`;
  },

  hide(el) {
    if (!el || el._orig === undefined) return;
    el.innerHTML = el._orig;
    el.disabled  = el._disabled || false;
    delete el._orig;
    delete el._disabled;
  }
};

// ══ GRADE UTILITIES ════════════════════════════════════════════
const Grade = {
  // Get letter grade + color from percentage score
  getLetter(pct) {
    if (pct >= 90) return { letter: 'A+', color: '#10b981', bg: '#d1fae5' };
    if (pct >= 85) return { letter: 'A',  color: '#10b981', bg: '#d1fae5' };
    if (pct >= 80) return { letter: 'A-', color: '#10b981', bg: '#d1fae5' };
    if (pct >= 75) return { letter: 'B+', color: '#3b82f6', bg: '#dbeafe' };
    if (pct >= 70) return { letter: 'B',  color: '#3b82f6', bg: '#dbeafe' };
    if (pct >= 65) return { letter: 'B-', color: '#3b82f6', bg: '#dbeafe' };
    if (pct >= 60) return { letter: 'C+', color: '#f59e0b', bg: '#fef3c7' };
    if (pct >= 55) return { letter: 'C',  color: '#f59e0b', bg: '#fef3c7' };
    if (pct >= 50) return { letter: 'C-', color: '#f59e0b', bg: '#fef3c7' };
    if (pct >= 45) return { letter: 'D',  color: '#f97316', bg: '#ffedd5' };
    return         { letter: 'F',  color: '#ef4444', bg: '#fee2e2' };
  },

  // Calculate weighted total from marks array
  // marks: [{score, maxScore, weight}, ...]
  calcWeighted(marks) {
    let total = 0;
    let totalWeight = 0;
    marks.forEach(m => {
      if (m.score !== null && m.score !== '' && m.maxScore > 0) {
        const pct = (Number(m.score) / Number(m.maxScore)) * 100;
        total += pct * (Number(m.weight) / 100);
        totalWeight += Number(m.weight);
      }
    });
    return totalWeight > 0 ? (total / totalWeight * totalWeight / 100).toFixed(1) : 0;
  },

  // Simple sum of (score/maxScore * weight)
  calcTotal(marks) {
    return marks.reduce((sum, m) => {
      if (m.score !== null && m.score !== '') {
        return sum + (Number(m.score) / Number(m.maxScore)) * Number(m.weight);
      }
      return sum;
    }, 0).toFixed(1);
  }
};

// ══ DATE UTILITIES ═════════════════════════════════════════════
const DateUtil = {
  format(dateStr) {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('en-ET', {
        year: 'numeric', month: 'short', day: 'numeric'
      });
    } catch { return dateStr; }
  },

  formatFull(dateStr) {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleString('en-ET', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return dateStr; }
  },

  now() {
    return new Date().toISOString();
  },

  today() {
    return new Date().toLocaleDateString('en-ET', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
  }
};

// ══ DOM UTILITIES ══════════════════════════════════════════════
const DOM = {
  // Get element by id
  id: (id) => document.getElementById(id),

  // Set innerHTML safely
  html(id, content) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = content;
  },

  // Show/hide elements
  show(id) { const el = document.getElementById(id); if (el) el.classList.remove('hidden'); },
  hide(id) { const el = document.getElementById(id); if (el) el.classList.add('hidden'); },

  // Toggle active tab
  activateTab(tabId, paneId, tabGroup, paneGroup) {
    document.querySelectorAll(tabGroup).forEach(t => t.classList.remove('active'));
    document.querySelectorAll(paneGroup).forEach(p => p.classList.remove('active'));
    document.getElementById(tabId)?.classList.add('active');
    document.getElementById(paneId)?.classList.add('active');
  },

  // Confirm dialog
  confirm(msg) {
    return window.confirm(msg);
  }
};

// ══ PROGRESS BAR HELPER ═════════════════════════════════════════
function progressBar(pct, color) {
  const c = color || (pct >= 70 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444');
  return `
    <div class="progress">
      <div class="progress-bar" style="width:${Math.min(pct,100)}%;background:${c};"></div>
    </div>`;
}

// ══ MODAL HELPERS ══════════════════════════════════════════════
function openModal(id) {
  document.getElementById(id)?.classList.add('show');
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('show');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('show');
  }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.show').forEach(m => m.classList.remove('show'));
  }
});

// ══ NUMBER FORMATTER ═══════════════════════════════════════════
function fmt(n, dec = 1) {
  return Number(n || 0).toFixed(dec);
}

// ══ INITIALS FROM NAME ═════════════════════════════════════════
function initials(name) {
  return (name || 'U')
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

// ══ DEBOUNCE ═══════════════════════════════════════════════════
function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// ══ COPY TO CLIPBOARD ══════════════════════════════════════════
async function copyToClipboard(text, successMsg = 'Copied!') {
  try {
    await navigator.clipboard.writeText(text);
    Toast.success(successMsg);
  } catch {
    Toast.error('Copy failed. Please copy manually.');
  }
}
