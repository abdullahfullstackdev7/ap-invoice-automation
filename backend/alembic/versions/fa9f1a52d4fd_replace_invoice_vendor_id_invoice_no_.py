"""replace invoice vendor_id invoice_no unique constraint with plain index

Revision ID: fa9f1a52d4fd
Revises: 975e8129afe3
Create Date: 2026-10-01 08:00:52.338743

Autogenerate also proposed dropping procrastinate_jobs/events/workers/
periodic_defers here, since those tables are applied as raw SQL (not
declared as SQLAlchemy models) and autogenerate diffs against
Base.metadata. That part was stripped; this migration only touches the
invoices index, per Plan.md section 7's duplicate-invoice handling (see
app/models/invoicing.py for why this is a plain index, not UNIQUE).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'fa9f1a52d4fd'
down_revision: Union[str, None] = '975e8129afe3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_invoices_vendor_invoice_no', 'invoices', type_='unique')
    op.create_index(
        'ix_invoices_vendor_invoice_no', 'invoices', ['vendor_id', 'invoice_no'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_invoices_vendor_invoice_no', table_name='invoices')
    op.create_unique_constraint(
        'uq_invoices_vendor_invoice_no', 'invoices', ['vendor_id', 'invoice_no']
    )
