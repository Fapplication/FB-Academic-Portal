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

# ── API Helper ────────────────────────────────────────────────
async def api_call(action: str, params: dict = {}) -> dict:
    all_params = {'action': action, **params}
    qs = '&'.join(f"{k}={v}" for k, v in all_params.items() if v is not None)
    url = f"{API_URL}?{qs}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                return json.loads(text)
    except Exception as e:
        logger.error(f"API error: {e}")
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

def course_keyboard(courses: list) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(c['courseName'], callback_data=f"course_{c['courseId']}")]
               for c in courses]
    buttons.append([InlineKeyboardButton('← Back', callback_data='back_main')])
    return InlineKeyboardMarkup(buttons)

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('← Back to Menu', callback_data='back_main')]])

# ════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    chat_id  = update.effective_chat.id
    state    = get_state(chat_id)
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
        "/start — Main menu\n"
        "/marks — View your marks\n"
        "/notices — Latest notices\n"
        "/tests — Online tests\n"
        "/notes — Lecture notes\n"
        "/complaints — My complaints\n"
        "/profile — My profile\n"
        "/link — Link account\n"
        "/unlink — Unlink account\n"
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
        # Unrecognized input
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

    # Save to Bot_Sessions via API
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
        total   = float(m.get('weightedTotal', 0))
        grade   = get_grade_letter(total)
        status  = m.get('status', 'Pending')
        status_icon = '✅' if status == 'Accepted' else '⚠️' if status == 'Complained' else '⏳'

        reply += f"*{m.get('courseName', '—')}*\n"
        reply += f"Code: {m.get('courseCode', '—')} | {status_icon} {status}\n"

        for a in m.get('assessments', []):
            score   = a.get('score')
            max_s   = a.get('maxScore', '?')
            weight  = a.get('weight', 0)
            scored  = f"{score}/{max_s}" if score is not None else '—'
            reply  += f"  • {a['name']} ({weight}%): {scored}\n"

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

    latest  = list(reversed(notices))[:5]
    reply   = "📣 *Latest Notices*\n\n"
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

    await msg.edit_text(
        "📝 *Online Tests*\n\nSelect a course to start:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses)
    )

async def handle_test_course_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    chat_id = update.effective_chat.id
    query   = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Loading questions...")

    res = await api_call('getOnlineTests', {'courseId': course_id})
    questions = res.get('questions', [])

    if not questions:
        await query.edit_message_text(
            "📭 No questions available for this course yet.",
            reply_markup=back_keyboard()
        )
        return

    # Start test
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
        [InlineKeyboardButton('A', callback_data=f'ans_A'),
         InlineKeyboardButton('B', callback_data=f'ans_B')],
        [InlineKeyboardButton('C', callback_data=f'ans_C'),
         InlineKeyboardButton('D', callback_data=f'ans_D')],
        [InlineKeyboardButton('⏭ Skip', callback_data='ans_skip'),
         InlineKeyboardButton('📤 Submit Test', callback_data='test_submit')]
    ])

    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    # Handle text answers (A/B/C/D)
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
    await msg.edit_text(
        "📚 *Lecture Notes*\n\nSelect a course:",
        parse_mode='Markdown',
        reply_markup=course_keyboard(courses)
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

    reply  = "📬 *Your Complaints*\n\n"
    icons  = {'Pending':'⏳','Resolved':'✅','Rejected':'❌','Accepted':'👍'}
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
    # Clean markdown for Telegram
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

    if data.startswith('course_'):
        course_id = data.replace('course_', '')
        step      = state.get('step', 'idle')
        if step == 'test_answering' or step == 'idle':
            # Could be test or notes
            # Check where we came from by checking pending step
            await handle_test_course_callback(update, context, course_id)
        return

    if data.startswith('ans_'):
        answer = data.replace('ans_', '')
        if answer == 'skip':
            state['test_current'] = state.get('test_current', 0) + 1
            await send_question(update, context, is_callback=True)
        elif answer == 'submit':
            await query.answer()
            await finish_test(update, context)
        elif answer in ['A','B','C','D']:
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
        await update.message.reply_text(f"✅ Broadcast sent!")
    else:
        await update.message.reply_text(f"❌ Failed: {res.get('message')}")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    res     = await api_call('getDashboard')
    today   = datetime.now().strftime('%Y-%m-%d')
    linked  = len([s for s in user_states.values() if s.get('studentId')])

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
    app.add_handler(CommandHandler('start',     start))
    app.add_handler(CommandHandler('help',      help_command))
    app.add_handler(CommandHandler('marks',     show_marks))
    app.add_handler(CommandHandler('notices',   show_notices))
    app.add_handler(CommandHandler('tests',     show_tests_menu))
    app.add_handler(CommandHandler('notes',     show_notes_menu))
    app.add_handler(CommandHandler('complaints',show_complaints))
    app.add_handler(CommandHandler('profile',   show_profile))
    app.add_handler(CommandHandler('link',      start_link))
    app.add_handler(CommandHandler('broadcast', admin_broadcast))
    app.add_handler(CommandHandler('adminstats',admin_stats))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
