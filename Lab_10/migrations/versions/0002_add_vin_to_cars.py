"""add vin to cars

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31 16:10:00

Adds the VIN column with a UNIQUE constraint. The column is nullable, so
cars created before the migration stay valid (SQLite allows many NULLs
in a UNIQUE column). Batch mode is used because SQLite cannot add a
constraint with ALTER TABLE.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cars", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("vin", sa.String(length=17), nullable=True)
        )
        batch_op.create_unique_constraint(batch_op.f("uq_cars_vin"), ["vin"])


def downgrade() -> None:
    with op.batch_alter_table("cars", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_cars_vin"), type_="unique")
        batch_op.drop_column("vin")
