"""FastAPI app wiring. The routers are thin; the logic lives in the modules they
call. See docs/03-architecture.md."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import SessionLocal, init_db
from app.models import Client
from app.routers import clients, documents

app = FastAPI(title="Document Collection")

# The React dev server runs on 5173; allow it during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router)
app.include_router(documents.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    # If the database is empty, seed the Rivera demo so the app is useful on first run.
    with SessionLocal() as db:
        if db.query(Client).count() == 0:
            from app.seed import seed

            seed(db)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# Serve the built React app if it exists (production), so the whole thing runs
# from one process. In dev you use the Vite server instead.
_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
