"""
Task creation, assignment, student task listing, repo linking, submission.
Authorization-safe helpers for both API and MCP/Claude.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db import SessionLocal
from app.models import (
    Task,
    TaskAssignment,
    TaskSubmission,
    Subject,
    Professor,
    Student,
    User,
)
import re
from app.queries.subjects import get_subject_enrolled_students
from app import github_service as gh


# Status values for TaskAssignment
STATUS_ASSIGNED = "ASSIGNED"
STATUS_VIEWED = "VIEWED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_REPO_LINKED = "REPO_LINKED"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_GRADED = "GRADED"


def _subject_name(session, subject_code: str) -> str:
    subj = session.query(Subject).filter(Subject.code == subject_code).first()
    return subj.name if subj else subject_code


# ---------- Professor: create task ----------
def create_task(
    professor_id: int,
    title: str,
    description: str,
    subject_id: str,
    deadline: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Professor creates a task for a subject. No professor-subject check (no such relation in schema)."""
    session = SessionLocal()
    try:
        prof = session.query(Professor).filter(Professor.id == professor_id).first()
        if not prof:
            raise ValueError("Professor not found")
        subject = session.query(Subject).filter(Subject.code == subject_id).first()
        if not subject:
            raise ValueError(f"Subject {subject_id} not found")
        task = Task(
            title=title.strip(),
            description=description.strip(),
            subject_id=subject_id,
            created_by_professor_id=professor_id,
            deadline=deadline,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "subject_id": task.subject_id,
            "subject_name": subject.name,
            "created_by_professor_id": task.created_by_professor_id,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }
    finally:
        session.close()


# ---------- Professor: assign task to all students in subject ----------
def assign_task_to_subject_students(task_id: int, professor_id: int) -> Dict[str, Any]:
    """Create TaskAssignment for every student enrolled in the task's subject. Idempotent."""
    session = SessionLocal()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        if task.created_by_professor_id != professor_id:
            raise ValueError("Only the task creator can assign it")
        students = get_subject_enrolled_students(task.subject_id)
        created = 0
        for s in students:
            idx = s["index"]
            existing = (
                session.query(TaskAssignment)
                .filter(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.student_index == idx,
                )
                .first()
            )
            if not existing:
                session.add(
                    TaskAssignment(
                        task_id=task_id,
                        student_index=idx,
                        status=STATUS_ASSIGNED,
                    )
                )
                created += 1
        session.commit()
        return {"task_id": task_id, "assigned_count": len(students), "new_assignments": created}
    finally:
        session.close()


def assign_task_to_students(
    task_id: int, professor_id: int, student_indices: List[int]
) -> Dict[str, Any]:
    """Create TaskAssignment for specific student indices (e.g. for demo). Idempotent. Only task creator."""
    session = SessionLocal()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        if task.created_by_professor_id != professor_id:
            raise ValueError("Only the task creator can assign it")
        created = 0
        for idx in student_indices:
            existing = (
                session.query(TaskAssignment)
                .filter(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.student_index == idx,
                )
                .first()
            )
            if not existing:
                session.add(
                    TaskAssignment(
                        task_id=task_id,
                        student_index=idx,
                        status=STATUS_ASSIGNED,
                    )
                )
                created += 1
        session.commit()
        return {"task_id": task_id, "assigned_count": len(student_indices), "new_assignments": created}
    finally:
        session.close()


