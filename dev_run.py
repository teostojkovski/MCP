"""
Web server for device login and consultations UI (finki_admin).
Run: uvicorn dev_run:app --host 127.0.0.1 --port 8000
Open http://127.0.0.1:8000/device to log in; http://127.0.0.1:8000/consultations to manage consultations.
"""
from app.queries import consultations as cq
import secrets
from datetime import date, timedelta

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.auth_store import approve_user_code
from app.user_auth import authenticate_user
from app.db import SessionLocal
from app.models import User

app = FastAPI()

DEV_SESSIONS: dict[str, dict] = {}
COOKIE_NAME = "dev_session"


def get_session(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    return DEV_SESSIONS.get(token) if token else None


def get_user_identity_from_session(session: dict) -> dict | None:
    """Resolve session (user_id, role) to professor_id / student_index from User table."""
    if not session:
        return None
    username = session.get("user_id")
    role = (session.get("role") or "").strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"role": role, "professor_id": None, "student_index": None}
        return {
            "role": role,
            "professor_id": getattr(user, "professor_id", None),
            "student_index": getattr(user, "student_index", None),
        }
    finally:
        db.close()


@app.get("/device", response_class=HTMLResponse)
def device_page(request: Request):
    session = get_session(request)
    if not session:
        return """
        <html>
          <body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
            <h2>Device Login (DEV)</h2>
            <p>Sign in first.</p>
            <form method="post" action="/login" style="display: grid; gap: 12px;">
              <label>Username: <input name="username" required style="width: 100%; padding: 8px;" /></label>
              <label>Password: <input name="password" type="password" required style="width: 100%; padding: 8px;" /></label>
              <button type="submit" style="padding: 10px; cursor: pointer;">Login</button>
            </form>
          </body>
        </html>
        """
    return """
    <html>
      <body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
        <h2>Device Login (DEV)</h2>
        <p>Paste the <b>user_code</b> from Claude's auth_start.</p>
        <form method="post" action="/device/approve" style="display: grid; gap: 12px;">
          <label>Code (user_code): <input name="user_code" required style="width: 100%; padding: 8px;" placeholder="ABCD-EFGH" /></label>
          <button type="submit" style="padding: 10px; cursor: pointer;">Approve</button>
        </form>
        <p><a href="/consultations">Consultations</a> | <a href="/logout">Logout</a></p>
      </body>
    </html>
    """


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    auth = authenticate_user(username.strip(), password)
    if not auth:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Login failed</h3>
          <p>Invalid username or password.</p>
          <a href="/device">Try again</a>
        </body></html>
        """
    user_id, role = auth
    token = secrets.token_urlsafe(24)
    DEV_SESSIONS[token] = {"user_id": user_id, "role": role}
    r = RedirectResponse(url="/consultations", status_code=302)
    r.set_cookie(key=COOKIE_NAME, value=token, httponly=True)
    return r


@app.get("/logout", response_class=RedirectResponse)
def logout(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        DEV_SESSIONS.pop(token, None)
    r = RedirectResponse(url="/device", status_code=302)
    r.delete_cookie(COOKIE_NAME)
    return r


@app.post("/device/approve", response_class=HTMLResponse)
def device_approve(request: Request, user_code: str = Form(...)):
    session = get_session(request)
    if not session:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Not logged in</h3>
          <a href="/device">Login first</a>
        </body></html>
        """
    user_id = session["user_id"]
    role = (session.get("role") or "").strip().lower()
    code = user_code.strip().upper().replace(" ", "-")
    ok = approve_user_code(user_code=code, user_id=user_id, role=role)
    if ok:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Approved</h3>
          <p>Go back to Claude; auth_status should return session_id.</p>
          <a href="/device">Approve another</a>
        </body></html>
        """
    return """
    <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
      <h3>Invalid or expired code</h3>
      <p>In Claude, call <b>auth_start</b> first, then paste the <b>user_code</b> here. If it still fails, the code may have expired (try auth_start again).</p>
      <a href="/device">Try again</a>
    </body></html>
    """


# ---------- Consultations UI (finki_admin) ----------


def _require_session(request: Request):
    session = get_session(request)
    if not session:
        return None, None
    identity = get_user_identity_from_session(session)
    return session, identity


@app.get("/consultations", response_class=HTMLResponse)
def consultations_page(request: Request):
    session, identity = _require_session(request)
    if not session or not identity:
        return RedirectResponse(url="/device", status_code=302)
    role = identity.get("role") or ""
    nav = '<p><a href="/device">Device login</a> | <a href="/consultations">Consultations</a> | <a href="/logout">Logout</a></p>'
    if role == "student":
        return _consultations_student_html(nav, identity)
    if role == "professor":
        return _consultations_professor_html(nav, identity)
    if role == "admin":
        return _consultations_admin_html(nav, identity)
    return HTMLResponse(f"<html><body>{nav}<p>Role {role!r} cannot access consultations.</p></body></html>")


def _consultations_student_html(nav: str, identity: dict) -> HTMLResponse:
    student_index = identity.get("student_index")
    if student_index is None:
        return HTMLResponse(f"<html><body>{nav}<p>Your account is not linked to a student. Use a student account.</p></body></html>")
    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Consultations – Student</title>
<style>
  body {{ font-family: sans-serif; max-width: 900px; margin: 20px auto; padding: 0 20px; }}
  section {{ margin: 24px 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
  button {{ padding: 8px 16px; cursor: pointer; }}
  .slot {{ margin: 4px 0; }}
  .booked {{ background: #e8f5e9; }}
  input, select {{ padding: 6px; margin: 4px; }}
</style>
</head>
<body>
{nav}
<h1>Consultations – Student</h1>
<section>
  <h2>Professors</h2>
  <div id="professors"></div>
</section>
<section>
  <h2>Available slots</h2>
  <p>Professor: <select id="selProfessor"></select>
  From: <input type="date" id="dateFrom" /> To: <input type="date" id="dateTo" />
  <button onclick="loadSlots()">Show slots</button></p>
  <div id="slots"></div>
</section>
<section>
  <h2>Book a slot</h2>
  <p>Professor: <select id="bookProfessor"></select>
  Date: <input type="date" id="bookDate" /> Start: <input type="time" id="bookTime" step="300" />
  Duration: <select id="bookDuration"><option value="15">15 min</option><option value="30">30 min</option><option value="60">60 min</option></select>
  <button onclick="bookSlot()">Book</button></p>
  <p id="bookMsg"></p>
</section>
<section>
  <h2>My bookings</h2>
  <div id="myBookings"></div>
</section>
<script>
  const studentIndex = {student_index};
  async function api(path) {{
    const r = await fetch('/consultations/api' + path, {{ credentials: 'same-origin' }});
    if (r.status === 401) {{ window.location = '/device'; return null; }}
    return r.json();
  }}
  async function loadProfessors() {{
    const d = await api('/professors');
    if (!d) return;
    const sel = document.getElementById('selProfessor');
    const sel2 = document.getElementById('bookProfessor');
    const div = document.getElementById('professors');
    if (d.error) {{ div.innerHTML = d.error; return; }}
    div.innerHTML = '<table><tr><th>Id</th><th>Name</th><th>Email</th></tr>' +
      (d.professors || []).map(p => '<tr><td>' + p.id + '</td><td>' + p.first_name + ' ' + p.last_name + '</td><td>' + p.email + '</td></tr>').join('') + '</table>';
    [sel, sel2].forEach(s => {{
      s.innerHTML = (d.professors || []).map(p => '<option value="' + p.id + '">' + p.first_name + ' ' + p.last_name + '</option>').join('');
    }});
  }}
  async function loadSlots() {{
    const pid = document.getElementById('selProfessor').value;
    const from = document.getElementById('dateFrom').value;
    const to = document.getElementById('dateTo').value;
    if (!pid || !from || !to) {{ document.getElementById('slots').innerHTML = 'Select professor and date range.'; return; }}
    const d = await api('/slots?professor_id=' + pid + '&date_from=' + from + '&date_to=' + to);
    if (!d) return;
    const div = document.getElementById('slots');
    if (d.error) {{ div.innerHTML = d.error; return; }}
    div.innerHTML = (d.slots || []).length === 0 ? 'No free slots.' : '<p>Free intervals (you can book 15, 30 or 60 min inside any):</p>' +
      (d.slots || []).map(s => '<div class="slot">' + s.date + ' ' + s.start_time + ' – ' + s.end_time + '</div>').join('');
  }}
  async function bookSlot() {{
    const pid = document.getElementById('bookProfessor').value;
    const d = document.getElementById('bookDate').value;
    const t = document.getElementById('bookTime').value;
    const dur = document.getElementById('bookDuration').value;
    if (!pid || !d || !t || !dur) {{ document.getElementById('bookMsg').textContent = 'Fill all fields.'; return; }}
    const r = await fetch('/consultations/api/book', {{ method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ professor_id: +pid, date: d, start_time: t, duration_minutes: +dur }}) }});
    const j = await r.json();
    document.getElementById('bookMsg').textContent = j.error || j.message || 'Booked.';
    if (j.message) loadMyBookings();
  }}
  async function loadMyBookings() {{
    const d = await api('/my-bookings');
    if (!d) return;
    const div = document.getElementById('myBookings');
    if (d.error) {{ div.innerHTML = d.error; return; }}
    const list = d.bookings || [];
    div.innerHTML = list.length === 0 ? 'No bookings.' : '<table><tr><th>Professor</th><th>Date</th><th>Time</th><th>Duration</th><th>Cancel</th></tr>' +
      list.map(b => '<tr><td>' + b.professor_name + '</td><td>' + b.date + '</td><td>' + b.start_time + '–' + b.end_time + '</td><td>' + (b.duration || '') + '</td><td><button onclick="cancelBooking(' + b.id + ')">Cancel</button></td></tr>').join('') + '</table>';
  }}
  async function cancelBooking(id) {{
    const r = await fetch('/consultations/api/cancel-booking', {{ method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ booking_id: id }}) }});
    const j = await r.json();
    if (j.message) loadMyBookings();
    else alert(j.error || 'Failed');
  }}
  loadProfessors();
  loadMyBookings();
  const today = new Date().toISOString().slice(0, 10);
  const next = new Date(Date.now() + 14*24*60*60*1000).toISOString().slice(0, 10);
  document.getElementById('dateFrom').value = today;
  document.getElementById('dateTo').value = next;
</script>
</body>
</html>""")


