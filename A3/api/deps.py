"""FastAPI dependencies shared by the routers (api/main.py, api/patient_api.py)."""

from fastapi import Request


def get_conn(request: Request):
    with request.app.state.pool.connection() as conn:
        yield conn
