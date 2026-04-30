from datetime import datetime
from sqlmodel import Field, MetaData, SQLModel, Relationship
from sqlalchemy import UniqueConstraint
from enum import Enum
from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Integer, ForeignKey, DateTime, Column
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyBaseAccessTokenTable,
)
from fastapi_users import schemas
from sqlalchemy.ext.declarative import declarative_base


class SmartPlug(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    installation_id: int | None = Field(default=None, foreign_key="installation.id")


class SmartPlugMeasure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    time: datetime  # stored in local time, like SolarEdge !
    value: float  # in Watt
    smartplug_id: int | None = Field(default=None, foreign_key="smartplug.id")
    __table_args__ = (UniqueConstraint("time", "smartplug_id"),)


# Join tables to give access to some users to some installations
class UserInstallationLink(SQLModel, table=True):
    # Note: because foreign_key="user.id" fails with
    # sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'userinstallationlink.user_id' could not find table 'user' with which to generate a foreign key to target column 'id'
    # we have to manually create foreign keys constraint in the generated migrations...
    user_id: int | None = Field(default=None, primary_key=True)
    installation_id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("user_id", "installation_id"),)


# Any solar installation
class Installation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    latitude: float
    longitude: float
    panel_angle: float | None = Field(default=30.0)
    panel_orientation: float | None = Field(default=157.0)
    manufacturer: str | None = Field(default=None)
    model: str | None = Field(default=None)


class WeatherForecast(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    target_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    reference_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    installation_id: int | None = Field(default=None, foreign_key="installation.id")
    temperature_2m: float | None = Field(default=None)
    shortwave_radiation: float | None = Field(default=None)
    diffuse_radiation: float | None = Field(default=None)
    precipitation: float | None = Field(default=None)
    windspeed_10m: float | None = Field(default=None)
    cloudcover_high: float | None = Field(default=None)
    cloudcover_medium: float | None = Field(default=None)
    cloudcover_low: float | None = Field(default=None)

    __table_args__ = (UniqueConstraint("installation_id", "target_time", "reference_time"),)


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
    solar_production: float
    solar_consumption: float
    grid_consumption: float
    # make sure the combination of these 3 fields is unique !
    __table_args__ = (UniqueConstraint("type", "time", "installation_id"),)

class WeatherHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    point_id: str = Field(index=True)
    temperature_2m: float
    shortwave_radiation: float
    diffuse_radiation: float
    precipitation: float
    windspeed_10m: float
    cloudcover_high: float
    cloudcover_medium: float
    cloudcover_low: float
    __table_args__ = (UniqueConstraint("time", "point_id"),)


# Declare a base from your metadata. This is required for migrations/env.py target_metadata access.
mymetadata = MetaData()
Base = declarative_base(metadata=mymetadata)


# User classed with incremental ID, based on Base user table from fastapi_users
# to have an email+hashed password+
class User(Base, SQLAlchemyBaseUserTable[Mapped[int]]):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


# Set relationships after both are fully defined:
Installation.users = Relationship(
    back_populates="installations", link_model=UserInstallationLink
)
User.installations = Relationship(
    back_populates="users", link_model=UserInstallationLink
)


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
