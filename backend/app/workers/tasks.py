import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from procrastinate import RetryStrategy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.session import async_session_factory
from app.extraction.cache import compute_ocr_text_hash, find_cached_extraction
from app.extraction.llm_fallback import apply_llm_fallback, build_router_from_settings
from app.extraction.persist import apply_extract_to_invoice, extract_to_json
from app.extraction.rules_extractor import run_rules_extraction
from app.extraction.types import InvoiceExtract
from app.extraction.validator import validate
from app.matching.service import run_match_for_invoice
from app.models.enums import (
    ExceptionSeverity,
    ExceptionStatus,
    ExtractionSource,
    InvoiceStatus,
    MatchOutcome,
    PaymentBatchStatus,
    PaymentStatus,
)
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Document, ExtractionRun, Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.matching import MatchLineResult, MatchResult
from app.models.payments import Payment, PaymentBatch
from app.models.procurement import POLine
from app.ocr.service import process_document
from app.ocr.types import OCRDocumentResult
from app.services.approval_routing import determine_routing
from app.services.audit import AuditService
from app.services.exception_routing import default_assignee_role, sla_due_at
from app.services.line_matching import LineCandidate, match_invoice_lines_to_po_lines
from app.services.notifications import notify_role
from app.services.payment_scheduling import decide_payment_schedule
from app.services.po_resolution import resolve_po
from app.services.storage import read_file
from app.services.vendor_resolution import resolve_vendor
from app.workers.procrastinate_app import procrastinate_app

logger = structlog.get_logger(__name__)


@procrastinate_app.task(
    name="process_invoice",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def process_invoice(document_id: str) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(document_id))
        if document is None:
            logger.warning("process_invoice_document_missing", document_id=document_id)
            return

        result = await session.execute(select(Invoice).where(Invoice.document_id == document.id))
        invoice = result.scalar_one_or_none()
        if invoice is None:
            logger.warning("process_invoice_invoice_missing", document_id=document_id)
            return

        if invoice.status != InvoiceStatus.uploaded:
            # Idempotency: a retry or a duplicate enqueue should not redo
            # work once a previous run already advanced the status.
            logger.info(
                "process_invoice_already_processed",
                invoice_id=str(invoice.id),
                status=invoice.status,
            )
            return

        started_at = datetime.now(UTC)
        content = read_file(document.storage_path)

        try:
            ocr_result = process_document(content, document.mime)
        except Exception:
            logger.exception("process_invoice_ocr_failed", invoice_id=str(invoice.id))
            raise

        invoice.status = InvoiceStatus.ocr_done
        invoice.extraction_confidence = (
            Decimal(str(round(ocr_result.mean_confidence, 3))) if ocr_result.pages else None
        )
        invoice.extracted_json = {"ocr": ocr_result.model_dump(mode="json")}

        latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)

        await AuditService(session).record(
            "invoice_ocr_completed",
            "invoice",
            actor_id=None,
            entity_id=invoice.id,
            after={
                "status": invoice.status.value,
                "mean_confidence": invoice.extraction_confidence,
            },
        )

        await session.commit()
        logger.info(
            "process_invoice_completed",
            invoice_id=str(invoice.id),
            mean_confidence=ocr_result.mean_confidence,
            latency_ms=latency_ms,
        )

    await extract_invoice_fields.defer_async(invoice_id=str(invoice.id))


