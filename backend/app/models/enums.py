import enum


class UserRole(enum.StrEnum):
    admin = "admin"
    ap_clerk = "ap_clerk"
    approver = "approver"
    finance_manager = "finance_manager"
    auditor = "auditor"


class VendorStatus(enum.StrEnum):
    active = "active"
    inactive = "inactive"


class VendorRiskTier(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class POStatus(enum.StrEnum):
    open = "open"
    closed = "closed"


class InvoiceStatus(enum.StrEnum):
    uploaded = "uploaded"
    ocr_done = "ocr_done"
    extracted = "extracted"
    matched = "matched"
    auto_approved = "auto_approved"
    exception = "exception"
    blocked = "blocked"
    approved = "approved"
    paid = "paid"
    needs_review = "needs_review"


class ExtractionSource(enum.StrEnum):
    rules = "rules"
    llm_text = "llm_text"
    llm_vision = "llm_vision"


class MatchOutcome(enum.StrEnum):
    auto_approved = "AUTO_APPROVED"
    exception = "EXCEPTION"
    blocked = "BLOCKED"


class MatchLineStatus(enum.StrEnum):
    ok = "ok"
    warning = "warning"
    exception = "exception"


class ExceptionSeverity(enum.StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class ExceptionStatus(enum.StrEnum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    escalated = "escalated"


class TolerancePolicyScope(enum.StrEnum):
    global_scope = "global"
    vendor = "vendor"
    category = "category"


class ApprovalDecision(enum.StrEnum):
    approved = "approved"
    rejected = "rejected"


class PaymentStatus(enum.StrEnum):
    scheduled = "scheduled"
    released = "released"
    settled = "settled"


class PaymentBatchStatus(enum.StrEnum):
    draft = "draft"
    released = "released"
    settled = "settled"


class PaymentMethod(enum.StrEnum):
    bank_file = "bank_file"


class LLMUsageStatus(enum.StrEnum):
    success = "success"
    error = "error"
    budget_stopped = "budget_stopped"
