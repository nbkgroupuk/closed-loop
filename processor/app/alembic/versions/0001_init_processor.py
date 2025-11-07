# alembic/versions/0001_init_processor.py
"""processor initial

Revision ID: p0001
Revises: 
Create Date: 2025-09-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'p0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('clearing_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('txn_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(18,2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('raw_iso', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table('settlement_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('batch_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('total_amount', sa.Numeric(18,2), nullable=True),
        sa.Column('items', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table('processor_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('topic', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table('processor_events')
    op.drop_table('settlement_batches')
    op.drop_table('clearing_entries')
