from typing import Annotated
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import asc, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
import os

from app.auth import setup_auth_routes
from app.db import get_session
from app.models import (
    Installation,
    Measure,
    MeasureType,
    User,
    UserInstallationLink,
    SmartPlugMeasure,
    SmartPlug,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
app = FastAPI()

# Configure CORS to allow any localhost website + the production domain as well.
origins = [
    "http://localhost:5173",
]
PHOTOV_DOMAIN = os.environ.get("PHOTOV_DOMAIN")
if PHOTOV_DOMAIN is not None:
    origins.append("https://" + PHOTOV_DOMAIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_users_setup = setup_auth_routes(app)


@app.get("/")
async def root():
    return {
        "message": "No default route /, please visit /docs to see the available routes !"
    }


# This defines a function to call to get the current user
# The logged user can get data only when active and verified !!
current_user_fn = fastapi_users_setup.current_user(
    optional=False, active=True, verified=True
)


# Make sure the user can access data from this installation or throw an HTTP exception otherwise
async def validate_current_user_can_access_installation(
    user_id,
    installation_id,
    session: SessionDep,
) -> Installation:
    result = await session.execute(
        select(UserInstallationLink).where(
            UserInstallationLink.user_id == user_id,
            UserInstallationLink.installation_id == installation_id,
        )
    )
    link = result.scalars().first()
    if link is None:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot access to installation with id {installation_id}",
        )

    result2 = await session.execute(
        select(Installation).where(
            Installation.id == installation_id,
        )
    )
    installation = result2.scalars().first()
    # This should be unreachable because of foreign keys integrity...
    if installation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Installation with id {installation_id} has been deleted...",
        )
    return installation


@app.get(
    "/measures/{installation_id}/{type}", description="Get measures of power or energy"
)
async def get_measures(
    session: SessionDep,
    installation_id: int,
    type: MeasureType,
    user: User = Depends(current_user_fn),
    ascending: bool = False,
    limit: int = 5760,  # this is one day of data
    offset: int = 0,
) -> list[Measure]:
    await validate_current_user_can_access_installation(
        user.id, installation_id, session
    )

    print(
        f"Request {limit} {type.value} measures as user {user.email} on {datetime.now()}"
    )
    stmt = (
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == type)
        .order_by(asc(Measure.time) if ascending else desc(Measure.time))
        .offset(offset)
    )
    # This is a way to avoid any limits if needed, with i.e. -1.
    if limit > 0:
        stmt = stmt.limit(limit)

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Offset {offset} cannot be negative !",
        )

    results = await session.execute(stmt)  # ignore this warning
    return results.scalars().all()


# TODO: add routes to get smartplugs and smartplugs measures for the frontend


@app.post(
    "/smartplugs/",
    description="Create a new smartplug with a name",
)
async def create_smartplug(
    session: SessionDep,
    smartplug: SmartPlug,
    user: User = Depends(current_user_fn),
):
    await validate_current_user_can_access_installation(
        user.id, smartplug.installation_id, session
    )
    smartplug.id = None

    ## TODO insert
    ## TODO return the generated object


@app.post(
    "/smartplugs/{installation_id}/",
    description="Send one power measure from a given smart-plug",
)
async def send_smartplug_measure(
    session: SessionDep,
    installation_id: int,
    measure: SmartPlugMeasure,
    user: User = Depends(current_user_fn),
):
    await validate_current_user_can_access_installation(
        user.id, installation_id, session
    )
    # Check the smartplug_id does exist and can be accessed
    related_smartplug = await session.execute(  # ignore this warning
        select(SmartPlug).where(SmartPlug.id == measure.smartplug_id)
    )
    if related_smartplug.first() is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid smartplug_id for this measure !",
        )
    if related_smartplug.first() is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid smartplug_id for this measure !",
        )

    measure.id = None
    # Check the time is not in the future
    # Check the value is not negative
    print(f"Request to save new smartplug value")

    # todo return new object
