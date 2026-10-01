from app.core.logging import configure_logging, get_logger
from app.workers.procrastinate_app import procrastinate_app

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    logger.info("worker_started")
    procrastinate_app.run_worker(queues=["invoices"], listen_notify=True)


if __name__ == "__main__":
    main()
