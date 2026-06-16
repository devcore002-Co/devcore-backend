import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

# ── Domain imports ─────────────────────────────────────────────────────────────
# Agency
from domains.agency.database import engine as agency_engine, Base as AgencyBase
import domains.agency.models  # noqa: F401 — registers models with AgencyBase
from domains.agency.routers import clients as agency_clients
from domains.agency.routers import projects as agency_projects
from domains.agency.routers import invoices as agency_invoices
from domains.agency.routers import agents as agency_agents
from domains.agency.routers import summary as agency_summary

# Trading
from domains.trading.database import engine as trading_engine, Base as TradingBase
import domains.trading.models  # noqa: F401
from domains.trading.routers import platforms as trading_platforms
from domains.trading.routers import referrals as trading_referrals
from domains.trading.routers import commissions as trading_commissions

# DevOS
from domains.devos.database import engine as devos_engine, Base as DevosBase
from domains.devos import models as devos_models  # noqa: F401
from domains.devos.routers import expenses as devos_expenses
from domains.devos.routers import income as devos_income
from domains.devos.routers import budget as devos_budget
from domains.devos.routers import debts as devos_debts
from domains.devos.routers import summary as devos_summary

# Portal
from domains.portal.database import engine as portal_engine, Base as PortalBase
from domains.portal import models as portal_models  # noqa: F401
from domains.portal.routers import auth as portal_auth
from domains.portal.routers import clients as portal_clients
from domains.portal.routers import notifications as portal_notifications
from domains.portal.routers import webhooks as portal_webhooks
from domains.portal.routers import admin as portal_admin

settings = get_settings()
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    for engine, base, name in [
        (agency_engine, AgencyBase, "agency"),
        (trading_engine, TradingBase, "trading"),
        (devos_engine, DevosBase, "devos"),
        (portal_engine, PortalBase, "portal"),
    ]:
        async with engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)
        logger.info(f"[{name}] Tables ready.")
    yield
    for engine in [agency_engine, trading_engine, devos_engine, portal_engine]:
        await engine.dispose()


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DevCore API",
    version="1.0.0",
    description="Unified backend for DevCore agency, trading, DevOS, and portal.",
    lifespan=lifespan,
)


# ── CORS ───────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Key middleware ─────────────────────────────────────────────────────────

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Agency routes
        if path.startswith("/agency/"):
            key = settings.agency_api_key
            if key and request.headers.get("X-API-Key", "") != key:
                return Response("Unauthorized", status_code=401)

        # DevOS and Trading routes share the devos_api_key
        elif path.startswith("/devos/") or path.startswith("/trading/"):
            key = settings.devos_api_key
            if key and request.headers.get("X-API-Key", "") != key:
                return Response("Unauthorized", status_code=401)

        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "devcore-backend"}


# Agency domain — /agency/*
app.include_router(agency_clients.router, prefix="/agency")
app.include_router(agency_projects.router, prefix="/agency")
app.include_router(agency_invoices.router, prefix="/agency")
app.include_router(agency_agents.router, prefix="/agency")
app.include_router(agency_summary.router, prefix="/agency")

# Trading domain — /trading/*
app.include_router(trading_platforms.router, prefix="/trading")
app.include_router(trading_referrals.router, prefix="/trading")
app.include_router(trading_commissions.router, prefix="/trading")

# DevOS domain — /devos/*
# Individual routers carry their own sub-prefix; include with /devos parent
app.include_router(devos_expenses.router, prefix="/devos")
app.include_router(devos_income.router, prefix="/devos")
app.include_router(devos_budget.router, prefix="/devos")
app.include_router(devos_debts.router, prefix="/devos")
# Summary router already has /devos prefix built-in — include at root
app.include_router(devos_summary.router)

# Portal domain — /portal/*
app.include_router(portal_auth.router, prefix="/portal")
app.include_router(portal_clients.router, prefix="/portal")
app.include_router(portal_notifications.router, prefix="/portal")
app.include_router(portal_webhooks.router, prefix="/portal")
app.include_router(portal_admin.router, prefix="/portal")
