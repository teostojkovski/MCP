"""
MCP tools for task assignment: student sees own tasks, professor sees submission overview.
All access goes through authorization helpers (same as API).
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
from app.queries import tasks as tq


async def task_list_my_handler(arguments: dict) -> list[TextContent]:
    """List tasks assigned to the current student. Requires student session."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role != "student":
        return [TextContent(type="text", text="FORBIDDEN: student only")]
    # Resolve username to student_index via User table
    from app.db import SessionLocal
    from app.models import User as UserModel
    session = SessionLocal()
    try:
        u = session.query(UserModel).filter(UserModel.username == user.get("user_id")).first()
        if not u or u.student_index is None:
            return [TextContent(type="text", text="Student account not linked")]
        tasks = tq.list_my_assignments(u.student_index)
    finally:
        session.close()
    if not tasks:
        return [TextContent(type="text", text="No tasks assigned to you.")]
    lines = [f"Assigned tasks ({len(tasks)}):"]
    for t in tasks:
        lines.append(
            f"  - [{t['assignment_id']}] {t['title']} ({t['subject_name']}) "
            f"| status: {t['status']} | repo: {'yes' if t.get('linked_repo_url') else 'no'} | "
            f"submitted: {t.get('submitted_at') or 'no'}"
        )
    return [TextContent(type="text", text="\n".join(lines))]


async def task_get_my_handler(arguments: dict) -> list[TextContent]:
    """Get details of one assigned task for the current student. Pass assignment_id or task_id."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role != "student":
        return [TextContent(type="text", text="FORBIDDEN: student only")]
    assignment_id = arguments.get("assignment_id")
    task_id = arguments.get("task_id")
    if not assignment_id and not task_id:
        return [TextContent(type="text", text="Provide assignment_id or task_id.")]
    username = user.get("user_id")
    out = tq.get_authorized_task_for_student(
        username, assignment_id=assignment_id, task_id=task_id
    )
    if not out:
        return [TextContent(type="text", text="Task not found or not assigned to you.")]
    lines = [
        f"Title: {out['title']}",
        f"Subject: {out['subject_name']}",
        f"Deadline: {out.get('deadline') or 'none'}",
        f"Status: {out['status']}",
        f"Description:\n{out.get('description', '')}",
    ]
    if out.get("linked_repo_url"):
        lines.append(f"Repo: {out['linked_repo_url']}")
    if out.get("submitted_at"):
        lines.append(f"Submitted at: {out['submitted_at']}")
    return [TextContent(type="text", text="\n".join(lines))]


async def task_submit_by_repo_handler(arguments: dict) -> list[TextContent]:
    """Submit a task by pasting the GitHub repo link. Student only; you can only submit for yourself."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role != "student":
        return [TextContent(type="text", text="FORBIDDEN: student only")]
    assignment_id = arguments.get("assignment_id")
    repo_url = (arguments.get("repo_url") or "").strip()
    branch = (arguments.get("branch") or "").strip() or None
    if not assignment_id:
        return [TextContent(type="text", text="Provide assignment_id (from task_list_my).")]
    if not repo_url:
        return [TextContent(type="text", text="Provide repo_url (e.g. https://github.com/owner/repo).")]
    from app.db import SessionLocal
    from app.models import User as UserModel
    session = SessionLocal()
    try:
        u = session.query(UserModel).filter(UserModel.username == user.get("user_id")).first()
        if not u or u.student_index is None:
            return [TextContent(type="text", text="Student account not linked")]
        student_index = u.student_index
        user_id = u.id
    finally:
        session.close()
    try:
        out = tq.submit_assignment_by_repo_url(
            student_index, int(assignment_id), user_id, repo_url, branch
        )
        lines = [
            "Submitted successfully.",
            f"Assignment: {out['assignment_id']}",
            f"Status: {out['status']}",
            f"Submitted at: {out.get('submitted_at') or '–'}",
            f"Repo: {out.get('repo_url') or '–'}",
            f"Branch: {out.get('branch') or '–'}",
            f"Commit: {out.get('commit_sha') or '–'}",
        ]
        return [TextContent(type="text", text="\n".join(lines))]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {str(e)}\n\nTip: Link your GitHub account first (with a personal access token) in the web UI so the system can verify the repo and record the commit.")]


