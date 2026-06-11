# ============================================================
# telegram-bot.py — Civil Engineering Student Portal Bot
# Connects to Google Sheets via Apps Script Web App API
# Deploy on Railway.app
# ============================================================

import os
import json
import logging
import aiohttp
from urllib.parse import urlencode
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get('BOT_TOKEN',  '8775466330:AAEEuQmHmynlKrn6O-FuyX5WDNFiT-5eSxA')
API_URL    = os.environ.get('API_URL',    'https://script.google.com/macros/s/AKfycbyov_ffNcgMZYP_-fzlLfs9HiCl_XFud1vFbIMC_VmU_DHk0r6wemzzXYAN6EHhdjGZ-g/exec')
ADMIN_ID   = int(os.environ.get('ADMIN_ID', '0'))
PORTAL_URL = os.environ.get('PORTAL_URL', 'https://github.com/Fapplication/FB-Academic-Portal/')

# ════════════════════════════════════════════════════════════
# HTTP SESSION  (one shared session for the whole process)
# ════════════════════════════════════════════════════════════
_http_session: aiohttp.ClientSession | None = None

async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session

async def api_call(action: str, params: dict = {}) -> dict:
    safe = {k: v for k, v in params.items() if v is not None}
    url  = f"{API_URL}?{urlencode({'action': action, **safe})}"
    try:
        session = await get_http_session()
        async with session.get(url, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            return json.loads(await resp.text())
    except Exception as e:
        logger.error(f"API [{action}] error: {e}")
        return {'success': False, 'message': str(e)}

# ════════════════════════════════════════════════════════════
# SESSION STATE  (in-memory per chat_id)
# ════════════════════════════════════════════════════════════
user_states: dict = {}

def get_state(chat_id: int) -> dict:
    if chat_id not in user_states:
        user_states[chat_id] = {'step': 'idle', 'studentId': None, 'name': '', 'data': {}}
    return user_states[chat_id]

def set_state(chat_id: int, step: str, **kwargs):
    s = get_state(chat_id)
    s['step'] = step
    s.update(kwargs)

def clear_state(chat_id: int):
    user_states[chat_id] = {'step': 'idle', 'studentId': None, 'name': '', 'data': {}}

# ════════════════════════════════════════════════════════════
# KEYBOARDS
# ════════════════════════════════════════════════════════════
def main_keyboard(linked: bool = True) -> ReplyKeyboardMarkup:
    if linked:
        rows = [
            [KeyboardButton('📊 My Marks'),     KeyboardButton('📣 Notices')],
            [KeyboardButton('📝 Online Tests'),  KeyboardButton('📚 Lecture Notes')],
            [KeyboardButton('📬 My Complaints'), KeyboardButton('🤖 Ask Chatbot')],
            [KeyboardButton('🔗 Portal Link'),   KeyboardButton('👤 My Profile')],
        ]
    else:
        rows = [
            [KeyboardButton('🔗 Link My Account')],
            [KeyboardButton('🔗 Portal Link')],
        ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def course_keyboard(courses: list, mode: str) -> InlineKeyboardMarkup:
    """mode = 'test' or 'notes' — encoded into callback so handler knows where to route."""
    rows = [
        [InlineKeyboardButton(c['courseName'], callback_data=f"course_{mode}_{c['courseId']}")]
        for c in courses
    ]
    rows.append([InlineKeyboardButton('← Back', callback_data='back_main')])
    return InlineKeyboardMarkup(rows)

def back_keyboard(label: str = '← Back to Menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data='back_main')]])

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📊 Dashboard',        callback_data='adm_dashboard')],
        [InlineKeyboardButton('👥 View Students',    callback_data='adm_students'),
         InlineKeyboardButton('➕ Add Student',      callback_data='adm_add_id')],
        [InlineKeyboardButton('🗑 Remove Student',   callback_data='adm_remove_id'),
         InlineKeyboardButton('📣 Send Notice',      callback_data='adm_notice')],
        [InlineKeyboardButton('📬 Complaints',       callback_data='adm_complaints'),
         InlineKeyboardButton('📈 Test Results',     callback_data='adm_test_results')],
        [InlineKeyboardButton('✖ Close',             callback_data='adm_close')],
    ])

# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════
def grade_letter(pct: float) -> str:
    if pct >= 90: return 'A+'
    if pct >= 85: return 'A'
    if pct >= 80: return 'A-'
    if pct >= 75: return 'B+'
    if pct >= 70: return 'B'
    if pct >= 65: return 'B-'
    if pct >= 60: return 'C+'
    if pct >= 55: return 'C'
    if pct >= 50: return 'C-'
    if pct >= 45: return 'D'
    return 'F'

def safe(text: str, limit: int = 200) -> str:
    text = str(text or '')
    return text[:limit] + ('…' if len(text) > limit else '')

# ════════════════════════════════════════════════════════════
# /start  /help
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id   = update.effective_chat.id
    state     = get_state(chat_id)
    is_linked = bool(state.get('studentId'))
    name      = update.effective_user.first_name

    await update.message.reply_text(
        f"👋 *Welcome, {name}!*\n\n"
        f"{'✅ Account linked: ' + state['studentId'] if is_linked else '🔗 No account linked yet.'}\n\n"
        f"📌 *What I can do:*\n"
        f"• 📊 View marks & grades\n"
        f"• 📣 Receive instant notices\n"
        f"• 📝 Take online tests\n"
        f"• 📚 Download lecture notes\n"
        f"• 📬 Track complaints\n"
        f"• 🤖 Chatbot assistant\n\n"
        f"{'Use the menu below.' if is_linked else 'Tap *Link My Account* or use /login.'}",
        parse_mode='Markdown',
        reply_markup=main_keyboard(is_linked)
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Commands*\n\n"
        "👤 *Account*\n"
        "/login — Log in with Student ID & password\n"
        "/logout — Log out\n"
        "/reset — Reset password via OTP\n"
        "/link — Link account (no password)\n"
        "/profile — View your profile\n\n"
        "📚 *Student*\n"
        "/marks — Your marks\n"
        "/notices — Latest notices\n"
        "/tests — Online tests\n"
        "/notes — Lecture notes\n"
        "/complaints — Your complaints\n\n"
        "🛡 *Admin only*\n"
        "/admin — Admin panel\n",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# LOGIN
# ════════════════════════════════════════════════════════════
async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    if state.get('studentId'):
        await update.message.reply_text(
            f"✅ Already logged in as `{state['studentId']}`.\nUse /logout to switch accounts.",
            parse_mode='Markdown', reply_markup=main_keyboard(True)
        )
        return
    set_state(chat_id, 'login_id')
    await update.message.reply_text(
        "🔐 *Login*\n\nEnter your *Student ID*:", parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# LOGOUT
# ════════════════════════════════════════════════════════════
async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    sid     = state.get('studentId')
    if not sid:
        await update.message.reply_text("ℹ️ You are not logged in.", reply_markup=main_keyboard(False))
        return
    await api_call('saveBotSession', {'chatId': chat_id, 'studentId': sid, 'status': 'unlinked'})
    clear_state(chat_id)
    await update.message.reply_text(
        "👋 *Logged out.* Account unlinked.\nUse /login to log in again.",
        parse_mode='Markdown', reply_markup=main_keyboard(False)
    )

# ════════════════════════════════════════════════════════════
# PASSWORD RESET
# ════════════════════════════════════════════════════════════
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'reset_id')
    await update.message.reply_text(
        "🔑 *Reset Password*\n\nEnter your *Student ID*:", parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# LINK (no password — just validates authorized ID)
# ════════════════════════════════════════════════════════════
async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'link_id')
    await update.message.reply_text(
        "🔗 *Link Account*\n\nEnter your *Student ID* (e.g. ETS0001/14):",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# MARKS
# ════════════════════════════════════════════════════════════
async def cmd_marks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    sid     = state.get('studentId')
    if not sid:
        await update.message.reply_text("❌ Log in first. Use /login.", reply_markup=main_keyboard(False))
        return
    msg = await update.message.reply_text("📊 Loading marks…")
    res = await api_call('getMarks', {'studentId': sid})
    if not res.get('success') or not res.get('marks'):
        await msg.edit_text("📊 No marks available yet.")
        return
    reply = "📊 *Your Marks*\n\n"
    for m in res['marks']:
        total = float(m.get('weightedTotal', 0))
        status = m.get('status', 'Pending')
        icon   = '✅' if status == 'Accepted' else '⚠️' if status == 'Complained' else '⏳'
        reply += f"*{m.get('courseName','—')}* ({m.get('courseCode','—')}) {icon}\n"
        for a in m.get('assessments', []):
            sc = a.get('score')
            reply += f"  • {a['name']} ({a.get('weight',0)}%): "
            reply += f"{sc}/{a.get('maxScore','?')}\n" if sc is not None else "—\n"
        reply += f"📈 *Total: {total}% — {grade_letter(total)}*\n\n"
    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

# ════════════════════════════════════════════════════════════
# NOTICES
# ════════════════════════════════════════════════════════════
async def cmd_notices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📣 Loading notices…")
    res = await api_call('getNotices')
    notices = res.get('notices', [])
    if not notices:
        await msg.edit_text("📣 No notices yet.")
        return
    reply = "📣 *Latest Notices*\n\n"
    icons = {'Exam':'📝','Assignment':'📋','Holiday':'🎉','Result':'📊','Urgent':'🚨'}
    for n in list(reversed(notices))[:5]:
        title = n.get('Title', n.get('title', 'Notice'))
        body  = n.get('Message', n.get('message', ''))
        ts    = str(n.get('Timestamp', n.get('timestamp', '')))[:10]
        cat   = n.get('Category', n.get('category', ''))
        reply += f"{icons.get(cat,'📢')} *{title}*"
        if ts: reply += f"  _{ts}_"
        reply += f"\n{safe(body, 200)}\n\n"
    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

# ════════════════════════════════════════════════════════════
# ONLINE TESTS
# ════════════════════════════════════════════════════════════
async def cmd_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not get_state(chat_id).get('studentId'):
        await update.message.reply_text("❌ Log in first. Use /login.", reply_markup=main_keyboard(False))
        return
    msg = await update.message.reply_text("📝 Loading courses…")
    res = await api_call('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📝 No courses available.")
        return
    await msg.edit_text(
        "📝 *Online Tests*\n\nPick a course:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses, 'test')
    )

async def _load_test(query, context, course_id: str):
    chat_id = query.message.chat_id
    await query.edit_message_text("📝 Loading questions…")
    res       = await api_call('getOnlineTests', {'courseId': course_id})
    questions = res.get('questions', [])
    if not questions:
        await query.edit_message_text("📭 No questions for this course yet.", reply_markup=back_keyboard())
        return
    set_state(chat_id, 'test_answering',
              test_questions=questions, test_course_id=course_id,
              test_current=0, test_answers={})
    await _send_question(query, context, is_callback=True)

async def _send_question(source, context, is_callback: bool = False):
    if is_callback:
        chat_id = source.message.chat_id
    else:
        chat_id = source.effective_chat.id
    state     = get_state(chat_id)
    questions = state.get('test_questions', [])
    current   = state.get('test_current', 0)
    if current >= len(questions):
        await _finish_test(source, context, is_callback)
        return
    q     = questions[current]
    total = len(questions)
    text  = (
        f"📝 *Q{current+1}/{total}*  (answered: {len(state.get('test_answers',{}))})\n\n"
        f"{q['question']}\n\n"
        f"🅰 {q['optionA']}\n🅱 {q['optionB']}\n🅲 {q['optionC']}\n🅳 {q['optionD']}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('A', callback_data='ans_A'),
         InlineKeyboardButton('B', callback_data='ans_B')],
        [InlineKeyboardButton('C', callback_data='ans_C'),
         InlineKeyboardButton('D', callback_data='ans_D')],
        [InlineKeyboardButton('⏭ Skip', callback_data='ans_skip'),
         InlineKeyboardButton('📤 Submit', callback_data='test_submit')],
    ])
    if is_callback:
        await source.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)
    else:
        await source.message.reply_text(text, parse_mode='Markdown', reply_markup=kb)

async def _finish_test(source, context, is_callback: bool = False):
    if is_callback:
        chat_id = source.message.chat_id
    else:
        chat_id = source.effective_chat.id
    state     = get_state(chat_id)
    answers   = state.get('test_answers', {})
    questions = state.get('test_questions', [])
    course_id = state.get('test_course_id', '')
    sid       = state.get('studentId', '')
    answered  = len(answers)
    total     = len(questions)
    pct       = round(answered / total * 100) if total else 0
    await api_call('submitTestResult', {
        'studentId': sid, 'courseId': course_id,
        'score': answered, 'total': total, 'answers': json.dumps(answers)
    })
    set_state(chat_id, 'idle')
    text = (
        f"🎉 *Test Submitted!*\n\n"
        f"Answered: {answered}/{total}\n"
        f"Score: {pct}%  —  {grade_letter(pct)}\n\n"
        f"Your instructor will review the results."
    )
    if is_callback:
        await source.edit_message_text(text, parse_mode='Markdown', reply_markup=back_keyboard())
    else:
        await source.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard(True))