def _consultations_professor_html(nav: str, identity: dict) -> HTMLResponse:
    professor_id = identity.get("professor_id")
    if professor_id is None:
        return HTMLResponse(f"<html><body>{nav}<p>Your account is not linked to a professor.</p></body></html>")
    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Consultations – Professor</title>
<style>
  body {{ font-family: sans-serif; max-width: 960px; margin: 20px auto; padding: 0 20px; }}
  section {{ margin: 24px 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
  button {{ padding: 8px 16px; cursor: pointer; margin: 2px; }}
  input, select {{ padding: 6px; margin: 4px; }}
</style>
</head>
<body>
{nav}
<h1>My Consultations</h1>
<section>
  <h2>Bookings with me</h2>
  <div id="bookings"></div>
</section>
<section>
  <h2>My availability (time frame per day, weekly)</h2>
  <div id="availabilities"></div>
  <p>Add time frame: Day <select id="addDay"><option value="0">Mon</option><option value="1">Tue</option><option value="2">Wed</option><option value="3">Thu</option><option value="4">Fri</option><option value="5">Sat</option><option value="6">Sun</option></select>
  From <input type="time" id="addStart" /> To <input type="time" id="addEnd" /> (students book 15/30/60 min within)
  <button onclick="addAvailability()">Add</button></p>
</section>
<section>
  <h2>Block a date (no consultations that day)</h2>
  <p>Date: <input type="date" id="blockDate" /> <button onclick="blockDate()">Block</button></p>
  <p>Blocked (click to unblock): <span id="blockedList"></span></p>
</section>
<script>
  const professorId = {professor_id};
  async function api(path, opts) {{
    const r = await fetch('/consultations/api' + path, opts || {{ credentials: 'same-origin' }});
    if (r.status === 401) {{ window.location = '/device'; return null; }}
    return r.json();
  }}
  async function loadBookings() {{
    const d = await api('/professor-bookings?professor_id=' + professorId);
    if (!d) return;
    const div = document.getElementById('bookings');
    if (d.error) {{ div.innerHTML = d.error; return; }}
    const list = d.bookings || [];
    div.innerHTML = list.length === 0 ? 'No bookings.' : '<table><tr><th>Student</th><th>Date</th><th>Time</th></tr>' +
      list.map(b => '<tr><td>' + b.student_name + ' (' + b.student_index + ')</td><td>' + b.date + '</td><td>' + b.start_time + '–' + b.end_time + '</td></tr>').join('') + '</table>';
  }}
  async function loadAvailabilities() {{
    const d = await api('/professor-availabilities?professor_id=' + professorId);
    if (!d) return;
    const div = document.getElementById('availabilities');
    if (d.error) {{ div.innerHTML = d.error; return; }}
    const list = d.availabilities || [];
    const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    div.innerHTML = list.length === 0 ? 'None. Add above.' : '<table><tr><th>Day</th><th>Time frame</th><th>Edit / Delete</th></tr>' +
      list.map(a => '<tr><td>' + days[a.day_of_week] + '</td><td>' + a.start_time + ' – ' + a.end_time + '</td><td><button onclick="editAvail(' + a.id + ')">Edit</button><button onclick="deleteAvail(' + a.id + ')">Delete</button></td></tr>').join('') + '</table>';
  }}
  async function addAvailability() {{
    const day = document.getElementById('addDay').value;
    const start = document.getElementById('addStart').value;
    const end = document.getElementById('addEnd').value;
    const d = await api('/availability', {{ method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ professor_id: professorId, day_of_week: +day, start_time: start, end_time: end, slot_duration: 15 }}) }});
    if (d && !d.error) loadAvailabilities();
    else if (d && d.error) alert(d.error);
  }}
  async function editAvail(id) {{
    const start = prompt('New start time (HH:MM):');
    const end = prompt('New end time (HH:MM):');
    if (start === null || end === null) return;
    const d = await api('/availability/' + id, {{ method: 'PUT', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ professor_id: professorId, start_time: start, end_time: end, slot_duration: 15 }}) }});
    if (d && !d.error) loadAvailabilities();
    else if (d && d.error) alert(d.error);
  }}
  async function deleteAvail(id) {{
    if (!confirm('Remove this availability slot?')) return;
    const d = await api('/availability/' + id + '?professor_id=' + professorId, {{ method: 'DELETE', credentials: 'same-origin' }});
    if (d && !d.error) loadAvailabilities();
    else if (d && d.error) alert(d.error);
  }}
  async function blockDate() {{
    const d = document.getElementById('blockDate').value;
    const r = await api('/block-date', {{ method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ professor_id: professorId, date: d }}) }});
    if (r && !r.error) {{ loadBlocked(); }}
    else if (r && r.error) alert(r.error);
  }}
  async function loadBlocked() {{
    const from = new Date().toISOString().slice(0, 10);
    const to = new Date(Date.now() + 90*24*60*60*1000).toISOString().slice(0, 10);
    const d = await api('/blocked-dates?professor_id=' + professorId + '&date_from=' + from + '&date_to=' + to);
    const dates = (d && d.dates) ? d.dates : [];
    const span = document.getElementById('blockedList');
    if (dates.length === 0) span.innerHTML = 'None';
    else span.innerHTML = dates.map(dt => '<button type="button" onclick="unblockDate(\\'' + dt + '\\')">' + dt + ' (unblock)</button> ').join('');
  }}
  async function unblockDate(dt) {{
    const r = await api('/unblock-date', {{ method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ professor_id: professorId, date: dt }}) }});
    if (r && !r.error) loadBlocked();
    else if (r && r.error) alert(r.error);
  }}
  loadBookings();
  loadAvailabilities();
  loadBlocked();
