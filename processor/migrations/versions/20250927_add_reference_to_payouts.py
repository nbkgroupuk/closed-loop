"""add reference field to payouts

Revision ID: 20250927_add_reference
Revises: <put_previous_revision_id_here>
Create Date: 2025-09-27 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250927_add_reference"
down_revision = "<put_previous_revision_id_here>"
branch_labels = None
depends_on = None


def upgrade():
    # add column 'reference' to payouts table
    op.add_column(
        "payouts",
        sa.Column("reference", sa.String(length=128), nullable=False, server_default="tmp")
    )
    # remove server_default after column is filled
    op.alter_column("payouts", "reference", server_default=None)

    # add unique constraint on reference
    op.create_unique_constraint("uq_payouts_reference", "payouts", ["reference"])


def downgrade():
    op.drop_constraint("uq_payouts_reference", "payouts", type_="unique")
    op.drop_column("payouts", "reference")
