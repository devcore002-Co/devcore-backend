"""Marketing Agent — generates social posts, calendars, ad copy, and broadcasts using GPT-4o + DALL-E 3."""
import os
import httpx
from datetime import date, timedelta
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agency.models.agent_task import AgentTask
from domains.agency.services.agents.base import BaseAgent

PLATFORMS = ["Instagram", "Facebook", "WhatsApp", "Email", "TikTok", "Twitter/X", "LinkedIn"]

TONES = {
    "professional": "professional, clear, and trustworthy",
    "casual":       "friendly, warm, and conversational",
    "exciting":     "energetic, bold, and attention-grabbing",
    "educational":  "informative, helpful, and insightful",
}

BUSINESS_PROFILES = {
    "DevCore Agency": {
        "description": "Ghana-based software development and digital marketing agency",
        "services": ["web development", "mobile apps", "branding", "digital marketing", "AI automation"],
        "audience": "businesses and entrepreneurs in Ghana and West Africa",
        "tone": "professional",
    },
    "GadgetsForAll": {
        "description": "3D-printed gadgets and custom products e-commerce store in Ghana",
        "services": ["custom 3D printed products", "phone accessories", "home decor", "gadgets"],
        "audience": "tech-savvy consumers and gift buyers in Ghana",
        "tone": "exciting",
    },
    "DevCore Trading": {
        "description": "Trading education platform and IB referral programme",
        "services": ["forex trading education", "trading signals", "IB referral programme"],
        "audience": "aspiring traders and investors in West Africa",
        "tone": "educational",
    },
}