@procrastinate_app.task(
    name="extract_invoice_fields",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def extract_invoice_fields(invoice_id: str) -> None:
    async with async_session_factory() as session:
        invoice = await session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("extract_invoice_fields_invoice_missing", invoice_id=invoice_id)
            return

        if invoice.status != InvoiceStatus.ocr_done:
            logger.info(
                "extract_invoice_fields_already_processed",
                invoice_id=invoice_id,
                status=invoice.status,
            )
            return

        if not invoice.extracted_json or "ocr" not in invoice.extracted_json:
            logger.warning("extract_invoice_fields_no_ocr_data", invoice_id=invoice_id)
            return

        ocr_result = OCRDocumentResult.model_validate(invoice.extracted_json["ocr"])
        ocr_text_hash = compute_ocr_text_hash(ocr_result)
        invoice.dup_key = ocr_text_hash

        cached = await find_cached_extraction(session, ocr_text_hash, invoice.id)
        if cached is not None and cached.extracted_json and "extraction" in cached.extracted_json:
            await _apply_cached_extraction(session, invoice, cached.id, cached.extracted_json)
            await session.commit()
            logger.info("extract_invoice_fields_cache_hit", invoice_id=invoice_id)
            await resolve_invoice_entities.defer_async(invoice_id=invoice_id)
            return

        started_at = datetime.now(UTC)
        extract = run_rules_extraction(ocr_result)
        validation = validate(extract)

        session.add(
            ExtractionRun(
                invoice_id=invoice.id,
                stage_path=ExtractionSource.rules,
                provider=None,
                model=None,
                tokens_in=None,
                tokens_out=None,
                latency_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                cache_hit=False,
                errors_json={"errors": validation.errors} if validation.errors else None,
                run_at=datetime.now(UTC),
            )
        )

        if validation.needs_llm:
            router = build_router_from_settings(session)
            if router is not None:
                all_text = "\n".join(line.text for page in ocr_result.pages for line in page.lines)
                llm_started = datetime.now(UTC)
                extract = await apply_llm_fallback(
                    extract, validation, all_text, all_text, router, invoice_id=invoice.id
                )
                validation = validate(extract)
                session.add(
                    ExtractionRun(
                        invoice_id=invoice.id,
                        stage_path=ExtractionSource.llm_text,
                        provider=None,
                        model=None,
                        tokens_in=None,
                        tokens_out=None,
                        latency_ms=int((datetime.now(UTC) - llm_started).total_seconds() * 1000),
                        cache_hit=False,
                        errors_json={"errors": validation.errors} if validation.errors else None,
                        run_at=datetime.now(UTC),
                    )
                )
            else:
                logger.info(
                    "extract_invoice_fields_no_llm_provider_configured", invoice_id=invoice_id
                )

        lines = apply_extract_to_invoice(invoice, extract)
        for line in lines:
            session.add(line)

        invoice.status = (
            InvoiceStatus.extracted if validation.passed else InvoiceStatus.needs_review
        )
        invoice.extracted_json = {
            **invoice.extracted_json,
            "extraction": extract_to_json(extract),
            "validation": {
                "passed": validation.passed,
                "failing_fields": validation.failing_fields,
                "low_confidence_fields": validation.low_confidence_fields,
            },
        }

        await AuditService(session).record(
            "invoice_extraction_completed",
            "invoice",
            actor_id=None,
            entity_id=invoice.id,
            after={"status": invoice.status.value, "validation_passed": validation.passed},
        )

        final_status = invoice.status
        await session.commit()
        logger.info(
            "extract_invoice_fields_completed",
            invoice_id=invoice_id,
            status=final_status,
            validation_passed=validation.passed,
        )

    if final_status == InvoiceStatus.extracted:
        await resolve_invoice_entities.defer_async(invoice_id=invoice_id)


@procrastinate_app.task(
    name="resolve_invoice_entities",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def resolve_invoice_entities(invoice_id: str) -> None:
    """Vendor resolution, PO resolution and line-to-PO-line mapping, per
    Plan.md section 6 / Phase 6. Does not change invoice.status (that
    vocabulary stops at "extracted" until Phase 7's match engine runs);
    results are stored under extracted_json["resolution"] for Phase 7 to
    consume, and invoices.vendor_id is set when vendor resolution succeeds.
    """
    async with async_session_factory() as session:
        invoice = await session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("resolve_invoice_entities_invoice_missing", invoice_id=invoice_id)
            return

        if invoice.status != InvoiceStatus.extracted:
            logger.info(
                "resolve_invoice_entities_wrong_status",
                invoice_id=invoice_id,
                status=invoice.status,
            )
            return

        if invoice.extracted_json and "resolution" in invoice.extracted_json:
            logger.info("resolve_invoice_entities_already_processed", invoice_id=invoice_id)
            return

        extract_data = (invoice.extracted_json or {}).get("extraction") or {}
        extract = InvoiceExtract.model_validate(extract_data)
        vendor_name = extract.vendor_name.value
        vendor_email = extract.vendor_email.value
        vendor_tax_id = extract.vendor_tax_id.value

        vendor_result = await resolve_vendor(
            session, vendor_name=vendor_name, vendor_address=vendor_email, tax_id=vendor_tax_id
        )
        if vendor_result.resolved:
            invoice.vendor_id = vendor_result.vendor_id
        else:
            session.add(
                ExceptionRecord(
                    invoice_id=invoice.id,
                    reason_code="VENDOR_UNRESOLVED",
                    severity=ExceptionSeverity.medium,
                    status=ExceptionStatus.open,
                    details_json={
                        "vendor_name": vendor_name,
                        "best_score": vendor_result.score,
                    },
                )
            )

        lines_result = await session.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        )
        invoice_lines = list(lines_result.scalars().all())

        po_result = await resolve_po(
            session,
            po_number_ref=invoice.po_number_ref,
            vendor_id=invoice.vendor_id,
            invoice_date=invoice.invoice_date,
            invoice_total=invoice.total,
            invoice_line_descriptions=[line.description for line in invoice_lines],
        )

        line_matches = []
        if po_result.po_id is not None:
            po_lines_result = await session.execute(
                select(POLine).where(POLine.po_id == po_result.po_id)
            )
            po_lines = list(po_lines_result.scalars().all())

            match_results = match_invoice_lines_to_po_lines(
                [LineCandidate(line.id, line.description, sku=line.sku) for line in invoice_lines],
                [LineCandidate(line.id, line.description) for line in po_lines],
            )
            for match in match_results:
                line_matches.append(
                    {
                        "invoice_line_id": str(match.invoice_line_id),
                        "po_line_id": str(match.po_line_id) if match.po_line_id else None,
                        "score": match.score,
                        "method": match.method,
                    }
                )

        invoice.extracted_json = {
            **(invoice.extracted_json or {}),
            "resolution": {
                "vendor": {
                    "vendor_id": str(vendor_result.vendor_id) if vendor_result.vendor_id else None,
                    "method": vendor_result.method,
                    "score": vendor_result.score,
                },
                "po": {
                    "po_id": str(po_result.po_id) if po_result.po_id else None,
                    "method": po_result.method,
                    "score": po_result.score,
                },
                "line_matches": line_matches,
            },
        }

        await AuditService(session).record(
            "invoice_entities_resolved",
            "invoice",
            actor_id=None,
            entity_id=invoice.id,
            after={
                "vendor_resolved": vendor_result.resolved,
                "po_resolved": po_result.po_id is not None,
            },
        )

        await session.commit()
        logger.info(
            "resolve_invoice_entities_completed",
            invoice_id=invoice_id,
            vendor_method=vendor_result.method,
            po_method=po_result.method,
            line_match_count=len(line_matches),
        )

    await match_invoice.defer_async(invoice_id=invoice_id)


@procrastinate_app.task(
    name="match_invoice",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def match_invoice(invoice_id: str) -> None:
    """3-way match and rules engine, Plan.md section 7. Safe to call
    repeatedly: an existing OPEN exception with the same reason code is
    never duplicated, so a late-arriving PO or GRN can trigger a clean
    re-match without flooding the exceptions queue.
    """
    async with async_session_factory() as session:
        invoice = await session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("match_invoice_invoice_missing", invoice_id=invoice_id)
            return

        rematchable_statuses = (
            InvoiceStatus.extracted,
            InvoiceStatus.matched,
            InvoiceStatus.exception,
        )
        if invoice.status not in rematchable_statuses:
            logger.info("match_invoice_wrong_status", invoice_id=invoice_id, status=invoice.status)
            return

        result = await run_match_for_invoice(session, invoice)
        decision = result.decision

        invoice_lines_result = await session.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        )
        invoice_lines = list(invoice_lines_result.scalars().all())
        po_lines_by_mapped_invoice_line = {
            m.invoice_line_id: m.po_line_id for m in result.line_mappings
        }
        po_line_rows: dict[uuid.UUID, POLine] = {}
        if result.po is not None:
            po_line_result = await session.execute(
                select(POLine).where(POLine.po_id == result.po.id)
            )
            po_line_rows = {line.id: line for line in po_line_result.scalars().all()}

        match_result = MatchResult(
            invoice_id=invoice.id,
            po_id=result.po.id if result.po else None,
            outcome=decision.outcome,
            score=(
                Decimal(str(round(len(po_lines_by_mapped_invoice_line) / len(invoice_lines), 4)))
                if invoice_lines
                else Decimal("0")
            ),
            tolerance_policy_id=None,
            run_at=datetime.now(UTC),
        )
        session.add(match_result)
        await session.flush()

        for invoice_line in invoice_lines:
            po_line_id = po_lines_by_mapped_invoice_line.get(invoice_line.id)
            po_line = po_line_rows.get(po_line_id) if po_line_id else None
            qty_var = (invoice_line.qty - po_line.qty) if po_line is not None else None
            price_var_pct = None
            if po_line is not None and po_line.unit_price != 0:
                price_var_pct = (
                    (invoice_line.unit_price - po_line.unit_price) / po_line.unit_price * 100
                )
            line_status = "ok"
            if po_line is None:
                line_status = "exception"
            elif (qty_var and qty_var != 0) or (price_var_pct and abs(price_var_pct) > 1):
                line_status = "warning"

            session.add(
                MatchLineResult(
                    match_id=match_result.id,
                    invoice_line_id=invoice_line.id,
                    po_line_id=po_line.id if po_line else None,
                    qty_inv=invoice_line.qty,
                    qty_po=po_line.qty if po_line else None,
                    qty_recv=None,
                    qty_prev_invoiced=po_line.qty_invoiced_cum if po_line else None,
                    price_inv=invoice_line.unit_price,
                    price_po=po_line.unit_price if po_line else None,
                    qty_var=qty_var,
                    price_var_pct=price_var_pct,
                    status=line_status,
                )
            )

        existing_open_result = await session.execute(
            select(ExceptionRecord.reason_code).where(
                ExceptionRecord.invoice_id == invoice.id,
                ExceptionRecord.status == ExceptionStatus.open,
            )
        )
        existing_open_reason_codes = {row[0] for row in existing_open_result.all()}

        default_assignee_by_role: dict[str, uuid.UUID | None] = {}
        new_exception_count = 0
        for draft in decision.exceptions:
            if draft.reason_code in existing_open_reason_codes:
                continue

            role = default_assignee_role(draft.reason_code)
            if role.value not in default_assignee_by_role:
                assignee_result = await session.execute(
                    select(User.id).where(User.role == role, User.is_active.is_(True)).limit(1)
                )
                default_assignee_by_role[role.value] = assignee_result.scalar_one_or_none()

            session.add(
                ExceptionRecord(
                    invoice_id=invoice.id,
                    reason_code=draft.reason_code,
                    severity=draft.severity,
                    status=ExceptionStatus.open,
                    details_json=draft.details,
                    assigned_to=default_assignee_by_role[role.value],
                    sla_due_at=sla_due_at(draft.severity),
                )
            )
            existing_open_reason_codes.add(draft.reason_code)
            new_exception_count += 1

        if decision.outcome == MatchOutcome.blocked:
            invoice.status = InvoiceStatus.blocked
        elif decision.outcome == MatchOutcome.exception:
            invoice.status = InvoiceStatus.exception
        else:
            invoice.status = InvoiceStatus.matched

        await AuditService(session).record(
            "invoice_matched",
            "invoice",
            actor_id=None,
            entity_id=invoice.id,
            after={
                "outcome": decision.outcome.value,
                "exception_count": len(decision.exceptions),
                "new_exceptions": new_exception_count,
            },
        )

        outcome = decision.outcome
        await session.commit()
        logger.info(
            "match_invoice_completed",
            invoice_id=invoice_id,
            outcome=decision.outcome.value,
            exception_count=len(decision.exceptions),
        )

    if outcome != MatchOutcome.blocked:
        await route_invoice.defer_async(invoice_id=invoice_id)


@procrastinate_app.task(
    name="route_invoice",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def route_invoice(invoice_id: str) -> None:
    """Approval routing, Plan.md section 8's default matrix. A clean match
    within the auto-approve limit skips human approval entirely and goes
    straight to payment scheduling; everything else waits in the
    exceptions/approvals queue for the role app.services.approval_routing
    decides is required, which the approvals API enforces at decision time.
    """
    async with async_session_factory() as session:
        invoice = await session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("route_invoice_invoice_missing", invoice_id=invoice_id)
            return
        if invoice.status not in (InvoiceStatus.matched, InvoiceStatus.exception):
            logger.info("route_invoice_wrong_status", invoice_id=invoice_id, status=invoice.status)
            return

        open_result = await session.execute(
            select(ExceptionRecord.reason_code).where(
                ExceptionRecord.invoice_id == invoice.id,
                ExceptionRecord.status.in_((ExceptionStatus.open, ExceptionStatus.in_review)),
            )
        )
        reason_codes = frozenset(row[0] for row in open_result.all())
        routing = await determine_routing(
            session,
            amount=invoice.total or Decimal("0"),
            has_exceptions=bool(reason_codes),
            exception_reason_codes=reason_codes,
        )

        if routing.auto_approved:
            invoice.status = InvoiceStatus.auto_approved
            await AuditService(session).record(
                "invoice_auto_approved",
                "invoice",
                actor_id=None,
                entity_id=invoice.id,
                after={"amount": str(invoice.total)},
            )
            await session.commit()
            logger.info("route_invoice_auto_approved", invoice_id=invoice_id)
            await schedule_payment.defer_async(invoice_id=invoice_id)
            return

        required_role = routing.steps[0]
        await notify_role(
            session,
            required_role,
            "Invoice awaiting approval",
            f"Invoice {invoice.invoice_no or invoice.id} needs {required_role.value} approval.",
            link=f"/invoices/{invoice.id}",
        )
        await AuditService(session).record(
            "invoice_routed_for_approval",
            "invoice",
            actor_id=None,
            entity_id=invoice.id,
            after={"required_role": required_role.value, "steps": [s.value for s in routing.steps]},
        )
        await session.commit()
        logger.info(
            "route_invoice_awaiting_approval",
            invoice_id=invoice_id,
            required_role=required_role,
        )


@procrastinate_app.task(
    name="schedule_payment",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def schedule_payment(invoice_id: str) -> None:
    """Creates the scheduled Payment row once an invoice is fully approved
    (or auto-approved), Plan.md section 8: pay on the due date, or earlier
    when the early-pay discount clears the annualized hurdle rate.
    """
    async with async_session_factory() as session:
        invoice = await session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("schedule_payment_invoice_missing", invoice_id=invoice_id)
            return
        if invoice.status not in (InvoiceStatus.auto_approved, InvoiceStatus.approved):
            logger.info(
                "schedule_payment_wrong_status", invoice_id=invoice_id, status=invoice.status
            )
            return

        existing = await session.execute(select(Payment).where(Payment.invoice_id == invoice.id))
        if existing.scalar_one_or_none() is not None:
            logger.info("schedule_payment_already_scheduled", invoice_id=invoice_id)
            return

        vendor = await session.get(Vendor, invoice.vendor_id) if invoice.vendor_id else None
        settings = get_settings()
        decision = decide_payment_schedule(
            invoice_date=invoice.invoice_date or date.today(),
            due_date=invoice.due_date or invoice.invoice_date or date.today(),
            discount_pct=vendor.discount_pct if vendor else None,
            discount_days=vendor.discount_days if vendor else None,
            hurdle_pct=Decimal(str(settings.early_pay_discount_hurdle_pct)),
        )

        payment = Payment(
            invoice_id=invoice.id,
            amount=invoice.total or Decimal("0"),
            scheduled_date=decision.scheduled_date,
            status=PaymentStatus.scheduled,
        )
        session.add(payment)
        await session.flush()

        await AuditService(session).record(
            "payment_scheduled",
            "payment",
            actor_id=None,
            entity_id=payment.id,
            after={
                "invoice_id": str(invoice.id),
                "scheduled_date": decision.scheduled_date.isoformat(),
                "early_pay_discount_taken": decision.early_pay_discount_taken,
            },
        )
        await session.commit()
        logger.info(
            "schedule_payment_completed",
            invoice_id=invoice_id,
            scheduled_date=decision.scheduled_date.isoformat(),
            early_pay_discount_taken=decision.early_pay_discount_taken,
        )


@procrastinate_app.task(
    name="settle_payment_batch",
    queue="invoices",
    retry=RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def settle_payment_batch(batch_id: str) -> None:
    """Simulated settlement: no real bank connection, Plan.md section 8.
    Runs as a follow-up job after a batch is released so `released` is
    visibly a distinct, auditable moment from `settled`.
    """
    async with async_session_factory() as session:
        batch = await session.get(PaymentBatch, uuid.UUID(batch_id))
        if batch is None:
            logger.warning("settle_payment_batch_missing", batch_id=batch_id)
            return
        if batch.status != PaymentBatchStatus.released:
            logger.info("settle_payment_batch_wrong_status", batch_id=batch_id, status=batch.status)
            return

        payments_result = await session.execute(select(Payment).where(Payment.batch_id == batch.id))
        payments = list(payments_result.scalars().all())

        now = datetime.now(UTC)
        for payment in payments:
            payment.status = PaymentStatus.settled
            invoice = await session.get(Invoice, payment.invoice_id)
            if invoice is not None:
                invoice.status = InvoiceStatus.paid

        batch.status = PaymentBatchStatus.settled

        await AuditService(session).record(
            "payment_batch_settled",
            "payment_batch",
            actor_id=None,
            entity_id=batch.id,
            after={"payment_count": len(payments), "settled_at": now.isoformat()},
        )
        await session.commit()
        logger.info(
            "settle_payment_batch_completed", batch_id=batch_id, payment_count=len(payments)
        )


async def _apply_cached_extraction(
    session: AsyncSession,
    invoice: Invoice,
    cached_invoice_id: uuid.UUID,
    cached_extracted_json: dict[str, object],
) -> None:
    extract = InvoiceExtract.model_validate(cached_extracted_json["extraction"])
    lines = apply_extract_to_invoice(invoice, extract)
    for line in lines:
        session.add(line)

    invoice.status = InvoiceStatus.extracted
    invoice.extracted_json = {
        **(invoice.extracted_json or {}),
        "extraction": extract_to_json(extract),
        "validation": {"passed": True, "failing_fields": [], "low_confidence_fields": []},
        "cache_hit_from": str(cached_invoice_id),
    }
    session.add(
        ExtractionRun(
            invoice_id=invoice.id,
            stage_path=ExtractionSource.rules,
            provider=None,
            model=None,
            tokens_in=None,
            tokens_out=None,
            latency_ms=0,
            cache_hit=True,
            errors_json=None,
            run_at=datetime.now(UTC),
        )
    )
