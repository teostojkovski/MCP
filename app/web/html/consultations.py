"""
Consultations page HTML builders. Same HTML/JS as original dev_run.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse


def consultations_student_html(nav: str, identity: dict) -> HTMLResponse:
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


def consultations_professor_html(nav: str, identity: dict) -> HTMLResponse:
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


def consultations_admin_html(nav: str, identity: dict) -> HTMLResponse:
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