async def task_list_my_created_professor_handler(arguments: dict) -> list[TextContent]:
    """List all tasks created by the current professor. Professor only."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role not in ("professor", "admin"):
        return [TextContent(type="text", text="FORBIDDEN: professor only")]
    username = user.get("user_id")
    tasks = tq.get_authorized_tasks_created_for_professor(username)
    if tasks is None:
        return [TextContent(type="text", text="Professor account not found or not linked.")]
    if not tasks:
        return [TextContent(type="text", text="You have not created any tasks yet.")]
    lines = [f"Tasks you created ({len(tasks)}):", ""]
    for t in tasks:
        deadline = t.get("deadline") or "no deadline"
        lines.append(f"  • [{t['id']}] {t['title']} — {t.get('subject_name', t.get('subject_id', ''))} (deadline: {deadline})")
    return [TextContent(type="text", text="\n".join(lines))]


async def task_submissions_professor_handler(arguments: dict) -> list[TextContent]:
    """List which students submitted a task. Professor only; only for tasks you created. Includes repo links to preview."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role not in ("professor", "admin"):
        return [TextContent(type="text", text="FORBIDDEN: professor only")]
    task_id = arguments.get("task_id")
    if not task_id:
        return [TextContent(type="text", text="Provide task_id.")]
    username = user.get("user_id")
    out = tq.get_authorized_submission_overview_for_professor(username, int(task_id))
    if not out:
        return [TextContent(type="text", text="Task not found or you are not the task creator.")]
    lines = [
        f"Task: {out['task_title']} ({out['subject_name']})",
        f"Assigned: {out['total_assigned']} | Submitted: {out['total_submitted']}",
        "",
        "Submissions (open repo link to preview):",
        "",
    ]
    for s in out.get("submissions", []):
        repo = s.get("linked_repo_url") or "–"
        sha = (s.get("commit_sha") or "")[:7] if s.get("commit_sha") else "–"
        lines.append(f"  • {s['student_name']} (index {s['student_index']}) — {s['status']}")
        lines.append(f"    Submitted: {s.get('submitted_at') or '–'} | Commit: {sha}")
        if repo != "–":
            lines.append(f"    Repo: {repo}")
        else:
            lines.append("    Repo: –")
        lines.append("")
    return [TextContent(type="text", text="\n".join(lines))]


