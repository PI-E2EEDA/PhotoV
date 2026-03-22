from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint
from enum import Enum


# Any solar installation
class Installation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    latitude: float
    longitude: float


class MeasureType(Enum):
    POWER = 1
    ENERGY = 1


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
