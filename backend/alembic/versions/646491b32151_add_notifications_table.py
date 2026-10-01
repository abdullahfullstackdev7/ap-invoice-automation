"""add notifications table

Revision ID: 646491b32151
Revises: fa9f1a52d4fd
Create Date: 2026-10-01 08:40:25.133153

Autogenerate also proposed dropping the four procrastinate_* tables, for
the same reason noted in fa9f1a52d4fd: they're raw SQL, not SQLAlchemy
models, so Base.metadata doesn't know about them. Stripped; this
migration only adds notifications (Plan.md section 8's in-app bell menu).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '646491b32151'
down_revision: Union[str, None] = 'fa9f1a52d4fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.String(length=1000), nullable=False),
        sa.Column('link', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
