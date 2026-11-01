"""create manufacturers and cars

Revision ID: 0001
Revises:
Create Date: 2026-10-30 10:00:00

Initial schema: two related tables (manufacturers 1 - N cars).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manufacturers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_manufacturers")),
        sa.UniqueConstraint("name", name=op.f("uq_manufacturers_name")),
    )
    op.create_table(
        "cars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("manufacturer_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("mileage", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "year BETWEEN 1900 AND 2100", name=op.f("ck_cars_year_range")
        ),
        sa.CheckConstraint(
            "price >= 0", name=op.f("ck_cars_price_not_negative")
        ),
        sa.CheckConstraint(
            "mileage >= 0", name=op.f("ck_cars_mileage_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["manufacturer_id"],
            ["manufacturers.id"],
            name=op.f("fk_cars_manufacturer_id_manufacturers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cars")),
    )


def downgrade() -> None:
    op.drop_table("cars")
    op.drop_table("manufacturers")
