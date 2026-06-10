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
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ── Logging ───────────────────────────────────────────────────

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Config (set as Railway environment variables) ─────────────
BOT_TOKEN   = os.environ.get('BOT_TOKEN',   '8775466330:AAEEuQmHmynlKrn6O-FuyX5WDNFiT-5eSxA')
API_URL     = os.environ.get('API_URL',     'https://script.google.com/macros/s/AKfycbyov_ffNcgMZYP_-fzlLfs9HiCl_XFud1vFbIMC_VmU_DHk0r6wemzzXYAN6EHhdjGZ-g/exec')
ADMIN_ID    = int(os.environ.get('ADMIN_ID', '0'))
PORTAL_URL  = os.environ.get('PORTAL_URL',  'https://fapplication.github.io/FB-Academic-Portal/')

# ── In-memory session store ───────────────────────────────────
# { chat_id: { role, studentId, name, step, data, loggedIn } }
sessions = {}

def sess(chat_id):
    if chat_id not in sessions:
        sessions[chat_id] = {
            'role': None, 'studentId': None, 'name': '',
            'step': 'idle', 'data': {}, 'loggedIn': False
        }
    return sessions[chat_id]

def is_student(chat_id):
    s = sess(chat_id)
    return s['loggedIn'] and s['role'] == 'student'

def is_instructor(chat_id):
    s = sess(chat_id)
    return s['loggedIn'] and s['role'] == 'instructor'

# ── API ───────────────────────────────────────────────────────
async def api(action, params={}):
    qs = '&'.join(f"{k}={v}" for k,v in {'action':action,**params}.items() if v is not None)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API_URL}?{qs}", allow_redirects=True,
                             timeout=aiohttp.ClientTimeout(total=20)) as r:
                return json.loads(await r.text())
    except Exception as e:
        return {'success': False, 'message': str(e)}

# ── Keyboards ─────────────────────────────────────────────────
def kb_guest():
    return ReplyKeyboardMarkup([
        [KeyboardButton('🎓 Student Login'),   KeyboardButton('👨‍🏫 Instructor Login')],
        [KeyboardButton('🔗 Portal Link'),      KeyboardButton('ℹ️ Help')],
    ], resize_keyboard=True)

def kb_student():
    return ReplyKeyboardMarkup([
        [KeyboardButton('📊 My Marks'),         KeyboardButton('📣 Notices')],
        [KeyboardButton('📝 Online Tests'),      KeyboardButton('📚 Lecture Notes')],
        [KeyboardButton('📬 My Complaints'),     KeyboardButton('🤖 Ask Chatbot')],
        [KeyboardButton('👤 My Profile'),        KeyboardButton('🚪 Logout')],
    ], resize_keyboard=True)

def kb_instructor():
    return ReplyKeyboardMarkup([
        [KeyboardButton('📊 Dashboard'),         KeyboardButton('👥 Manage Students')],
        [KeyboardButton('📤 Upload Marks'),       KeyboardButton('📬 Complaints')],
        [KeyboardButton('📣 Send Notice'),        KeyboardButton('📚 Lecture Notes')],
        [KeyboardButton('⚖️ Assessments'),        KeyboardButton('🚪 Logout')],
    ], resize_keyboard=True)

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton('← Back', callback_data='back')]])

def grade(pct):
    for g,t in [('A+',90),('A',85),('A-',80),('B+',75),('B',70),
                ('B-',65),('C+',60),('C',55),('C-',50),('D',45)]:
        if pct >= t: return g
    return 'F'

# ════════════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    s   = sess(cid)
    s['step'] = 'idle'

    if s['loggedIn']:
        kb = kb_student() if s['role']=='student' else kb_instructor()
        await update.message.reply_text(
            f"👋 Welcome back, *{s['name']}*!\nUse the menu below.",
            parse_mode='Markdown', reply_markup=kb
        )
    else:
        await update.message.reply_text(
            "👋 *Welcome to Civil Eng. Student Portal Bot!*\n\n"
            "Please login to access your account.",
            parse_mode='Markdown', reply_markup=kb_guest()
        )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Commands*\n\n"
        "/start — Main menu\n"
        "/logout — Logout\n"
        "/marks — My marks\n"
        "/notices — Latest notices\n"
        "/profile — My profile\n"
        "/help — This message\n\n"
        "*Admin only:*\n"
        "/admin — Admin panel\n"
        "/broadcast <msg> — Send to all\n"
        "/stats — System statistics",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# MESSAGE DISPATCHER
