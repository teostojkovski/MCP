"""
Create FastAPI app and include all routers. Same paths as original dev_run.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.web.routers import device, consultations_pages, consultations_api
from app.web.routers import tasks_pages, tasks_api, github_api, subjects_api


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(device.router)
    app.include_router(consultations_pages.router)
    app.include_router(consultations_api.router)
    app.include_router(tasks_pages.router)
    app.include_router(tasks_api.router)
    app.include_router(github_api.router)
    app.include_router(subjects_api.router)
    return app
