"""create app roles and grants

Revision ID: 39a4e8a09dcf
Revises: aa814cf60ddc
Create Date: 2026-09-30 12:39:50.190655

Creates the two runtime database roles referenced throughout Plan.md
section 5 and 7: app_rw (used by the API and worker; read/write on
business tables but no DDL and no UPDATE/DELETE on the append-only
audit_log) and app_ro (read-only, used by analytics). Migrations
themselves always run as the separate apdb_admin role, which owns the
schema and is never used by the running application.
"""
import os
from typing import Sequence, Union

from alembic import op

revision: str = '39a4e8a09dcf'
down_revision: Union[str, None] = 'aa814cf60ddc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quoted_password(env_var: str, default: str) -> str:
    password = os.environ.get(env_var, default)
    return password.replace("'", "''")


def upgrade() -> None:
    app_rw_password = _quoted_password("DB_APP_RW_PASSWORD", "change_me")
    app_ro_password = _quoted_password("DB_APP_RO_PASSWORD", "change_me_ro")

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
                CREATE ROLE app_rw LOGIN PASSWORD '{app_rw_password}';
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_ro') THEN
                CREATE ROLE app_ro LOGIN PASSWORD '{app_ro_password}';
            END IF;
        END
        $$;
        """
    )

    op.execute("GRANT CONNECT ON DATABASE apdb TO app_rw, app_ro")
    op.execute("GRANT USAGE ON SCHEMA public TO app_rw, app_ro")
    op.execute("REVOKE CREATE ON SCHEMA public FROM app_rw, app_ro")

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw"
    )

    # audit_log is append-only: app_rw may insert and read, never update or delete.
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM app_rw")

    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_ro")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_ro"
    )


def downgrade() -> None:
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM app_ro")
    op.execute("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM app_ro")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_rw"
    )
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM app_rw")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_rw, app_ro")
    op.execute("REVOKE CONNECT ON DATABASE apdb FROM app_rw, app_ro")
    op.execute("DROP ROLE IF EXISTS app_ro")
    op.execute("DROP ROLE IF EXISTS app_rw")
