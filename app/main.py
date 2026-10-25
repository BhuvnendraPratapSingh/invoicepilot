"""InvoicePilot — AP Decision Workbench

Main application entry point.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.config import settings
from app.db import init_db, SessionLocal
from app.api.routes import router as api_router
from app.services.seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    init_db()

    # Seed data if tables are empty
    db = SessionLocal()
    try:
        from app.models.vendor import Vendor
        if db.query(Vendor).count() == 0:
            seed_all(db)
            print("✓ Seed data loaded")
        else:
            print("✓ Database already populated")
    finally:
        db.close()

    # Mark any interrupted processing attempts
    db = SessionLocal()
    try:
        from app.models.invoice import ProcessingAttempt
        interrupted = db.query(ProcessingAttempt).filter(
            ProcessingAttempt.execution_state == "RUNNING"
        ).all()
        for att in interrupted:
            att.execution_state = "INTERRUPTED"
            att.error_message = "Process interrupted during startup recovery"
        if interrupted:
            db.commit()
            print(f"⚠ Marked {len(interrupted)} interrupted processing attempts")
    finally:
        db.close()

    yield


app = FastAPI(
    title="InvoicePilot",
    description="AP Decision Workbench — AI-assisted extraction with deterministic financial controls",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files and templates
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# API routes
app.include_router(api_router)


# ─── HTML Pages ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "demo_mode": settings.demo_mode,
        "business_date": str(settings.get_business_date()),
    })


@app.get("/case/{case_id}", response_class=HTMLResponse)
async def case_detail_page(request: Request, case_id: str):
    return templates.TemplateResponse(request, "case_detail.html", {
        "case_id": case_id,
        "demo_mode": settings.demo_mode,
        "business_date": str(settings.get_business_date()),
    })


@app.get("/health-page", response_class=HTMLResponse)
async def health_page(request: Request):
    return templates.TemplateResponse(request, "health.html", {
        "demo_mode": settings.demo_mode,
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", settings.app_port))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
