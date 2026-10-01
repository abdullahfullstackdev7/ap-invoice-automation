"""add procrastinate job queue schema

Revision ID: 7512a5784e63
Revises: 7bae789e7082
Create Date: 2026-09-30 18:00:00.000000

Applies procrastinate's own schema.sql (its jobs table, enums, triggers
and functions) as part of our regular migration chain, so a fresh
database reaches full demo state with a single `alembic upgrade head`
rather than a separate `procrastinate schema --apply` step. app_rw
already has SELECT/INSERT/UPDATE/DELETE on these tables via the
`ALTER DEFAULT PRIVILEGES` set up in the roles migration, since they are
created by the same apdb_admin role that ran that statement.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import procrastinate.sql

revision: str = '7512a5784e63'
down_revision: Union[str, None] = '7bae789e7082'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA_SQL_PATH = Path(procrastinate.sql.__file__).parent / "schema.sql"


def upgrade() -> None:
    op.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS procrastinate_events, procrastinate_periodic_defers, "
        "procrastinate_jobs, procrastinate_workers CASCADE"
    )
    op.execute("DROP TYPE IF EXISTS procrastinate_job_to_defer_v1")
    op.execute("DROP TYPE IF EXISTS procrastinate_job_event_type")
    op.execute("DROP TYPE IF EXISTS procrastinate_job_status")
