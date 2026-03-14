import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


load_dotenv()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set in .env")
    return url


def get_engine(echo: bool = False) -> Engine:
    """Return a SQLAlchemy engine for the configured Postgres database."""
    return create_engine(get_database_url(), echo=echo, future=True)


def ensure_schemas(engine: Engine) -> None:
    """Create bronze/silver/gold schemas if they do not already exist."""
    bronze = os.getenv("BRONZE_SCHEMA", "bronze")
    silver = os.getenv("SILVER_SCHEMA", "silver")
    gold = os.getenv("GOLD_SCHEMA", "gold")

    with engine.begin() as conn:
        for schema in (bronze, silver, gold):
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))

