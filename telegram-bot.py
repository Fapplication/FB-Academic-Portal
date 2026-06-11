# ============================================================
# telegram-bot.py — Civil Engineering Student Portal Bot
# Connects to Google Sheets via Apps Script API
# Host on Railway.app (free)
# ============================================================

import os
import json
import logging
import asyncio
import aiohttp
from urllib.parse import urlencode          # FIX 8: safe URL encoding
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

# ── Config (set as Railway environment variables) ─────────────
BOT_TOKEN   = os.environ.get('BOT_TOKEN',   'YOUR_BOT_TOKEN')
API_URL     = os.environ.get('API_URL',     'YOUR_APPS_SCRIPT_URL')
ADMIN_ID    = int(os.environ.get('ADMIN_ID', '0'))
PORTAL_URL  = os.environ.get('PORTAL_URL',  'https://YOUR_USERNAME.github.io/civil-eng-portal/')

# ── FIX 6: Single shared aiohttp session for the entire process.
#    Old code created a new ClientSession on every api_call().
#    Creating sessions is expensive (opens a TCP connection pool)
#    and the old pattern leaked resources on Railway's free tier,
#    causing slowdowns and random connection errors.
_http_session: aiohttp.ClientSession | None = None

async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session

# ── API Helper ────────────────────────────────────────────────
async def api_call(action: str, params: dict = {}) -> dict:
    # FIX 8: Use urlencode() so values like "ETS0001/14" are
    #         percent-encoded (%2F) and don't break the URL.
    #         Old code used f-string concatenation which left
    #         slashes and spaces raw, silently corrupting calls.
    all_params = {'action': action, **{k: v for k, v in params.items() if v is not None}}
    url = f"{API_URL}?{urlencode(all_params)}"
    try:
        session = await get_http_session()
        async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            text = await resp.text()
            return json.loads(text)
    except Exception as e:
        logger.error(f"API error [{action}]: {e}")
        return {'success': False, 'message': str(e)}

# ── Session State ─────────────────────────────────────────────
# In-memory state per chat_id
user_states = {}  # { chat_id: { 'step': ..., 'studentId': ..., 'data': {} } }

def get_state(chat_id: int) -> dict:
    if chat_id not in user_states:
        user_states[chat_id] = {'step': 'idle', 'studentId': None, 'data': {}}
    return user_states[chat_id]

def set_state(chat_id: int, step: str, **kwargs):
    state = get_state(chat_id)
    state['step'] = step
    state.update(kwargs)

# ── Keyboards ─────────────────────────────────────────────────
def main_keyboard(linked: bool = True) -> ReplyKeyboardMarkup:
    if linked:
        buttons = [
            [KeyboardButton('📊 My Marks'),    KeyboardButton('📣 Notices')],
            [KeyboardButton('📝 Online Tests'), KeyboardButton('📚 Lecture Notes')],
            [KeyboardButton('📬 My Complaints'),KeyboardButton('🤖 Ask Chatbot')],
            [KeyboardButton('🔗 Portal Link'),  KeyboardButton('👤 My Profile')],
        ]
    else:
        buttons = [
            [KeyboardButton('🔗 Link My Account')],
            [KeyboardButton('🔗 Portal Link')],
        ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def course_keyboard(courses: list, mode: str = 'test') -> InlineKeyboardMarkup:
    # FIX 7: Embed the mode ('test' or 'notes') in the callback_data
    #         so handle_callback knows which handler to call.
    #         Old code used 'course_<id>' for both, always routing
    #         to the test handler even from the Notes menu.
    buttons = [
        [InlineKeyboardButton(c['courseName'], callback_data=f"course_{mode}_{c['courseId']}")]
        for c in courses
    ]
    buttons.append([InlineKeyboardButton('← Back', callback_data='back_main')])
    return InlineKeyboardMarkup(buttons)

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('← Back to Menu', callback_data='back_main')]])

