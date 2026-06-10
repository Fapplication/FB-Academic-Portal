// ============================================================
// Code.gs — Google Apps Script Backend
// Civil Engineering Student Portal + Telegram Bot API
// Deploy: Web App → Execute as Me → Access: Anyone
// ============================================================

const ss = SpreadsheetApp.getActiveSpreadsheet();

// ── Admin credentials (change before deploying) ───────────────
const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = hashStr('admin123');

// ── Telegram Bot Token (for OTP sending) ──────────────────────
const TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN';

// ════════════════════════════════════════════════════════════
// ROUTER
// ════════════════════════════════════════════════════════════
function doGet(e)  { return route(e); }
function doPost(e) { return route(e); }

function route(e) {
  const p      = e.parameter || {};
  let   post   = {};
  try { if (e.postData) post = JSON.parse(e.postData.contents || '{}'); } catch(_) {}
  const data   = Object.assign({}, post, p);
  const action = data.action;
  let   result;

  try {
    switch (action) {
      // ── AUTH
      case 'checkAuthorizedID': result = checkAuthorizedID(data); break;
      case 'sendOTP':           result = sendOTP(data);           break;
      case 'verifyOTP':         result = verifyOTP(data);         break;
      case 'registerStudent':   result = registerStudent(data);   break;
      case 'loginStudent':      result = loginStudent(data);      break;
      case 'loginInstructor':   result = loginInstructor(data);   break;
      case 'resetPassword':     result = resetPassword(data);     break;

      // ── STUDENT
      case 'getMarks':          result = getMarks(data);          break;
      case 'submitComplaint':   result = submitComplaint(data);   break;
      case 'getLectureNotes':   result = getLectureNotes(data);   break;
      case 'getOnlineTests':    result = getOnlineTests(data);    break;
      case 'submitTestResult':  result = submitTestResult(data);  break;
      case 'chatbot':           result = chatbot(data);           break;
      case 'getNotices':        result = getNotices(data);        break;

      // ── COURSES & ASSESSMENTS (dynamic)
      case 'getCourses':            result = getCourses(data);            break;
      case 'addCourse':             result = addCourse(data);             break;
      case 'deleteCourse':          result = deleteCourse(data);          break;
      case 'getCourseAssessments':  result = getCourseAssessments(data);  break;
      case 'addAssessment':         result = addAssessment(data);         break;
      case 'deleteAssessment':      result = deleteAssessment(data);      break;

      // ── INSTRUCTOR
      case 'getDashboard':      result = getDashboard(data);      break;
      case 'getAllStudents':     result = getAllStudents(data);    break;
      case 'getStudentMarks':   result = getStudentMarks(data);  break;
      case 'updateMark':        result = updateMark(data);        break;
      case 'uploadQuestion':    result = uploadQuestion(data);    break;
      case 'deleteQuestion':    result = deleteQuestion(data);    break;
      case 'uploadLectureNote': result = uploadLectureNote(data); break;
      case 'deleteLectureNote': result = deleteLectureNote(data); break;
      case 'sendNotice':        result = sendNotice(data);        break;
      case 'getComplaints':     result = getComplaints(data);     break;
      case 'resolveComplaint':  result = resolveComplaint(data);  break;
      case 'getAuthorizedIDs':  result = getAuthorizedIDs(data);  break;
      case 'addAuthorizedID':   result = addAuthorizedID(data);   break;
      case 'getTestResults':    result = getTestResults(data);    break;

      // ── TELEGRAM BOT WEBHOOK
      case 'telegramWebhook':   result = telegramWebhook(data);   break;

      default: result = { success: false, message: 'Unknown action: ' + action };
    }
  } catch(err) {
    result = { success: false, message: err.message };
  }

  const out = ContentService.createTextOutput(JSON.stringify(result));
  out.setMimeType(ContentService.MimeType.JSON);
  return out;
}

// ════════════════════════════════════════════════════════════
// HELPERS
// ════════════════════════════════════════════════════════════
function getSheet(name) {
  const sh = ss.getSheetByName(name);
  if (!sh) throw new Error('Sheet not found: ' + name);
  return sh;
}

function getOrCreateSheet(name, headers) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(headers);
  }
  return sh;
}

function sheetToObjects(sh) {
  const data = sh.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  return data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = row[i]; });
    return obj;
  });
}

function hashStr(str) {
  return Utilities.base64Encode(
    Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(str))
  );
}

function genId() {
  return Utilities.getUuid().replace(/-/g,'').substring(0,12);
}

function nowStr() {
  return new Date().toISOString();
}

