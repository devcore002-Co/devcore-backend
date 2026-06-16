from sqlalchemy.orm import DeclarativeBase
from database import make_db
from config import get_settings

_settings = get_settings()
engine, _factory, get_db = make_db(_settings.database_url_1)


class Base(DeclarativeBase):
    pass