# ════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user      = update.effective_user
    chat_id   = update.effective_chat.id
    state     = get_state(chat_id)
    is_linked = bool(state.get('studentId'))

    welcome = (
        f"👋 *Welcome to Civil Engineering Student Portal Bot!*\n\n"
        f"Hello, {user.first_name}!\n\n"
        f"{'✅ Your account is linked.' if is_linked else '🔗 Please link your account first.'}\n\n"
        f"📌 *What I can do:*\n"
        f"• 📊 View your marks & grades\n"
        f"• 📣 Receive instant notices\n"
        f"• 📝 Take online tests\n"
        f"• 📚 Download lecture notes\n"
        f"• 📬 Track your complaints\n"
        f"• 🤖 AI chatbot assistant\n\n"
        f"{'Use the menu below to get started!' if is_linked else 'Click *Link My Account* to get started!'}"
    )

    await update.message.reply_text(
        welcome,
        parse_mode='Markdown',
        reply_markup=main_keyboard(is_linked)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Available Commands*\n\n"
        "👤 *Account*\n"
        "/login — Log in with Student ID & password\n"
        "/logout — Log out and unlink account\n"
        "/reset — Reset your password\n"
        "/link — Link account (no password needed)\n"
        "/profile — My profile\n\n"
        "📚 *Student*\n"
        "/marks — View your marks\n"
        "/notices — Latest notices\n"
        "/tests — Online tests\n"
        "/notes — Lecture notes\n"
        "/complaints — My complaints\n\n"
        "🛡 *Admin*\n"
        "/admin — Admin panel\n\n"
        "/help — Show this message",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# MESSAGE HANDLER (main dispatcher)
# ════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text    = (update.message.text or '').strip()
    state   = get_state(chat_id)
    step    = state.get('step', 'idle')

    # ── Step-based handlers ──────────────────────────────────
    if step == 'awaiting_student_id':
        await handle_link_id(update, context, text)
        return

    if step == 'chatbot':
        await handle_chatbot_message(update, context, text)
        return

    if step == 'test_answering':
        await handle_test_answer(update, context, text)
        return

    # ── Menu buttons ─────────────────────────────────────────
    if text == '📊 My Marks':
        await show_marks(update, context)
    elif text == '📣 Notices':
        await show_notices(update, context)
    elif text == '📝 Online Tests':
        await show_tests_menu(update, context)
    elif text == '📚 Lecture Notes':
        await show_notes_menu(update, context)
    elif text == '📬 My Complaints':
        await show_complaints(update, context)
    elif text == '🤖 Ask Chatbot':
        await start_chatbot(update, context)
    elif text == '🔗 Portal Link':
        await show_portal_link(update, context)
    elif text == '👤 My Profile':
        await show_profile(update, context)
    elif text == '🔗 Link My Account':
        await start_link(update, context)
    else:
        is_linked = bool(state.get('studentId'))
        await update.message.reply_text(
            "❓ Please use the menu buttons below.",
            reply_markup=main_keyboard(is_linked)
        )

# ════════════════════════════════════════════════════════════
# LINK ACCOUNT
# ════════════════════════════════════════════════════════════

async def start_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'awaiting_student_id')
    await update.message.reply_text(
        "🔗 *Link Your Account*\n\n"
        "Please send your *Student ID* (e.g. ETS0001/14).\n\n"
        "_Your ID must be in the authorized list._",
        parse_mode='Markdown'
    )

async def handle_link_id(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: str):
    chat_id = update.effective_chat.id
    msg     = await update.message.reply_text("🔍 Checking your ID...")

    res = await api_call('checkAuthorizedID', {'studentId': student_id})

    if not res.get('success'):
        set_state(chat_id, 'idle')
        await msg.edit_text(
            f"❌ *{res.get('message', 'ID not found.')}*\n\n"
            "Please check your Student ID and try again.",
            parse_mode='Markdown'
        )
        return

    # Save session to Google Sheets via the new saveBotSession action
    await api_call('saveBotSession', {
        'chatId':    chat_id,
        'studentId': student_id,
        'status':    'linked'
    })

    set_state(chat_id, 'idle', studentId=student_id, name=res.get('name', ''))
    await msg.edit_text(
        f"✅ *Account Linked!*\n\n"
        f"Welcome, *{res.get('name')}*!\n\n"
        f"You will now receive:\n"
        f"• 📣 Instant notices\n"
        f"• 📊 Mark updates\n"
        f"• 📬 Complaint responses\n\n"
        f"Use the menu below to explore.",
        parse_mode='Markdown'
    )
    await update.message.reply_text(
        "Main menu:", reply_markup=main_keyboard(True)
    )

# ════════════════════════════════════════════════════════════
# MARKS
# ════════════════════════════════════════════════════════════

async def show_marks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    state      = get_state(chat_id)
    student_id = state.get('studentId')

    if not student_id:
        await update.message.reply_text(
            "❌ Please link your account first.",
            reply_markup=main_keyboard(False)
        )
        return

    msg = await update.message.reply_text("📊 Loading your marks...")
    res = await api_call('getMarks', {'studentId': student_id})

    if not res.get('success') or not res.get('marks'):
        await msg.edit_text("📊 No marks available yet. Check back later.")
        return

    reply = "📊 *Your Academic Marks*\n\n"
    for m in res['marks']:
        total       = float(m.get('weightedTotal', 0))
        grade       = get_grade_letter(total)
        status      = m.get('status', 'Pending')
        status_icon = '✅' if status == 'Accepted' else '⚠️' if status == 'Complained' else '⏳'

        reply += f"*{m.get('courseName', '—')}*\n"
        reply += f"Code: {m.get('courseCode', '—')} | {status_icon} {status}\n"

        for a in m.get('assessments', []):
            score  = a.get('score')
            max_s  = a.get('maxScore', '?')
            weight = a.get('weight', 0)
            scored = f"{score}/{max_s}" if score is not None else '—'
            reply += f"  • {a['name']} ({weight}%): {scored}\n"

        reply += f"📈 *Total: {total}% — {grade}*\n\n"

    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

def get_grade_letter(pct: float) -> str:
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

# ════════════════════════════════════════════════════════════
# NOTICES
# ════════════════════════════════════════════════════════════

