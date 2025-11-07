"""add unique constraint to external_ref in payouts

Revision ID: xxxxxxxxxxxx
Revises: 468918f7d625
Create Date: 2025-09-27 19:30:00.000000
"""
from alembic import op

# revision identifiers
revision = "xxxxxxxxxxxx"  # keep same as filename prefix
down_revision = "468918f7d625"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_payouts_external_ref", "payouts", ["external_ref"]
    )


def downgrade():
    op.drop_constraint(
        "uq_payouts_external_ref", "payouts", type_="unique"
    )
