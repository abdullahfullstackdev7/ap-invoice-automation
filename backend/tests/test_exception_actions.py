import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from app.services.exception_actions import apply_exception_action
from tests.conftest import make_user


async def _invoice_with_exception(
    db_session: AsyncSession, *, total: Decimal, uploader_id: uuid.UUID | None = None
) -> tuple[Invoice, ExceptionRecord]:
    vendor = Vendor(code=f"V{uuid.uuid4().hex[:8]}", name="Acme", name_normalized="acme")
    db_session.add(vendor)
    await db_session.flush()

    document = Document(
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        filename="f.png",
        mime="image/png",
        size=1,
        storage_path="x",
        uploaded_by=uploader_id,
        uploaded_at=datetime.now(UTC),
    )
    db_session.add(document)
    await db_session.flush()

    invoice = Invoice(
        document_id=document.id,
        vendor_id=vendor.id,
        invoice_no="INV-1",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        total=total,
        status=InvoiceStatus.exception,
    )
    db_session.add(invoice)
    await db_session.flush()

    exception = ExceptionRecord(
        invoice_id=invoice.id,
        reason_code="PRICE_VARIANCE",
        severity=ExceptionSeverity.medium,
        status=ExceptionStatus.open,
        details_json={"note": "test"},
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(invoice)
    await db_session.refresh(exception)
    return invoice, exception


async def test_approve_requires_a_reason_for_ap_clerk(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_exception_action(
            db_session,
            exception=exception,
            invoice=invoice,
            actor=clerk,
            action="approve",
            comment=None,
            assignee_id=None,
        )
    assert exc_info.value.status_code == 422


async def test_approve_with_reason_resolves_the_exception(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk2@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    result = await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="approve",
        comment="within policy",
        assignee_id=None,
    )
    await db_session.commit()

    assert result.fully_approved is True
    assert exception.status == ExceptionStatus.resolved
    assert exception.resolved_by == clerk.id
    assert exception.resolution == "within policy"
    assert invoice.status == InvoiceStatus.approved


async def test_approve_rejects_when_amount_exceeds_approval_limit(db_session: AsyncSession) -> None:
    # Still within the ap_clerk amount tier (<= 2,500), so the role check
    # passes; it's this clerk's own personal approval_limit that's too low.
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("2000"))
    clerk = await make_user(
        db_session, "clerk3@example.com", UserRole.ap_clerk, approval_limit=Decimal("1000")
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_exception_action(
            db_session,
            exception=exception,
            invoice=invoice,
            actor=clerk,
            action="approve",
            comment="too big for me",
            assignee_id=None,
        )
    assert exc_info.value.status_code == 403


async def test_reject_requires_a_comment(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk4@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_exception_action(
            db_session,
            exception=exception,
            invoice=invoice,
            actor=clerk,
            action="reject",
            comment=None,
            assignee_id=None,
        )
    assert exc_info.value.status_code == 422


async def test_reject_sends_invoice_back_to_needs_review(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk5@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="reject",
        comment="bad invoice",
        assignee_id=None,
    )
    await db_session.commit()

    assert invoice.status == InvoiceStatus.needs_review
    assert exception.status == ExceptionStatus.resolved
    assert exception.resolution == "rejected: bad invoice"


async def test_hold_puts_exception_in_review_without_resolving(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk6@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="hold",
        comment="waiting on vendor",
        assignee_id=None,
    )
    await db_session.commit()

    assert exception.status == ExceptionStatus.in_review
    assert exception.resolution == "on hold: waiting on vendor"


async def test_reassign_requires_an_assignee(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk7@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_exception_action(
            db_session,
            exception=exception,
            invoice=invoice,
            actor=clerk,
            action="reassign",
            comment=None,
            assignee_id=None,
        )
    assert exc_info.value.status_code == 422


async def test_reassign_sets_assigned_to(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk8@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )
    approver = await make_user(db_session, "approver8@example.com", UserRole.approver)

    await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="reassign",
        comment=None,
        assignee_id=approver.id,
    )
    await db_session.commit()

    assert exception.assigned_to == approver.id


async def test_add_comment_appends_without_changing_status(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk9@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="add_comment",
        comment="checking with the vendor",
        assignee_id=None,
    )
    await db_session.commit()

    assert exception.status == ExceptionStatus.open
    details = exception.details_json or {}
    comments = details["comments"]
    assert isinstance(comments, list)
    assert len(comments) == 1
    assert comments[0]["comment"] == "checking with the vendor"


async def test_re_match_requests_a_re_run_without_changing_status(db_session: AsyncSession) -> None:
    invoice, exception = await _invoice_with_exception(db_session, total=Decimal("1000"))
    clerk = await make_user(
        db_session, "clerk10@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )

    result = await apply_exception_action(
        db_session,
        exception=exception,
        invoice=invoice,
        actor=clerk,
        action="re_match",
        comment=None,
        assignee_id=None,
    )
    await db_session.commit()

    assert result.re_match_requested is True
    assert exception.status == ExceptionStatus.open


async def test_uploader_cannot_approve_their_own_exception(db_session: AsyncSession) -> None:
    clerk = await make_user(
        db_session, "clerk11@example.com", UserRole.ap_clerk, approval_limit=Decimal("2500")
    )
    invoice, exception = await _invoice_with_exception(
        db_session, total=Decimal("1000"), uploader_id=clerk.id
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_exception_action(
            db_session,
            exception=exception,
            invoice=invoice,
            actor=clerk,
            action="approve",
            comment="self approving",
            assignee_id=None,
        )
    assert exc_info.value.status_code == 403
