"""
Web server for device login, consultations UI, and task assignment + GitHub submission.
Run: uvicorn dev_run:app --host 127.0.0.1 --port 8000
Open http://127.0.0.1:8000/device to log in; /consultations; /tasks (professor); /my-tasks (student).
"""
from app.web.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
