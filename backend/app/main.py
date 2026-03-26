import os
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import setup_auth_routes
from app.db import get_database_strategy, get_session, get_user_db
from app.models import Measure, MeasureType, User

SessionDep = Annotated[AsyncSession, Depends(get_session)]
app = FastAPI()

setup_auth_routes(app)


@app.get("/")
async def root():
    return {
        "message": "No default route /, please visit /docs to see the available routes !"
    }


@app.get("/measures/{installation_id}/{type}")
async def get_measures(
    session: SessionDep,
    installation_id: int,
    type: MeasureType,
):
    results = await session.exec(
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == type)
    )
    return results.fetchall()
