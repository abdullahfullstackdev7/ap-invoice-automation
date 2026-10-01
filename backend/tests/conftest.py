import os
import tempfile
from collections.abc import AsyncGenerator, Callable, Coroutine
from decimal import Decimal

os.environ.setdefault("FILE_STORAGE_PATH", tempfile.mkdtemp(prefix="ap_test_files_"))

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.identity import User  # noqa: E402

TEST_PASSWORD = "CorrectHorseBattery12"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://app_rw:change_me@localhost:5433/apdb",
)
TEST_DATABASE_ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+asyncpg://apdb_admin:change_me_admin@localhost:5433/apdb",
)

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

admin_engine = create_async_engine(TEST_DATABASE_ADMIN_URL, poolclass=NullPool)
AdminSessionLocal = async_sessionmaker(admin_engine, expire_on_commit=False)

TRUNCATE_TABLES = [
    "audit_log",
    "refresh_tokens",
    "users",
    "extraction_runs",
    "llm_usage",
    "invoices",
    "documents",
    "procrastinate_jobs",
    "vendors",
    "items",
    "purchase_orders",
    "po_lines",
    "goods_receipts",
    "gr_lines",
    "exceptions",
    "approvals",
    "approval_policies",
    "payments",
    "payment_batches",
    "notifications",
]


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncGenerator[None, None]:
    # TRUNCATE needs table-owner-level privilege; app_rw intentionally does
    # not have it (and cannot DELETE from audit_log at all), so cleanup
    # between tests runs as apdb_admin, same as a CI reset step would.
    async with admin_engine.begin() as conn:
        await conn.exec_driver_sql(f"TRUNCATE {', '.join(TRUNCATE_TABLES)} CASCADE")
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def admin_db_session() -> AsyncGenerator[AsyncSession, None]:
    """A session using apdb_admin, for tests that simulate direct DB access
    bypassing the application (e.g. audit log tamper detection). app_rw
    cannot UPDATE or DELETE audit_log by design; see Plan.md section 5.
    """
    async with AdminSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def deferred_jobs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Records process_invoice.defer_async calls instead of touching a real
    Procrastinate connection pool. The pool is tied to the event loop that
    opened it, which makes opening/closing it per test (pytest-asyncio's
    function-scoped loops) fragile; job deferral is procrastinate's own
    tested behavior, not ours, so the endpoint test boundary is "did we
    enqueue the right task with the right args."
    """
    from app.workers import tasks

    calls: list[dict[str, object]] = []

    def _make_fake_defer_async(
        task_name: str,
    ) -> Callable[..., Coroutine[object, object, None]]:
        async def _fake_defer_async(**kwargs: object) -> None:
            calls.append({"task": task_name, **kwargs})

        return _fake_defer_async

    # Tasks call app.db.session.async_session_factory directly (they don't
    # go through FastAPI's get_db_session dependency), and that module-level
    # engine uses normal pooling. A pooled asyncpg connection can't survive
    # being reused across pytest-asyncio's function-scoped event loops (the
    # same failure mode NullPool works around for the engines above), so
    # tests that call a task's .func() directly need it repointed at the
    # NullPool test engine too.
    monkeypatch.setattr(tasks, "async_session_factory", TestSessionLocal)

    monkeypatch.setattr(
        tasks.process_invoice, "defer_async", _make_fake_defer_async("process_invoice")
    )
    monkeypatch.setattr(
        tasks.extract_invoice_fields,
        "defer_async",
        _make_fake_defer_async("extract_invoice_fields"),
    )
    monkeypatch.setattr(
        tasks.resolve_invoice_entities,
        "defer_async",
        _make_fake_defer_async("resolve_invoice_entities"),
    )
    monkeypatch.setattr(tasks.match_invoice, "defer_async", _make_fake_defer_async("match_invoice"))
    monkeypatch.setattr(tasks.route_invoice, "defer_async", _make_fake_defer_async("route_invoice"))
    monkeypatch.setattr(
        tasks.schedule_payment, "defer_async", _make_fake_defer_async("schedule_payment")
    )
    monkeypatch.setattr(
        tasks.settle_payment_batch,
        "defer_async",
        _make_fake_defer_async("settle_payment_batch"),
    )
    return calls


@pytest_asyncio.fixture
async def client(deferred_jobs: list[dict[str, object]]) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def make_user(
    session: AsyncSession,
    email: str,
    role: UserRole,
    *,
    approval_limit: Decimal | None = None,
    password: str = TEST_PASSWORD,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=email.split("@")[0],
        role=role,
        approval_limit=approval_limit,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
