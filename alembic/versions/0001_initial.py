"""initial

Revision ID: 0001
Revises:
Create Date: 2026-07-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stocktopus_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("material_group", sa.Text(), nullable=True),
        sa.Column("material_type", sa.Text(), nullable=True),
        sa.Column("size_type", sa.Text(), nullable=False),
        sa.Column("width_mm", sa.Float(), nullable=True),
        sa.Column("height_mm", sa.Float(), nullable=True),
        sa.Column("length_mm", sa.Float(), nullable=True),
        sa.Column("thickness_mm", sa.Float(), nullable=True),
        sa.Column("size_unit", sa.Text(), nullable=True),
        sa.Column("size_string", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("price_range", sa.Text(), nullable=True),
        sa.Column("supplier_name", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("raw_stocktopus_json", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_from_stocktopus_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("friendly_name", sa.Text(), nullable=True),
        sa.Column("matex", sa.Text(), nullable=True),
        sa.Column("prepit", sa.Text(), nullable=True),
        sa.Column("imp", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("primary_cutter", sa.Text(), nullable=True),
        sa.Column("primary_tool", sa.Text(), nullable=True),
        sa.Column("tool_tips", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_materials_active", "materials", ["active"], unique=False)
    op.create_index(
        "ix_materials_size_type",
        "materials",
        ["size_type"],
        unique=False,
        mysql_length={"size_type": 255},
    )
    op.create_index(
        "ix_materials_stocktopus_id",
        "materials",
        ["stocktopus_id"],
        unique=True,
        mysql_length={"stocktopus_id": 255},
    )


def downgrade() -> None:
    op.drop_index("ix_materials_stocktopus_id", table_name="materials")
    op.drop_index("ix_materials_size_type", table_name="materials")
    op.drop_index("ix_materials_active", table_name="materials")
    op.drop_table("materials")