# ---------- Professor: list tasks I created ----------
def list_tasks_created_by_professor(professor_id: int) -> List[Dict[str, Any]]:
    """All tasks created by this professor, with subject name and basic info."""
    session = SessionLocal()
    try:
        tasks = (
            session.query(Task)
            .filter(Task.created_by_professor_id == professor_id)
            .order_by(Task.created_at.desc())
            .all()
        )
        out = []
        for t in tasks:
            subject = session.query(Subject).filter(Subject.code == t.subject_id).first()
            out.append({
                "id": t.id,
                "title": t.title,
                "subject_id": t.subject_id,
                "subject_name": subject.name if subject else t.subject_id,
                "deadline": t.deadline.isoformat() if t.deadline else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
        return out
    finally:
        session.close()


def get_authorized_tasks_created_for_professor(username: str) -> Optional[List[Dict[str, Any]]]:
    """List all tasks created by the current user (professor). Returns None if not a professor."""
    session = SessionLocal()
    try:
        professor_id = _resolve_professor_id_for_username(session, username)
        if professor_id is None:
            return None
        return list_tasks_created_by_professor(professor_id)
    finally:
        session.close()


# ---------- Professor: get task details ----------
def get_task_for_professor(task_id: int, professor_id: int) -> Optional[Dict[str, Any]]:
    """Task details only if the professor created it."""
    session = SessionLocal()
    try:
        task = (
            session.query(Task)
            .filter(Task.id == task_id, Task.created_by_professor_id == professor_id)
            .first()
        )
        if not task:
            return None
        subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "subject_id": task.subject_id,
            "subject_name": subject.name if subject else task.subject_id,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }
    finally:
        session.close()


# ---------- Professor: submission overview ----------
def get_submission_overview_for_professor(
    task_id: int, professor_id: int
) -> Optional[Dict[str, Any]]:
    """List assigned students and submission status. Only for task creator."""
    session = SessionLocal()
    try:
        task = (
            session.query(Task)
            .filter(Task.id == task_id, Task.created_by_professor_id == professor_id)
            .first()
        )
        if not task:
            return None
        assignments = (
            session.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task_id)
            .order_by(TaskAssignment.student_index)
            .all()
        )
        subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
        submissions_list = []
        for a in assignments:
            student = session.query(Student).filter(Student.index == a.student_index).first()
            latest = (
                session.query(TaskSubmission)
                .filter(TaskSubmission.task_assignment_id == a.id)
                .order_by(TaskSubmission.submitted_at.desc())
                .first()
            )
            # Use submission row's submitted_at when available (source of truth for submit time)
            submitted_at_str = (
                latest.submitted_at.isoformat() if latest and latest.submitted_at else
                (a.submitted_at.isoformat() if a.submitted_at else None)
            )
            submissions_list.append({
                "assignment_id": a.id,
                "student_index": a.student_index,
                "student_name": f"{student.first_name} {student.last_name}" if student else str(a.student_index),
                "status": a.status,
                "linked_repo_url": a.linked_repo_url,
                "linked_repo_owner": a.linked_repo_owner,
                "linked_repo_name": a.linked_repo_name,
                "linked_branch": a.linked_branch,
                "submitted_at": submitted_at_str,
                "commit_sha": latest.commit_sha if latest else None,
            })
        total_assigned = len(assignments)
        total_submitted = sum(1 for a in assignments if a.status == STATUS_SUBMITTED or a.status == STATUS_GRADED)
        return {
            "task_id": task.id,
            "task_title": task.title,
            "subject_name": subject.name if subject else task.subject_id,
            "total_assigned": total_assigned,
            "total_submitted": total_submitted,
            "submissions": submissions_list,
        }
    finally:
        session.close()


# ---------- Student: list my assignments ----------
def list_my_assignments(student_index: int) -> List[Dict[str, Any]]:
    """All task assignments for this student with task and subject info."""
    session = SessionLocal()
    try:
        assignments = (
            session.query(TaskAssignment)
            .join(Task)
            .filter(TaskAssignment.student_index == student_index)
            .order_by(Task.created_at.desc())
            .all()
        )
        out = []
        for a in assignments:
            task = a.task
            subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
            out.append({
                "assignment_id": a.id,
                "task_id": task.id,
                "title": task.title,
                "description": task.description,
                "subject_name": subject.name if subject else task.subject_id,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "status": a.status,
                "linked_repo_owner": a.linked_repo_owner,
                "linked_repo_name": a.linked_repo_name,
                "linked_repo_url": a.linked_repo_url,
                "linked_branch": a.linked_branch,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            })
        return out
    finally:
        session.close()


