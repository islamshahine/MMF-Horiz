"""FastAPI entrypoint: ``uvicorn api.main:app --reload`` (from repo root)."""

from fastapi import FastAPI

from api.routes import router

app = FastAPI(
    title="AQUASIGHT™ MMF Engine API",
    version="1.0.0",
    description="Engineering compute for horizontal multi-media filters. "
    "Single source of truth: ``engine.compute.compute_all``. "
    "POST ``/compute`` accepts SI JSON by default; pass ``unit_system=imperial`` to send US display units.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
