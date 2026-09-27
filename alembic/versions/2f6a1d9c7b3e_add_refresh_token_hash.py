"""add refresh_token_hash to users

Revision ID: 2f6a1d9c7b3e
Revises: 1af2eabdbbdd
Create Date: 2026-09-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2f6a1d9c7b3e'
down_revision: Union[str, Sequence[str], None] = '1af2eabdbbdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_token_hash")