# ════════════════════════════════════════════════════════════
# LECTURE NOTES
# ════════════════════════════════════════════════════════════
async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📚 Loading courses…")
    res = await api_call('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📚 No courses available.")
        return
    await msg.edit_text(
        "📚 *Lecture Notes*\n\nPick a course:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses, 'notes')
    )

async def _load_notes(query, context, course_id: str):
    await query.edit_message_text("📚 Loading notes…")
    res   = await api_call('getLectureNotes', {'courseId': course_id})
    notes = res.get('notes', [])
    if not notes:
        await query.edit_message_text("📭 No notes uploaded yet.", reply_markup=back_keyboard())
        return
    icons = {'PDF':'📄','Word':'📝','PPT':'📊','Video':'🎥','Link':'🔗'}
    reply = "📚 *Lecture Notes*\n\n"
    for n in notes[:10]:
        title = n.get('Topic_Title', n.get('topicTitle', 'Untitled'))
        url   = n.get('Resource_URL', n.get('resourceUrl', ''))
        ftype = n.get('FileType', n.get('fileType', 'File'))
        reply += f"{icons.get(ftype,'📁')} [{title}]({url})\n"
    await query.edit_message_text(
        reply, parse_mode='Markdown',
        reply_markup=back_keyboard(),
        disable_web_page_preview=True
    )

# ════════════════════════════════════════════════════════════
# COMPLAINTS
# ════════════════════════════════════════════════════════════
async def cmd_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sid     = get_state(chat_id).get('studentId')
    if not sid:
        await update.message.reply_text("❌ Log in first. Use /login.", reply_markup=main_keyboard(False))
        return
    msg = await update.message.reply_text("📬 Loading complaints…")
    res = await api_call('getComplaints')
    mine = [c for c in res.get('complaints', [])
            if str(c.get('StudentID', c.get('studentId',''))).strip() == str(sid).strip()]
    if not mine:
        await msg.edit_text(
            "📬 No complaints on record.\n\nRaise one via the portal → My Marks → Raise Complaint.",
            reply_markup=back_keyboard()
        )
        return
    reply = "📬 *Your Complaints*\n\n"
    icons = {'Pending':'⏳','Resolved':'✅','Rejected':'❌','Accepted':'👍'}
    for c in reversed(mine[-5:]):
        status   = c.get('Status', c.get('status','Pending'))
        course   = c.get('Course_ID', c.get('courseId','—'))
        ctype    = c.get('Type', c.get('type','—'))
        response = c.get('Response', c.get('response',''))
        ts       = str(c.get('Timestamp', c.get('timestamp','')))[:10]
        reply   += f"{icons.get(status,'⏳')} *{status}* — {ctype}\n"
        reply   += f"📚 {course}  📅 {ts}\n"
        if response: reply += f"💬 {safe(response, 100)}\n"
        reply   += "\n"
    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

# ════════════════════════════════════════════════════════════
# CHATBOT
# ════════════════════════════════════════════════════════════
async def cmd_chatbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'chatbot')
    await update.message.reply_text(
        "🤖 *Chatbot*\n\nAsk me about marks, tests, notes, complaints, or account issues.\n"
        "_Send /start to exit._",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# PROFILE  /  PORTAL LINK
# ════════════════════════════════════════════════════════════
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    user    = update.effective_user
    if not state.get('studentId'):
        await update.message.reply_text(
            "❌ No account linked.\nUse /login or /link.",
            parse_mode='Markdown', reply_markup=main_keyboard(False)
        )
        return
    await update.message.reply_text(
        f"👤 *Profile*\n\n"
        f"🆔 `{state['studentId']}`\n"
        f"👤 {state.get('name','—')}\n"
        f"📱 @{user.username or '—'}\n"
        f"🔗 Status: ✅ Linked\n\n"
        f"[Open Portal]({PORTAL_URL})",
        parse_mode='Markdown', reply_markup=back_keyboard()
    )

async def show_portal_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔗 *Student Portal*\n\n{PORTAL_URL}\n\nLogin with your Student ID and password.",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# ADMIN PANEL
# ════════════════════════════════════════════════════════════
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    await update.message.reply_text(
        "🛡 *Admin Panel*", parse_mode='Markdown',
        reply_markup=admin_menu_keyboard()
    )

# ════════════════════════════════════════════════════════════
# CALLBACK HANDLER  (all inline button presses)
# ════════════════════════════════════════════════════════════
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    await query.answer()

    # ── Back to main ─────────────────────────────────────────
    if data == 'back_main':
        is_linked = bool(state.get('studentId'))
        await query.edit_message_text("🏠 Main Menu")
        await context.bot.send_message(
            chat_id=chat_id, text="Use the menu below:",
            reply_markup=main_keyboard(is_linked)
        )
        return

    # ── Course selected for TESTS ─────────────────────────────
    if data.startswith('course_test_'):
        course_id = data[len('course_test_'):]
        await _load_test(query, context, course_id)
        return

    # ── Course selected for NOTES ─────────────────────────────
    if data.startswith('course_notes_'):
        course_id = data[len('course_notes_'):]
        await _load_notes(query, context, course_id)
        return

    # ── Test answer buttons ───────────────────────────────────
    if data.startswith('ans_'):
        answer = data[4:]
        if answer == 'skip':
            state['test_current'] = state.get('test_current', 0) + 1
            await _send_question(query, context, is_callback=True)
        elif answer in ('A', 'B', 'C', 'D'):
            current = state.get('test_current', 0)
            state.setdefault('test_answers', {})[current] = answer
            state['test_current'] = current + 1
            await _send_question(query, context, is_callback=True)
        return

    if data == 'test_submit':
        await _finish_test(query, context, is_callback=True)
        return

    # ── ADMIN callbacks ───────────────────────────────────────
    if data.startswith('adm_'):
        if update.effective_user.id != ADMIN_ID:
            await query.answer("❌ Admin only.", show_alert=True)
            return
        await _handle_admin_callback(query, context, data, chat_id, state)
        return

async def _handle_admin_callback(query, context, data: str, chat_id: int, state: dict):
    """All adm_ callbacks routed here."""

    if data == 'adm_close':
        await query.edit_message_text("🛡 Admin panel closed.")
        return

    if data == 'adm_back':
        await query.edit_message_text(
            "🛡 *Admin Panel*", parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )
        return

    # Dashboard
    if data == 'adm_dashboard':
        await query.edit_message_text("⏳ Loading…")
        res    = await api_call('getDashboard')
        linked = len([s for s in user_states.values() if s.get('studentId')])
        text   = (
            f"📊 *Dashboard*\n\n"
            f"👥 Authorized Students: {res.get('totalStudents','—')}\n"
            f"📚 Total Assessments:   {res.get('totalAssessments','—')}\n"
            f"📬 Pending Complaints:  {res.get('pendingComplaints','—')}\n"
            f"📈 Avg Score:           {res.get('avgScore','—')}%\n"
            f"📱 Active Bot Sessions: {linked}\n\n*Courses:*\n"
        )
        for c in res.get('courses', []):
            text += f"• {c.get('courseName','—')} (`{c.get('courseCode','—')}`)"
            text += f"  avg {c.get('avgScore','—')}%\n"
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
        )
        return

    # View students
    if data == 'adm_students':
        await query.edit_message_text("⏳ Loading…")
        res  = await api_call('getAuthorizedIDs')
        ids  = res.get('ids', [])
        text = f"👥 *Authorized Students* ({len(ids)})\n\n"
        for s in ids[:30]:
            text += f"• `{s.get('ID','')}` — {s.get('Name','—')}\n"
        if len(ids) > 30:
            text += f"\n_…and {len(ids)-30} more._"
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
        )
        return

    # Add student
    if data == 'adm_add_id':
        set_state(chat_id, 'admin_add_id')
        await query.edit_message_text(
            "➕ *Add Student*\n\nSend details as:\n"
            "`StudentID | Full Name | Email`\n\n"
            "Example: `ETS0050/14 | Abebe Bekele | a@b.com`\n\n"
            "_/admin to cancel_",
            parse_mode='Markdown'
        )
        return

    # Remove student
    if data == 'adm_remove_id':
        set_state(chat_id, 'admin_remove_id')
        await query.edit_message_text(
            "🗑 *Remove Student*\n\nSend the Student ID to remove:\n"
            "`ETS0050/14`\n\n_/admin to cancel_",
            parse_mode='Markdown'
        )
        return

    # Send notice
    if data == 'adm_notice':
        set_state(chat_id, 'admin_notice')
        await query.edit_message_text(
            "📣 *Send Notice*\n\nFormat:\n"
            "`Title | Message | Category`\n\n"
            "Categories: Exam, Assignment, Holiday, Result, Urgent, General\n\n"
            "Example: `Exam Schedule | Mid exam starts Monday | Exam`\n\n"
            "_/admin to cancel_",
            parse_mode='Markdown'
        )
        return

    # Complaints
    if data == 'adm_complaints':
        await query.edit_message_text("⏳ Loading…")
        res     = await api_call('getComplaints')
        pending = [c for c in res.get('complaints', [])
                   if (c.get('Status') or c.get('status','')) == 'Pending']
        if not pending:
            await query.edit_message_text(
                "✅ No pending complaints.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
            )
            return
        state['pending_complaints'] = pending
        state['complaint_index']    = 0
        await _show_complaint(query, state)
        return

    if data == 'adm_complaint_next':
        state['complaint_index'] = state.get('complaint_index', 0) + 1
        await _show_complaint(query, state)
        return

    if data == 'adm_complaint_resolve':
        set_state(chat_id, 'admin_resolve_complaint')
        c = state.get('pending_complaints', [])[state.get('complaint_index', 0)]
        state['resolving_complaint'] = c
        await query.edit_message_text(
            f"✅ Resolving complaint from `{c.get('StudentID','')}`\n\n"
            f"Type your response (or `skip`):",
            parse_mode='Markdown'
        )
        return

    if data == 'adm_complaint_reject':
        c   = state.get('pending_complaints', [])[state.get('complaint_index', 0)]
        res = await api_call('resolveComplaint', {
            'studentId': c.get('StudentID',''),
            'timestamp': c.get('Timestamp',''),
            'status':    'Rejected',
            'response':  'Your complaint has been reviewed and rejected.'
        })
        msg = "❌ Complaint rejected and student notified." if res.get('success') else f"⚠️ {res.get('message')}"
        await query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
        )
        return

    # Test results
    if data == 'adm_test_results':
        await query.edit_message_text("⏳ Loading…")
        res     = await api_call('getTestResults')
        results = res.get('results', [])
        if not results:
            await query.edit_message_text(
                "📭 No test results yet.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
            )
            return
        text = f"📈 *Test Results* (last {min(10,len(results))} of {len(results)})\n\n"
        for r in results[-10:]:
            sid   = r.get('StudentID', r.get('studentId','—'))
            cid   = r.get('Course_ID', r.get('courseId','—'))
            sc    = r.get('Score', r.get('score','—'))
            tot   = r.get('Total', r.get('total','—'))
            ts    = str(r.get('Timestamp', r.get('timestamp','')))[:10]
            text += f"• `{sid}` | {cid} | {sc}/{tot} | {ts}\n"
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
        )
        return

