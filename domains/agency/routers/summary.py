from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from domains.agency.database import get_db
from domains.agency.models.client import Client
from domains.agency.models.project import Project
from domains.agency.models.invoice import Invoice
from domains.agency.models.agent_task import AgentTask

router = APIRouter(tags=["Agency · Summary"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)

    total_clients = await db.scalar(select(func.count(Client.id))) or 0
    active_projects = await db.scalar(
        select(func.count(Project.id)).where(Project.status == "active")
    ) or 0
    month_revenue = await db.scalar(
        select(func.sum(Invoice.total)).where(
            Invoice.status == "paid",
            cast(Invoice.paid_at, Date) >= month_start,
        )
    ) or 0
    overdue = await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.status.in_(["sent", "draft"]),
            Invoice.due_date.isnot(None),
            Invoice.due_date < today,
        )
    ) or 0
    pending_agent_tasks = await db.scalar(
        select(func.count(AgentTask.id)).where(AgentTask.status == "pending")
    ) or 0
    total_invoiced = await db.scalar(select(func.sum(Invoice.total))) or 0
    total_paid = await db.scalar(
        select(func.sum(Invoice.total)).where(Invoice.status == "paid")
    ) or 0

    return {
        "business": "DevCore Agency",
        "total_clients": total_clients,
        "active_projects": active_projects,
        "month_revenue_ghs": round(float(month_revenue), 2),
        "month_expenses_ghs": 0.0,
        "net_profit_ghs": round(float(month_revenue), 2),
        "overdue_invoices": overdue,
        "pending_agent_tasks": pending_agent_tasks,
        "total_invoiced_ghs": round(float(total_invoiced), 2),
        "total_paid_ghs": round(float(total_paid), 2),
        "outstanding_ghs": round(float(total_invoiced) - float(total_paid), 2),
    }
