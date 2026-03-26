from typing import Annotated
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, SQLModel, create_engine, select

from app.db import get_database_url
from app.models import Measure, MeasureType


async def get_session():
    async with AsyncSession(engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
app = FastAPI()

engine = create_async_engine(get_database_url(True))


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
