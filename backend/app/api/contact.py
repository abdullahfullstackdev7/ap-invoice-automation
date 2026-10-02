from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.session import get_db_session
from app.models.contact import ContactSubmission
from app.schemas.contact import ContactSubmissionCreate

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def submit_contact_form(
    request: Request,
    body: ContactSubmissionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    submission = ContactSubmission(
        name=body.name,
        email=body.email,
        company=body.company,
        message=body.message,
        submitted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.commit()
    return {"status": "received"}
