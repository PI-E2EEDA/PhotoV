"""Convert core timestamps to TIMESTAMPTZ

Revision ID: bb2d9f4f1d5a
Revises: 6b74f9e4fa0b
Create Date: 2026-04-16 16:20:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bb2d9f4f1d5a"
down_revision: Union[str, Sequence[str], None] = "6b74f9e4fa0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _convert_column(table_name: str, column_name: str, to_tz: bool) -> None:
    target_type = "TIMESTAMP WITH TIME ZONE" if to_tz else "TIMESTAMP WITHOUT TIME ZONE"
    source_type = "timestamp without time zone" if to_tz else "timestamp with time zone"

    op.execute(
        f"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table_name}'
          AND column_name = '{column_name}'
          AND data_type = '{source_type}'
    ) THEN
        ALTER TABLE public.{table_name}
        ALTER COLUMN {column_name} TYPE {target_type}
        USING {column_name} AT TIME ZONE 'UTC';
    END IF;
END $$;
"""
    )


def upgrade() -> None:
    """Upgrade schema."""
    # Existing values are treated as UTC when converting from naive timestamp.
    _convert_column("measure", "time", to_tz=True)
    _convert_column("smartplugmeasure", "time", to_tz=True)
    _convert_column("weatherhistory", "time", to_tz=True)
    _convert_column("weatherforecast", "target_time", to_tz=True)
    _convert_column("weatherforecast", "reference_time", to_tz=True)


def downgrade() -> None:
    """Downgrade schema."""
    _convert_column("weatherforecast", "reference_time", to_tz=False)
    _convert_column("weatherforecast", "target_time", to_tz=False)
    _convert_column("weatherhistory", "time", to_tz=False)
    _convert_column("smartplugmeasure", "time", to_tz=False)
    _convert_column("measure", "time", to_tz=False)
