"""Agent API — run agents, list tasks, approve/reject, execute."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from domains.agency.database import get_db
from domains.agency.models.agent_task import AgentTask
from domains.agency.services.agents import ManagerAgent, SEAgent, MarketingAgent
from domains.agency.services.agents.marketing_agent import PLATFORMS, TONES, BUSINESS_PROFILES

router = APIRouter(prefix="/agents", tags=["Agency · Agents"])


def _out(t: AgentTask) -> dict:
    return {
        "id": t.id,
        "agent_name": t.agent_name,
        "task_type": t.task_type,
        "status": t.status,
        "priority": t.priority,
        "title": t.title,
        "context": t.context,
        "draft": t.draft,
        "result": t.result,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "executed_at": t.executed_at.isoformat() if t.executed_at else None,
    }


@router.post("/run/manager")
async def run_manager_agent(db: AsyncSession = Depends(get_db)):
    agent = ManagerAgent(db)
    tasks = await agent.run()
    return {"created": len(tasks), "tasks": [_out(t) for t in tasks]}


class SETaskRequest(BaseModel):
    repo: str
    description: str
    target_files: Optional[list[str]] = None
    priority: str = "normal"


@router.post("/run/software-engineer")
async def create_se_task(body: SETaskRequest, db: AsyncSession = Depends(get_db)):
    agent = SEAgent(db)
    task = await agent.create_task(
        repo=body.repo,
        task_description=body.description,
        target_files=body.target_files,
        priority=body.priority,
    )
    return _out(task)


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    agent_name: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(AgentTask).order_by(desc(AgentTask.created_at)).limit(limit)
    if status:
        q = q.where(AgentTask.status == status)
    if agent_name:
        q = q.where(AgentTask.agent_name == agent_name)
    result = await db.execute(q)
    return [_out(t) for t in result.scalars().all()]


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Task not found")
    return _out(t)


class ReviewBody(BaseModel):
    action: str
    edited_draft: Optional[dict] = None


@router.post("/tasks/{task_id}/review")
async def review_task(task_id: int, body: ReviewBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status != "pending":
        raise HTTPException(400, f"Task is already '{t.status}', cannot review")
    if body.action == "approve":
        t.status = "approved"
        if body.edited_draft:
            t.draft = body.edited_draft
    elif body.action == "reject":
        t.status = "rejected"
    else:
        raise HTTPException(400, "action must be 'approve' or 'reject'")
    t.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return _out(t)


@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status != "approved":
        raise HTTPException(400, "Task must be approved before executing")
    t.status = "executing"
    await db.flush()
    try:
        if t.agent_name == "manager":
            agent = ManagerAgent(db)
        elif t.agent_name == "software_engineer":
            agent = SEAgent(db)
        elif t.agent_name == "marketing":
            agent = MarketingAgent(db)
        else:
            raise HTTPException(400, f"Unknown agent: {t.agent_name}")
        result_data = await agent.execute(t)
        t.status = "done"
        t.result = result_data
    except Exception as exc:
        t.status = "failed"
        t.result = {"error": str(exc)}
    t.executed_at = datetime.now(timezone.utc)
    await db.flush()
    return _out(t)


@router.get("/summary")
async def agents_summary(db: AsyncSession = Depends(get_db)):
    all_tasks_result = await db.execute(select(AgentTask))
    tasks = all_tasks_result.scalars().all()
    by_status: dict = {}
    by_agent: dict = {}
    for t in tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_agent[t.agent_name] = by_agent.get(t.agent_name, 0) + 1
    return {
        "total": len(tasks),
        "by_status": by_status,
        "by_agent": by_agent,
        "pending_review": by_status.get("pending", 0),
    }


@router.get("/marketing/options")
async def marketing_options():
    return {
        "businesses": list(BUSINESS_PROFILES.keys()),
        "platforms": PLATFORMS,
        "tones": list(TONES.keys()),
    }


class SocialPostRequest(BaseModel):
    business: str
    platform: str
    topic: str
    tone: str = "professional"
    priority: str = "normal"


class ContentCalendarRequest(BaseModel):
    business: str
    platform: str
    days: int = 7
    theme: Optional[str] = ""
    tone: str = "professional"


class AdCopyRequest(BaseModel):
    business: str
    platform: str
    campaign: str
    budget_ghs: float = 0
    tone: str = "exciting"


class BroadcastRequest(BaseModel):
    business: str
    channel: str
    subject: str
    audience: str = "clients"
    tone: str = "professional"


class ContentBriefRequest(BaseModel):
    business: str
    client: str
    content_type: str
    platforms: list[str]
    media_url: str
    media_type: str = "image"
    notes: str = ""


@router.post("/run/marketing/social-post")
async def run_social_post(body: SocialPostRequest, db: AsyncSession = Depends(get_db)):
    agent = MarketingAgent(db)
    task = await agent.create_social_post(
        business=body.business, platform=body.platform,
        topic=body.topic, tone=body.tone, priority=body.priority,
    )
    return _out(task)


@router.post("/run/marketing/content-calendar")
async def run_content_calendar(body: ContentCalendarRequest, db: AsyncSession = Depends(get_db)):
    agent = MarketingAgent(db)
    task = await agent.create_content_calendar(
        business=body.business, platform=body.platform,
        days=body.days, theme=body.theme or "", tone=body.tone,
    )
    return _out(task)


@router.post("/run/marketing/ad-copy")
async def run_ad_copy(body: AdCopyRequest, db: AsyncSession = Depends(get_db)):
    agent = MarketingAgent(db)
    task = await agent.create_ad_copy(
        business=body.business, platform=body.platform,
        campaign=body.campaign, budget_ghs=body.budget_ghs, tone=body.tone,
    )
    return _out(task)


@router.post("/run/marketing/content-brief")
async def run_content_brief(body: ContentBriefRequest, db: AsyncSession = Depends(get_db)):
    agent = MarketingAgent(db)
    task = await agent.create_content_brief(
        business=body.business, client=body.client,
        content_type=body.content_type, platforms=body.platforms,
        media_url=body.media_url, media_type=body.media_type, notes=body.notes,
    )
    return _out(task)


@router.post("/run/marketing/broadcast")
async def run_broadcast(body: BroadcastRequest, db: AsyncSession = Depends(get_db)):
    agent = MarketingAgent(db)
    task = await agent.create_broadcast(
        business=body.business, channel=body.channel,
        subject=body.subject, audience=body.audience, tone=body.tone,
    )
    return _out(task)