# ════════════════════════════════════════════════════════════
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = (update.message.text or '').strip()
    s    = sess(cid)
    step = s['step']

    # ── Step handlers ────────────────────────────────────────
    if step == 'await_student_id':    await do_student_login_id(update, ctx, text);  return
    if step == 'await_student_pass':  await do_student_login_pass(update, ctx, text); return
    if step == 'await_instr_user':    await do_instr_login_user(update, ctx, text);   return
    if step == 'await_instr_pass':    await do_instr_login_pass(update, ctx, text);   return
    if step == 'chatbot':             await do_chatbot(update, ctx, text);             return
    if step == 'await_notice_title':  await do_notice_title(update, ctx, text);       return
    if step == 'await_notice_msg':    await do_notice_msg(update, ctx, text);         return
    if step == 'await_bulk_csv':      await do_bulk_csv(update, ctx, text);           return
    if step == 'await_single_mark':   await do_single_mark(update, ctx, text);        return
    if step.startswith('test_'):      await do_test_step(update, ctx, text, step);    return

    # ── Guest menu ───────────────────────────────────────────
    if text == '🎓 Student Login':     await start_student_login(update, ctx);  return
    if text == '👨‍🏫 Instructor Login': await start_instr_login(update, ctx);   return
    if text == '🔗 Portal Link':       await show_portal(update, ctx);          return
    if text == 'ℹ️ Help':             await cmd_help(update, ctx);              return

    # ── Student menu ─────────────────────────────────────────
    if text == '📊 My Marks':         await show_marks(update, ctx);       return
    if text == '📣 Notices':          await show_notices(update, ctx);     return
    if text == '📝 Online Tests':     await show_tests(update, ctx);       return
    if text == '📚 Lecture Notes':    await show_notes(update, ctx);       return
    if text == '📬 My Complaints':    await show_complaints(update, ctx);  return
    if text == '🤖 Ask Chatbot':      await start_chatbot(update, ctx);    return
    if text == '👤 My Profile':       await show_profile(update, ctx);     return
    if text == '🚪 Logout':           await do_logout(update, ctx);        return

    # ── Instructor menu ──────────────────────────────────────
    if text == '📊 Dashboard':        await instr_dashboard(update, ctx);   return
    if text == '👥 Manage Students':  await instr_students(update, ctx);    return
    if text == '📤 Upload Marks':     await instr_upload_marks(update, ctx); return
    if text == '📬 Complaints':       await instr_complaints(update, ctx);  return
    if text == '📣 Send Notice':      await instr_send_notice(update, ctx); return
    if text == '📚 Lecture Notes':    await instr_notes(update, ctx);       return
    if text == '⚖️ Assessments':      await instr_assessments(update, ctx); return

    # ── Fallback ─────────────────────────────────────────────
    kb = kb_student() if is_student(cid) else kb_instructor() if is_instructor(cid) else kb_guest()
    await update.message.reply_text("❓ Use the menu.", reply_markup=kb)

# ════════════════════════════════════════════════════════════
# LOGIN — STUDENT
# ════════════════════════════════════════════════════════════
async def start_student_login(update, ctx):
    cid = update.effective_chat.id
    sess(cid)['step'] = 'await_student_id'
    await update.message.reply_text(
        "🎓 *Student Login*\n\nEnter your *Student ID*:",
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )

async def do_student_login_id(update, ctx, text):
    cid = update.effective_chat.id
    s   = sess(cid)
    s['data']['studentId'] = text
    s['step'] = 'await_student_pass'
    await update.message.reply_text("🔒 Enter your *Password*:", parse_mode='Markdown')

async def do_student_login_pass(update, ctx, text):
    cid = update.effective_chat.id
    s   = sess(cid)
    msg = await update.message.reply_text("⏳ Logging in...")
    res = await api('loginStudent', {'studentId': s['data']['studentId'], 'password': text})
    if res.get('success'):
        s.update({'loggedIn': True, 'role': 'student',
                  'studentId': s['data']['studentId'], 'name': res['name'], 'step': 'idle'})
        # Save chatId to Bot_Sessions
        await api('saveBotSession', {'chatId': cid, 'studentId': s['studentId'], 'status': 'linked'})
        await msg.edit_text(f"✅ *Welcome, {res['name']}!*", parse_mode='Markdown')
        await update.message.reply_text("Main menu:", reply_markup=kb_student())
    else:
        s['step'] = 'idle'
        await msg.edit_text(f"❌ {res.get('message','Login failed.')}")
        await update.message.reply_text("Try again:", reply_markup=kb_guest())

# ════════════════════════════════════════════════════════════
# LOGIN — INSTRUCTOR
# ════════════════════════════════════════════════════════════
async def start_instr_login(update, ctx):
    cid = update.effective_chat.id
    sess(cid)['step'] = 'await_instr_user'
    await update.message.reply_text(
        "👨‍🏫 *Instructor Login*\n\nEnter your *Username*:",
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )

