"""grant sequence usage to app roles

Revision ID: 975e8129afe3
Revises: 7512a5784e63
Create Date: 2026-09-30 14:28:00.315623

Our own tables use UUID primary keys (no sequences), but procrastinate's
job queue tables use serial/identity columns backed by sequences. The
original roles migration only granted table privileges; sequences need
their own grant.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '975e8129afe3'
down_revision: Union[str, None] = '7512a5784e63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO app_rw"
    )
    op.execute("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO app_ro")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO app_ro"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON SEQUENCES FROM app_ro"
    )
    op.execute("REVOKE SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_ro")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM app_rw"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_rw")
