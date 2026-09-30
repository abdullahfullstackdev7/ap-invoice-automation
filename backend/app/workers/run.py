from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    logger.info("worker_started")
    # Job definitions are registered here in Phase 4 (Procrastinate app and tasks).


if __name__ == "__main__":
    main()
