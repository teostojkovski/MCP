"""
Pydantic schemas for task API (optional validation and docs).
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., max_length=10000)
    subject_id: str = Field(..., min_length=1, max_length=20)
    deadline: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    subject_id: str
    subject_name: str
    deadline: Optional[str] = None
    created_at: Optional[str] = None


class StudentTaskResponse(BaseModel):
    assignment_id: int
    task_id: int
    title: str
    description: str
    subject_name: str
    deadline: Optional[str] = None
    status: str
    linked_repo_owner: Optional[str] = None
    linked_repo_name: Optional[str] = None
    linked_repo_url: Optional[str] = None
    linked_branch: Optional[str] = None
    submitted_at: Optional[str] = None


class LinkGitHubRequest(BaseModel):
    github_username: str = Field(..., min_length=1)
    github_user_id: Optional[str] = None
    access_token: Optional[str] = None


class LinkRepoRequest(BaseModel):
    repo_owner: str = Field(..., min_length=1)
    repo_name: str = Field(..., min_length=1)
    repo_url: Optional[str] = None
    branch: str = Field(default="main", max_length=255)


class SubmitTaskResponse(BaseModel):
    assignment_id: int
    status: str
    submitted_at: Optional[str] = None
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None


class SubmissionRow(BaseModel):
    assignment_id: int
    student_index: int
    student_name: str
    status: str
    linked_repo_url: Optional[str] = None
    linked_repo_owner: Optional[str] = None
    linked_repo_name: Optional[str] = None
    linked_branch: Optional[str] = None
    submitted_at: Optional[str] = None
    commit_sha: Optional[str] = None


class TaskSubmissionOverviewResponse(BaseModel):
    task_id: int
    task_title: str
    subject_name: str
    total_assigned: int
    total_submitted: int
    submissions: List[SubmissionRow]