async def _show_complaint(query, state: dict):
    pending = state.get('pending_complaints', [])
    idx     = state.get('complaint_index', 0)
    if idx >= len(pending):
        await query.edit_message_text(
            "✅ All complaints reviewed.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='adm_back')]])
        )
        return
    c    = pending[idx]
    text = (
        f"📬 *Complaint {idx+1}/{len(pending)}*\n\n"
        f"👤 `{c.get('StudentID','—')}`\n"
        f"📚 {c.get('Course_ID','—')}\n"
        f"🔖 {c.get('Type','—')}\n"
        f"📅 {str(c.get('Timestamp',''))[:10]}\n\n"
        f"💬 _{safe(c.get('Message',''),300)}_"
    )
    rows = [
        [InlineKeyboardButton('✅ Resolve', callback_data='adm_complaint_resolve'),
         InlineKeyboardButton('❌ Reject',  callback_data='adm_complaint_reject')],
    ]
    if idx + 1 < len(pending):
        rows.append([InlineKeyboardButton('⏭ Next complaint', callback_data='adm_complaint_next')])
    rows.append([InlineKeyboardButton('← Back', callback_data='adm_back')])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(rows))

# ════════════════════════════════════════════════════════════
# MESSAGE HANDLER  — single unified dispatcher
# ════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text    = (update.message.text or '').strip()
    state   = get_state(chat_id)
    step    = state.get('step', 'idle')

    # ══ Step-based flows ════════════════════════════════════

    # Login: waiting for student ID
    if step == 'login_id':
        set_state(chat_id, 'login_pw', pending_id=text)
        await update.message.reply_text(
            f"🔐 ID: `{text}`\n\nNow enter your *password*:", parse_mode='Markdown'
        )
        return

    # Login: waiting for password
    if step == 'login_pw':
        pending_id = state.get('pending_id', '')
        msg = await update.message.reply_text("⏳ Verifying…")
        res = await api_call('loginStudent', {'studentId': pending_id, 'password': text})
        if res.get('success'):
            await api_call('saveBotSession', {'chatId': chat_id, 'studentId': pending_id, 'status': 'linked'})
            set_state(chat_id, 'idle', studentId=pending_id, name=res.get('name', ''))
            await msg.edit_text(
                f"✅ *Welcome back, {res.get('name')}!*\n🆔 `{pending_id}`",
                parse_mode='Markdown'
            )
            await update.message.reply_text("Main menu:", reply_markup=main_keyboard(True))
        else:
            set_state(chat_id, 'idle')
            await msg.edit_text(
                f"❌ {res.get('message','Invalid credentials.')}\n\nUse /login to try again.",
                parse_mode='Markdown', reply_markup=main_keyboard(False)
            )
        return

    # Link account: waiting for student ID
    if step == 'link_id':
        msg = await update.message.reply_text("🔍 Checking ID…")
        res = await api_call('checkAuthorizedID', {'studentId': text})
        if res.get('success'):
            await api_call('saveBotSession', {'chatId': chat_id, 'studentId': text, 'status': 'linked'})
            set_state(chat_id, 'idle', studentId=text, name=res.get('name',''))
            await msg.edit_text(
                f"✅ *Linked!* Welcome, *{res.get('name')}*!", parse_mode='Markdown'
            )
            await update.message.reply_text("Main menu:", reply_markup=main_keyboard(True))
        else:
            set_state(chat_id, 'idle')
            await msg.edit_text(
                f"❌ {res.get('message','ID not found.')}\n\nTry again with /link.",
                parse_mode='Markdown', reply_markup=main_keyboard(False)
            )
        return

    # Password reset: waiting for student ID
    if step == 'reset_id':
        msg = await update.message.reply_text("⏳ Sending OTP…")
        res = await api_call('sendOTP', {'studentId': text, 'purpose': 'RESET'})
        if res.get('success'):
            set_state(chat_id, 'reset_otp', reset_id=text)
            via     = res.get('sentVia','')
            contact = res.get('contact','')
            await msg.edit_text(
                f"📨 OTP sent via *{via}*{' to ' + contact if contact else ''}.\n\n"
                f"Enter the *6-digit OTP*:", parse_mode='Markdown'
            )
        else:
            set_state(chat_id, 'idle')
            await msg.edit_text(
                f"❌ {res.get('message','Failed.')}\n\nUse /reset to try again.",
                parse_mode='Markdown'
            )
        return

    # Password reset: waiting for OTP
    if step == 'reset_otp':
        reset_id = state.get('reset_id', '')
        res = await api_call('verifyOTP', {'studentId': reset_id, 'otp': text})
        if res.get('success'):
            set_state(chat_id, 'reset_newpw', reset_id=reset_id, verified_otp=text)
            await update.message.reply_text(
                "✅ OTP verified!\n\nEnter your *new password* (min 6 chars):",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ {res.get('message','Invalid OTP.')}\n\nTry again or use /reset.",
                parse_mode='Markdown'
            )
        return

    # Password reset: waiting for new password
    if step == 'reset_newpw':
        if len(text) < 6:
            await update.message.reply_text("⚠️ Min 6 characters. Try again:")
            return
        reset_id = state.get('reset_id', '')
        otp      = state.get('verified_otp', '')
        msg = await update.message.reply_text("⏳ Resetting…")
        res = await api_call('resetPassword', {
            'studentId': reset_id, 'otp': otp, 'newPassword': text
        })
        set_state(chat_id, 'idle')
        if res.get('success'):
            await msg.edit_text(
                "✅ *Password reset!* Use /login to log in.",
                parse_mode='Markdown', reply_markup=main_keyboard(False)
            )
        else:
            await msg.edit_text(
                f"❌ {res.get('message','Reset failed.')}\n\nUse /reset to try again.",
                parse_mode='Markdown'
            )
        return

    # Chatbot mode
    if step == 'chatbot':
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        res   = await api_call('chatbot', {'message': text, 'studentId': state.get('studentId','')})
        reply = res.get('reply', "I couldn't process that. Try again.").replace('**','*')
        await update.message.reply_text(reply, parse_mode='Markdown')
        return

    # Admin: add student ID
    if step == 'admin_add_id':
        set_state(chat_id, 'idle')
        parts = [p.strip() for p in text.split('|')]
        if len(parts) < 2:
            await update.message.reply_text("⚠️ Format: `StudentID | Name | Email`", parse_mode='Markdown')
            return
        res = await api_call('addAuthorizedID', {
            'studentId': parts[0], 'name': parts[1],
            'email': parts[2] if len(parts) > 2 else ''
        })
        await update.message.reply_text(
            f"✅ `{parts[0]}` added." if res.get('success') else f"❌ {res.get('message')}",
            parse_mode='Markdown'
        )
        return

    # Admin: remove student ID
    if step == 'admin_remove_id':
        set_state(chat_id, 'idle')
        # No deleteAuthorizedID action in GAS yet — notify admin
        await update.message.reply_text(
            f"⚠️ Removal of `{text.strip()}` must be done manually in the Google Sheet "
            f"(*Authorized_IDs* tab).\n\n"
            f"The portal does not expose a delete-ID API for safety.",
            parse_mode='Markdown'
        )
        return

    # Admin: send notice
    if step == 'admin_notice':
        set_state(chat_id, 'idle')
        parts    = [p.strip() for p in text.split('|')]
        title    = parts[0] if parts else 'Notice'
        message  = parts[1] if len(parts) > 1 else text
        category = parts[2] if len(parts) > 2 else 'General'
        msg = await update.message.reply_text("⏳ Sending…")
        res = await api_call('sendNotice', {'title': title, 'message': message, 'category': category})
        await msg.edit_text(
            f"✅ Notice sent and broadcast to all students!" if res.get('success')
            else f"❌ {res.get('message')}",
            parse_mode='Markdown'
        )
        return

    # Admin: resolve complaint response
    if step == 'admin_resolve_complaint':
        set_state(chat_id, 'idle')
        c        = state.get('resolving_complaint', {})
        response = '' if text.lower() == 'skip' else text
        msg = await update.message.reply_text("⏳ Resolving…")
        res = await api_call('resolveComplaint', {
            'studentId': c.get('StudentID',''),
            'timestamp': c.get('Timestamp',''),
            'status':    'Resolved',
            'response':  response
        })
        await msg.edit_text(
            "✅ Resolved and student notified." if res.get('success') else f"❌ {res.get('message')}",
            parse_mode='Markdown'
        )
        return

    # ══ Menu button presses (idle state) ════════════════════
    if text == '📊 My Marks':        await cmd_marks(update, context)
    elif text == '📣 Notices':       await cmd_notices(update, context)
    elif text == '📝 Online Tests':  await cmd_tests(update, context)
    elif text == '📚 Lecture Notes': await cmd_notes(update, context)
    elif text == '📬 My Complaints': await cmd_complaints(update, context)
    elif text == '🤖 Ask Chatbot':   await cmd_chatbot(update, context)
    elif text == '🔗 Portal Link':   await show_portal_link(update, context)
    elif text == '👤 My Profile':    await cmd_profile(update, context)
    elif text == '🔗 Link My Account': await cmd_link(update, context)
    else:
        is_linked = bool(state.get('studentId'))
        await update.message.reply_text(
            "❓ Use the menu buttons or /help for commands.",
            reply_markup=main_keyboard(is_linked)
        )

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    if BOT_TOKEN == '8775466330:AAEEuQmHmynlKrn6O-FuyX5WDNFiT-5eSxA':
        logger.error("❌ Set BOT_TOKEN environment variable!")
        return
    if API_URL == 'https://script.google.com/macros/s/AKfycbyov_ffNcgMZYP_-fzlLfs9HiCl_XFud1vFbIMC_VmU_DHk0r6wemzzXYAN6EHhdjGZ-g/exec':
        logger.error("❌ Set API_URL environment variable!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start',       cmd_start))
    app.add_handler(CommandHandler('help',        cmd_help))
    app.add_handler(CommandHandler('login',       cmd_login))
    app.add_handler(CommandHandler('logout',      cmd_logout))
    app.add_handler(CommandHandler('reset',       cmd_reset))
    app.add_handler(CommandHandler('link',        cmd_link))
    app.add_handler(CommandHandler('marks',       cmd_marks))
    app.add_handler(CommandHandler('notices',     cmd_notices))
    app.add_handler(CommandHandler('tests',       cmd_tests))
    app.add_handler(CommandHandler('notes',       cmd_notes))
    app.add_handler(CommandHandler('complaints',  cmd_complaints))
    app.add_handler(CommandHandler('profile',     cmd_profile))
    app.add_handler(CommandHandler('admin',       cmd_admin))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot started.")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