</script>
</body>
</html>""")


def _consultations_admin_html(nav: str, identity: dict) -> HTMLResponse:
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Consultations – Admin</title>
<style>
  body { font-family: sans-serif; max-width: 1000px; margin: 20px auto; padding: 0 20px; }
  section { margin: 24px 0; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
  button { padding: 8px 16px; cursor: pointer; }
</style>
</head>
<body>
""" + nav + """
<h1>Consultations – Admin</h1>
<section>
  <h2>All professors</h2>
  <div id="professors"></div>
</section>
<section>
  <h2>Bookings per professor</h2>
  <p>Professor: <select id="selProf"></select> <button onclick="loadProfBookings()">Load</button></p>
  <div id="profBookings"></div>
</section>
<script>
  async function api(path) {
    const r = await fetch('/consultations/api' + path, { credentials: 'same-origin' });
    if (r.status === 401) { window.location = '/device'; return null; }
    return r.json();
  }
  async function loadProfessors() {
    const d = await api('/professors');
    if (!d) return;
    document.getElementById('professors').innerHTML = (d.professors || []).length === 0 ? 'None' :
      '<table><tr><th>Id</th><th>Name</th><th>Email</th></tr>' +
      d.professors.map(p => '<tr><td>' + p.id + '</td><td>' + p.first_name + ' ' + p.last_name + '</td><td>' + p.email + '</td></tr>').join('') + '</table>';
    const sel = document.getElementById('selProf');
    sel.innerHTML = (d.professors || []).map(p => '<option value="' + p.id + '">' + p.first_name + ' ' + p.last_name + '</option>').join('');
  }
  async function loadProfBookings() {
    const pid = document.getElementById('selProf').value;
    const d = await api('/professor-bookings?professor_id=' + pid);
    if (!d) return;
    const list = d.bookings || [];
    document.getElementById('profBookings').innerHTML = list.length === 0 ? 'No bookings.' :
      '<table><tr><th>Student</th><th>Date</th><th>Time</th></tr>' +
      list.map(b => '<tr><td>' + b.student_name + '</td><td>' + b.date + '</td><td>' + b.start_time + '–' + b.end_time + '</td></tr>').join('') + '</table>';
  }
  loadProfessors();
</script>
</body>
</html>""")


