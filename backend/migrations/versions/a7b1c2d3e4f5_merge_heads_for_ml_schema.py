"""Merge heads before ML schema sync

Revision ID: a7b1c2d3e4f5
Revises: bb2d9f4f1d5a, ff93234e580b
Create Date: 2026-04-26 22:00:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "a7b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = (
    "bb2d9f4f1d5a",
    "ff93234e580b",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    return None


def downgrade() -> None:
    """Downgrade schema."""
    return None

