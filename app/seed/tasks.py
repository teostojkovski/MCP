"""
Create task-related tables (tasks, task_assignments, task_submissions, github_accounts).
Run once after DB and users/subjects/professors/students exist.
"""
from __future__ import annotations

from app.db import engine
from app.models import Base, Task, TaskAssignment, TaskSubmission, GitHubAccount


def create_task_tables() -> None:
    """Create task and GitHub account tables if they do not exist."""
    Base.metadata.create_all(
        engine,
        tables=[
            Task.__table__,
            TaskAssignment.__table__,
            TaskSubmission.__table__,
            GitHubAccount.__table__,
        ],
    )


if __name__ == "__main__":
    create_task_tables()
    print("Task tables created.")
