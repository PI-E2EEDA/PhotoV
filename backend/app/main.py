from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import setup_auth_routes
from app.db import get_session
from app.models import Installation, Measure, MeasureType, User, UserInstallationLink

SessionDep = Annotated[AsyncSession, Depends(get_session)]
app = FastAPI()

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
    # This should be unreachable...
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
):
    await validate_current_user_can_access_installation(
        user.id, installation_id, session
    )
    print(f"request as user {user.email}")
    results = await session.execute(  # ignore this warning
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == type)
        .limit(3)
    )
    return results.scalars().all()