@app.get("/consultations/api/professors")
def api_professors(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    role = (identity.get("role") or "").lower()
    if role not in ("student", "admin"):
        return JSONResponse({"error": "Only students and admins can list professors"})
    professors = cq.list_professors()
    return JSONResponse({"professors": professors})


@app.get("/consultations/api/slots")
def api_slots(request: Request, professor_id: int, date_from: str, date_to: str):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None and identity.get("role") != "admin":
        return JSONResponse({"error": "Student account required"})
    if student_index is None:
        return JSONResponse({"error": "Pass student_index for admin"})
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except ValueError:
        return JSONResponse({"error": "Invalid date format"})
    slots = cq.list_available_slots(professor_id, student_index, df, dt)
    return JSONResponse({"slots": slots})


@app.post("/consultations/api/book")
async def api_book(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    student_index = identity.get("student_index")
    if student_index is None and identity.get("role") == "admin":
        student_index = body.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    professor_id = body.get("professor_id")
    date_str = body.get("date")
    start_time_str = body.get("start_time")
    duration_minutes = body.get("duration_minutes")
    if not all([professor_id, date_str, start_time_str, duration_minutes]):
        return JSONResponse({"error": "professor_id, date, start_time, duration_minutes required"})
    try:
        from datetime import time
        booking_date = date.fromisoformat(date_str)
        h, m = map(int, start_time_str.split(":"))
        start_time = time(hour=h, minute=m)
        result = cq.book_slot(student_index, professor_id,
                              booking_date, start_time, int(duration_minutes))
        return JSONResponse({"message": "Booked", "id": result["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.get("/consultations/api/my-bookings")
def api_my_bookings(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    bookings = cq.list_my_bookings_student(student_index)

    def dur(b):
        s = b.get("start_time", "0:0").split(":")
        e = b.get("end_time", "0:0").split(":")
        return (int(e[0])*60+int(e[1])) - (int(s[0])*60+int(s[1]))
    for b in bookings:
        b["duration"] = dur(b)
    return JSONResponse({"bookings": bookings})


@app.post("/consultations/api/cancel-booking")
async def api_cancel_booking(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    booking_id = body.get("booking_id")
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    try:
        out = cq.cancel_booking(student_index, booking_id)
        if out:
            return JSONResponse({"message": "Cancelled"})
        return JSONResponse({"error": "Booking not found or not yours"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.get("/consultations/api/professor-bookings")
def api_professor_bookings(request: Request, professor_id: int):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    role = (identity.get("role") or "").lower()
    if role not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"})
    if role == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only view your own bookings"})
    bookings = cq.list_bookings_professor(professor_id)
    return JSONResponse({"bookings": bookings})


@app.get("/consultations/api/professor-availabilities")
def api_professor_availabilities(request: Request, professor_id: int):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only view your own availability"})
    from app.models import ConsultationAvailability
    db = SessionLocal()
    try:
        rows = db.query(ConsultationAvailability).filter(ConsultationAvailability.professor_id == professor_id).order_by(
            ConsultationAvailability.day_of_week, ConsultationAvailability.start_time).all()
        availabilities = [{"id": a.id, "day_of_week": a.day_of_week, "start_time": a.start_time.strftime(
            "%H:%M"), "end_time": a.end_time.strftime("%H:%M"), "slot_duration": a.slot_duration} for a in rows]
        return JSONResponse({"availabilities": availabilities})
    finally:
        db.close()


@app.post("/consultations/api/availability")
async def api_add_availability(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only add your own availability"})
    from datetime import time
    try:
        h, m = map(int, body.get("start_time", "0:0").split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, body.get("end_time", "0:0").split(":"))
        end_time = time(hour=h, minute=m)
        out = cq.create_availability(professor_id, int(body.get(
            "day_of_week")), start_time, end_time, int(body.get("slot_duration", 15)))
        return JSONResponse({"message": "Added", "id": out["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.get("/consultations/api/blocked-dates")
def api_blocked_dates(request: Request, professor_id: int, date_from: str, date_to: str):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except ValueError:
        return JSONResponse({"error": "Invalid date"})
    dates = cq.list_blocked_dates(professor_id, df, dt)
    return JSONResponse({"dates": dates})


@app.post("/consultations/api/block-date")
async def api_block_date(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        d = date.fromisoformat(body.get("date", ""))
        cq.block_date(professor_id, d)
        return JSONResponse({"message": "Blocked"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.post("/consultations/api/unblock-date")
async def api_unblock_date(request: Request):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        d = date.fromisoformat(body.get("date", ""))
        ok = cq.unblock_date(professor_id, d)
        return JSONResponse({"message": "Unblocked" if ok else "Not found"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.put("/consultations/api/availability/{availability_id:int}")
async def api_edit_availability(request: Request, availability_id: int):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    from datetime import time
    try:
        h, m = map(int, body.get("start_time", "0:0").split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, body.get("end_time", "0:0").split(":"))
        end_time = time(hour=h, minute=m)
        out = cq.edit_availability(professor_id, availability_id, start_time, end_time, int(
            body.get("slot_duration", 15)))
        if out is None:
            return JSONResponse({"error": "Availability not found"})
        return JSONResponse({"message": "Updated", "id": out["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@app.delete("/consultations/api/availability/{availability_id:int}")
def api_delete_availability(request: Request, availability_id: int, professor_id: int):
    _, identity = _require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    ok = cq.delete_availability(professor_id, availability_id)
    return JSONResponse({"message": "Deleted"} if ok else {"error": "Not found"})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
