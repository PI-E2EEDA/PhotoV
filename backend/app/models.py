from datetime import datetime
from enum import Enum

from sqlalchemy import UniqueConstraint, Column, DateTime
from sqlmodel import Field, SQLModel


class Installation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    latitude: float
    longitude: float


class MeasureType(Enum):
    POWER = 1
    ENERGY = 2  # FIX: was 1, same as POWER → Python treats them as aliases


class Measure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    type: MeasureType
    time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    installation_id: int | None = Field(default=None, foreign_key="installation.id")
    solar_consumption: float
    solar_production: float
    grid_consumption: float
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