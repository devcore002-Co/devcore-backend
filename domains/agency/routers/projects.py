from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from domains.agency.database import get_db
from domains.agency.models.project import Project

router = APIRouter(prefix="/projects", tags=["Agency · Projects"])


class ProjectCreate(BaseModel):
    client_id: int
    title: str
    description: Optional[str] = None
    service_type: Optional[str] = None
    status: str = "active"
    budget: Optional[float] = None
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    github_repo: Optional[str] = None
    vercel_url: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    service_type: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[str] = None
    github_repo: Optional[str] = None
    vercel_url: Optional[str] = None


def _d(v) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _out(p: Project, include_client: bool = False) -> dict:
    d = {
        "id": p.id, "client_id": p.client_id, "title": p.title,
        "description": p.description, "service_type": p.service_type,
        "status": p.status, "budget": p.budget,
        "start_date": _d(p.start_date), "deadline": _d(p.deadline),
        "github_repo": p.github_repo, "vercel_url": p.vercel_url,
        "created_at": _d(p.created_at), "updated_at": _d(p.updated_at),
        "client_name": None,
    }
    if include_client and p.client:
        d["client_name"] = p.client.name
    return d


@router.get("/")
async def list_projects(
    status: Optional[str] = None,
    client_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Project).options(selectinload(Project.client)).order_by(Project.created_at.desc())
    if status:
        q = q.where(Project.status == status)
    if client_id:
        q = q.where(Project.client_id == client_id)
    result = await db.execute(q)
    return [_out(p, include_client=True) for p in result.scalars().all()]


@router.post("/", status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    p = Project(**body.model_dump())
    db.add(p)
    await db.flush()
    await db.refresh(p)
    return _out(p)


@router.patch("/{project_id}")
async def update_project(project_id: int, body: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Project not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.flush()
    await db.refresh(p)
    return _out(p)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Project not found")
    await db.delete(p)
