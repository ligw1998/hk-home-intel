from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def create_db_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def database_health(database_url: str) -> dict[str, object]:
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "healthy": True,
            "dialect": engine.dialect.name,
            "url_redacted": _redact_url(database_url),
        }
    finally:
        engine.dispose()


def _redact_url(database_url: str) -> str:
    if "@" not in database_url:
        return database_url
    prefix, suffix = database_url.split("@", 1)
    head = prefix.rsplit("://", 1)[0]
    return f"{head}://***:***@{suffix}"