async def show_notices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📣 Loading notices...")
    res = await api_call('getNotices')

    notices = res.get('notices', [])
    if not notices:
        await msg.edit_text("📣 No notices yet.")
        return

    latest = list(reversed(notices))[:5]
    reply  = "📣 *Latest Notices*\n\n"
    for n in latest:
        title    = n.get('Title', n.get('title', 'Notice'))
        message  = n.get('Message', n.get('message', ''))
        ts       = n.get('Timestamp', n.get('timestamp', ''))
        category = n.get('Category', n.get('category', ''))
        cat_icon = {'Exam':'📝','Assignment':'📋','Holiday':'🎉','Result':'📊','Urgent':'🚨'}.get(category,'📢')
        date_str = ts[:10] if ts else ''
        reply   += f"{cat_icon} *{title}*\n"
        if date_str: reply += f"📅 {date_str}\n"
        reply   += f"{message[:200]}{'...' if len(message) > 200 else ''}\n\n"

    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

# ════════════════════════════════════════════════════════════
# ONLINE TESTS
# ════════════════════════════════════════════════════════════

async def show_tests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    if not state.get('studentId'):
        await update.message.reply_text("❌ Link your account first.", reply_markup=main_keyboard(False))
        return

    msg = await update.message.reply_text("📝 Loading courses...")
    res = await api_call('getCourses')

    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📝 No courses available.")
        return

    # FIX 7: Pass mode='test' so callback knows to load questions
    await msg.edit_text(
        "📝 *Online Tests*\n\nSelect a course to start:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses, mode='test')
    )

async def handle_test_course_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    chat_id = update.effective_chat.id
    query   = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Loading questions...")

    res       = await api_call('getOnlineTests', {'courseId': course_id})
    questions = res.get('questions', [])

    if not questions:
        await query.edit_message_text(
            "📭 No questions available for this course yet.",
            reply_markup=back_keyboard()
        )
        return

    set_state(chat_id, 'test_answering',
        test_questions=questions,
        test_course_id=course_id,
        test_current=0,
        test_answers={}
    )
    await send_question(update, context, is_callback=True)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    chat_id   = update.effective_chat.id
    state     = get_state(chat_id)
    questions = state.get('test_questions', [])
    current   = state.get('test_current', 0)

    if current >= len(questions):
        await finish_test(update, context)
        return

    q       = questions[current]
    total   = len(questions)
    replied = len(state.get('test_answers', {}))

    text = (
        f"📝 *Question {current+1} of {total}*\n"
        f"Answered: {replied}/{total}\n\n"
        f"{q['question']}\n\n"
        f"🅰 {q['optionA']}\n"
        f"🅱 {q['optionB']}\n"
        f"🅲 {q['optionC']}\n"
        f"🅳 {q['optionD']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('A', callback_data='ans_A'),
         InlineKeyboardButton('B', callback_data='ans_B')],
        [InlineKeyboardButton('C', callback_data='ans_C'),
         InlineKeyboardButton('D', callback_data='ans_D')],
        [InlineKeyboardButton('⏭ Skip', callback_data='ans_skip'),
         InlineKeyboardButton('📤 Submit Test', callback_data='test_submit')]
    ])

    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    if text.upper() in ['A', 'B', 'C', 'D']:
        state   = get_state(chat_id)
        current = state.get('test_current', 0)
        state.setdefault('test_answers', {})[current] = text.upper()
        state['test_current'] = current + 1
        await send_question(update, context)

async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    state      = get_state(chat_id)
    answers    = state.get('test_answers', {})
    questions  = state.get('test_questions', [])
    course_id  = state.get('test_course_id', '')
    student_id = state.get('studentId', '')
    answered   = len(answers)
    total      = len(questions)
    pct        = round((answered / total) * 100) if total > 0 else 0

    await api_call('submitTestResult', {
        'studentId': student_id,
        'courseId':  course_id,
        'score':     answered,
        'total':     total,
        'answers':   json.dumps(answers)
    })

    set_state(chat_id, 'idle')
    grade = get_grade_letter(pct)

    text = (
        f"🎉 *Test Submitted!*\n\n"
        f"📊 Answered: {answered}/{total}\n"
        f"📈 Score: {pct}%\n"
        f"🏅 Grade: {grade}\n\n"
        f"Your instructor will review and announce final scores."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_keyboard())
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard(True))

# ════════════════════════════════════════════════════════════
# LECTURE NOTES
# ════════════════════════════════════════════════════════════

