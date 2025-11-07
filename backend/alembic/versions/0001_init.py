# alembic/versions/0001_init.py
"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2025-09-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Numeric(18,2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('pan_mask', sa.String(length=8), nullable=False),
        sa.Column('expiry', sa.String(length=5), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('protocol', sa.String(length=64), nullable=False),
        sa.Column('de39', sa.String(length=3), nullable=True),
        sa.Column('de38', sa.String(length=12), nullable=True),
        sa.Column('gateway_txn_id', sa.String(length=128), nullable=True),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('meta', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_transactions_correlation_id', 'transactions', ['correlation_id'])
    op.create_index('ix_transactions_idempotency_key', 'transactions', ['idempotency_key'])

    op.create_table('payouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=True),
        sa.Column('external_ref', sa.String(length=256), nullable=True),
        sa.Column('attempts', sa.Integer, nullable=True, default=0),
        sa.Column('error_msg', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table('outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('target', sa.String(length=128), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table('event_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('topic', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table('event_logs')
    op.drop_table('outbox')
    op.drop_table('payouts')
    op.drop_index('ix_transactions_idempotency_key', table_name='transactions')
    op.drop_index('ix_transactions_correlation_id', table_name='transactions')
    op.drop_table('transactions')
