"""Bridge missing historical revision

Revision ID: 6b74f9e4fa0b
Revises: f09934c53fbc
Create Date: 2026-04-16 19:05:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6b74f9e4fa0b"
down_revision: Union[str, Sequence[str], None] = "f09934c53fbc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op bridge: this revision existed in database history but file is missing.
    return None


def downgrade() -> None:
    """Downgrade schema."""
    return None

