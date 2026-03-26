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

fastapi_users_setup = setup_auth_routes(app)


@app.get("/")
async def root():
    return {
        "message": "No default route /, please visit /docs to see the available routes !"
    }


# The logged user must always be active and verified !!
current_user = fastapi_users_setup.current_user(active=True, verified=True)


@app.get("/measures/{installation_id}/{type}")
async def get_measures(
    session: SessionDep,
    installation_id: int,
    type: MeasureType,
    user: User = Depends(current_user),
):
    print(f"request as user {user.email}")
    results = await session.execute(  # ignore this warning
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == type)
        .limit(3)
    )
    return results.scalars().all()
