from datetime import datetime
from sqlmodel import Field, SQLModel


class Building(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    latitude: float
    longitude: float


# All power measures are in Watt
class PowerMeasure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    time: datetime
    solar_power_consumption: float
    solar_power_production: float
    grid_power_consumption: float
    building_id: int | None = Field(default=None, foreign_key="building.id")


# All energy measures are in Watt·hours
class EnergyMeasure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    time: datetime
    solar_energy_consumption: float
    solar_energy_production: int
    grid_energy_consumption: float
    building_id: int | None = Field(default=None, foreign_key="building.id")
