from __future__ import annotations

from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    from app.routers import admin_users, auth, duties, duty_swaps, exports as exports_routes, instruction, reports

    app.include_router(auth.router)
    app.include_router(instruction.router)
    app.include_router(admin_users.router)
    app.include_router(duties.router)
    app.include_router(duty_swaps.router)
    app.include_router(reports.router)
    app.include_router(exports_routes.router)
