"""add contact submissions table

Revision ID: 2ee5d911ab50
Revises: 83476e7f6e10
Create Date: 2026-10-01 13:34:41.616294

Autogenerate also proposed dropping the four procrastinate_* tables, for
the reason noted in fa9f1a52d4fd, 646491b32151 and 83476e7f6e10: raw SQL,
not SQLAlchemy models. Stripped; this migration only adds
contact_submissions (Plan.md section 10's public Contact form).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2ee5d911ab50'
down_revision: Union[str, None] = '83476e7f6e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contact_submissions',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('company', sa.String(length=200), nullable=True),
        sa.Column('message', sa.String(length=4000), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_contact_submissions')),
    )
    op.create_index(
        op.f('ix_contact_submissions_submitted_at'),
        'contact_submissions',
        ['submitted_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_contact_submissions_submitted_at'), table_name='contact_submissions')
    op.drop_table('contact_submissions')
