"""
FastAPI application entrypoint.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.storage.db import init_db
from backend.app.config import DB_PATH

app = FastAPI(
    title="Fact Knowledge Layer API",
    description=(
        "Ingests PDFs, extracts facts with grounded evidence, "
        "canonicalizes them, and reasons about cross-document relationships."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    init_db(DB_PATH)


@app.get("/health")
def health():
    return {"status": "ok"}
