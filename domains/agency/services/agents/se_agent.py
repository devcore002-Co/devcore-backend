"""Software Engineer Agent — uses Claude to write code, opens GitHub PRs, deploys to Vercel."""
import os
import base64
import httpx
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agency.models.agent_task import AgentTask
from domains.agency.services.agents.base import BaseAgent

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class SEAgent(BaseAgent):
    name = "software_engineer"

    async def run(self) -> list[AgentTask]:
        """SE agent tasks are created on-demand, not by scanning — return empty."""
        return []

    async def create_task(
        self,
        repo: str,
        task_description: str,
        target_files: list[str] | None = None,
        priority: str = "normal",
    ) -> AgentTask:
        """Create a coding task. `repo` = 'devcore002-Co/repo-name'."""
        task = await self._save_task(
            task_type="code_task",
            title=f"[SE] {task_description[:120]}",
            context={
                "repo": repo,
                "description": task_description,
                "target_files": target_files or [],
            },
            draft={"status": "queued", "plan": ""},
            priority=priority,
        )
        return task

    async def execute(self, task: AgentTask) -> dict:
        """Generate code with GPT-4o, open a GitHub PR, optionally trigger Vercel deploy."""
        repo = task.context.get("repo", "")
        description = task.context.get("description", "")
        target_files = task.context.get("target_files", [])

        if not repo or not description:
            return {"error": "Missing repo or description in task context"}
        if not GITHUB_TOKEN:
            return {"error": "GITHUB_TOKEN not set"}
        if not OPENAI_API_KEY:
            return {"error": "OPENAI_API_KEY not set"}

        # 1. Read relevant files from GitHub
        file_contents = await self._read_files(repo, target_files)

        # 2. Ask GPT-4o to write the code changes
        changes = await self._generate_changes(description, file_contents)

        # 3. Create branch + commit changes + open PR
        pr_url = await self._open_pr(repo, description, changes)

        return {
            "pr_url": pr_url,
            "files_changed": list(changes.keys()),
            "repo": repo,
        }

    # ── GitHub helpers ───────────────────────────────────────────

    async def _read_files(self, repo: str, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        async with httpx.AsyncClient() as client:
            for path in paths[:10]:
                r = await client.get(
                    f"https://api.github.com/repos/{repo}/contents/{path}",
                    headers=GH_HEADERS, timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("encoding") == "base64":
                        contents[path] = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return contents

    async def _generate_changes(self, description: str, file_contents: dict[str, str]) -> dict[str, str]:
        context_block = ""
        for path, content in file_contents.items():
            context_block += f"\n\n--- {path} ---\n{content[:3000]}"

        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert software engineer working on DevCore Agency's codebase. "
                        "When given a task, output ONLY valid JSON in this exact format:\n"
                        '{"path/to/file.py": "full file content here", "path/to/other.py": "..."}\n'
                        "Include only files that need to be created or modified. "
                        "Write production-quality code. No explanations outside the JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Task: {description}\n\nExisting files for context:{context_block}\n\nOutput the JSON with file changes:",
                },
            ],
            response_format={"type": "json_object"},
        )
        import json
        raw = resp.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

    async def _open_pr(self, repo: str, description: str, changes: dict[str, str]) -> str:
        if not changes:
            return ""

        import re, time
        branch = "agent/se-" + re.sub(r"[^a-z0-9]", "-", description[:40].lower()) + f"-{int(time.time())}"

        async with httpx.AsyncClient() as client:
            # Get default branch SHA
            r = await client.get(f"https://api.github.com/repos/{repo}", headers=GH_HEADERS, timeout=10)
            default_branch = r.json().get("default_branch", "main")

            r = await client.get(
                f"https://api.github.com/repos/{repo}/git/refs/heads/{default_branch}",
                headers=GH_HEADERS, timeout=10,
            )
            base_sha = r.json()["object"]["sha"]

            # Create branch
            await client.post(
                f"https://api.github.com/repos/{repo}/git/refs",
                headers=GH_HEADERS, timeout=10,
                json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            )

            # Commit each file
            for path, content in changes.items():
                # Check if file exists
                existing = await client.get(
                    f"https://api.github.com/repos/{repo}/contents/{path}",
                    headers=GH_HEADERS, timeout=10,
                )
                payload: dict = {
                    "message": f"[SE Agent] {description[:72]}",
                    "content": base64.b64encode(content.encode()).decode(),
                    "branch": branch,
                }
                if existing.status_code == 200:
                    payload["sha"] = existing.json()["sha"]
                await client.put(
                    f"https://api.github.com/repos/{repo}/contents/{path}",
                    headers=GH_HEADERS, timeout=15, json=payload,
                )

            # Open PR
            pr_resp = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=GH_HEADERS, timeout=10,
                json={
                    "title": f"[SE Agent] {description[:72]}",
                    "body": f"Automated PR from DevCore SE Agent.\n\n**Task:** {description}\n\n**Files changed:** {', '.join(changes.keys())}",
                    "head": branch,
                    "base": default_branch,
                },
            )
            return pr_resp.json().get("html_url", "")
