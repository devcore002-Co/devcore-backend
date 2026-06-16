"""Shared async SQLAlchemy engine/session factory used by every domain."""
import ssl
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_STRIP_PARAMS = {"sslmode", "ssl", "channel_binding"}


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in qs.items() if k not in _STRIP_PARAMS}
    clean = urlunparse(parsed._replace(query=urlencode(filtered, doseq=True)))
    if clean.startswith("postgresql://") and "+asyncpg" not in clean:
        clean = "postgresql+asyncpg://" + clean[len("postgresql://"):]
    elif clean.startswith("sqlite://") and "+aiosqlite" not in clean:
        clean = "sqlite+aiosqlite://" + clean[len("sqlite://"):]
    return clean


def make_db(database_url: str):
    """Return (engine, session_factory, get_db_dep) for a given DATABASE_URL."""
    url = _clean_url(database_url)
    is_sqlite = url.startswith("sqlite")

    connect_args: dict = {}
    if not is_sqlite:
        ctx = ssl.create_default_context()
        connect_args = {"ssl": ctx, "statement_cache_size": 0}

    engine = create_async_engine(
        url,
        poolclass=None if is_sqlite else NullPool,
        connect_args=connect_args,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def get_db() -> AsyncSession:  # type: ignore[return]
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return engine, factory, get_db