async def task_get_submission_repo_handler(arguments: dict) -> list[TextContent]:
    """Get one student's submission repo URL and commit for a task. Professor only; use to preview that student's repo."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role not in ("professor", "admin"):
        return [TextContent(type="text", text="FORBIDDEN: professor only")]
    task_id = arguments.get("task_id")
    student_index = arguments.get("student_index")
    if not task_id or student_index is None:
        return [TextContent(type="text", text="Provide task_id and student_index.")]
    username = user.get("user_id")
    out = tq.get_authorized_submission_repo_for_professor(
        username, int(task_id), int(student_index)
    )
    if not out:
        return [TextContent(type="text", text="Not found or you are not the task creator.")]
    repo = out.get("repo_url") or "–"
    lines = [
        f"Task: {out['task_title']}",
        f"Student: {out['student_name']} (index {out['student_index']})",
        f"Submitted: {out.get('submitted_at') or '–'}",
        f"Branch: {out.get('branch') or '–'}",
        f"Commit: {out.get('commit_sha') or '–'}",
        "",
        "Preview repo (open in browser):",
        repo,
    ]
    return [TextContent(type="text", text="\n".join(lines))]


async def task_get_submission_contents_handler(arguments: dict) -> list[TextContent]:
    """Fetch a student's submitted repo contents so you can analyze and grade it. Professor only."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role not in ("professor", "admin"):
        return [TextContent(type="text", text="FORBIDDEN: professor only")]
    task_id = arguments.get("task_id")
    student_index = arguments.get("student_index")
    path = (arguments.get("path") or "").strip()
    if not task_id or student_index is None:
        return [TextContent(type="text", text="Provide task_id and student_index. Optionally pass path (e.g. '' for root, 'README.md', 'src') to fetch a specific file or directory.")]
    username = user.get("user_id")
    out = tq.get_authorized_submission_contents_for_professor(username, int(task_id), int(student_index), path=path)
    if not out:
        return [TextContent(type="text", text="Not found or you are not the task creator for this submission.")]
    if out.get("error"):
        return [TextContent(type="text", text=f"Could not fetch repo contents: {out['error']}\n\nRepo: {out.get('repo_owner')}/{out.get('repo_name')} at ref {out.get('ref', '')[:7]}.")]
    text = out.get("contents_text") or ""
    header = f"Submission: {out.get('student_name')} — Task: {out.get('task_title')}\nRepo: {out.get('repo_owner')}/{out.get('repo_name')} at commit {out.get('ref', '')[:7]}\nPath: {out.get('path') or '(root)'}\n\n"
    return [TextContent(type="text", text=header + text)]


TASK_TOOLS = [
    ToolDef(
        tool=Tool(
            name="task_list_my",
            description="List tasks assigned to the current student. Student only.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        handler=task_list_my_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_get_my",
            description="Get details of one assigned task for the current student. Pass assignment_id or task_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "assignment_id": {"type": "integer", "description": "Assignment ID"},
                    "task_id": {"type": "integer", "description": "Task ID (alternative)"},
                },
                "required": [],
            },
        ),
        handler=task_get_my_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_submit_by_repo",
            description="Submit a task by pasting the GitHub repo URL. Student only; you can only submit for yourself. Requires GitHub account linked (with token). Pass assignment_id from task_list_my and repo_url (e.g. https://github.com/owner/repo).",
            inputSchema={
                "type": "object",
                "properties": {
                    "assignment_id": {"type": "integer", "description": "Assignment ID (from task_list_my)"},
                    "repo_url": {"type": "string", "description": "GitHub repo URL, e.g. https://github.com/owner/repo"},
                    "branch": {"type": "string", "description": "Branch name (optional; default from repo if omitted)"},
                },
                "required": ["assignment_id", "repo_url"],
            },
        ),
        handler=task_submit_by_repo_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_list_my_created_professor",
            description="List all tasks you created (professor only). Use this to see your task IDs before asking for submissions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        handler=task_list_my_created_professor_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_submissions_professor",
            description="List which students submitted a task (professor only). Includes repo links to preview. Pass task_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID"},
                },
                "required": ["task_id"],
            },
        ),
        handler=task_submissions_professor_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_get_submission_repo",
            description="Get one student's submission repo URL and commit for a task (professor only). Use to preview that student's GitHub repo. Pass task_id and student_index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID"},
                    "student_index": {"type": "integer", "description": "Student index number"},
                },
                "required": ["task_id", "student_index"],
            },
        ),
        handler=task_get_submission_repo_handler,
    ),
    ToolDef(
        tool=Tool(
            name="task_get_submission_contents",
            description="Fetch the actual file/directory contents of a student's submitted repo (professor only). Use this to analyze and grade the submission: you get the repo contents at the submitted commit (README, code, etc.) so you can evaluate it. Pass task_id and student_index; optionally path (e.g. empty for root listing + README, or 'src', 'README.md') to get a specific file or folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID"},
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "path": {"type": "string", "description": "Optional: path in repo ('' for root, 'README.md', 'src', etc.)"},
                },
                "required": ["task_id", "student_index"],
            },
        ),
        handler=task_get_submission_contents_handler,
    ),
]
