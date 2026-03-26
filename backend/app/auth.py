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

from app.db import get_database_strategy, get_session, get_user_db
from app.models import Measure, MeasureType, User, UserCreate, UserUpdate, UserRead

# https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/transports/bearer/
bearer_transport = BearerTransport(tokenUrl="token")

# https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/backend/
auth_backend = AuthenticationBackend(
    name="api_bearer_db_auth",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)

# https://fastapi-users.github.io/fastapi-users/latest/configuration/user-manager/
AUTH_SERVER_SECRET = os.environ.get("AUTH_SERVER_SECRET")

if AUTH_SERVER_SECRET is None:
    print("ERROR: AUTH_SERVER_SECRET variable has not been configured !")
    exit(2)


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = AUTH_SERVER_SECRET
    verification_token_secret = AUTH_SERVER_SECRET

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ):
        print(f"User {user.id} with email {user.email} logged in.")

    async def on_after_register(self, user: User, request: Request | None = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(
    user_db=Depends(get_user_db),
):
    yield UserManager(user_db)


fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)


# Setup the only routes we need from fastapi_users
def setup_auth_routes(app: FastAPI):
    # Allow login on /auth/login
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth",
        tags=["auth"],
    )

    # Allow register on /auth/register
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
