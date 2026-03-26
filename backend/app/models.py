from datetime import datetime
from sqlmodel import Field, MetaData, SQLModel
from sqlalchemy import UniqueConstraint
from enum import Enum
from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyBaseAccessTokenTable,
)
from fastapi_users import schemas
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base


# Any solar installation
class Installation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    latitude: float
    longitude: float


class MeasureType(Enum):
    power = "power"
    energy = "energy"


# A measure of power or energy
# All power measures are in Watt
# All energy measures are in Watt·hours
class Measure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    type: MeasureType
    time: datetime
    installation_id: int | None = Field(default=None, foreign_key="installation.id")
    solar_consumption: float
    solar_production: float
    grid_consumption: float
    # make sure the combination of these 3 fields is unique !
    __table_args__ = (UniqueConstraint("type", "time", "installation_id"),)


# Declare a base from your metadata
Base: DeclarativeMeta = declarative_base(metadata=MetaData())


# User classed with incremental ID, based on Base user table from fastapi_users
# to have an email+hashed password+
class User(Base, SQLAlchemyBaseUserTable[Mapped[int]]):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


# API Token stored in database and managed by fastapi_users
# Configured with https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/strategies/database/
class AccessToken(Base, SQLAlchemyBaseAccessTokenTable[int]):
    @declared_attr
    def user_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer, ForeignKey("user.id", ondelete="cascade"), nullable=False
        )


# NOTE: those models are only for validation requests managed by fastapi_users. They will not create database models !
class UserRead(schemas.BaseUser[int]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