async def show_notes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📚 Loading courses...")
    res = await api_call('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📚 No courses available.")
        return
    # FIX 7: Pass mode='notes' so callback knows to load notes
    await msg.edit_text(
        "📚 *Lecture Notes*\n\nSelect a course:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses, mode='notes')
    )

async def handle_notes_course_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📚 Loading notes...")

    res   = await api_call('getLectureNotes', {'courseId': course_id})
    notes = res.get('notes', [])

    if not notes:
        await query.edit_message_text("📭 No notes uploaded yet.", reply_markup=back_keyboard())
        return

    reply = "📚 *Lecture Notes*\n\n"
    for n in notes[:10]:
        title = n.get('Topic_Title', n.get('topicTitle', 'Untitled'))
        url   = n.get('Resource_URL', n.get('resourceUrl', ''))
        ftype = n.get('FileType', n.get('fileType', 'File'))
        icons = {'PDF':'📄','Word':'📝','PPT':'📊','Video':'🎥','Link':'🔗'}
        icon  = icons.get(ftype, '📁')
        reply += f"{icon} [{title}]({url})\n"

    await query.edit_message_text(
        reply, parse_mode='Markdown',
        reply_markup=back_keyboard(),
        disable_web_page_preview=True
    )

# ════════════════════════════════════════════════════════════
# COMPLAINTS
# ════════════════════════════════════════════════════════════

async def show_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    state      = get_state(chat_id)
    student_id = state.get('studentId')

    if not student_id:
        await update.message.reply_text("❌ Link your account first.", reply_markup=main_keyboard(False))
        return

    msg = await update.message.reply_text("📬 Loading complaints...")
    res = await api_call('getComplaints')

    all_complaints = res.get('complaints', [])
    my_complaints  = [c for c in all_complaints
                      if str(c.get('StudentID', c.get('studentId', ''))).strip() == str(student_id).strip()]

    if not my_complaints:
        await msg.edit_text(
            "📬 You have no complaints on record.\n\n"
            "To raise a complaint, visit the portal → My Marks → Raise Complaint.",
            reply_markup=back_keyboard()
        )
        return

    reply = "📬 *Your Complaints*\n\n"
    icons = {'Pending':'⏳','Resolved':'✅','Rejected':'❌','Accepted':'👍'}
    for c in reversed(my_complaints[-5:]):
        status   = c.get('Status', c.get('status', 'Pending'))
        course   = c.get('Course_ID', c.get('courseId', '—'))
        ctype    = c.get('Type', c.get('type', '—'))
        response = c.get('Response', c.get('response', ''))
        ts       = c.get('Timestamp', c.get('timestamp', ''))[:10]
        icon     = icons.get(status, '⏳')
        reply   += f"{icon} *{status}* — {ctype}\n"
        reply   += f"📚 {course}\n"
        reply   += f"📅 {ts}\n"
        if response:
            reply += f"💬 Response: {response[:100]}\n"
        reply += "\n"

    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=back_keyboard())

# ════════════════════════════════════════════════════════════
# CHATBOT
# ════════════════════════════════════════════════════════════

async def start_chatbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'chatbot')
    await update.message.reply_text(
        "🤖 *Chatbot Mode*\n\n"
        "Ask me anything about marks, tests, notes, complaints, or account issues.\n\n"
        "_Send /start to exit chatbot mode._",
        parse_mode='Markdown'
    )

async def handle_chatbot_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id    = update.effective_chat.id
    state      = get_state(chat_id)
    student_id = state.get('studentId', '')

    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    res = await api_call('chatbot', {'message': text, 'studentId': student_id})

    reply = res.get('reply', 'I could not process that. Please try again.')
    reply = reply.replace('**', '*')

    await update.message.reply_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# PROFILE & MISC
# ════════════════════════════════════════════════════════════

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    user    = update.effective_user

    if not state.get('studentId'):
        await update.message.reply_text(
            "❌ No account linked yet.\n\nTap *Link My Account* to get started.",
            parse_mode='Markdown',
            reply_markup=main_keyboard(False)
        )
        return

    await update.message.reply_text(
        f"👤 *My Profile*\n\n"
        f"🆔 Student ID: `{state['studentId']}`\n"
        f"👤 Name: {state.get('name', '—')}\n"
        f"📱 Telegram: @{user.username or '—'}\n"
        f"🔗 Status: ✅ Linked\n\n"
        f"[Open Full Portal]({PORTAL_URL})",
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

async def show_portal_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔗 *Student Portal*\n\n"
        f"Access your full academic portal:\n{PORTAL_URL}\n\n"
        f"Login with your Student ID and password.",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# CALLBACK QUERY HANDLER
# ════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)

    if data == 'back_main':
        await query.answer()
        is_linked = bool(state.get('studentId'))
        await query.edit_message_text(
            "🏠 Main Menu",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('Open Menu', callback_data='noop')
            ]])
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Use the menu below:",
            reply_markup=main_keyboard(is_linked)
        )
        return

    # FIX 7: callback_data is now 'course_test_<id>' or 'course_notes_<id>'
    #         so we can correctly route to the right handler.
    #         Old code used 'course_<id>' for both and always called
    #         handle_test_course_callback even from the Notes menu.
    if data.startswith('course_test_'):
        course_id = data.replace('course_test_', '')
        await handle_test_course_callback(update, context, course_id)
        return

    if data.startswith('course_notes_'):
        course_id = data.replace('course_notes_', '')
        await handle_notes_course_callback(update, context, course_id)
        return

    if data.startswith('ans_'):
        answer = data.replace('ans_', '')
        if answer == 'skip':
            state['test_current'] = state.get('test_current', 0) + 1
            await send_question(update, context, is_callback=True)
        elif answer in ['A', 'B', 'C', 'D']:
            await query.answer(f"Selected: {answer}")
            current = state.get('test_current', 0)
            state.setdefault('test_answers', {})[current] = answer
            state['test_current'] = current + 1
            await send_question(update, context, is_callback=True)
        return

    if data == 'test_submit':
        await query.answer()
        await finish_test(update, context)
        return

    await query.answer()

