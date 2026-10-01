import procrastinate

from app.core.settings import get_settings


def _plain_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


def build_app() -> procrastinate.App:
    settings = get_settings()
    connector = procrastinate.PsycopgConnector(conninfo=_plain_dsn(settings.database_url))
    return procrastinate.App(connector=connector, import_paths=["app.workers.tasks"])


procrastinate_app = build_app()
