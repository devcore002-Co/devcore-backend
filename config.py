from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DevCore API"
    app_env: str = "development"

    # ── Databases (2 PostgreSQL instances on Railway) ──────────────────────────
    # DB 1 → DevOS + Portal  (expenses/debts/income + client accounts/notifications)
    # DB 2 → Agency + Trading  (clients/projects/invoices + platforms/referrals)
    database_url_1: str = "sqlite+aiosqlite:///./db1.db"
    database_url_2: str = "sqlite+aiosqlite:///./db2.db"

    # ── Auth keys ──────────────────────────────────────────────────────────────
    agency_api_key: str = ""
    devos_api_key: str = ""          # shared secret with gadgets-web
    portal_admin_key: str = ""       # DevOS uses this to call /portal/admin/*
    portal_webhook_secret: str = ""  # client stores use this for /portal/webhooks/*

    # ── JWT (portal auth) ──────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production-minimum-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── Magic link (portal) ────────────────────────────────────────────────────
    magic_link_expire_minutes: int = 15
    magic_link_scheme: str = "devcore://auth/verify"
    chief_emails: str = ""           # comma-separated allowlist
    chief_business_name: str = "DevCore HQ"
    chief_dashboard_url: str = ""

    # ── SMTP ───────────────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # ── Firebase (portal push notifications) ──────────────────────────────────
    firebase_credentials_json: str = ""   # full JSON string (Vercel env var)
    firebase_credentials_path: str = "firebase-credentials.json"

    # ── Google OAuth (portal) ─────────────────────────────────────────────────
    google_client_ids: str = ""      # comma-separated

    # ── Portal API base URL (used to build magic-link HTTPS landing page) ──────
    portal_api_base_url: str = "https://devcore-backend.railway.app"

    # ── AI ─────────────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # ── Cloudinary (content publishing) ───────────────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ── CORS ───────────────────────────────────────────────────────────────────
    allowed_origins: str = "*"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def chief_emails_list(self) -> list[str]:
        return [e.strip() for e in self.chief_emails.split(",") if e.strip()]

    @property
    def google_client_ids_list(self) -> list[str]:
        return [c.strip() for c in self.google_client_ids.split(",") if c.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
