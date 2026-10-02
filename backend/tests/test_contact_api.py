from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import ContactSubmission


async def test_contact_submission_is_stored(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post(
        "/api/v1/contact",
        json={
            "name": "Jordan Smith",
            "email": "jordan@example.com",
            "company": "Example Co",
            "message": "We'd like a demo of the 3-way match workflow.",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"status": "received"}

    rows = (await db_session.execute(select(ContactSubmission))).scalars().all()
    assert len(rows) == 1
    assert rows[0].email == "jordan@example.com"
    assert rows[0].company == "Example Co"


async def test_contact_submission_requires_valid_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/contact",
        json={"name": "Jordan Smith", "email": "not-an-email", "message": "Hello"},
    )
    assert response.status_code == 422


async def test_contact_submission_requires_a_message(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/contact",
        json={"name": "Jordan Smith", "email": "jordan@example.com", "message": ""},
    )
    assert response.status_code == 422


async def test_contact_submission_does_not_require_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/contact",
        json={"name": "Anon", "email": "anon@example.com", "message": "Hi"},
    )
    assert response.status_code == 201
