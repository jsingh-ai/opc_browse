from __future__ import annotations

from fastapi import APIRouter, HTTPException

from opc_browse.config import get_settings
from opc_browse.models import (
    DashboardListResponse,
    DashboardPayload,
    DashboardSaveRequest,
)
from opc_browse.services.dashboards import (
    delete_dashboard,
    list_dashboards,
    load_dashboard,
    save_dashboard,
)


router = APIRouter(tags=["dashboards"])


@router.get("/dashboards", response_model=DashboardListResponse)
async def get_dashboards():
    settings = get_settings()
    return {"dashboards": list_dashboards(settings.dashboard_storage_dir)}


@router.post("/dashboards", response_model=DashboardPayload)
async def create_or_update_dashboard(payload: DashboardSaveRequest):
    settings = get_settings()
    try:
        saved = save_dashboard(payload.model_dump(), settings.dashboard_storage_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return saved


@router.get("/dashboards/{dashboard_id}", response_model=DashboardPayload)
async def get_dashboard(dashboard_id: str):
    settings = get_settings()
    try:
        return load_dashboard(dashboard_id, settings.dashboard_storage_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc


@router.delete("/dashboards/{dashboard_id}")
async def remove_dashboard(dashboard_id: str):
    settings = get_settings()
    return {"deleted": delete_dashboard(dashboard_id, settings.dashboard_storage_dir)}
