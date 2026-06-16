"""Base agent interface shared by all DevCore Agency agents."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from domains.agency.models.agent_task import AgentTask


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _save_task(
        self,
        task_type: str,
        title: str,
        context: dict,
        draft: dict,
        priority: str = "normal",
    ) -> AgentTask:
        task = AgentTask(
            agent_name=self.name,
            task_type=task_type,
            status="pending",
            priority=priority,
            title=title,
            context=context,
            draft=draft,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    @abstractmethod
    async def run(self) -> list[AgentTask]:
        """Analyse data and produce pending draft tasks."""

    @abstractmethod
    async def execute(self, task: AgentTask) -> dict:
        """Execute an approved task and return a result dict."""
