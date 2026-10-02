"""add exceptions opened_at column

Revision ID: 83476e7f6e10
Revises: 646491b32151
Create Date: 2026-10-01 12:20:55.859846

Needed for Phase 9's exceptions-trend and exception-heatmap analytics,
which have no other reliable per-exception creation timestamp to group
by. server_default=now() backfills any pre-existing rows; new rows set
it explicitly in app/workers/tasks.py. Autogenerate also proposed
dropping the four procrastinate_* tables, for the reason noted in
fa9f1a52d4fd and 646491b32151: they're raw SQL, not SQLAlchemy models.
Stripped.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '83476e7f6e10'
down_revision: Union[str, None] = '646491b32151'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'exceptions',
        sa.Column(
            'opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.alter_column('exceptions', 'opened_at', server_default=None)
    op.create_index(op.f('ix_exceptions_opened_at'), 'exceptions', ['opened_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exceptions_opened_at'), table_name='exceptions')
    op.drop_column('exceptions', 'opened_at')