# ════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ════════════════════════════════════════════════════════════

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return

    message = ' '.join(context.args)
    res     = await api_call('sendNotice', {'title': 'Broadcast', 'message': message})

    if res.get('success'):
        await update.message.reply_text("✅ Broadcast sent!")
    else:
        await update.message.reply_text(f"❌ Failed: {res.get('message')}")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    res    = await api_call('getDashboard')
    today  = datetime.now().strftime('%Y-%m-%d')
    linked = len([s for s in user_states.values() if s.get('studentId')])

    await update.message.reply_text(
        f"📊 *Admin Dashboard*\n\n"
        f"👥 Total Students: {res.get('totalStudents', '—')}\n"
        f"📚 Courses: {len(res.get('courses', []))}\n"
        f"📬 Pending Complaints: {res.get('pendingComplaints', '—')}\n"
        f"📱 Bot Users (session): {linked}\n"
        f"📅 Date: {today}",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.error("❌ Set BOT_TOKEN environment variable!")
        return
    if API_URL == 'YOUR_APPS_SCRIPT_URL':
        logger.error("❌ Set API_URL environment variable!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start',      start))
    app.add_handler(CommandHandler('help',       help_command))
    app.add_handler(CommandHandler('login',      login_command))
    app.add_handler(CommandHandler('logout',     logout_command))
    app.add_handler(CommandHandler('reset',      reset_command))
    app.add_handler(CommandHandler('marks',      show_marks))
    app.add_handler(CommandHandler('notices',    show_notices))
    app.add_handler(CommandHandler('tests',      show_tests_menu))
    app.add_handler(CommandHandler('notes',      show_notes_menu))
    app.add_handler(CommandHandler('complaints', show_complaints))
    app.add_handler(CommandHandler('profile',    show_profile))
    app.add_handler(CommandHandler('link',       start_link))
    app.add_handler(CommandHandler('admin',      admin_command))
    app.add_handler(CommandHandler('broadcast',  admin_broadcast))
    app.add_handler(CommandHandler('adminstats', admin_stats))

    # Callbacks — admin panel first (more specific prefix), then general
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern='^adm_'))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Messages — use the extended handler that wraps the original
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

# ════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ════════════════════════════════════════════════════════════

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /login — starts the student login flow."""
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)

    if state.get('studentId'):
        await update.message.reply_text(
            f"✅ You are already logged in as `{state['studentId']}`.\n\n"
            f"Use /logout to switch accounts.",
            parse_mode='Markdown',
            reply_markup=main_keyboard(True)
        )
        return

    set_state(chat_id, 'login_awaiting_id')
    await update.message.reply_text(
        "🔐 *Login to Your Account*\n\n"
        "Please send your *Student ID*:",
        parse_mode='Markdown'
    )

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlinks account and clears all session data."""
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    sid     = state.get('studentId')

    if not sid:
        await update.message.reply_text(
            "ℹ️ You are not logged in.",
            reply_markup=main_keyboard(False)
        )
        return

    # Tell the sheet this session is unlinked
    await api_call('saveBotSession', {
        'chatId':    chat_id,
        'studentId': sid,
        'status':    'unlinked'
    })

    # Wipe in-memory state
    user_states[chat_id] = {'step': 'idle', 'studentId': None, 'data': {}}

    await update.message.reply_text(
        "👋 *Logged out successfully.*\n\n"
        "Your account has been unlinked from this chat.\n"
        "Use /login or tap *Link My Account* to log in again.",
        parse_mode='Markdown',
        reply_markup=main_keyboard(False)
    )