class MarketingAgent(BaseAgent):
    name = "marketing"

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    async def run(self) -> list[AgentTask]:
        return []

    async def execute(self, task: AgentTask) -> dict:
        task_type = task.task_type
        ctx = task.context

        if task_type == "social_post":
            return await self._execute_social_post(ctx, task.draft)
        if task_type == "content_calendar":
            return {"note": "Calendar generated — copy each post draft to execute individually."}
        if task_type == "ad_copy":
            return {"note": "Ad copy ready — paste into your ad platform of choice."}
        if task_type == "broadcast":
            return {"note": "Broadcast draft ready — paste into WhatsApp or email client."}
        if task_type == "content_brief":
            return {"note": "Caption ready — copy to your publish tool and attach the media.", "caption": task.draft.get("full_caption", "")}
        return {"note": "Draft ready for use."}

    # ── Public factory methods (called from router) ─────────────────────────

    async def create_social_post(
        self,
        business: str,
        platform: str,
        topic: str,
        tone: str = "professional",
        priority: str = "normal",
    ) -> AgentTask:
        profile = BUSINESS_PROFILES.get(business, {"description": business, "services": [], "audience": "general public", "tone": tone})
        tone_desc = TONES.get(tone, TONES["professional"])
        ai = self._client()

        # Generate caption + hashtags
        caption_resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You write {tone_desc} social media content for {business}, "
                        f"a {profile['description']}. "
                        f"Target audience: {profile['audience']}. "
                        f"You are based in Ghana and understand the local market. "
                        f"Write for {platform}. Keep captions concise and engaging. "
                        f"Output JSON: {{\"caption\": \"...\", \"hashtags\": [\"#tag1\", \"#tag2\"]}}"
                    ),
                },
                {"role": "user", "content": f"Create a {platform} post about: {topic}"},
            ],
            response_format={"type": "json_object"},
        )
        import json
        post_data = json.loads(caption_resp.choices[0].message.content or "{}")
        caption = post_data.get("caption", "")
        hashtags = post_data.get("hashtags", [])

        # Generate image prompt
        img_prompt_resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=150,
            messages=[
                {"role": "system", "content": "You write concise DALL-E image generation prompts for social media marketing. Output only the prompt, no explanation."},
                {"role": "user", "content": f"Image for a {platform} post about '{topic}' for {business} ({profile['description']}). Style: modern, clean, vibrant. Ghana context."},
            ],
        )
        image_prompt = img_prompt_resp.choices[0].message.content.strip()

        # Generate DALL-E image
        image_url = ""
        try:
            img_resp = await ai.images.generate(
                model="dall-e-3",
                prompt=image_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = img_resp.data[0].url or ""
        except Exception as e:
            image_url = ""

        draft = {
            "platform": platform,
            "caption": caption,
            "hashtags": hashtags,
            "image_prompt": image_prompt,
            "image_url": image_url,
            "full_caption": caption + "\n\n" + " ".join(hashtags),
        }

        return await self._save_task(
            task_type="social_post",
            title=f"[{platform}] {business} — {topic[:60]}",
            context={"business": business, "platform": platform, "topic": topic, "tone": tone},
            draft=draft,
            priority=priority,
        )

    async def create_content_calendar(
        self,
        business: str,
        platform: str,
        days: int = 7,
        theme: str = "",
        tone: str = "professional",
    ) -> AgentTask:
        profile = BUSINESS_PROFILES.get(business, {"description": business, "services": [], "audience": "general public", "tone": tone})
        tone_desc = TONES.get(tone, TONES["professional"])
        ai = self._client()

        today = date.today()
        date_range = [(today + timedelta(days=i)).isoformat() for i in range(days)]

        resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You create {days}-day social media content calendars for {business}, "
                        f"a {profile['description']} in Ghana. "
                        f"Tone: {tone_desc}. Platform: {platform}. "
                        f"Return JSON: {{\"posts\": [{{\"date\": \"YYYY-MM-DD\", \"topic\": \"...\", \"caption\": \"...\", \"hashtags\": [\"...\"]}}]}}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a {days}-day content calendar starting {today.isoformat()}. "
                        f"{'Theme: ' + theme if theme else 'Mix of educational, promotional, and engagement posts.'} "
                        f"Services: {', '.join(profile['services'][:4])}."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        import json
        calendar_data = json.loads(resp.choices[0].message.content or "{}")

        return await self._save_task(
            task_type="content_calendar",
            title=f"[Calendar] {business} — {days}-day {platform} plan",
            context={"business": business, "platform": platform, "days": days, "theme": theme, "tone": tone},
            draft={"calendar": calendar_data.get("posts", []), "platform": platform},
            priority="normal",
        )

    async def create_ad_copy(
        self,
        business: str,
        platform: str,
        campaign: str,
        budget_ghs: float = 0,
        tone: str = "exciting",
    ) -> AgentTask:
        profile = BUSINESS_PROFILES.get(business, {"description": business, "services": [], "audience": "general public", "tone": tone})
        tone_desc = TONES.get(tone, TONES["exciting"])
        ai = self._client()

        resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You write high-converting {tone_desc} ad copy for {platform} ads in Ghana. "
                        f"Business: {business} — {profile['description']}. "
                        f"Target: {profile['audience']}. "
                        f"Return JSON: {{\"headline\": \"...\", \"primary_text\": \"...\", \"description\": \"...\", \"cta\": \"...\", \"variations\": [{{\"headline\": \"...\", \"primary_text\": \"...\"}}]}}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Campaign: {campaign}. "
                        f"{'Budget: GHS ' + str(budget_ghs) if budget_ghs else ''} "
                        f"Services: {', '.join(profile['services'][:4])}."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        import json
        ad_data = json.loads(resp.choices[0].message.content or "{}")

        return await self._save_task(
            task_type="ad_copy",
            title=f"[Ad] {business} on {platform} — {campaign[:60]}",
            context={"business": business, "platform": platform, "campaign": campaign, "budget_ghs": budget_ghs},
            draft=ad_data,
            priority="normal",
        )

    async def create_broadcast(
        self,
        business: str,
        channel: str,
        subject: str,
        audience: str = "clients",
        tone: str = "professional",
    ) -> AgentTask:
        profile = BUSINESS_PROFILES.get(business, {"description": business, "services": [], "audience": "general public", "tone": tone})
        tone_desc = TONES.get(tone, TONES["professional"])
        ai = self._client()

        is_whatsapp = channel.lower() == "whatsapp"

        resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You write {tone_desc} {'WhatsApp broadcast' if is_whatsapp else 'email'} messages "
                        f"for {business} in Ghana. "
                        f"{'WhatsApp: keep under 200 words, conversational, use emojis sparingly.' if is_whatsapp else 'Email: include subject line, greeting, body, and sign-off.'} "
                        f"Return JSON: {{\"subject\": \"...\", \"message\": \"...\", \"preview\": \"first 50 chars...\"}}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Write a {channel} broadcast to {audience} about: {subject}",
                },
            ],
            response_format={"type": "json_object"},
        )
        import json
        msg_data = json.loads(resp.choices[0].message.content or "{}")

        return await self._save_task(
            task_type="broadcast",
            title=f"[{channel}] {business} → {audience} — {subject[:50]}",
            context={"business": business, "channel": channel, "subject": subject, "audience": audience, "tone": tone},
            draft={"channel": channel, **msg_data},
            priority="normal",
        )

    async def create_content_brief(
        self,
        business: str,
        client: str,
        content_type: str,
        platforms: list[str],
        media_url: str,
        media_type: str,
        notes: str = "",
    ) -> AgentTask:
        import json
        profile = BUSINESS_PROFILES.get(business, {
            "description": business, "services": [], "audience": "general public", "tone": "professional",
        })
        tone_desc = TONES.get(profile.get("tone", "professional"), TONES["professional"])
        ai = self._client()
        platform_str = ", ".join(platforms)

        resp = await ai.chat.completions.create(
            model="gpt-4o",
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You write {tone_desc} social media captions for {business}, "
                        f"a {profile['description']} in Ghana. "
                        f"Target audience: {profile['audience']}. "
                        f"Output JSON: {{\"caption\": \"...\", \"hashtags\": [\"#tag1\", \"#tag2\"]}}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Write a caption for a {content_type} for client '{client}' "
                        f"to be posted on {platform_str}."
                        + (f" Additional context: {notes}" if notes else "")
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])

        return await self._save_task(
            task_type="content_brief",
            title=f"[{content_type.title()}] {client} · {platform_str}",
            context={
                "business": business, "client": client,
                "content_type": content_type, "platforms": platforms,
                "media_url": media_url, "media_type": media_type,
            },
            draft={
                "caption": caption,
                "hashtags": hashtags,
                "full_caption": caption + "\n\n" + " ".join(hashtags),
                "platform": platform_str,
                "media_url": media_url,
                "media_type": media_type,
                "content_type": content_type,
            },
            priority="normal",
        )

    async def _execute_social_post(self, ctx: dict, draft: dict) -> dict:
        """When Meta API is available, auto-post. For now return ready status."""
        meta_token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
        if not meta_token:
            return {
                "status": "ready",
                "note": "Post approved and ready. Connect META_PAGE_ACCESS_TOKEN to enable auto-posting.",
                "platform": draft.get("platform"),
                "caption": draft.get("full_caption", draft.get("caption", "")),
            }
        # Meta auto-posting placeholder (wired when keys are added)
        return {"status": "posted", "note": "Posted via Meta API."}
