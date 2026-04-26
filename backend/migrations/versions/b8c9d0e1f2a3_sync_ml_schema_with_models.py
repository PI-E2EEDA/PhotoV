"""Sync ML schema with current models

Revision ID: b8c9d0e1f2a3
Revises: a7b1c2d3e4f5
Create Date: 2026-04-26 22:05:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _convert_smartplugmeasure_time_to_naive() -> None:
    op.execute(
        """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'smartplugmeasure'
          AND column_name = 'time'
          AND data_type = 'timestamp with time zone'
    ) THEN
        ALTER TABLE public.smartplugmeasure
        ALTER COLUMN time TYPE TIMESTAMP WITHOUT TIME ZONE
        USING time AT TIME ZONE 'UTC';
    END IF;
END $$;
"""
    )


def _convert_smartplugmeasure_time_to_tz() -> None:
    op.execute(
        """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'smartplugmeasure'
          AND column_name = 'time'
          AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE public.smartplugmeasure
        ALTER COLUMN time TYPE TIMESTAMP WITH TIME ZONE
        USING time AT TIME ZONE 'UTC';
    END IF;
END $$;
"""
    )


def _ensure_installation_columns() -> None:
    op.execute(
        """
ALTER TABLE public.installation ADD COLUMN IF NOT EXISTS panel_angle DOUBLE PRECISION;
ALTER TABLE public.installation ADD COLUMN IF NOT EXISTS panel_orientation DOUBLE PRECISION;
ALTER TABLE public.installation ADD COLUMN IF NOT EXISTS manufacturer VARCHAR;
ALTER TABLE public.installation ADD COLUMN IF NOT EXISTS model VARCHAR;
"""
    )


def _ensure_weatherforecast_table() -> None:
    op.execute(
        """
CREATE TABLE IF NOT EXISTS public.weatherforecast (
    id INTEGER PRIMARY KEY,
    target_time TIMESTAMP WITH TIME ZONE NOT NULL,
    reference_time TIMESTAMP WITH TIME ZONE NOT NULL,
    installation_id INTEGER,
    temperature_2m DOUBLE PRECISION,
    shortwave_radiation DOUBLE PRECISION,
    diffuse_radiation DOUBLE PRECISION,
    precipitation DOUBLE PRECISION,
    windspeed_10m DOUBLE PRECISION,
    cloudcover_high DOUBLE PRECISION,
    cloudcover_medium DOUBLE PRECISION,
    cloudcover_low DOUBLE PRECISION,
    CONSTRAINT weatherforecast_installation_id_fkey
        FOREIGN KEY (installation_id)
        REFERENCES public.installation (id),
    CONSTRAINT weatherforecast_installation_id_target_time_reference_time_key
        UNIQUE (installation_id, target_time, reference_time)
);
"""
    )


def _ensure_weatherhistory_table() -> None:
    op.execute(
        """
CREATE TABLE IF NOT EXISTS public.weatherhistory (
    id INTEGER PRIMARY KEY,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    point_id VARCHAR NOT NULL,
    temperature_2m DOUBLE PRECISION NOT NULL,
    shortwave_radiation DOUBLE PRECISION NOT NULL,
    diffuse_radiation DOUBLE PRECISION NOT NULL,
    precipitation DOUBLE PRECISION NOT NULL,
    windspeed_10m DOUBLE PRECISION NOT NULL,
    cloudcover_high DOUBLE PRECISION NOT NULL,
    cloudcover_medium DOUBLE PRECISION NOT NULL,
    cloudcover_low DOUBLE PRECISION NOT NULL,
    CONSTRAINT weatherhistory_time_point_id_key UNIQUE (time, point_id)
);
CREATE INDEX IF NOT EXISTS ix_weatherhistory_point_id ON public.weatherhistory (point_id);
"""
    )


def upgrade() -> None:
    """Upgrade schema."""
    _ensure_installation_columns()
    _ensure_weatherforecast_table()
    _ensure_weatherhistory_table()

    _convert_smartplugmeasure_time_to_naive()


def downgrade() -> None:
    """Downgrade schema."""
    _convert_smartplugmeasure_time_to_tz()

    op.drop_index(op.f("ix_weatherhistory_point_id"), table_name="weatherhistory")
    op.drop_table("weatherhistory")
    op.drop_table("weatherforecast")

    op.drop_column("installation", "model")
    op.drop_column("installation", "manufacturer")
    op.drop_column("installation", "panel_orientation")
    op.drop_column("installation", "panel_angle")