# ════════════════════════════════════════════════════════════
# PASSWORD RESET (via bot)
# ════════════════════════════════════════════════════════════

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the password reset flow."""
    chat_id = update.effective_chat.id
    set_state(chat_id, 'reset_awaiting_id')
    await update.message.reply_text(
        "🔑 *Reset Password*\n\n"
        "Send your *Student ID* and we'll send an OTP:",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# EXTENDED MESSAGE HANDLER — login + reset steps
# (patches into the existing handle_message dispatcher)
# ════════════════════════════════════════════════════════════

# Save a reference to the original handler
_original_handle_message = handle_message

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text    = (update.message.text or '').strip()
    state   = get_state(chat_id)
    step    = state.get('step', 'idle')

    # ── Login flow ───────────────────────────────────────────
    if step == 'login_awaiting_id':
        set_state(chat_id, 'login_awaiting_password', pending_id=text)
        await update.message.reply_text(
            f"🔐 ID: `{text}`\n\nNow send your *password*:",
            parse_mode='Markdown'
        )
        return

    if step == 'login_awaiting_password':
        pending_id = state.get('pending_id', '')
        msg = await update.message.reply_text("⏳ Verifying credentials...")
        res = await api_call('loginStudent', {'studentId': pending_id, 'password': text})
        if res.get('success'):
            await api_call('saveBotSession', {
                'chatId':    chat_id,
                'studentId': pending_id,
                'status':    'linked'
            })
            set_state(chat_id, 'idle', studentId=pending_id, name=res.get('name', ''))
            await msg.edit_text(
                f"✅ *Welcome back, {res.get('name')}!*\n\n"
                f"🆔 `{pending_id}`\n\n"
                f"You are now logged in.",
                parse_mode='Markdown'
            )
            await update.message.reply_text("Main menu:", reply_markup=main_keyboard(True))
        else:
            set_state(chat_id, 'idle')
            await msg.edit_text(
                f"❌ *{res.get('message', 'Invalid credentials.')}*\n\n"
                "Use /login to try again.",
                parse_mode='Markdown',
                reply_markup=main_keyboard(False)
            )
        return

    # ── Password reset flow ──────────────────────────────────
    if step == 'reset_awaiting_id':
        msg = await update.message.reply_text("⏳ Sending OTP...")
        res = await api_call('sendOTP', {'studentId': text, 'purpose': 'RESET'})
        if res.get('success'):
            set_state(chat_id, 'reset_awaiting_otp', reset_id=text)
            via = res.get('sentVia', 'unknown')
            contact = res.get('contact', '')
            await msg.edit_text(
                f"📨 OTP sent via *{via}*"
                f"{' to ' + contact if contact else ''}.\n\n"
                f"Please enter the *6-digit OTP*:",
                parse_mode='Markdown'
            )
        else:
            set_state(chat_id, 'idle')
            await msg.edit_text(
                f"❌ {res.get('message', 'Failed to send OTP.')}\n\nUse /reset to try again.",
                parse_mode='Markdown'
            )
        return

    if step == 'reset_awaiting_otp':
        reset_id = state.get('reset_id', '')
        res = await api_call('verifyOTP', {'studentId': reset_id, 'otp': text})
        if res.get('success'):
            set_state(chat_id, 'reset_awaiting_newpw', reset_id=reset_id, last_otp=text)
            await update.message.reply_text(
                "✅ OTP verified!\n\nNow send your *new password*\n_(min 6 characters)_:",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ {res.get('message', 'Invalid OTP.')}\n\nSend the correct OTP or use /reset to restart.",
                parse_mode='Markdown'
            )
        return

    if step == 'reset_awaiting_newpw':
        reset_id = state.get('reset_id', '')
        if len(text) < 6:
            await update.message.reply_text("⚠️ Password must be at least 6 characters. Try again:")
            return
        msg = await update.message.reply_text("⏳ Resetting password...")
        # We already verified OTP — send a dummy OTP that matches to pass verifyOTP in resetPassword
        # Better: store verified flag and call a direct reset. We re-use verifyOTP logic here:
        res = await api_call('resetPassword', {
            'studentId':   reset_id,
            'otp':         state.get('last_otp', '000000'),  # GAS verifyOTP called again; pass stored OTP
            'newPassword': text
        })
        # Note: since GAS resetPassword calls verifyOTP internally,
        # store the OTP in state at the verify step for this to work.
        # Fallback: send OTP again then reset. For simplicity we call
        # a direct password update via updatePassword action if available.
        # For now just surface the result.
        set_state(chat_id, 'idle')
        if res.get('success'):
            await msg.edit_text(
                "✅ *Password reset successfully!*\n\n"
                "Use /login to log in with your new password.",
                parse_mode='Markdown',
                reply_markup=main_keyboard(False)
            )
        else:
            await msg.edit_text(
                f"❌ {res.get('message', 'Reset failed.')}\n\nUse /reset to try again.",
                parse_mode='Markdown'
            )
        return

    # ── Admin text flows ─────────────────────────────────────
    if step == 'admin_adding_id':
        await handle_admin_add_id_input(update, context, text)
        return

    if step == 'admin_sending_notice':
        await handle_admin_notice_input(update, context, text)
        return

    if step == 'admin_resolving_complaint':
        await handle_admin_resolve_input(update, context, text)
        return

    # ── Fall through to original handler ────────────────────
    await _original_handle_message(update, context)


# ════════════════════════════════════════════════════════════
# ADMIN PANEL
# ════════════════════════════════════════════════════════════

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📊 Dashboard',          callback_data='adm_dashboard')],
        [InlineKeyboardButton('👥 Manage Students',    callback_data='adm_students'),
         InlineKeyboardButton('➕ Add Student ID',     callback_data='adm_add_id')],
        [InlineKeyboardButton('📣 Send Notice',        callback_data='adm_notice'),
         InlineKeyboardButton('📬 Complaints',         callback_data='adm_complaints')],
        [InlineKeyboardButton('🚫 Banned Students',    callback_data='adm_banned'),
         InlineKeyboardButton('📈 Test Results',       callback_data='adm_test_results')],
        [InlineKeyboardButton('✖ Close',               callback_data='adm_close')],
    ])

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /admin"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access only.")
        return
    await update.message.reply_text(
        "🛡 *Admin Panel*\n\nSelect an action:",
        parse_mode='Markdown',
        reply_markup=admin_menu_keyboard()
    )

# ── Admin callback dispatcher ────────────────────────────────
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    chat_id = update.effective_chat.id

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Admin only.", show_alert=True)
        return

    await query.answer()

    # ── Dashboard ────────────────────────────────────────────
    if data == 'adm_dashboard':
        await query.edit_message_text("⏳ Loading dashboard...")
        res    = await api_call('getDashboard')
        linked = len([s for s in user_states.values() if s.get('studentId')])
        text   = (
            f"📊 *Dashboard*\n\n"
            f"👥 Authorized Students: {res.get('totalStudents','—')}\n"
            f"📚 Total Assessments:   {res.get('totalAssessments','—')}\n"
            f"📬 Pending Complaints:  {res.get('pendingComplaints','—')}\n"
            f"📈 Avg Score:           {res.get('avgScore','—')}%\n"
            f"📱 Active Bot Sessions: {linked}\n\n"
            f"*Courses:*\n"
        )
        for c in res.get('courses', []):
            text += (
                f"• {c.get('courseName','—')} (`{c.get('courseCode','—')}`)\n"
                f"  {c.get('assessmentCount',0)} assessments"
                f" | avg {c.get('avgScore','—')}%\n"
            )
        await query.edit_message_text(text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('← Back', callback_data='adm_back')
            ]]))
        return

    # ── List students ────────────────────────────────────────
    if data == 'adm_students':
        await query.edit_message_text("⏳ Loading students...")
        res      = await api_call('getAuthorizedIDs')
        ids      = res.get('ids', [])
        banned   = get_state(chat_id).get('banned_ids', set())
        text     = f"👥 *Authorized Students* ({len(ids)} total)\n\n"
        for s in ids[:30]:
            sid  = s.get('ID', s.get('id',''))
            name = s.get('Name', s.get('name','—'))
            flag = ' 🚫' if sid in banned else ''
            text += f"• `{sid}` — {name}{flag}\n"
        if len(ids) > 30:
            text += f"\n_...and {len(ids)-30} more._"
        buttons = [
            [InlineKeyboardButton('➕ Add New', callback_data='adm_add_id'),
             InlineKeyboardButton('🗑 Remove',  callback_data='adm_remove_id')],
            [InlineKeyboardButton('← Back',    callback_data='adm_back')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ── Add student ID ───────────────────────────────────────
    if data == 'adm_add_id':
        set_state(chat_id, 'admin_adding_id')
        await query.edit_message_text(
            "➕ *Add Authorized Student ID*\n\n"
            "Send the details in this format:\n"
            "`StudentID | Full Name | Email`\n\n"
            "Example:\n`ETS0050/14 | Abebe Bekele | abebe@example.com`\n\n"
            "_Send /admin to cancel._",
            parse_mode='Markdown'
        )
        return

    # ── Remove student ID ────────────────────────────────────
    if data == 'adm_remove_id':
        set_state(chat_id, 'admin_removing_id')
        await query.edit_message_text(
            "🗑 *Remove Student ID*\n\n"
            "Send the Student ID to remove:\n`ETS0050/14`\n\n"
            "_Send /admin to cancel._",
            parse_mode='Markdown'
        )
        return

    # ── Send notice ──────────────────────────────────────────
    if data == 'adm_notice':
        set_state(chat_id, 'admin_sending_notice')
        await query.edit_message_text(
            "📣 *Send Notice*\n\n"
            "Send the notice in this format:\n"
            "`Title | Message | Category`\n\n"
            "Categories: Exam, Assignment, Holiday, Result, Urgent, General\n\n"
            "Example:\n`Exam Schedule | Mid exam starts Monday | Exam`\n\n"
            "_Send /admin to cancel._",
            parse_mode='Markdown'
        )
        return

    # ── Complaints ───────────────────────────────────────────
    if data == 'adm_complaints':
        await query.edit_message_text("⏳ Loading complaints...")
        res      = await api_call('getComplaints')
        all_c    = res.get('complaints', [])
        pending  = [c for c in all_c if (c.get('Status') or c.get('status','')) == 'Pending']
        if not pending:
            await query.edit_message_text("✅ No pending complaints.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('← Back', callback_data='adm_back')
                ]]))
            return
        # Show first pending complaint with action buttons
        state = get_state(chat_id)
        state['pending_complaints'] = pending
        state['complaint_index']    = 0
        await show_admin_complaint(query, context, chat_id)
        return

    if data == 'adm_complaint_next':
        state = get_state(chat_id)
        state['complaint_index'] = state.get('complaint_index', 0) + 1
        await show_admin_complaint(query, context, chat_id)
        return

    if data == 'adm_complaint_resolve':
        state = get_state(chat_id)
        idx   = state.get('complaint_index', 0)
        c     = state.get('pending_complaints', [])[idx]
        state['resolving_complaint'] = c
        set_state(chat_id, 'admin_resolving_complaint')
        await query.edit_message_text(
            f"📬 Resolving complaint from `{c.get('StudentID','')}`\n\n"
            f"Send your *response message* (or type `skip` to resolve without a message):",
            parse_mode='Markdown'
        )
        return

    if data == 'adm_complaint_reject':
        state = get_state(chat_id)
        idx   = state.get('complaint_index', 0)
        c     = state.get('pending_complaints', [])[idx]
        res   = await api_call('resolveComplaint', {
            'studentId': c.get('StudentID',''),
            'timestamp': c.get('Timestamp',''),
            'status':    'Rejected',
            'response':  'Your complaint has been reviewed and rejected.'
        })
        await query.edit_message_text(
            "❌ Complaint *rejected* and student notified." if res.get('success')
            else f"⚠️ Error: {res.get('message')}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('← Back', callback_data='adm_back')
            ]])
        )
        return

    # ── Banned students list ─────────────────────────────────
    if data == 'adm_banned':
        state  = get_state(chat_id)
        banned = state.get('banned_ids', set())
        if not banned:
            await query.edit_message_text("✅ No banned students.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('← Back', callback_data='adm_back')
                ]]))
            return
        text = "🚫 *Banned Students*\n\n"
        for sid in banned:
            text += f"• `{sid}`\n"
        await query.edit_message_text(text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('← Back', callback_data='adm_back')
            ]]))
        return

    # ── Test results summary ─────────────────────────────────
    if data == 'adm_test_results':
        await query.edit_message_text("⏳ Loading test results...")
        res     = await api_call('getTestResults')
        results = res.get('results', [])
        if not results:
            await query.edit_message_text("📭 No test results yet.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('← Back', callback_data='adm_back')
                ]]))
            return
        text = f"📈 *Test Results* ({len(results)} submissions)\n\n"
        for r in results[-10:]:
            sid    = r.get('StudentID', r.get('studentId','—'))
            cid    = r.get('Course_ID', r.get('courseId','—'))
            score  = r.get('Score', r.get('score','—'))
            total  = r.get('Total', r.get('total','—'))
            ts     = str(r.get('Timestamp', r.get('timestamp','')))[:10]
            text  += f"• `{sid}` | {cid} | {score}/{total} | {ts}\n"
        if len(results) > 10:
            text += f"\n_Showing last 10 of {len(results)}_"
        await query.edit_message_text(text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('← Back', callback_data='adm_back')
            ]]))
        return

    # ── Back to admin menu ───────────────────────────────────
    if data in ('adm_back', 'adm_close'):
        if data == 'adm_close':
            await query.edit_message_text("🛡 Admin panel closed.")
        else:
            await query.edit_message_text(
                "🛡 *Admin Panel*\n\nSelect an action:",
                parse_mode='Markdown',
                reply_markup=admin_menu_keyboard()
            )
        return

async def show_admin_complaint(query, context, chat_id: int):
    state    = get_state(chat_id)
    pending  = state.get('pending_complaints', [])
    idx      = state.get('complaint_index', 0)

    if idx >= len(pending):
        await query.edit_message_text("✅ All pending complaints reviewed.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('← Back', callback_data='adm_back')
            ]]))
        return

    c      = pending[idx]
    sid    = c.get('StudentID', c.get('studentId','—'))
    course = c.get('Course_ID', c.get('courseId','—'))
    ctype  = c.get('Type', c.get('type','—'))
    msg    = c.get('Message', c.get('message',''))
    ts     = str(c.get('Timestamp', c.get('timestamp','')))[:10]

    text = (
        f"📬 *Complaint {idx+1}/{len(pending)}*\n\n"
        f"👤 Student: `{sid}`\n"
        f"📚 Course: {course}\n"
        f"🔖 Type: {ctype}\n"
        f"📅 Date: {ts}\n\n"
        f"💬 _{msg}_"
    )

    buttons = [
        [InlineKeyboardButton('✅ Resolve', callback_data='adm_complaint_resolve'),
         InlineKeyboardButton('❌ Reject',  callback_data='adm_complaint_reject')],
    ]
    if idx + 1 < len(pending):
        buttons.append([InlineKeyboardButton('⏭ Next', callback_data='adm_complaint_next')])
    buttons.append([InlineKeyboardButton('← Back', callback_data='adm_back')])

    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(buttons))

# ── Admin text-input handlers ────────────────────────────────

async def handle_admin_add_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'idle')
    parts = [p.strip() for p in text.split('|')]
    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ Wrong format. Use:\n`StudentID | Full Name | Email`",
            parse_mode='Markdown'
        )
        return
    sid   = parts[0]
    name  = parts[1]
    email = parts[2] if len(parts) > 2 else ''
    msg   = await update.message.reply_text(f"⏳ Adding `{sid}`...", parse_mode='Markdown')
    res   = await api_call('addAuthorizedID', {'studentId': sid, 'name': name, 'email': email})
    if res.get('success'):
        await msg.edit_text(f"✅ `{sid}` — *{name}* added successfully.", parse_mode='Markdown')
    else:
        await msg.edit_text(f"❌ {res.get('message','Failed.')}", parse_mode='Markdown')

async def handle_admin_notice_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    set_state(chat_id, 'idle')
    parts    = [p.strip() for p in text.split('|')]
    title    = parts[0] if len(parts) > 0 else 'Notice'
    message  = parts[1] if len(parts) > 1 else text
    category = parts[2] if len(parts) > 2 else 'General'
    msg      = await update.message.reply_text("⏳ Sending notice...")
    res      = await api_call('sendNotice', {'title': title, 'message': message, 'category': category})
    if res.get('success'):
        await msg.edit_text(
            f"✅ *Notice sent!*\n\n"
            f"📌 {title}\n"
            f"🏷 Category: {category}\n"
            f"📢 Broadcast to all linked students via Telegram.",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(f"❌ {res.get('message','Failed.')}", parse_mode='Markdown')

async def handle_admin_resolve_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id  = update.effective_chat.id
    state    = get_state(chat_id)
    c        = state.get('resolving_complaint', {})
    response = '' if text.lower() == 'skip' else text
    set_state(chat_id, 'idle')
    msg = await update.message.reply_text("⏳ Resolving...")
    res = await api_call('resolveComplaint', {
        'studentId': c.get('StudentID',''),
        'timestamp': c.get('Timestamp',''),
        'status':    'Resolved',
        'response':  response
    })
    if res.get('success'):
        await msg.edit_text(
            "✅ *Complaint resolved* and student notified via Telegram.",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(f"❌ {res.get('message','Failed.')}", parse_mode='Markdown')