async def do_instr_login_user(update, ctx, text):
    cid = update.effective_chat.id
    sess(cid)['data']['username'] = text
    sess(cid)['step'] = 'await_instr_pass'
    await update.message.reply_text("🔒 Enter your *Password*:", parse_mode='Markdown')

async def do_instr_login_pass(update, ctx, text):
    cid = update.effective_chat.id
    s   = sess(cid)
    msg = await update.message.reply_text("⏳ Logging in...")
    res = await api('loginInstructor', {'username': s['data']['username'], 'password': text})
    if res.get('success'):
        s.update({'loggedIn': True, 'role': 'instructor', 'name': res['name'], 'step': 'idle'})
        await msg.edit_text(f"✅ *Welcome, {res['name']}!*", parse_mode='Markdown')
        await update.message.reply_text("Instructor menu:", reply_markup=kb_instructor())
    else:
        s['step'] = 'idle'
        await msg.edit_text(f"❌ {res.get('message','Login failed.')}")
        await update.message.reply_text("Try again:", reply_markup=kb_guest())

# ════════════════════════════════════════════════════════════
# LOGOUT
# ════════════════════════════════════════════════════════════
async def do_logout(update, ctx):
    cid = update.effective_chat.id
    s   = sess(cid)
    name = s.get('name','')
    s.update({'loggedIn': False, 'role': None, 'studentId': None, 'name': '', 'step': 'idle', 'data': {}})
    await update.message.reply_text(
        f"👋 *Logged out, {name}.*\n\nSee you next time!",
        parse_mode='Markdown', reply_markup=kb_guest()
    )

async def cmd_logout(update, ctx):
    await do_logout(update, ctx)

# ════════════════════════════════════════════════════════════
# STUDENT — MARKS
# ════════════════════════════════════════════════════════════
async def show_marks(update, ctx):
    cid = update.effective_chat.id
    if not is_student(cid):
        await update.message.reply_text("❌ Please login first.", reply_markup=kb_guest()); return
    s   = sess(cid)
    msg = await update.message.reply_text("📊 Loading marks...")
    res = await api('getMarks', {'studentId': s['studentId']})
    if not res.get('success') or not res.get('marks'):
        await msg.edit_text("📊 No marks available yet."); return
    reply = "📊 *Your Marks*\n\n"
    for m in res['marks']:
        total = float(m.get('weightedTotal', 0))
        g     = grade(total)
        reply += f"📚 *{m.get('courseName','—')}* ({m.get('courseCode','')})\n"
        for a in m.get('assessments', []):
            sc = a.get('score')
            mx = a.get('maxScore','?')
            reply += f"  • {a['name']} ({a['weight']}%): {f'{sc}/{mx}' if sc is not None else '—'}\n"
        reply += f"  📈 *Total: {total}% — {g}*\n\n"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# STUDENT — NOTICES
# ════════════════════════════════════════════════════════════
async def show_notices(update, ctx):
    msg = await update.message.reply_text("📣 Loading...")
    res = await api('getNotices')
    notices = list(reversed(res.get('notices', [])))[:5]
    if not notices:
        await msg.edit_text("📣 No notices yet."); return
    reply = "📣 *Latest Notices*\n\n"
    for n in notices:
        title = n.get('Title', n.get('title','Notice'))
        body  = n.get('Message', n.get('message',''))
        ts    = (n.get('Timestamp', n.get('timestamp','')) or '')[:10]
        reply += f"*{title}*\n📅 {ts}\n{body[:200]}{'...' if len(body)>200 else ''}\n\n"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# STUDENT — ONLINE TESTS
