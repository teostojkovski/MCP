"""
Tasks page HTML builders. Same HTML/JS as original dev_run.
"""
from __future__ import annotations

import html as html_module
from fastapi.responses import HTMLResponse

from app.queries import tasks as tq


def tasks_professor_html(identity: dict) -> HTMLResponse:
    nav = '<p><a href="/device">Device login</a> | <a href="/consultations">Consultations</a> | <a href="/tasks">Tasks</a> | <a href="/my-tasks">My tasks</a> | <a href="/logout">Logout</a></p>'
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Tasks – Professor</title>
<style>
  body { font-family: sans-serif; max-width: 960px; margin: 20px auto; padding: 0 20px; }
  section { margin: 24px 0; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
  button { padding: 8px 16px; cursor: pointer; margin: 2px; }
  input, select, textarea { padding: 6px; margin: 4px; }
  textarea { width: 100%; min-height: 80px; }
  .card { border: 1px solid #ddd; padding: 12px; margin: 8px 0; }
</style>
</head>
<body>
""" + nav + """
<h1>Task Management</h1>
<section>
  <h2>Create task</h2>
  <p>Subject: <select id="createSubject"></select></p>
  <p>Title: <input type="text" id="createTitle" style="width: 100%;" placeholder="Task title" /></p>
  <p>Description: <textarea id="createDesc" placeholder="Task description"></textarea></p>
  <p>Deadline (optional): <input type="datetime-local" id="createDeadline" /></p>
  <button onclick="createTask()">Create task</button>
  <span id="createMsg"></span>
</section>
<section>
  <h2>Assign task to subject students</h2>
  <p>Task ID: <input type="number" id="assignTaskId" placeholder="e.g. 1" />
  <button onclick="assignTask()">Assign to all students in subject</button></p>
  <span id="assignMsg"></span>
</section>
<section>
  <h2>Task submissions</h2>
  <p>Task ID: <input type="number" id="subTaskId" placeholder="e.g. 1" />
  <button onclick="loadSubmissions()">Load submissions</button></p>
  <div id="submissions"></div>
</section>
<script>
  async function api(path, opts) {
    const r = await fetch(path, opts || { credentials: 'same-origin' });
    if (r.status === 401) { window.location = '/device'; return null; }
    return r.json();
  }
  async function loadSubjects() {
    const r = await fetch('/consultations/api/professors', { credentials: 'same-origin' });
    if (r.status !== 200) return;
    const subjRes = await fetch('/tasks/api/subjects', { credentials: 'same-origin' });
    if (subjRes.status !== 200) { document.getElementById('createSubject').innerHTML = '<option value="">Load failed</option>'; return; }
    const subjData = await subjRes.json();
    const sel = document.getElementById('createSubject');
    sel.innerHTML = (subjData.subjects || []).map(s => '<option value="' + s.code + '">' + s.name + ' (' + s.code + ')</option>').join('');
  }
  async function createTask() {
    const subject_id = document.getElementById('createSubject').value;
    const title = document.getElementById('createTitle').value.trim();
    const desc = document.getElementById('createDesc').value.trim();
    const deadline = document.getElementById('createDeadline').value;
    if (!subject_id || !title || !desc) { document.getElementById('createMsg').textContent = 'Fill subject, title, description.'; return; }
    const body = { title, description: desc, subject_id, deadline: deadline || null };
    const out = await api('/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!out) return;
    if (out.error) { document.getElementById('createMsg').textContent = out.error; return; }
    document.getElementById('createMsg').textContent = 'Created task ID ' + out.id;
    document.getElementById('createTitle').value = '';
    document.getElementById('createDesc').value = '';
    document.getElementById('assignTaskId').value = out.id;
  }
  async function assignTask() {
    const task_id = document.getElementById('assignTaskId').value;
    if (!task_id) { document.getElementById('assignMsg').textContent = 'Enter task ID.'; return; }
    const out = await api('/tasks/' + task_id + '/assign-subject-students', { method: 'POST' });
    if (!out) return;
    document.getElementById('assignMsg').textContent = out.error || ('Assigned: ' + (out.assigned_count || 0) + ' students, ' + (out.new_assignments || 0) + ' new.');
  }
  async function loadSubmissions() {
    const task_id = document.getElementById('subTaskId').value;
    if (!task_id) { document.getElementById('submissions').innerHTML = 'Enter task ID.'; return; }
    const out = await api('/tasks/' + task_id + '/submissions');
    if (!out) return;
    const div = document.getElementById('submissions');
    if (out.error) { div.innerHTML = out.error; return; }
    const subs = out.submissions || [];
    div.innerHTML = '<p><strong>' + out.task_title + '</strong> (' + out.subject_name + ')</p>' +
      '<p>Assigned: ' + out.total_assigned + ' | Submitted: ' + out.total_submitted + '</p>' +
      '<table><tr><th>Student</th><th>Status</th><th>Repo</th><th>Submitted</th><th>Commit</th></tr>' +
      subs.map(s => '<tr><td>' + s.student_name + ' (' + s.student_index + ')</td><td>' + s.status + '</td><td>' +
        (s.linked_repo_url ? '<a href="' + s.linked_repo_url + '" target="_blank">' + (s.linked_repo_name || s.linked_repo_url) + '</a>' : '–') + '</td><td>' + (s.submitted_at || '–') + '</td><td>' + (s.commit_sha ? s.commit_sha.substring(0,7) : '–') + '</td></tr>').join('') + '</table>';
  }
  loadSubjects();
</script>
</body>
</html>""")


def my_tasks_student_html(identity: dict) -> HTMLResponse:
    student_index = identity.get("student_index")
    if student_index is None:
        return HTMLResponse("<html><body><p>Your account is not linked to a student.</p></body></html>")
    username = (identity.get("username") or "").strip()
    username_safe = html_module.escape(username)
    try:
        tasks_data = tq.list_my_assignments(student_index) or []
    except Exception as e:
        tasks_data = []
        task_list_html = "<p class=\"err\">Error loading tasks: " + html_module.escape(str(e)) + "</p>"
    else:
        if not tasks_data:
            task_list_html = "<p><strong>0 tasks</strong> for student_index=" + html_module.escape(str(student_index)) + ". Re-run the seed: <code>py -m app.seed.consultations</code></p>"
        else:
            def _esc(s):
                if s is None:
                    return ""
                return html_module.escape(str(s))
            rows = []
            for t in tasks_data:
                title = _esc(t.get("title"))
                subj = _esc(t.get("subject_name"))
                deadline = _esc(t.get("deadline") or "–")
                status = _esc(t.get("status"))
                repo = "Yes" if t.get("linked_repo_url") else "No"
                aid = int(t.get("assignment_id", 0))
                rows.append(
                    "<tr><td>" + title + "</td><td>" + subj + "</td><td>" + deadline + "</td><td class=\"status\">" + status + "</td><td>" + repo + "</td>"
                    + "<td><button type=\"button\" onclick=\"openDetail(" + str(aid) + ")\">Open</button></td></tr>"
                )
            task_list_html = (
                "<p><strong>Showing " + str(len(tasks_data)) + " task(s).</strong></p>"
                '<table><tr><th>Title</th><th>Subject</th><th>Deadline</th><th>Status</th><th>Repo</th><th>Action</th></tr>'
                + "".join(rows)
                + "</table>"
            )
    nav = '<p><a href="/device">Device login</a> | <a href="/consultations">Consultations</a> | <a href="/tasks">Tasks</a> | <a href="/my-tasks">My tasks</a> | <a href="/logout">Logout</a></p>'
    resp = HTMLResponse("""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<title>My Tasks</title>
<style>
  body { font-family: sans-serif; max-width: 920px; margin: 20px auto; padding: 0 20px; }
  section { margin: 24px 0; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
  button { padding: 8px 16px; cursor: pointer; margin: 2px; }
  input, select, textarea { padding: 6px; margin: 4px; }
  .card { border: 1px solid #ddd; padding: 12px; margin: 8px 0; }
  .status { font-weight: bold; }
  .err { color: #c00; font-weight: bold; }
</style>
</head>
<body>
""" + nav + """
<h1>My Tasks</h1>
<p>Logged in as <strong>""" + username_safe + """</strong></p>
<p style="background:#fff3cd; padding: 8px; border-radius: 4px;"><strong>Tip:</strong> Use one address for everything (e.g. <code>http://localhost:8000</code>). Log in at <a href="/device">/device</a> first; then Link GitHub and Open tasks will work. After linking here, you can also <strong>submit a repo via Claude</strong> (e.g. &quot;submit assignment 1 with repo https://github.com/username/repo&quot;). Professors can use Claude to list submissions and open repo links.</p>
<section>
  <h2>Link GitHub (once)</h2>
  <p style="color:#555;">Link your GitHub account here once. Then open a task below only to choose which repo to submit.</p>
  <p><strong>What to enter:</strong></p>
  <ul style="color:#555; margin: 0 0 12px 0;">
    <li><strong>GitHub username</strong> – your GitHub login (e.g. the name in github.com/YourUsername). Required.</li>
    <li><strong>Personal access token</strong> – optional. Only needed if you want to use &quot;Load my repos&quot;. Create one at GitHub → Settings → Developer settings → Personal access tokens.</li>
  </ul>
  <p id="githubStatus">Checking…</p>
  <p>
    <label>GitHub username: <input type="text" id="ghUsername" placeholder="e.g. johndoe" style="width: 220px;" /></label><br/>
    <label>Token (optional): <input type="password" id="ghToken" placeholder="ghp_xxxx or leave empty" style="width: 280px;" /></label><br/>
    <button type="button" id="linkGhBtn">Link GitHub</button>
  </p>
  <div id="ghFeedback" style="margin: 10px 0; padding: 10px; border-radius: 6px; font-weight: bold; min-height: 24px;"></div>
  <p><button type="button" id="loadReposBtn">Load my repos</button> <button type="button" id="copyReposBtn">Copy repo list</button> <span id="reposStatus"></span></p>
  <div id="reposList"></div>
</section>
<section>
  <h2>Assigned tasks</h2>
  <p style="color:#666;font-size:0.9em;">Click <strong>Open</strong> on a task only when you want to link a repo and submit.</p>
  <div id="taskList">""" + task_list_html + """</div>
</section>
<section id="detailSection" style="display:none;">
  <h2>Task – link repo and submit</h2>
  <div id="taskDetail"></div>
  <hr/>
  <p>Owner <input type="text" id="repoOwner" placeholder="owner" />
  Repo <input type="text" id="repoName" placeholder="repo" /> Branch <input type="text" id="repoBranch" value="main" />
  <button type="button" id="linkRepoBtn">Link repo</button></p>
  <p><button type="button" id="loadReposDetailBtn">Load my repos</button> <span id="reposDetailStatus"></span></p>
  <div id="reposListDetail"></div>
  <p><button type="button" id="submitTaskBtn">Submit task</button> <span id="submitMsg"></span></p>
</section>
<script>
  const studentIndex = """ + str(student_index) + """;
  let currentAssignmentId = null;
  async function api(path, opts) {
    var url = path.startsWith('http') ? path : (window.location.origin + path);
    var ctrl = new AbortController();
    var to = setTimeout(function() { ctrl.abort(); }, 15000);
    try {
      var r = await fetch(url, Object.assign({ credentials: 'same-origin', signal: ctrl.signal }, opts || {}));
      clearTimeout(to);
      var data = await r.json().catch(function() { return {}; });
      if (r.status === 401) return { _status: 401, error: 'Not authenticated. Log in at the same site (e.g. /device) first.' };
      if (!r.ok) return Object.assign(data, { _status: r.status });
      return data;
    } catch (e) {
      clearTimeout(to);
      return { error: e.name === 'AbortError' ? 'Request timed out' : (e.message || 'Network error') };
    }
  }
  function esc(s) {
    if (s == null) return '';
    var x = String(s);
    var dq = String.fromCharCode(34);
    var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;' };
    map[dq] = '&quot;';
    return x.split('').map(function(c) { return map[c] || c; }).join('');
  }
  async function loadMyTasks() {
    const div = document.getElementById('taskList');
    try {
      const out = await api('/api/my-tasks');
      if (!out) { div.innerHTML = 'Session lost. <a href="/device">Log in again</a>.'; return; }
      if (out.error || out._status === 403) {
        div.innerHTML = '<p class="err">' + esc(out.error || 'Forbidden') + '</p><p>Re-run the consultation seed: <code>py -m app.seed.consultations</code></p>';
        return;
      }
      const list = Array.isArray(out.tasks) ? out.tasks : [];
      if (list.length === 0) {
        div.innerHTML = 'No tasks assigned. Re-run the seed: <code>py -m app.seed.consultations</code>';
        return;
      }
      div.innerHTML = '<table><tr><th>Title</th><th>Subject</th><th>Deadline</th><th>Status</th><th>Repo</th><th>Action</th></tr>' +
        list.map(function(t) { return '<tr><td>' + esc(t.title) + '</td><td>' + esc(t.subject_name) + '</td><td>' + esc(t.deadline || '–') + '</td><td class="status">' + esc(t.status) + '</td><td>' + (t.linked_repo_url ? 'Yes' : 'No') + '</td><td><button type="button" onclick="openDetail(' + Number(t.assignment_id) + ')">Open</button></td></tr>'; }).join('') + '</table>';
    } catch (e) {
      div.innerHTML = '<p class="err">Error loading tasks: ' + esc(e.message) + '</p>';
    }
  }
  function openDetail(assignmentId) {
    try {
      currentAssignmentId = assignmentId;
      var section = document.getElementById('detailSection');
      if (!section) { alert('Task panel not found. Refresh the page.'); return; }
      section.style.display = 'block';
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      var taskDiv = document.getElementById('taskDetail');
      if (taskDiv) taskDiv.innerHTML = '<p>Loading task…</p>';
      var reposDetail = document.getElementById('reposListDetail');
      if (reposDetail) reposDetail.innerHTML = '';
      var reposStatus = document.getElementById('reposDetailStatus');
      if (reposStatus) reposStatus.textContent = '';
      loadDetail();
      loadGitHubStatus();
    } catch (err) {
      alert('Error opening task: ' + (err.message || err));
    }
  }
  async function loadDetail() {
    if (!currentAssignmentId) return;
    const div = document.getElementById('taskDetail');
    const out = await api('/my/tasks/' + currentAssignmentId);
    if (!out) { div.innerHTML = '<p class="err">Session lost. <a href="/device">Log in again</a>.</p>'; return; }
    if (out.error || out._status) {
      div.innerHTML = '<p class="err">' + esc(out.error || 'Error ' + (out._status || '')) + '</p>';
      return;
    }
    div.innerHTML = '<p><strong>' + esc(out.title) + '</strong> (' + esc(out.subject_name) + ')</p><p>' + (out.deadline ? 'Deadline: ' + esc(out.deadline) : '') + '</p><pre style="white-space: pre-wrap;">' + esc(out.description || '') + '</pre><p>Status: ' + esc(out.status) + (out.linked_repo_url ? ' | Repo: <a href="' + esc(out.linked_repo_url) + '" target="_blank">' + esc(out.linked_repo_url) + '</a>' : '') + '</p>';
    document.getElementById('repoOwner').value = out.linked_repo_owner || '';
    document.getElementById('repoName').value = out.linked_repo_name || '';
    document.getElementById('repoBranch').value = out.linked_branch || 'main';
  }
  async function loadGitHubStatus() {
    var out = await api('/github/me');
    var el = document.getElementById('githubStatus');
    if (!el) return;
    if (out && out._status === 401) { el.innerHTML = 'Not logged in. <a href="/device">Log in here</a> (same address as this page, e.g. http://localhost:8000/device).'; return; }
    if (!out || out.error) { el.textContent = 'Could not check status.'; return; }
    if (out.linked) { el.textContent = 'Linked: ' + (out.account && out.account.github_username ? out.account.github_username : 'Yes'); }
    else { el.textContent = 'Not linked. Enter username (and optional token) above and click Link GitHub.'; }
  }
  async function linkGitHub() {
    var feedback = document.getElementById('ghFeedback');
    var btn = document.getElementById('linkGhBtn');
    function show(msg, isErr) {
      if (feedback) {
        feedback.style.background = isErr ? '#fee' : '#dfd';
        feedback.style.color = isErr ? '#c00' : '#161';
        feedback.textContent = msg;
        feedback.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else { alert(msg); }
    }
    try {
      if (feedback) { feedback.style.background = ''; feedback.style.color = ''; feedback.textContent = ''; }
      var username = (document.getElementById('ghUsername') || {}).value;
      if (typeof username !== 'string') username = '';
      username = username.trim();
      var token = (document.getElementById('ghToken') || {}).value;
      if (typeof token !== 'string') token = '';
      token = token.trim();
      if (!username) {
        show('Please enter your GitHub username (your login at github.com).', true);
        return;
      }
      if (btn) { btn.disabled = true; btn.textContent = 'Linking…'; }
      show('Linking…', false);
      var out = await api('/github/link', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ github_username: username, access_token: token || null }) });
      if (btn) { btn.disabled = false; btn.textContent = 'Link GitHub'; }
      console.log('github/link response', out);
      if (!out) {
        show('Request failed (no response). Check the browser console (F12).', true);
        return;
      }
      if (out._status === 401 || (out.error && out.error.indexOf('Not authenticated') >= 0)) {
        show('You are not logged in. Open /device in the same tab, log in with your student account, then come back here.', true);
        return;
      }
      if (out.error || out._status) {
        show('Error: ' + (out.error || ('HTTP ' + out._status)), true);
        return;
      }
      show('GitHub account linked successfully. You can now open a task and link a repo.', false);
      if (btn) btn.textContent = 'Link GitHub';
      loadGitHubStatus();
    } catch (e) {
      if (btn) { btn.disabled = false; btn.textContent = 'Link GitHub'; }
      var errMsg = (e && (e.message || e.toString())) || 'Unknown error';
      show('Error: ' + errMsg, true);
      console.error('linkGitHub error', e);
    }
  }
  async function loadRepos() {
    const out = await api('/github/repos');
    document.getElementById('reposStatus').textContent = '';
    if (!out) return;
    const repos = out.repos || [];
    const div = document.getElementById('reposList');
    if (out.error) { document.getElementById('reposStatus').textContent = out.error; return; }
    if (repos.length === 0) { div.innerHTML = 'No repos found for your linked GitHub account.'; return; }
    div.innerHTML = '<ul>' + repos.map(function(r) { return '<li>' + r.full_name + ' (' + (r.default_branch || 'main') + ')</li>'; }).join('') + '</ul>';
  }
  async function loadReposInDetail() {
    const out = await api('/github/repos');
    document.getElementById('reposDetailStatus').textContent = '';
    if (!out) return;
    const repos = out.repos || [];
    const div = document.getElementById('reposListDetail');
    if (out.error) { document.getElementById('reposDetailStatus').textContent = out.error; return; }
    if (repos.length === 0) { div.innerHTML = 'No repos (link GitHub above; public repos listed without token).'; return; }
    var ul = document.createElement('ul');
    repos.forEach(function(r) {
      var li = document.createElement('li');
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Use this repo';
      btn.dataset.owner = r.owner || '';
      btn.dataset.name = r.name || '';
      btn.dataset.branch = (r.default_branch || 'main');
      btn.onclick = function() { setRepo(btn.dataset.owner, btn.dataset.name, btn.dataset.branch); };
      li.appendChild(btn);
      li.appendChild(document.createTextNode(' ' + (r.full_name || '')));
      ul.appendChild(li);
    });
    div.innerHTML = '';
    div.appendChild(ul);
  }
  function setRepo(owner, name, branch) {
    document.getElementById('repoOwner').value = owner;
    document.getElementById('repoName').value = name;
    document.getElementById('repoBranch').value = branch || 'main';
  }
  async function copyReposToClipboard() {
    const out = await api('/github/repos');
    const statusEl = document.getElementById('reposStatus');
    if (!out) { statusEl.textContent = 'Session lost.'; return; }
    if (out.error) { statusEl.textContent = out.error; return; }
    const repos = out.repos || [];
    if (repos.length === 0) { statusEl.textContent = 'No repos for linked account.'; return; }
    const text = repos.map(function(r) { return r.html_url || ('https://github.com/' + (r.owner || '') + '/' + (r.name || '')); }).join(String.fromCharCode(10));
    try {
      await navigator.clipboard.writeText(text);
      statusEl.textContent = 'Copied ' + repos.length + ' repo(s). Paste into Claude.';
    } catch (e) {
      statusEl.textContent = 'Copy failed: ' + (e.message || 'unknown');
    }
  }
  async function linkRepo() {
    if (!currentAssignmentId) return;
    const owner = document.getElementById('repoOwner').value.trim();
    const name = document.getElementById('repoName').value.trim();
    const branch = document.getElementById('repoBranch').value.trim() || 'main';
    if (!owner || !name) { alert('Enter repo owner and name'); return; }
    const out = await api('/my/tasks/' + currentAssignmentId + '/link-repo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_owner: owner, repo_name: name, branch }) });
    if (out && !out.error) { loadDetail(); loadMyTasks(); alert('Repo linked.'); }
    else if (out && out.error) alert(out.error);
  }
  async function submitTask() {
    if (!currentAssignmentId) return;
    const out = await api('/my/tasks/' + currentAssignmentId + '/submit', { method: 'POST' });
    if (!out) return;
    if (out.error) { document.getElementById('submitMsg').textContent = out.error; return; }
    document.getElementById('submitMsg').textContent = 'Submitted at ' + (out.submitted_at || '');
    loadDetail();
    loadMyTasks();
  }
  // Attach all button handlers in code (no inline onclick that can break)
  var linkBtn = document.getElementById('linkGhBtn');
  if (linkBtn) linkBtn.onclick = linkGitHub;
  var loadReposBtn = document.getElementById('loadReposBtn');
  if (loadReposBtn) loadReposBtn.onclick = loadRepos;
  var copyReposBtn = document.getElementById('copyReposBtn');
  if (copyReposBtn) copyReposBtn.onclick = copyReposToClipboard;
  var linkRepoBtn = document.getElementById('linkRepoBtn');
  if (linkRepoBtn) linkRepoBtn.onclick = linkRepo;
  var loadReposDetailBtn = document.getElementById('loadReposDetailBtn');
  if (loadReposDetailBtn) loadReposDetailBtn.onclick = loadReposInDetail;
  var submitTaskBtn = document.getElementById('submitTaskBtn');
  if (submitTaskBtn) submitTaskBtn.onclick = submitTask;
  loadGitHubStatus();
</script>
</body>
</html>""")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp
