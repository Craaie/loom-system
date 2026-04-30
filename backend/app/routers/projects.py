"""项目管理路由"""

import uuid
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.project import ProjectCreate
from app.db.repository import get_repository

logger = logging.getLogger("loom.router.projects")
router = APIRouter(prefix="/api/v2", tags=["projects"])


@router.post("/projects")
async def create_project(req: ProjectCreate):
    repo = get_repository()
    project_id = str(uuid.uuid4())
    project = repo.create_project(project_id, req.name, req.description)
    return {"id": project.id, "name": project.name}


@router.get("/projects")
async def list_projects():
    repo = get_repository()
    projects = repo.get_projects()
    return [{"id": p.id, "name": p.name} for p in projects]


@router.get("/projects/{id}/stats")
async def get_project_stats(id: str):
    repo = get_repository()
    return repo.get_project_stats(id)


@router.delete("/projects/{id}")
async def delete_project(id: str):
    repo = get_repository()
    success = repo.delete_project(id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "id": id}