// ════════════════════════════════════════════════════════════
// OTP — Send via Telegram first, Email fallback
// ════════════════════════════════════════════════════════════
function sendOtpToUser(studentId, otp) {
  const users  = sheetToObjects(getOrCreateSheet('Users',
    ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']));
  const user   = users.find(u => String(u['ID']).trim() === String(studentId).trim());
  if (!user) return { sent: false, message: 'Student not found.' };

  const tgUser = (user['Telegram_Username'] || '').trim().replace('@','');
  const email  = (user['Email'] || '').trim();

  // Try Telegram first
  if (tgUser && TELEGRAM_BOT_TOKEN !== 'YOUR_TELEGRAM_BOT_TOKEN') {
    try {
      // Get chat_id from Bot_Sessions
      const sessions = sheetToObjects(getOrCreateSheet('Bot_Sessions',
        ['ChatID','StudentID','Status','Step']));
      const session  = sessions.find(s =>
        String(s['StudentID']).trim() === String(studentId).trim()
      );
      if (session && session['ChatID']) {
        const url  = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
        const payload = {
          chat_id: session['ChatID'],
          text: `🔑 Your OTP code is: *${otp}*\n\nThis code expires in 10 minutes.\n\nIf you did not request this, ignore this message.`,
          parse_mode: 'Markdown'
        };
        UrlFetchApp.fetch(url, {
          method: 'POST',
          contentType: 'application/json',
          payload: JSON.stringify(payload)
        });
        return { sent: true, via: 'telegram', contact: tgUser };
      }
    } catch(err) {
      Logger.log('Telegram OTP error: ' + err.message);
    }
  }

  // Fallback: Email
  if (email) {
    try {
      MailApp.sendEmail({
        to: email,
        subject: 'Your Password Reset OTP – Civil Eng. Portal',
        body: `Your OTP code is: ${otp}\n\nThis code expires in 10 minutes.\n\nIf you did not request this, ignore this message.`
      });
      return { sent: true, via: 'email', contact: email.replace(/(.{2}).+(@.+)/, '$1***$2') };
    } catch(err) {
      Logger.log('Email OTP error: ' + err.message);
    }
  }

  return { sent: false, message: 'No Telegram or Email on file. Contact your instructor.' };
}

// ════════════════════════════════════════════════════════════
// AUTH
// ════════════════════════════════════════════════════════════
function checkAuthorizedID(data) {
  const sh   = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  const rows = sheetToObjects(sh);
  const found= rows.find(r => String(r['ID']).trim() === String(data.studentId).trim());
  if (!found) return { success: false, message: 'Student ID not found in authorized list.' };

  const users    = sheetToObjects(getOrCreateSheet('Users',
    ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']));
  const registered = users.find(u => String(u['ID']).trim() === String(data.studentId).trim());
  return { success: true, name: found['Name'], alreadyRegistered: !!registered };
}

function sendOTP(data) {
  const studentId = String(data.studentId || '').trim();
  const purpose   = data.purpose || 'RESET';

  // Check student exists in Users (for reset) or Authorized_IDs (for register)
  if (purpose === 'RESET') {
    const users = sheetToObjects(getOrCreateSheet('Users',
      ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']));
    const user  = users.find(u => String(u['ID']).trim() === studentId);
    if (!user) return { success: false, message: 'Student ID not registered.' };
  }

  const otp = String(Math.floor(100000 + Math.random() * 900000));

  // Save OTP
  const sh   = getOrCreateSheet('OTP_Verification', ['Student_ID','OTP_Code','Timestamp','Purpose']);
  const data2= sh.getDataRange().getValues();
  // Delete old OTPs for this student
  for (let i = data2.length - 1; i >= 1; i--) {
    if (String(data2[i][0]).trim() === studentId) sh.deleteRow(i + 1);
  }
  sh.appendRow([studentId, otp, nowStr(), purpose]);

  const result = sendOtpToUser(studentId, otp);
  if (!result.sent) return { success: false, message: result.message };

  return { success: true, message: 'OTP sent.', sentVia: result.via, contact: result.contact };
}

function verifyOTP(data) {
  const sh   = getOrCreateSheet('OTP_Verification', ['Student_ID','OTP_Code','Timestamp','Purpose']);
  const rows = sheetToObjects(sh);
  const rec  = rows.find(r =>
    String(r['Student_ID']).trim() === String(data.studentId).trim() &&
    String(r['OTP_Code']).trim()   === String(data.otp).trim()
  );
  if (!rec) return { success: false, message: 'Invalid OTP.' };
  const age = (new Date() - new Date(rec['Timestamp'])) / 1000 / 60;
  if (age > 10) return { success: false, message: 'OTP expired. Please request a new one.' };
  return { success: true };
}

function registerStudent(data) {
  const sh     = getOrCreateSheet('Users',
    ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']);
  const rows   = sheetToObjects(sh);
  const exists = rows.find(u => String(u['ID']).trim() === String(data.studentId).trim());
  if (exists) return { success: false, message: 'Student already registered.' };

  const authSh = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  const authRows = sheetToObjects(authSh);
  const auth   = authRows.find(r => String(r['ID']).trim() === String(data.studentId).trim());
  if (!auth) return { success: false, message: 'Student ID not authorized.' };

  sh.appendRow([
    data.studentId,
    hashStr(data.password),
    auth['Name'],
    data.email            || auth['Email']             || '',
    data.telegramUsername || auth['Telegram_Username'] || '',
    'student',
    nowStr()
  ]);
  return { success: true, message: 'Registration successful!' };
}

function loginStudent(data) {
  const sh   = getOrCreateSheet('Users',
    ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']);
  const rows = sheetToObjects(sh);
  const user = rows.find(u =>
    String(u['ID']).trim() === String(data.studentId).trim() &&
    u['Password']          === hashStr(data.password)
  );
  if (!user) return { success: false, message: 'Invalid Student ID or password.' };
  return { success: true, name: user['Name'], studentId: user['ID'] };
}

function loginInstructor(data) {
  if (data.username === ADMIN_USERNAME && hashStr(data.password) === ADMIN_PASSWORD) {
    return { success: true, name: 'Instructor', role: 'instructor' };
  }
  return { success: false, message: 'Invalid credentials.' };
}

function resetPassword(data) {
  const check = verifyOTP(data);
  if (!check.success) return check;

  const sh   = getOrCreateSheet('Users',
    ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']);
  const vals = sh.getDataRange().getValues();
  const hdrs = vals[0];
  const idIdx= hdrs.indexOf('ID');
  const pwIdx= hdrs.indexOf('Password');

  for (let i = 1; i < vals.length; i++) {
    if (String(vals[i][idIdx]).trim() === String(data.studentId).trim()) {
      sh.getRange(i + 1, pwIdx + 1).setValue(hashStr(data.newPassword));
      return { success: true, message: 'Password reset successfully.' };
    }
  }
  return { success: false, message: 'Student not found.' };
}

// ════════════════════════════════════════════════════════════
// COURSES (Dynamic)
// ════════════════════════════════════════════════════════════
function getCourses(data) {
  const sh   = getOrCreateSheet('Courses', ['Course_ID','Course_Name','Course_Code','CreatedAt']);
  const rows = sheetToObjects(sh);
  return {
    success: true,
    courses: rows.map(r => ({
      courseId:   r['Course_ID'],
      courseName: r['Course_Name'],
      courseCode: r['Course_Code'],
      createdAt:  r['CreatedAt']
    }))
  };
}

function addCourse(data) {
  if (!data.courseName) return { success: false, message: 'Course name required.' };
  const sh  = getOrCreateSheet('Courses', ['Course_ID','Course_Name','Course_Code','CreatedAt']);
  const id  = genId();
  sh.appendRow([id, data.courseName, data.courseCode || '', nowStr()]);
  return { success: true, courseId: id, message: 'Course added.' };
}

function deleteCourse(data) {
  const sh   = getOrCreateSheet('Courses', ['Course_ID','Course_Name','Course_Code','CreatedAt']);
  const vals = sh.getDataRange().getValues();
  for (let i = vals.length - 1; i >= 1; i--) {
    if (String(vals[i][0]) === String(data.courseId)) {
      sh.deleteRow(i + 1);
      return { success: true };
    }
  }
  return { success: false, message: 'Course not found.' };
}

// ════════════════════════════════════════════════════════════
// ASSESSMENTS (Dynamic)
// ════════════════════════════════════════════════════════════
function getCourseAssessments(data) {
  const sh   = getOrCreateSheet('Assessments',
    ['Assessment_ID','Course_ID','Name','Weight','MaxScore','CreatedAt']);
  const rows = sheetToObjects(sh);
  const filtered = rows
    .filter(r => String(r['Course_ID']) === String(data.courseId))
    .map(r => ({
      assessmentId: r['Assessment_ID'],
      courseId:     r['Course_ID'],
      name:         r['Name'],
      weight:       r['Weight'],
      maxScore:     r['MaxScore'],
      createdAt:    r['CreatedAt']
    }));
  return { success: true, assessments: filtered };
}

function addAssessment(data) {
  if (!data.courseId || !data.name || !data.weight || !data.maxScore) {
    return { success: false, message: 'Missing fields.' };
  }
  const sh = getOrCreateSheet('Assessments',
    ['Assessment_ID','Course_ID','Name','Weight','MaxScore','CreatedAt']);
  const id = genId();
  sh.appendRow([id, data.courseId, data.name, Number(data.weight), Number(data.maxScore), nowStr()]);
  return { success: true, assessmentId: id };
}

function deleteAssessment(data) {
  const sh   = getOrCreateSheet('Assessments',
    ['Assessment_ID','Course_ID','Name','Weight','MaxScore','CreatedAt']);
  const vals = sh.getDataRange().getValues();
  for (let i = vals.length - 1; i >= 1; i--) {
    if (String(vals[i][0]) === String(data.assessmentId)) {
      sh.deleteRow(i + 1);
      return { success: true };
    }
  }
  return { success: false, message: 'Assessment not found.' };
}

// ════════════════════════════════════════════════════════════
// MARKS
// ════════════════════════════════════════════════════════════
function getStudentMarks(data) {
  // Returns all students with their marks for a given course
  const authSh = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  const students = sheetToObjects(authSh);

  const marksSh  = getOrCreateSheet('Marks',
    ['StudentID','Course_ID','Assessment_ID','Score','UpdatedAt']);
  const allMarks = sheetToObjects(marksSh);

  const result = students.map(s => {
    const studentMarks = allMarks.filter(m =>
      String(m['StudentID'])  === String(s['ID']) &&
      String(m['Course_ID'])  === String(data.courseId)
    );
    const marksMap = {};
    studentMarks.forEach(m => { marksMap[m['Assessment_ID']] = m['Score']; });
    return { studentId: s['ID'], name: s['Name'], marks: marksMap };
  });

  return { success: true, students: result };
}

function getMarks(data) {
  // Returns all marks for a specific student across all courses
  const coursesSh  = getOrCreateSheet('Courses', ['Course_ID','Course_Name','Course_Code','CreatedAt']);
  const assessSh   = getOrCreateSheet('Assessments',
    ['Assessment_ID','Course_ID','Name','Weight','MaxScore','CreatedAt']);
  const marksSh    = getOrCreateSheet('Marks',
    ['StudentID','Course_ID','Assessment_ID','Score','UpdatedAt']);
  const complaintsSh = getOrCreateSheet('Complaints',
    ['StudentID','Course_ID','Assessment_ID','Type','Message','Status','Timestamp','Response']);

  const courses     = sheetToObjects(coursesSh);
  const assessments = sheetToObjects(assessSh);
  const marks       = sheetToObjects(marksSh);
  const complaints  = sheetToObjects(complaintsSh);

  const result = courses.map(c => {
    const courseAssessments = assessments.filter(a =>
      String(a['Course_ID']) === String(c['Course_ID'])
    );

    const assessData = courseAssessments.map(a => {
      const markRow = marks.find(m =>
        String(m['StudentID'])     === String(data.studentId) &&
        String(m['Course_ID'])     === String(c['Course_ID']) &&
        String(m['Assessment_ID']) === String(a['Assessment_ID'])
      );
      return {
        assessmentId: a['Assessment_ID'],
        name:         a['Name'],
        weight:       Number(a['Weight']),
        maxScore:     Number(a['MaxScore']),
        score:        markRow ? markRow['Score'] : null
      };
    });

    // Weighted total
    let weightedTotal = 0;
    let totalWeight   = 0;
    assessData.forEach(a => {
      if (a.score !== null && a.score !== '' && a.maxScore > 0) {
        weightedTotal += (Number(a.score) / a.maxScore) * a.weight;
        totalWeight   += a.weight;
      }
    });
    const finalTotal = totalWeight > 0
      ? (weightedTotal / totalWeight * totalWeight).toFixed(1)
      : 0;

    // Complaint status
    const complaint = complaints.find(comp =>
      String(comp['StudentID']) === String(data.studentId) &&
      String(comp['Course_ID']) === String(c['Course_ID'])
    );
    const status = complaint
      ? (complaint['Status'] || 'Pending')
      : (assessData.some(a => a.score !== null) ? 'Pending' : null);

    return {
      courseId:          c['Course_ID'],
      courseName:        c['Course_Name'],
      courseCode:        c['Course_Code'],
      assessments:       assessData,
      weightedTotal:     finalTotal,
      status:            status,
      complaintResponse: complaint ? complaint['Response'] : null
    };
  }).filter(c => c.assessments.length > 0);

  return { success: true, marks: result };
}

function updateMark(data) {
  const sh   = getOrCreateSheet('Marks',
    ['StudentID','Course_ID','Assessment_ID','Score','UpdatedAt']);
  const vals = sh.getDataRange().getValues();
  const hdrs = vals[0];

  // Find existing row
  for (let i = 1; i < vals.length; i++) {
    if (
      String(vals[i][hdrs.indexOf('StudentID')])     === String(data.studentId)  &&
      String(vals[i][hdrs.indexOf('Course_ID')])     === String(data.courseId)   &&
      String(vals[i][hdrs.indexOf('Assessment_ID')]) === String(data.assessmentId)
    ) {
      sh.getRange(i + 1, hdrs.indexOf('Score')     + 1).setValue(Number(data.score));
      sh.getRange(i + 1, hdrs.indexOf('UpdatedAt') + 1).setValue(nowStr());
      return { success: true };
    }
  }

  // Insert new row
  sh.appendRow([
    data.studentId, data.courseId, data.assessmentId,
    Number(data.score), nowStr()
  ]);
  return { success: true };
}

// ════════════════════════════════════════════════════════════
// COMPLAINTS
// ════════════════════════════════════════════════════════════
function submitComplaint(data) {
  const sh = getOrCreateSheet('Complaints',
    ['StudentID','Course_ID','Assessment_ID','Type','Message','Status','Timestamp','Response']);

  // If type is 'Accept', just record as Accepted
  const status = data.status || 'Pending';
  sh.appendRow([
    data.studentId, data.courseId, data.assessmentId || '',
    data.type || 'General', data.message || '',
    status, nowStr(), ''
  ]);

  // Notify via Telegram if bot is set up
  if (status === 'Pending' && TELEGRAM_BOT_TOKEN !== 'YOUR_TELEGRAM_BOT_TOKEN') {
    try {
      notifyInstructorComplaint(data);
    } catch(_) {}
  }

  return { success: true };
}

function getComplaints(data) {
  const sh   = getOrCreateSheet('Complaints',
    ['StudentID','Course_ID','Assessment_ID','Type','Message','Status','Timestamp','Response']);
  return { success: true, complaints: sheetToObjects(sh) };
}

function resolveComplaint(data) {
  const sh   = getOrCreateSheet('Complaints',
    ['StudentID','Course_ID','Assessment_ID','Type','Message','Status','Timestamp','Response']);
  const vals = sh.getDataRange().getValues();
  const hdrs = vals[0];
  const sidIdx = hdrs.indexOf('StudentID');
  const tsIdx  = hdrs.indexOf('Timestamp');
  const stIdx  = hdrs.indexOf('Status');
  const resIdx = hdrs.indexOf('Response');

  for (let i = 1; i < vals.length; i++) {
    if (
      String(vals[i][sidIdx]) === String(data.studentId) &&
      String(vals[i][tsIdx])  === String(data.timestamp)
    ) {
      sh.getRange(i+1, stIdx  + 1).setValue(data.status   || 'Resolved');
      sh.getRange(i+1, resIdx + 1).setValue(data.response || '');

      // Notify student via Telegram
      if (TELEGRAM_BOT_TOKEN !== 'YOUR_TELEGRAM_BOT_TOKEN') {
        try { notifyStudentComplaintResolved(data); } catch(_) {}
      }
      return { success: true };
    }
  }
  return { success: false, message: 'Complaint not found.' };
}

// ════════════════════════════════════════════════════════════
// LECTURE NOTES
// ════════════════════════════════════════════════════════════
function getLectureNotes(data) {
  const sh   = getOrCreateSheet('Lecture_Notes',
    ['Note_ID','Course_ID','Topic_Title','Resource_URL','FileType','UploadedAt']);
  const rows = sheetToObjects(sh);
  const filtered = data.courseId
    ? rows.filter(r => String(r['Course_ID']) === String(data.courseId))
    : rows;
  return { success: true, notes: filtered };
}

function uploadLectureNote(data) {
  if (!data.courseId || !data.title || !data.url) {
    return { success: false, message: 'Missing required fields.' };
  }
  const sh = getOrCreateSheet('Lecture_Notes',
    ['Note_ID','Course_ID','Topic_Title','Resource_URL','FileType','UploadedAt']);
  const id = genId();
  sh.appendRow([id, data.courseId, data.title, data.url, data.fileType || 'File', nowStr()]);
  return { success: true, noteId: id };
}

function deleteLectureNote(data) {
  const sh   = getOrCreateSheet('Lecture_Notes',
    ['Note_ID','Course_ID','Topic_Title','Resource_URL','FileType','UploadedAt']);
  const vals = sh.getDataRange().getValues();
  for (let i = vals.length - 1; i >= 1; i--) {
    if (String(vals[i][0]) === String(data.noteId)) {
      sh.deleteRow(i + 1);
      return { success: true };
    }
  }
  return { success: false, message: 'Note not found.' };
}

// ════════════════════════════════════════════════════════════
// ONLINE TESTS
// ════════════════════════════════════════════════════════════
function getOnlineTests(data) {
  const sh   = getOrCreateSheet('Online_Tests',
    ['Question_ID','Course_ID','Question_Text','Option_A','Option_B','Option_C','Option_D','Correct_Answer']);
  const rows = sheetToObjects(sh);
  const filtered = data.courseId
    ? rows.filter(r => String(r['Course_ID']) === String(data.courseId))
    : rows;

  // Strip correct answers before sending to student
  const sanitized = filtered.map(q => ({
    id:       q['Question_ID'],
    courseId: q['Course_ID'],
    question: q['Question_Text'],
    optionA:  q['Option_A'],
    optionB:  q['Option_B'],
    optionC:  q['Option_C'],
    optionD:  q['Option_D']
    // correctAnswer intentionally omitted
  }));
  return { success: true, questions: sanitized };
}

function uploadQuestion(data) {
  if (!data.courseId || !data.question || !data.optionA) {
    return { success: false, message: 'Missing required fields.' };
  }
  const sh = getOrCreateSheet('Online_Tests',
    ['Question_ID','Course_ID','Question_Text','Option_A','Option_B','Option_C','Option_D','Correct_Answer']);
  const id = genId();
  sh.appendRow([
    id, data.courseId, data.question,
    data.optionA, data.optionB, data.optionC, data.optionD,
    data.correctAnswer || 'A'
  ]);
  return { success: true, questionId: id };
}

function deleteQuestion(data) {
  const sh   = getOrCreateSheet('Online_Tests',
    ['Question_ID','Course_ID','Question_Text','Option_A','Option_B','Option_C','Option_D','Correct_Answer']);
  const vals = sh.getDataRange().getValues();
  for (let i = vals.length - 1; i >= 1; i--) {
    if (String(vals[i][0]) === String(data.questionId)) {
      sh.deleteRow(i + 1);
      return { success: true };
    }
  }
  return { success: false, message: 'Question not found.' };
}

function submitTestResult(data) {
  const sh = getOrCreateSheet('Test_Results',
    ['StudentID','Course_ID','Score','Total','Answers','Timestamp']);
  sh.appendRow([
    data.studentId, data.courseId,
    data.score, data.total,
    data.answers || '', nowStr()
  ]);
  return { success: true };
}

function getTestResults(data) {
  const sh   = getOrCreateSheet('Test_Results',
    ['StudentID','Course_ID','Score','Total','Answers','Timestamp']);
  const rows = sheetToObjects(sh);
  const filtered = data.courseId
    ? rows.filter(r => String(r['Course_ID']) === String(data.courseId))
    : rows;
  return { success: true, results: filtered };
}

// ════════════════════════════════════════════════════════════
// NOTICES
// ════════════════════════════════════════════════════════════
function getNotices(data) {
  const sh = getOrCreateSheet('Notices', ['Title','Message','Category','Timestamp','SentBy']);
  return { success: true, notices: sheetToObjects(sh) };
}

function sendNotice(data) {
  if (!data.title || !data.message) {
    return { success: false, message: 'Title and message required.' };
  }
  const sh = getOrCreateSheet('Notices', ['Title','Message','Category','Timestamp','SentBy']);
  sh.appendRow([data.title, data.message, data.category || 'General', nowStr(), 'Instructor']);

  // Broadcast to all Telegram users
  if (TELEGRAM_BOT_TOKEN !== 'YOUR_TELEGRAM_BOT_TOKEN') {
    try { broadcastToTelegram(data.title, data.message); } catch(_) {}
  }
  return { success: true };
}

// ════════════════════════════════════════════════════════════
// CHATBOT
// ════════════════════════════════════════════════════════════
function chatbot(data) {
  const msg = (data.message || '').toLowerCase();
  if (msg.includes('mark') || msg.includes('grade') || msg.includes('score')) {
    return { success: true, reply: '📊 *Viewing Your Marks*\n\nGo to *My Marks* from the sidebar.\n\nYou will see your score for each assessment, weighted total, letter grade, and options to Accept or Raise a Complaint.' };
  }
  if (msg.includes('complaint') || msg.includes('appeal')) {
    return { success: true, reply: '📬 *Submitting a Complaint*\n\nGo to *My Marks* → find the course → click "Raise Complaint".\n\nSelect the assessment, type, and write your message. You can only complain while status is Pending.' };
  }
  if (msg.includes('test') || msg.includes('exam') || msg.includes('quiz')) {
    return { success: true, reply: '📝 *Taking Online Tests*\n\nGo to *Online Tests* from the sidebar.\n\n1. Select your course\n2. Review the intro\n3. Click Start Test\n4. Answer and navigate freely\n5. Submit before the timer ends.' };
  }
  if (msg.includes('note') || msg.includes('lecture') || msg.includes('material')) {
    return { success: true, reply: '📚 *Lecture Notes*\n\nGo to *Lecture Notes* from the sidebar.\n\nYou can filter by course, search by title, and download PDF, Word, PPT files.' };
  }
  if (msg.includes('password') || msg.includes('forgot') || msg.includes('reset')) {
    return { success: true, reply: '🔑 *Reset Password*\n\nOn the login page, click "Forgot password?"\n\n1. Enter your Student ID\n2. Receive OTP via Telegram or Email\n3. Enter OTP\n4. Set new password' };
  }
  if (msg.includes('telegram') || msg.includes('bot') || msg.includes('notification')) {
    return { success: true, reply: '✈️ *Telegram Bot*\n\nJoin @FBResultPortalBot on Telegram.\n\nYou will receive mark notifications, notices, and complaint updates instantly.' };
  }
  if (msg.includes('grade') || msg.includes('gpa') || msg.includes('calculate')) {
    return { success: true, reply: '🏅 *Grade Calculation*\n\nYour grade uses weighted assessments.\n\nTotal = Σ (score/maxScore × weight)\n\nGrade scale: A+(90+), A(85+), B+(75+), C(55+), F(<50)' };
  }
  if (msg.includes('hello') || msg.includes('hi') || msg.includes('hey')) {
    return { success: true, reply: '👋 Hello! I am your portal assistant.\n\nAsk me about marks, tests, lecture notes, complaints, or account issues.' };
  }
  if (msg.includes('thank')) {
    return { success: true, reply: '😊 You are welcome! Feel free to ask anything else.' };
  }
  return { success: true, reply: '🤔 I am not sure about that.\n\nTry asking about:\n• marks or grades\n• online tests\n• lecture notes\n• complaints\n• password reset\n• Telegram bot' };
}

// ════════════════════════════════════════════════════════════
// INSTRUCTOR DASHBOARD
// ════════════════════════════════════════════════════════════
function getDashboard(data) {
  const authSh  = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  const students = sheetToObjects(authSh);

  const coursesSh = getOrCreateSheet('Courses', ['Course_ID','Course_Name','Course_Code','CreatedAt']);
  const courses   = sheetToObjects(coursesSh);

  const assessSh  = getOrCreateSheet('Assessments',
    ['Assessment_ID','Course_ID','Name','Weight','MaxScore','CreatedAt']);
  const assessments = sheetToObjects(assessSh);

  const marksSh   = getOrCreateSheet('Marks',
    ['StudentID','Course_ID','Assessment_ID','Score','UpdatedAt']);
  const marks     = sheetToObjects(marksSh);

  const complSh   = getOrCreateSheet('Complaints',
    ['StudentID','Course_ID','Assessment_ID','Type','Message','Status','Timestamp','Response']);
  const complaints = sheetToObjects(complSh);

  const pendingComplaints = complaints.filter(c =>
    (c['Status'] || '') === 'Pending'
  ).length;

  // Per-course stats
  const courseStats = courses.map(c => {
    const cAssess = assessments.filter(a => String(a['Course_ID']) === String(c['Course_ID']));
    const cMarks  = marks.filter(m => String(m['Course_ID']) === String(c['Course_ID']));
    const scores  = cMarks.map(m => Number(m['Score'] || 0)).filter(s => s > 0);
    const avg     = scores.length
      ? (scores.reduce((a,b) => a+b, 0) / scores.length).toFixed(1)
      : null;
    return {
      courseId:        c['Course_ID'],
      courseName:      c['Course_Name'],
      courseCode:      c['Course_Code'],
      studentCount:    students.length,
      assessmentCount: cAssess.length,
      avgScore:        avg
    };
  });

  // Overall avg
  const allScores = marks.map(m => Number(m['Score']||0)).filter(s => s > 0);
  const overallAvg = allScores.length
    ? (allScores.reduce((a,b) => a+b, 0) / allScores.length).toFixed(1)
    : null;

  return {
    success:           true,
    totalStudents:     students.length,
    pendingComplaints: pendingComplaints,
    totalAssessments:  assessments.length,
    avgScore:          overallAvg,
    courses:           courseStats
  };
}

function getAllStudents(data) {
  const sh   = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  return { success: true, students: sheetToObjects(sh) };
}

function getAuthorizedIDs(data) {
  const sh = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  return { success: true, ids: sheetToObjects(sh) };
}

function addAuthorizedID(data) {
  if (!data.studentId || !data.name) {
    return { success: false, message: 'Student ID and name required.' };
  }
  const sh = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
  sh.appendRow([data.studentId, data.name, data.email || '', data.telegramUsername || '']);
  return { success: true };
}

// ════════════════════════════════════════════════════════════
// TELEGRAM BOT WEBHOOK
// ════════════════════════════════════════════════════════════
function telegramWebhook(data) {
  const update = data.update ? JSON.parse(data.update) : data;
  handleTelegramUpdate(update);
  return { success: true };
}

// Called by Telegram webhook (POST to this web app)
function doPost_Telegram(update) {
  handleTelegramUpdate(update);
}

function handleTelegramUpdate(update) {
  if (!update || !update.message) return;
  const msg    = update.message;
  const chatId = msg.chat.id;
  const text   = (msg.text || '').trim();
  const user   = msg.from;

  // Save/update session
  const sessSh = getOrCreateSheet('Bot_Sessions', ['ChatID','StudentID','Status','Step']);
  const sessions = sheetToObjects(sessSh);
  let session  = sessions.find(s => String(s['ChatID']) === String(chatId));

  if (text === '/start') {
    sendTelegram(chatId,
      `👋 Welcome to *Civil Eng. Student Portal Bot*!\n\n` +
      `I help you:\n` +
      `• 📊 View your marks\n` +
      `• 📣 Receive instant notices\n` +
      `• 🔔 Get complaint updates\n\n` +
      `Send your *Student ID* to link your account.`,
      mainKeyboard()
    );
    updateSession(sessSh, chatId, '', 'awaiting_id', 'Step');
    return;
  }

  if (text === '📊 My Marks') {
    if (!session || !session['StudentID']) {
      sendTelegram(chatId, 'Please send your Student ID first.');
      return;
    }
    const marksRes = getMarks({ studentId: session['StudentID'] });
    if (!marksRes.marks || !marksRes.marks.length) {
      sendTelegram(chatId, '📊 No marks available yet.');
      return;
    }
    let reply = '📊 *Your Marks*\n\n';
    marksRes.marks.forEach(m => {
      reply += `*${m.courseName}*\n`;
      reply += `Total: ${m.weightedTotal}%\n`;
      (m.assessments || []).forEach(a => {
        reply += `  • ${a.name}: ${a.score !== null ? a.score + '/' + a.maxScore : '—'}\n`;
      });
      reply += '\n';
    });
    sendTelegram(chatId, reply);
    return;
  }

  if (text === '📣 Notices') {
    const noticesRes = getNotices({});
    const notices    = noticesRes.notices || [];
    if (!notices.length) {
      sendTelegram(chatId, '📣 No notices yet.');
      return;
    }
    const latest = notices[notices.length - 1];
    sendTelegram(chatId,
      `📣 *Latest Notice*\n\n*${latest['Title']}*\n\n${latest['Message']}`
    );
    return;
  }

  if (text === '🤖 Ask Chatbot') {
    sendTelegram(chatId, 'Ask me anything! Type your question.');
    updateSession(sessSh, chatId, session?.StudentID || '', 'chatbot', 'Step');
    return;
  }

  if (text === '🔗 Portal Link') {
    sendTelegram(chatId,
      '🔗 Access the full portal at:\nhttps://YOUR_GITHUB_USERNAME.github.io/civil-eng-portal/'
    );
    return;
  }

  // Handle chatbot mode
  if (session && session['Step'] === 'chatbot') {
    const botRes = chatbot({ message: text });
    sendTelegram(chatId, botRes.reply || 'I could not process that.', mainKeyboard());
    updateSession(sessSh, chatId, session['StudentID'], 'idle', 'Step');
    return;
  }

  // Handle Student ID linking
  if (!session || !session['StudentID'] || session['Step'] === 'awaiting_id') {
    const authSh = getOrCreateSheet('Authorized_IDs', ['ID','Name','Email','Telegram_Username']);
    const authRows = sheetToObjects(authSh);
    const found  = authRows.find(r => String(r['ID']).trim() === text.trim());

    if (found) {
      updateSession(sessSh, chatId, text.trim(), 'linked', 'Status');
      updateSession(sessSh, chatId, text.trim(), text.trim(), 'StudentID');
      sendTelegram(chatId,
        `✅ Account linked!\n\nWelcome, *${found['Name']}*!\n\nYou will now receive notifications here.`,
        mainKeyboard()
      );
      // Update telegram username in Users sheet
      try {
        const usersSh = getOrCreateSheet('Users',
          ['ID','Password','Name','Email','Telegram_Username','Role','RegisteredAt']);
        const usersVals = usersSh.getDataRange().getValues();
        const hdrs = usersVals[0];
        for (let i = 1; i < usersVals.length; i++) {
          if (String(usersVals[i][hdrs.indexOf('ID')]).trim() === text.trim()) {
            usersSh.getRange(i+1, hdrs.indexOf('ChatID')+1).setValue(String(chatId));
            break;
          }
        }
      } catch(_) {}
      // Save chatId in Bot_Sessions properly
      saveChatId(sessSh, chatId, text.trim());
    } else {
      sendTelegram(chatId,
        '❌ Student ID not found.\n\nPlease enter your exact Student ID (e.g. ETS0001/14).'
      );
    }
    return;
  }

  // Default
  sendTelegram(chatId, '❓ Use the menu below.', mainKeyboard());
}

function mainKeyboard() {
  return {
    keyboard: [
      [{ text: '📊 My Marks' }, { text: '📣 Notices' }],
      [{ text: '🤖 Ask Chatbot' }, { text: '🔗 Portal Link' }]
    ],
    resize_keyboard: true
  };
}

function sendTelegram(chatId, text, replyMarkup) {
  if (TELEGRAM_BOT_TOKEN === 'YOUR_TELEGRAM_BOT_TOKEN') return;
  const url     = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  const payload = {
    chat_id:    chatId,
    text:       text,
    parse_mode: 'Markdown'
  };
  if (replyMarkup) payload.reply_markup = replyMarkup;
  try {
    UrlFetchApp.fetch(url, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
  } catch(e) {
    Logger.log('Telegram send error: ' + e.message);
  }
}

function updateSession(sh, chatId, studentId, value, field) {
  const vals = sh.getDataRange().getValues();
  const hdrs = vals[0];
  const cidIdx = hdrs.indexOf('ChatID');
  const fldIdx = hdrs.indexOf(field);
  for (let i = 1; i < vals.length; i++) {
    if (String(vals[i][cidIdx]) === String(chatId)) {
      if (fldIdx >= 0) sh.getRange(i+1, fldIdx+1).setValue(value);
      return;
    }
  }
  sh.appendRow([chatId, studentId, 'linked', value]);
}

function saveChatId(sh, chatId, studentId) {
  const vals = sh.getDataRange().getValues();
  const hdrs = vals[0];
  const cidIdx = hdrs.indexOf('ChatID');
  const sidIdx = hdrs.indexOf('StudentID');
  for (let i = 1; i < vals.length; i++) {
    if (String(vals[i][sidIdx]) === String(studentId)) {
      sh.getRange(i+1, cidIdx+1).setValue(String(chatId));
      return;
    }
  }
}

function broadcastToTelegram(title, message) {
  const sh       = getOrCreateSheet('Bot_Sessions', ['ChatID','StudentID','Status','Step']);
  const sessions = sheetToObjects(sh);
  sessions.forEach(s => {
    if (s['ChatID'] && s['Status'] === 'linked') {
      sendTelegram(s['ChatID'],
        `📣 *New Notice*\n\n*${title}*\n\n${message}`
      );
      Utilities.sleep(50);
    }
  });
}

function notifyInstructorComplaint(data) {
  // Notify instructor via Telegram if they have a linked account
  // Add instructor's chat ID here or retrieve from a settings sheet
}

function notifyStudentComplaintResolved(data) {
  const sh       = getOrCreateSheet('Bot_Sessions', ['ChatID','StudentID','Status','Step']);
  const sessions = sheetToObjects(sh);
  const session  = sessions.find(s =>
    String(s['StudentID']) === String(data.studentId)
  );
  if (session && session['ChatID']) {
    sendTelegram(session['ChatID'],
      `📬 *Complaint Update*\n\nYour complaint has been *${data.status}*.\n\n💬 Response: ${data.response}`
    );
  }
}

// ════════════════════════════════════════════════════════════
// SET TELEGRAM WEBHOOK
// Run this function once from the Apps Script editor
// ════════════════════════════════════════════════════════════
function setTelegramWebhook() {
  const webAppUrl = ScriptApp.getService().getUrl();
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook`;
  const res = UrlFetchApp.fetch(url, {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify({ url: webAppUrl })
  });
  Logger.log(res.getContentText());
}
