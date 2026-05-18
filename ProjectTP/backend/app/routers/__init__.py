from __future__ import annotations

from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    from app.routers import (
        admin_users,
        auth,
        duties_live as duties,
        duty_notify_dispatch,
        duty_swaps,
        exports as exports_routes,
        instruction,
        me_duty_leave,
        reports,
    )

    app.include_router(auth.router)
    app.include_router(instruction.router)
    app.include_router(me_duty_leave.router)
    app.include_router(admin_users.router)
    # Регистрируется до duties.router: те же пути dispatch, но с query strict_timing (см. duty_notify_dispatch).
    app.include_router(duty_notify_dispatch.router)
    app.include_router(duties.router)
    app.include_router(duty_swaps.router)
    app.include_router(reports.router)
    app.include_router(exports_routes.router)
