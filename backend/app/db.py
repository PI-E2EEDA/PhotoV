# This setup is based on this article
# https://testdriven.io/blog/fastapi-sqlmodel/
from sqlmodel import create_engine, SQLModel
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from collections.abc import AsyncGenerator
from fastapi_users.db import SQLAlchemyUserDatabase
from app.models import User, AccessToken
from fastapi import Depends
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
)
from fastapi_users.authentication.strategy.db import (
    AccessTokenDatabase,
    DatabaseStrategy,
)


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


engine = create_async_engine(get_database_url(True))
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


# https://fastapi-users.github.io/fastapi-users/latest/configuration/databases/sqlalchemy/
# TODO: remove duplication ??
async def get_session():
    async with AsyncSession(engine) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_access_token_db(
    session: AsyncSession = Depends(get_async_session),
):
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(
        access_token_db, lifetime_seconds=(3 * 7 * 24 * 3600)
    )  # 3 weeks