# ════════════════════════════════════════════════════════════
async def show_tests(update, ctx):
    cid = update.effective_chat.id
    if not is_student(cid):
        await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("📝 Loading courses...")
    res = await api('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📝 No courses."); return
    btns = [[InlineKeyboardButton(c['courseName'], callback_data=f"test_{c['courseId']}")]
            for c in courses]
    await msg.edit_text("📝 *Select course for test:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(btns))

# ════════════════════════════════════════════════════════════
# STUDENT — LECTURE NOTES
# ════════════════════════════════════════════════════════════
async def show_notes(update, ctx):
    msg = await update.message.reply_text("📚 Loading courses...")
    res = await api('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📚 No courses."); return
    btns = [[InlineKeyboardButton(c['courseName'], callback_data=f"notes_{c['courseId']}")]
            for c in courses]
    await msg.edit_text("📚 *Select course for notes:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(btns))

# ════════════════════════════════════════════════════════════
# STUDENT — COMPLAINTS
# ════════════════════════════════════════════════════════════
async def show_complaints(update, ctx):
    cid = update.effective_chat.id
    if not is_student(cid):
        await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    s   = sess(cid)
    msg = await update.message.reply_text("📬 Loading...")
    res = await api('getComplaints')
    mine = [c for c in res.get('complaints',[])
            if str(c.get('StudentID',c.get('studentId',''))).strip() == str(s['studentId']).strip()]
    if not mine:
        await msg.edit_text("📬 No complaints on record.\n\nTo raise one, visit the portal → My Marks."); return
    reply = "📬 *Your Complaints*\n\n"
    icons = {'Pending':'⏳','Resolved':'✅','Rejected':'❌','Accepted':'👍'}
    for c in reversed(mine[-5:]):
        st   = c.get('Status', c.get('status','Pending'))
        tp   = c.get('Type',   c.get('type','—'))
        resp = c.get('Response', c.get('response',''))
        ts   = (c.get('Timestamp', c.get('timestamp','')) or '')[:10]
        reply += f"{icons.get(st,'⏳')} *{st}* — {tp} | {ts}\n"
        if resp: reply += f"💬 {resp[:100]}\n"
        reply += "\n"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# STUDENT — CHATBOT
# ════════════════════════════════════════════════════════════
async def start_chatbot(update, ctx):
    cid = update.effective_chat.id
    sess(cid)['step'] = 'chatbot'
    await update.message.reply_text(
        "🤖 *Chatbot Mode*\nAsk me anything! Send /start to exit.",
        parse_mode='Markdown'
    )

async def do_chatbot(update, ctx, text):
    cid = update.effective_chat.id
    await ctx.bot.send_chat_action(chat_id=cid, action='typing')
    res = await api('chatbot', {'message': text, 'studentId': sess(cid).get('studentId','')})
    reply = res.get('reply','I could not process that.').replace('**','*')
    await update.message.reply_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# STUDENT — PROFILE
# ════════════════════════════════════════════════════════════
async def show_profile(update, ctx):
    cid = update.effective_chat.id
    if not is_student(cid):
        await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    s   = sess(cid)
    u   = update.effective_user
    await update.message.reply_text(
        f"👤 *My Profile*\n\n"
        f"🆔 Student ID: `{s['studentId']}`\n"
        f"👤 Name: {s['name']}\n"
        f"📱 Telegram: @{u.username or '—'}\n"
        f"✅ Status: Logged in\n\n"
        f"[Open Portal]({PORTAL_URL})",
        parse_mode='Markdown'
    )

async def show_portal(update, ctx):
    await update.message.reply_text(
        f"🔗 *Student Portal*\n\n{PORTAL_URL}\n\nLogin with your Student ID and password.",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — DASHBOARD
# ════════════════════════════════════════════════════════════
async def instr_dashboard(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid):
        await update.message.reply_text("❌ Login as instructor first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("📊 Loading dashboard...")
    res = await api('getDashboard')
    if not res.get('success'):
        await msg.edit_text("❌ Could not load dashboard."); return
    courses = res.get('courses', [])
    reply   = (
        f"📊 *Instructor Dashboard*\n\n"
        f"👥 Total Students: *{res.get('totalStudents','—')}*\n"
        f"📚 Courses: *{len(courses)}*\n"
        f"📬 Pending Complaints: *{res.get('pendingComplaints','—')}*\n"
        f"📈 Class Average: *{res.get('avgScore','—')}%*\n\n"
        f"*Course Summary:*\n"
    )
    for c in courses:
        avg = c.get('avgScore')
        reply += f"• {c['courseName'][:35]} — Avg: {avg+'%' if avg else '—'}\n"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — STUDENTS LIST
# ════════════════════════════════════════════════════════════
async def instr_students(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("👥 Loading students...")
    res = await api('getAllStudents')
    students = res.get('students', [])
    if not students:
        await msg.edit_text("👥 No students found."); return
    reply = f"👥 *All Students ({len(students)})*\n\n"
    for i, s in enumerate(students[:20], 1):
        sid  = s.get('ID','—')
        name = s.get('Name','—')
        reply += f"{i}. `{sid}` — {name}\n"
    if len(students) > 20:
        reply += f"\n_...and {len(students)-20} more. View all on portal._"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — UPLOAD MARKS (CSV per course)
# ════════════════════════════════════════════════════════════
async def instr_upload_marks(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("📤 Loading courses...")
    res = await api('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("📤 No courses. Add courses on the portal first."); return
    btns = [[InlineKeyboardButton(c['courseName'], callback_data=f"umarks_{c['courseId']}")]
            for c in courses]
    btns.append([InlineKeyboardButton('📋 Download Template', callback_data='marks_template')])
    await msg.edit_text(
        "📤 *Upload Marks*\n\nSelect a course to upload marks for:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def handle_umarks_course(update, ctx, course_id):
    cid   = update.effective_chat.id
    query = update.callback_query
    await query.answer()

    # Load assessments for this course
    res   = await api('getCourseAssessments', {'courseId': course_id})
    assms = res.get('assessments', [])
    if not assms:
        await query.edit_message_text(
            "⚠️ No assessments defined for this course.\n\nAdd assessments on the portal first.",
            reply_markup=kb_back()
        ); return

    # Store in session
    s = sess(cid)
    s['data']['upload_courseId']  = course_id
    s['data']['upload_assms']     = assms
    s['step'] = 'await_bulk_csv'

    assm_list = '\n'.join([f"  • {a['name']} (ID: {a['assessmentId']}, Max: {a['maxScore']})" for a in assms])
    template  = 'StudentID,' + ','.join([a['name'] for a in assms]) + '\n'
    template += 'ETS0001/14,' + ','.join(['85'] * len(assms))

    await query.edit_message_text(
        f"📤 *Upload Marks — CSV Format*\n\n"
        f"*Available Assessments:*\n{assm_list}\n\n"
        f"*Paste CSV data below:*\n"
        f"`{template}`\n\n"
        f"First row (header) will be skipped.\n"
        f"Columns must match assessment names exactly.\n\n"
        f"Send your CSV data now:",
        parse_mode='Markdown'
    )

async def do_bulk_csv(update, ctx, text):
    cid = update.effective_chat.id
    s   = sess(cid)
    s['step'] = 'idle'

    course_id = s['data'].get('upload_courseId')
    assms     = s['data'].get('upload_assms', [])

    if not course_id or not assms:
        await update.message.reply_text("❌ Session expired. Try again.", reply_markup=kb_instructor()); return

    msg   = await update.message.reply_text("⏳ Processing CSV...")
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        await msg.edit_text("❌ No data found."); return

    # Parse header
    header = [h.strip() for h in lines[0].split(',')]
    is_header = header[0].lower() in ['studentid','student_id','id','student id']
    data_lines = lines[1:] if is_header else lines

    if not data_lines:
        await msg.edit_text("❌ No data rows found."); return

    # Map assessment names to IDs
    assm_map = {a['name'].lower(): a for a in assms}
    col_assms = []
    if is_header:
        for col in header[1:]:
            matched = assm_map.get(col.strip().lower())
            col_assms.append(matched)
    else:
        col_assms = assms  # use order

    saved = 0; failed = 0; errors = []
    for line in data_lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 2: continue
        student_id = parts[0]
        for i, score_str in enumerate(parts[1:]):
            if i >= len(col_assms): break
            assm = col_assms[i]
            if not assm: continue
            try:
                score = float(score_str)
                max_s = float(assm['maxScore'])
                if score < 0 or score > max_s:
                    errors.append(f"{student_id}/{assm['name']}: score {score} out of range")
                    failed += 1; continue
                res = await api('updateMark', {
                    'courseId':     course_id,
                    'assessmentId': assm['assessmentId'],
                    'studentId':    student_id,
                    'score':        score
                })
                if res.get('success'): saved += 1
                else: failed += 1; errors.append(f"{student_id}: {res.get('message','')}")
            except:
                failed += 1; errors.append(f"{student_id}: invalid score '{score_str}'")

    reply = f"📤 *Upload Complete!*\n\n✅ Saved: {saved}\n❌ Failed: {failed}\n"
    if errors[:3]:
        reply += "\n*Errors (first 3):*\n" + '\n'.join(errors[:3])
    await msg.edit_text(reply, parse_mode='Markdown')
    await update.message.reply_text("Back to menu:", reply_markup=kb_instructor())

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — COMPLAINTS
# ════════════════════════════════════════════════════════════
async def instr_complaints(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("📬 Loading complaints...")
    res = await api('getComplaints')
    all_c   = res.get('complaints', [])
    pending = [c for c in all_c if (c.get('Status',c.get('status','')) == 'Pending')]
    if not pending:
        await msg.edit_text("📬 No pending complaints. ✅"); return

    reply = f"📬 *Pending Complaints ({len(pending)})*\n\n"
    btns  = []
    for c in pending[:5]:
        sid  = c.get('StudentID', c.get('studentId','—'))
        tp   = c.get('Type',      c.get('type','—'))
        ts   = (c.get('Timestamp',c.get('timestamp','')) or '')[:10]
        reply += f"👤 *{sid}* — {tp} | {ts}\n"
        reply += f"_{(c.get('Message',c.get('message','')) or '')[:80]}_\n\n"
        ts_key = c.get('Timestamp', c.get('timestamp',''))
        btns.append([
            InlineKeyboardButton(f"✅ Resolve {sid}", callback_data=f"resolve_{sid}_{ts_key[:19]}"),
            InlineKeyboardButton(f"❌ Reject {sid}",  callback_data=f"reject_{sid}_{ts_key[:19]}")
        ])
    if len(pending) > 5:
        reply += f"_...{len(pending)-5} more on portal_"
    await msg.edit_text(reply, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(btns) if btns else None)

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — SEND NOTICE
# ════════════════════════════════════════════════════════════
async def instr_send_notice(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    sess(cid)['step'] = 'await_notice_title'
    await update.message.reply_text(
        "📣 *Send Notice*\n\nEnter the *notice title*:",
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )

async def do_notice_title(update, ctx, text):
    cid = update.effective_chat.id
    sess(cid)['data']['notice_title'] = text
    sess(cid)['step'] = 'await_notice_msg'
    await update.message.reply_text("✏️ Now enter the *notice message*:", parse_mode='Markdown')

async def do_notice_msg(update, ctx, text):
    cid   = update.effective_chat.id
    s     = sess(cid)
    title = s['data'].get('notice_title','Notice')
    s['step'] = 'idle'
    msg = await update.message.reply_text("📣 Sending notice...")
    res = await api('sendNotice', {'title': title, 'message': text, 'category': 'General'})
    if res.get('success'):
        await msg.edit_text(f"✅ *Notice sent to all students!*\n\n*{title}*", parse_mode='Markdown')
    else:
        await msg.edit_text(f"❌ Failed: {res.get('message','')}")
    await update.message.reply_text("Back to menu:", reply_markup=kb_instructor())

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — LECTURE NOTES
# ════════════════════════════════════════════════════════════
async def instr_notes(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("📚 Loading notes...")
    res = await api('getLectureNotes')
    notes = res.get('notes', [])
    if not notes:
        await msg.edit_text("📚 No notes uploaded yet.\n\nUpload notes on the portal."); return
    reply = f"📚 *Uploaded Notes ({len(notes)})*\n\n"
    for n in notes[:10]:
        title = n.get('Topic_Title', n.get('topicTitle','Untitled'))
        url   = n.get('Resource_URL', n.get('resourceUrl',''))
        reply += f"• [{title}]({url})\n"
    if len(notes) > 10:
        reply += f"\n_...{len(notes)-10} more on portal_"
    await msg.edit_text(reply, parse_mode='Markdown', disable_web_page_preview=True)

# ════════════════════════════════════════════════════════════
# INSTRUCTOR — ASSESSMENTS
# ════════════════════════════════════════════════════════════
async def instr_assessments(update, ctx):
    cid = update.effective_chat.id
    if not is_instructor(cid): await update.message.reply_text("❌ Login first.", reply_markup=kb_guest()); return
    msg = await update.message.reply_text("⚖️ Loading courses...")
    res = await api('getCourses')
    courses = res.get('courses', [])
    if not courses:
        await msg.edit_text("⚖️ No courses. Add on portal first."); return
    reply = "⚖️ *Assessment Weights*\n\n"
    for c in courses:
        ar = await api('getCourseAssessments', {'courseId': c['courseId']})
        assms = ar.get('assessments', [])
        total = sum(float(a.get('weight',0)) for a in assms)
        reply += f"*{c['courseName']}*\n"
        if assms:
            for a in assms:
                reply += f"  • {a['name']}: {a['weight']}% (max {a['maxScore']})\n"
            reply += f"  Total weight: {'✅' if total==100 else '⚠️'} {total}%\n"
        else:
            reply += "  _No assessments defined_\n"
        reply += "\n"
    await msg.edit_text(reply, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ════════════════════════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    cid   = update.effective_chat.id
    await query.answer()

    if data == 'back':
        kb = kb_student() if is_student(cid) else kb_instructor() if is_instructor(cid) else kb_guest()
        await query.edit_message_text("Main menu:")
        await ctx.bot.send_message(cid, "Use menu:", reply_markup=kb)
        return

    if data == 'marks_template':
        res = await api('getCourses')
        courses = res.get('courses', [])
        tmpl = ""
        for c in courses:
            ar    = await api('getCourseAssessments', {'courseId': c['courseId']})
            assms = ar.get('assessments', [])
            if assms:
                tmpl += f"# {c['courseName']} ({c.get('courseCode','')})\n"
                tmpl += 'StudentID,' + ','.join(a['name'] for a in assms) + '\n'
                tmpl += 'ETS0001/14,' + ','.join('0' for _ in assms) + '\n\n'
        await query.edit_message_text(
            f"📋 *CSV Template:*\n\n```\n{tmpl[:1500]}\n```\nCopy, fill in scores, send back.",
            parse_mode='Markdown'
        )
        return

    if data.startswith('umarks_'):
        course_id = data.replace('umarks_', '')
        await handle_umarks_course(update, ctx, course_id)
        return

    if data.startswith('test_'):
        course_id = data.replace('test_', '')
        await start_test(update, ctx, course_id)
        return

    if data.startswith('notes_'):
        course_id = data.replace('notes_', '')
        await load_notes_for_course(update, ctx, course_id)
        return

    if data.startswith('ans_'):
        await handle_test_callback_answer(update, ctx, data)
        return

    if data == 'test_submit':
        await finish_test(update, ctx)
        return

    if data.startswith('resolve_') or data.startswith('reject_'):
        parts   = data.split('_', 2)
        action  = parts[0]
        sid     = parts[1]
        ts      = parts[2] if len(parts) > 2 else ''
        status  = 'Resolved' if action == 'resolve' else 'Rejected'
        default = 'Mark reviewed and resolved.' if status=='Resolved' else 'Mark is correct.'
        res = await api('resolveComplaint', {'studentId': sid, 'timestamp': ts,
                                              'status': status, 'response': default})
        if res.get('success'):
            await query.edit_message_text(f"{'✅' if status=='Resolved' else '❌'} Complaint *{status}* for `{sid}`.",
                parse_mode='Markdown')
        else:
            await query.edit_message_text(f"❌ Failed: {res.get('message','')}")
        return

# ════════════════════════════════════════════════════════════
# ONLINE TEST FLOW
# ════════════════════════════════════════════════════════════
async def start_test(update, ctx, course_id):
    cid   = update.effective_chat.id
    query = update.callback_query
    await query.edit_message_text("📝 Loading questions...")
    res   = await api('getOnlineTests', {'courseId': course_id})
    qs    = res.get('questions', [])
    if not qs:
        await query.edit_message_text("📭 No questions for this course yet.", reply_markup=kb_back()); return
    s = sess(cid)
    s.update({'step':'test_q', 'data': {**s['data'],
        'tqs': qs, 'tcourse': course_id, 'tnum': 0, 'tans': {}}})
    await send_test_q(query.message, ctx, cid, edit=True)

async def send_test_q(message, ctx, cid, edit=False):
    s   = sess(cid)
    qs  = s['data']['tqs']
    num = s['data']['tnum']
    if num >= len(qs):
        await finish_test_msg(message, ctx, cid, edit); return
    q   = qs[num]
    txt = (f"📝 *Q{num+1}/{len(qs)}* | Answered: {len(s['data']['tans'])}/{len(qs)}\n\n"
           f"{q['question']}\n\n"
           f"🅰 {q['optionA']}\n🅱 {q['optionB']}\n🅲 {q['optionC']}\n🅳 {q['optionD']}")
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton('A',callback_data='ans_A'), InlineKeyboardButton('B',callback_data='ans_B')],
        [InlineKeyboardButton('C',callback_data='ans_C'), InlineKeyboardButton('D',callback_data='ans_D')],
        [InlineKeyboardButton('⏭ Skip',callback_data='ans_skip'), InlineKeyboardButton('📤 Submit',callback_data='test_submit')]
    ])
    if edit:
        await message.edit_text(txt, parse_mode='Markdown', reply_markup=kb)
    else:
        await message.reply_text(txt, parse_mode='Markdown', reply_markup=kb)

async def handle_test_callback_answer(update, ctx, data):
    cid   = update.effective_chat.id
    query = update.callback_query
    s     = sess(cid)
    ans   = data.replace('ans_','')
    if ans != 'skip' and ans in ['A','B','C','D']:
        s['data']['tans'][s['data']['tnum']] = ans
    s['data']['tnum'] = s['data'].get('tnum',0) + 1
    await send_test_q(query.message, ctx, cid, edit=True)

async def finish_test(update, ctx):
    cid   = update.effective_chat.id
    query = update.callback_query
    await finish_test_msg(query.message, ctx, cid, edit=True)

async def finish_test_msg(message, ctx, cid, edit=False):
    s      = sess(cid)
    qs     = s['data'].get('tqs', [])
    ans    = s['data'].get('tans', {})
    course = s['data'].get('tcourse','')
    total  = len(qs)
    done   = len(ans)
    pct    = round((done/total)*100) if total else 0
    s['step'] = 'idle'
    await api('submitTestResult', {
        'studentId': s.get('studentId',''),
        'courseId': course, 'score': done, 'total': total
    })
    txt = (f"🎉 *Test Submitted!*\n\nAnswered: {done}/{total}\nScore: {pct}% — {grade(pct)}\n\n"
           f"Your instructor will review results.")
    if edit: await message.edit_text(txt, parse_mode='Markdown')
    else:    await message.reply_text(txt, parse_mode='Markdown', reply_markup=kb_student())

async def do_test_step(update, ctx, text, step):
    if text.upper() in ['A','B','C','D']:
        cid = update.effective_chat.id
        s   = sess(cid)
        s['data']['tans'][s['data']['tnum']] = text.upper()
        s['data']['tnum'] += 1
        await send_test_q(update.message, ctx, cid)

# ════════════════════════════════════════════════════════════
# NOTES FOR COURSE
# ════════════════════════════════════════════════════════════
async def load_notes_for_course(update, ctx, course_id):
    query = update.callback_query
    await query.edit_message_text("📚 Loading notes...")
    res   = await api('getLectureNotes', {'courseId': course_id})
    notes = res.get('notes', [])
    if not notes:
        await query.edit_message_text("📭 No notes for this course yet.", reply_markup=kb_back()); return
    reply = "📚 *Lecture Notes*\n\n"
    icons = {'PDF':'📄','Word':'📝','PPT':'📊','Video':'🎥','Link':'🔗'}
    for n in notes[:10]:
        title = n.get('Topic_Title', n.get('topicTitle','Untitled'))
        url   = n.get('Resource_URL', n.get('resourceUrl',''))
        ftype = n.get('FileType', n.get('fileType','File'))
        reply += f"{icons.get(ftype,'📁')} [{title}]({url})\n"
    await query.edit_message_text(reply, parse_mode='Markdown',
        reply_markup=kb_back(), disable_web_page_preview=True)

# ════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ════════════════════════════════════════════════════════════
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if update.effective_user.id != ADMIN_ID and not is_instructor(cid):
        await update.message.reply_text("❌ Admin only."); return
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton('📊 Dashboard',      callback_data='adm_dash')],
        [InlineKeyboardButton('👥 All Students',   callback_data='adm_students')],
        [InlineKeyboardButton('📬 All Complaints', callback_data='adm_complaints')],
        [InlineKeyboardButton('📣 Broadcast',      callback_data='adm_broadcast')],
        [InlineKeyboardButton('📈 System Stats',   callback_data='adm_stats')],
    ])
    await update.message.reply_text("🔧 *Admin Panel*", parse_mode='Markdown', reply_markup=btns)

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID and not is_instructor(update.effective_chat.id):
        await update.message.reply_text("❌ Admin only."); return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast Your message here"); return
    msg    = ' '.join(ctx.args)
    status = await update.message.reply_text("📣 Broadcasting...")
    res    = await api('sendNotice', {'title': 'Broadcast', 'message': msg, 'category': 'General'})
    await status.edit_text(f"{'✅ Broadcast sent!' if res.get('success') else '❌ Failed: ' + res.get('message','')}")

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID and not is_instructor(update.effective_chat.id):
        await update.message.reply_text("❌ Admin only."); return
    res     = await api('getDashboard')
    linked  = sum(1 for s in sessions.values() if s.get('loggedIn'))
    today   = datetime.now().strftime('%Y-%m-%d %H:%M')
    await update.message.reply_text(
        f"📈 *System Stats*\n\n"
        f"👥 Students: {res.get('totalStudents','—')}\n"
        f"📚 Courses: {len(res.get('courses',[]))}\n"
        f"📬 Pending: {res.get('pendingComplaints','—')}\n"
        f"📱 Active sessions: {linked}\n"
        f"📅 {today}",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    if 'YOUR_BOT_TOKEN' in BOT_TOKEN:
        logger.error("❌ Set BOT_TOKEN!"); return
    if 'YOUR_APPS_SCRIPT' in API_URL:
        logger.error("❌ Set API_URL!"); return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start',     cmd_start))
    app.add_handler(CommandHandler('help',      cmd_help))
    app.add_handler(CommandHandler('logout',    cmd_logout))
    app.add_handler(CommandHandler('marks',     show_marks))
    app.add_handler(CommandHandler('notices',   show_notices))
    app.add_handler(CommandHandler('tests',     show_tests))
    app.add_handler(CommandHandler('notes',     show_notes))
    app.add_handler(CommandHandler('complaints',show_complaints))
    app.add_handler(CommandHandler('profile',   show_profile))
    app.add_handler(CommandHandler('admin',     cmd_admin))
    app.add_handler(CommandHandler('broadcast', cmd_broadcast))
    app.add_handler(CommandHandler('stats',     cmd_stats))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("🤖 Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
PYEOF




