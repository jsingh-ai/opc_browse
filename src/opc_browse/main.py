from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from opc_browse.routers import (
    analysis,
    dashboards,
    health,
    machines,
    tag_profiles,
    tags,
    timeseries,
)


app = FastAPI(title="opc_browse", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

app.include_router(health.router)
app.include_router(machines.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(tag_profiles.router, prefix="/api")
app.include_router(timeseries.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(dashboards.router, prefix="/api")
