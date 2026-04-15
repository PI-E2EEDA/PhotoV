# This setup is based on this article
# https://testdriven.io/blog/fastapi-sqlmodel/
from sqlmodel import create_engine, SQLModel
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
import os


def get_database_url(use_async: bool) -> str:
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "demo")
    POSTGRES_USER = os.environ.get("POSTGRES_USER", "photov")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "photov")
    DB_HOST = os.environ.get("DB_HOST", "localhost")

    return URL.create(
        # Note: it seems that fastapi requires to use an async runtime
        # but alembic require it to be sync, so we allow the choice via use_async
        drivername="postgresql+" + ("asyncpg" if use_async else "psycopg"),
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=DB_HOST,
        port=5432,
        database=POSTGRES_DB,
    ).render_as_string(hide_password=False)


engine = AsyncEngine(create_engine(get_database_url(use_async=True), echo=True, future=True))

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
