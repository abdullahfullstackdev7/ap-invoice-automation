import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsDaily
from app.models.enums import UserRole
from app.models.masterdata import Vendor
from tests.conftest import TEST_PASSWORD, make_user

ALL_ROLES = [
    UserRole.admin,
    UserRole.ap_clerk,
    UserRole.approver,
    UserRole.finance_manager,
    UserRole.auditor,
]


async def _login_as(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> None:
    email = f"{role.value}@example.com"
    await make_user(db_session, email, role)
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _seed_one_day(db_session: AsyncSession) -> date:
    vendor = Vendor(code=f"V{uuid.uuid4().hex[:8]}", name="Acme", name_normalized="acme")
    db_session.add(vendor)
    await db_session.flush()
    d = date(2026, 9, 20)
    db_session.add(
        AnalyticsDaily(
            date=d, vendor_id=vendor.id, invoices_count=3, value=Decimal("300"), stp_count=2
        )
    )
    await db_session.commit()
    return d


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_kpis_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await _seed_one_day(db_session)
    await _login_as(client, db_session, role)

    response = await client.get("/api/v1/analytics/kpis")

    if role in (UserRole.admin, UserRole.finance_manager, UserRole.auditor):
        assert response.status_code == 200
    else:
        assert response.status_code == 403


async def test_kpis_sets_etag_and_honors_if_none_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_one_day(db_session)
    await _login_as(client, db_session, UserRole.admin)

    first = await client.get("/api/v1/analytics/kpis")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert etag

    second = await client.get("/api/v1/analytics/kpis", headers={"If-None-Match": etag})
    assert second.status_code == 304


async def test_volume_value_trend_csv_export(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_one_day(db_session)
    await _login_as(client, db_session, UserRole.finance_manager)

    response = await client.get(
        "/api/v1/analytics/volume-value-trend",
        params={"date_from": "2026-09-20", "date_to": "2026-09-20", "format": "csv"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "invoices_count" in response.text


async def test_spend_by_vendor_is_paginated(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_one_day(db_session)
    await _login_as(client, db_session, UserRole.auditor)

    response = await client.get(
        "/api/v1/analytics/spend-by-vendor",
        params={"date_from": "2026-09-20", "date_to": "2026-09-20", "limit": 1, "offset": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert len(body["items"]) <= 1


async def test_extraction_accuracy_is_file_based_and_handles_missing_files(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.admin)

    response = await client.get("/api/v1/analytics/extraction-accuracy")
    assert response.status_code == 200
    body = response.json()
    assert "note" in body
    assert "extraction" in body
    assert "matching" in body