# ---------- Student: get my assignment detail ----------
def get_my_assignment(student_index: int, assignment_id: int) -> Optional[Dict[str, Any]]:
    """Single assignment detail only if it belongs to this student."""
    session = SessionLocal()
    try:
        a = (
            session.query(TaskAssignment)
            .filter(
                TaskAssignment.id == assignment_id,
                TaskAssignment.student_index == student_index,
            )
            .first()
        )
        if not a:
            return None
        task = a.task
        subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
        return {
            "assignment_id": a.id,
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "subject_name": subject.name if subject else task.subject_id,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "status": a.status,
            "linked_repo_owner": a.linked_repo_owner,
            "linked_repo_name": a.linked_repo_name,
            "linked_repo_url": a.linked_repo_url,
            "linked_branch": a.linked_branch,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
    finally:
        session.close()


# ---------- Student: link repo to assignment ----------
def link_repo_to_assignment(
    student_index: int,
    assignment_id: int,
    repo_owner: str,
    repo_name: str,
    repo_url: str,
    branch: str,
    user_id: int,
) -> Dict[str, Any]:
    """Link a GitHub repo to the assignment. Verifies assignment ownership and optionally repo access."""
    session = SessionLocal()
    try:
        a = (
            session.query(TaskAssignment)
            .filter(
                TaskAssignment.id == assignment_id,
                TaskAssignment.student_index == student_index,
            )
            .first()
        )
        if not a:
            raise ValueError("Assignment not found or not yours")
        ok, msg = gh.validate_repository(repo_owner, repo_name, user_id)
        if not ok:
            raise ValueError(msg or "Could not validate repository")
        a.linked_repo_owner = repo_owner.strip()
        a.linked_repo_name = repo_name.strip()
        a.linked_repo_url = repo_url.strip() or f"https://github.com/{repo_owner}/{repo_name}"
        a.linked_branch = branch.strip() or "main"
        a.status = STATUS_REPO_LINKED
        session.commit()
        session.refresh(a)
        return {
            "assignment_id": a.id,
            "status": a.status,
            "linked_repo_owner": a.linked_repo_owner,
            "linked_repo_name": a.linked_repo_name,
            "linked_repo_url": a.linked_repo_url,
            "linked_branch": a.linked_branch,
        }
    finally:
        session.close()


# ---------- Student: submit by repo URL (for LLM: paste link, submit for self only) ----------
def _parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from URLs like https://github.com/owner/repo or https://github.com/owner/repo/."""
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("repo_url is required")
    url = repo_url.strip()
    # Match github.com/owner/repo (with optional .git and trailing slashes)
    m = re.match(
        r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?\s*$",
        url,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip().removesuffix(".git")
    # Also allow short form owner/repo
    m = re.match(r"([^/]+)/([^/]+?)(?:\.git)?\s*$", url)
    if m:
        return m.group(1).strip(), m.group(2).strip().removesuffix(".git")
    raise ValueError(
        "Invalid GitHub repo URL. Use https://github.com/owner/repo or owner/repo"
    )


def submit_assignment_by_repo_url(
    student_index: int,
    assignment_id: int,
    user_id: int,
    repo_url: str,
    branch: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit an assignment by pasting a GitHub repo URL. Only the assigned student can submit.
    Links the repo then creates submission with latest commit SHA.
    Requires the student to have linked their GitHub account (with token) so we can verify the repo.
    """
    owner, repo = _parse_github_repo_url(repo_url)
    canonical_url = f"https://github.com/{owner}/{repo}"
    # Get default branch if not provided
    if not branch or not branch.strip():
        ok, default_branch = gh.validate_repository(owner, repo, user_id)
        if not ok:
            raise ValueError(default_branch or "Could not validate repository")
        branch = default_branch or "main"
    else:
        branch = branch.strip()
        ok, msg = gh.validate_repository(owner, repo, user_id)
        if not ok:
            raise ValueError(msg or "Could not validate repository")
    # Link repo then submit (both enforce assignment belongs to student_index)
    link_repo_to_assignment(
        student_index, assignment_id, owner, repo, canonical_url, branch, user_id
    )
    return submit_assignment(student_index, assignment_id, user_id)


# ---------- Student: submit assignment ----------
def submit_assignment(student_index: int, assignment_id: int, user_id: int) -> Dict[str, Any]:
    """Create submission snapshot (repo + latest commit SHA) and set status to SUBMITTED."""
    session = SessionLocal()
    try:
        a = (
            session.query(TaskAssignment)
            .filter(
                TaskAssignment.id == assignment_id,
                TaskAssignment.student_index == student_index,
            )
            .first()
        )
        if not a:
            raise ValueError("Assignment not found or not yours")
        if not a.linked_repo_owner or not a.linked_repo_name:
            raise ValueError("Link a repository first before submitting")
        sha, err = gh.get_latest_commit_sha(
            a.linked_repo_owner, a.linked_repo_name, a.linked_branch or "main", user_id
        )
        if err or not sha:
            raise ValueError(err or "Could not get latest commit SHA")
        now = datetime.now(timezone.utc)
        sub = TaskSubmission(
            task_assignment_id=a.id,
            github_repo_owner=a.linked_repo_owner,
            github_repo_name=a.linked_repo_name,
            github_repo_url=a.linked_repo_url or f"https://github.com/{a.linked_repo_owner}/{a.linked_repo_name}",
            branch=a.linked_branch or "main",
            commit_sha=sha,
        )
        session.add(sub)
        a.status = STATUS_SUBMITTED
        a.submitted_at = now
        session.commit()
        session.refresh(a)
        return {
            "assignment_id": a.id,
            "status": a.status,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "repo_url": a.linked_repo_url,
            "branch": a.linked_branch,
            "commit_sha": sha,
        }
    finally:
        session.close()


# ---------- Authorization helpers for Claude / MCP ----------
def get_authorized_task_for_student(
    username: str, assignment_id: Optional[int] = None, task_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Return task/assignment data only if the current user (by username) is the assigned student.
    For MCP: pass session user_id (username) and either assignment_id or task_id.
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user or user.student_index is None:
            return None
        student_index = user.student_index
        if assignment_id is not None:
            a = (
                session.query(TaskAssignment)
                .filter(
                    TaskAssignment.id == assignment_id,
                    TaskAssignment.student_index == student_index,
                )
                .first()
            )
            if not a:
                return None
            task = a.task
            subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
            return {
                "assignment_id": a.id,
                "task_id": task.id,
                "title": task.title,
                "description": task.description,
                "subject_name": subject.name if subject else task.subject_id,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "status": a.status,
                "linked_repo_url": a.linked_repo_url,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
        if task_id is not None:
            a = (
                session.query(TaskAssignment)
                .filter(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.student_index == student_index,
                )
                .first()
            )
            if not a:
                return None
            task = a.task
            subject = session.query(Subject).filter(Subject.code == task.subject_id).first()
            return {
                "assignment_id": a.id,
                "task_id": task.id,
                "title": task.title,
                "description": task.description,
                "subject_name": subject.name if subject else task.subject_id,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "status": a.status,
                "linked_repo_url": a.linked_repo_url,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
        return None
    finally:
        session.close()


def _resolve_professor_id_for_username(session, username: str) -> Optional[int]:
    """
    Resolve username to professor_id. Uses User.professor_id if set.
    If User exists but professor_id is None, infers from username 'prof_<id>'
    (convention from consultation seed) and backfills User.professor_id.
    """
    if not username or not isinstance(username, str):
        return None
    user = session.query(User).filter(User.username == username.strip()).first()
    if not user:
        return None
    pid = getattr(user, "professor_id", None)
    if pid is not None:
        return int(pid)
    # Backfill: username prof_<id> -> Professor.id
    m = re.match(r"^prof_(\d+)$", (username or "").strip(), re.IGNORECASE)
    if not m:
        return None
    try:
        prof_id = int(m.group(1))
    except (ValueError, IndexError):
        return None
    prof = session.query(Professor).filter(Professor.id == prof_id).first()
    if not prof:
        return None
    user.professor_id = prof_id
    try:
        session.commit()
    except Exception:
        session.rollback()
    return prof_id


def get_authorized_submission_overview_for_professor(
    username: str, task_id: int
) -> Optional[Dict[str, Any]]:
    """
    Return submission overview only if the current user (by username) is the task's professor.
    For MCP: pass session user_id (username) and task_id.
    """
    session = SessionLocal()
    try:
        professor_id = _resolve_professor_id_for_username(session, username)
        if professor_id is None:
            return None
        return get_submission_overview_for_professor(task_id, professor_id)
    finally:
        session.close()


def get_authorized_submission_repo_for_professor(
    username: str, task_id: int, student_index: int
) -> Optional[Dict[str, Any]]:
    """
    Return one student's submission repo URL and commit SHA for a task.
    Professor only; only for tasks they created. Lets professor preview that student's repo via LLM.
    """
    session = SessionLocal()
    try:
        professor_id = _resolve_professor_id_for_username(session, username)
        if professor_id is None:
            return None
        task = (
            session.query(Task)
            .filter(
                Task.id == task_id,
                Task.created_by_professor_id == professor_id,
            )
            .first()
        )
        if not task:
            return None
        a = (
            session.query(TaskAssignment)
            .filter(
                TaskAssignment.task_id == task_id,
                TaskAssignment.student_index == student_index,
            )
            .first()
        )
        if not a:
            return None
        student = session.query(Student).filter(Student.index == student_index).first()
        latest = (
            session.query(TaskSubmission)
            .filter(TaskSubmission.task_assignment_id == a.id)
            .order_by(TaskSubmission.submitted_at.desc())
            .first()
        )
        return {
            "task_id": task_id,
            "task_title": task.title,
            "student_index": student_index,
            "student_name": f"{student.first_name} {student.last_name}" if student else str(student_index),
            "repo_url": a.linked_repo_url,
            "repo_owner": a.linked_repo_owner,
            "repo_name": a.linked_repo_name,
            "branch": a.linked_branch,
            "commit_sha": latest.commit_sha if latest else None,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
    finally:
        session.close()


def get_authorized_submission_contents_for_professor(
    username: str,
    task_id: int,
    student_index: int,
    path: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Fetch repo contents for a student's submission so the professor (or LLM) can analyze/grade it.
    Returns dict with contents_text, repo_owner, repo_name, ref, path; or None if not authorized.
    Uses the submission's stored commit SHA so we analyze the exact submitted version.
    """
    repo_info = get_authorized_submission_repo_for_professor(username, task_id, student_index)
    if not repo_info:
        return None
    owner = (repo_info.get("repo_owner") or "").strip()
    name = (repo_info.get("repo_name") or "").strip()
    ref = (repo_info.get("commit_sha") or repo_info.get("branch") or "main").strip()
    if not owner or not name:
        return {
            "contents_text": None,
            "error": "Submission has no repo owner/name stored.",
            "repo_owner": owner,
            "repo_name": name,
            "ref": ref,
            "path": path or "",
        }
    contents_text, err = gh.fetch_repo_contents(owner, name, ref, path=path or "", token=None)
    if err:
        return {
            "contents_text": None,
            "error": err,
            "repo_owner": owner,
            "repo_name": name,
            "ref": ref,
            "path": path or "",
        }
    return {
        "contents_text": contents_text,
        "error": None,
        "repo_owner": owner,
        "repo_name": name,
        "ref": ref,
        "path": path or "",
        "task_title": repo_info.get("task_title"),
        "student_name": repo_info.get("student_name"),
    }
