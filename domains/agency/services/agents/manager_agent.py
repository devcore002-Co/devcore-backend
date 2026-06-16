"""Agency Manager Agent — monitors clients, projects, invoices and drafts actions."""
import os
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from domains.agency.models.agent_task import AgentTask
from domains.agency.models.client import Client
from domains.agency.models.project import Project
from domains.agency.models.invoice import Invoice
from domains.agency.services.agents.base import BaseAgent

_DAYS_STALE = 7      # flag projects with no update in this many days
_DAYS_OVERDUE = 0    # flag invoices past due_date


class ManagerAgent(BaseAgent):
    name = "manager"

    async def run(self) -> list[AgentTask]:
        tasks: list[AgentTask] = []
        today = date.today()

        # ── 1. Overdue invoices ──────────────────────────────────
        result = await self.db.execute(
            select(Invoice).where(Invoice.status.in_(["sent", "draft"]))
        )
        invoices = result.scalars().all()
        for inv in invoices:
            if not inv.due_date:
                continue
            due = inv.due_date if isinstance(inv.due_date, date) else date.fromisoformat(str(inv.due_date))
            days_late = (today - due).days
            if days_late > _DAYS_OVERDUE:
                client_res = await self.db.execute(select(Client).where(Client.id == inv.client_id))
                client = client_res.scalar_one_or_none()
                client_name = client.name if client else f"Client #{inv.client_id}"
                draft_msg = await self._draft_reminder(client_name, inv, days_late)
                task = await self._save_task(
                    task_type="invoice_reminder",
                    title=f"Invoice #{inv.invoice_number} overdue {days_late}d — send reminder to {client_name}",
                    context={
                        "invoice_id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "client_name": client_name,
                        "client_email": client.email if client else None,
                        "amount": inv.total,
                        "currency": inv.currency,
                        "due_date": str(inv.due_date) if inv.due_date else None,
                        "days_late": days_late,
                    },
                    draft={"message": draft_msg, "channel": "whatsapp"},
                    priority="high" if days_late > 7 else "normal",
                )
                tasks.append(task)

        # ── 2. Stale active projects ─────────────────────────────
        result = await self.db.execute(
            select(Project).where(Project.status == "active")
        )
        projects = result.scalars().all()
        for proj in projects:
            updated = proj.updated_at if proj.updated_at else proj.created_at
            days_since = (datetime.now(timezone.utc) - updated.replace(tzinfo=timezone.utc)).days
            if days_since >= _DAYS_STALE:
                client_res = await self.db.execute(select(Client).where(Client.id == proj.client_id))
                client = client_res.scalar_one_or_none()
                client_name = client.name if client else f"Client #{proj.client_id}"
                draft_msg = await self._draft_project_update(client_name, proj, days_since)
                task = await self._save_task(
                    task_type="project_update",
                    title=f'"{proj.title}" — send {days_since}d update to {client_name}',
                    context={
                        "project_id": proj.id,
                        "project_title": proj.title,
                        "client_name": client_name,
                        "client_email": client.email if client else None,
                        "days_since_update": days_since,
                        "status": proj.status,
                        "deadline": str(proj.deadline) if proj.deadline else None,
                    },
                    draft={"message": draft_msg, "channel": "whatsapp"},
                )
                tasks.append(task)

        # ── 3. Approaching deadlines ─────────────────────────────
        for proj in projects:
            if not proj.deadline:
                continue
            dl = proj.deadline if isinstance(proj.deadline, date) else date.fromisoformat(str(proj.deadline))
            days_left = (dl - today).days
            if 0 <= days_left <= 3:
                client_res = await self.db.execute(select(Client).where(Client.id == proj.client_id))
                client = client_res.scalar_one_or_none()
                client_name = client.name if client else f"Client #{proj.client_id}"
                task = await self._save_task(
                    task_type="deadline_alert",
                    title=f'"{proj.title}" deadline in {days_left}d — alert {client_name}',
                    context={
                        "project_id": proj.id,
                        "project_title": proj.title,
                        "client_name": client_name,
                        "deadline": str(proj.deadline) if proj.deadline else None,
                        "days_left": days_left,
                    },
                    draft={
                        "message": (
                            f"Hi {client_name}, just a reminder that your project "
                            f'"{proj.title}" is due in {days_left} day(s) on {proj.deadline}. '
                            "Please review and confirm everything is on track. — DevCore Team"
                        ),
                        "channel": "whatsapp",
                    },
                    priority="high",
                )
                tasks.append(task)

        return tasks

    async def execute(self, task: AgentTask) -> dict:
        """Execution for manager tasks is sending the drafted message."""
        # WhatsApp / email sending will be wired when Meta API keys are added.
        return {
            "sent": False,
            "note": "Message queued — WhatsApp API not yet connected. Add META_ACCESS_TOKEN to activate sending.",
            "draft_message": task.draft.get("message", ""),
        }

    # ── AI drafting helpers ──────────────────────────────────────

    async def _draft_reminder(self, client_name: str, inv: Invoice, days_late: int) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return (
                f"Hi {client_name}, this is a reminder that Invoice #{inv.invoice_number} "
                f"for {inv.currency} {inv.total:,.2f} was due on {inv.due_date} "
                f"({days_late} days ago). Please arrange payment at your earliest convenience. "
                "Thank you — DevCore Team"
            )
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            messages=[
                {"role": "system", "content": "You write short, professional but warm WhatsApp invoice reminder messages for a Ghana-based tech agency called DevCore. Keep it under 80 words."},
                {"role": "user", "content": f"Client: {client_name}. Invoice #{inv.invoice_number} for {inv.currency} {inv.total:,.2f}, due {inv.due_date}, {days_late} days overdue."},
            ],
        )
        return resp.choices[0].message.content.strip()

    async def _draft_project_update(self, client_name: str, proj: Project, days_since: int) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return (
                f"Hi {client_name}, we're checking in on your project \"{proj.title}\". "
                "Work is progressing well. We'll share a full update shortly. "
                "Feel free to reach out if you have any questions. — DevCore Team"
            )
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=200,
            messages=[
                {"role": "system", "content": "You write short, professional WhatsApp project update messages for DevCore, a Ghana-based software & marketing agency. Keep it under 60 words."},
                {"role": "user", "content": f"Client: {client_name}. Project: \"{proj.title}\". No update sent in {days_since} days. Status: {proj.status}. Deadline: {proj.deadline or 'not set'}."},
            ],
        )
        return resp.choices[0].message.content.strip()
