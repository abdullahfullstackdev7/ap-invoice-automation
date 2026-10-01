from pydantic import BaseModel, ConfigDict


class LLMHeaderOutput(BaseModel):
    """Raw LLM header output: everything stays a string here and is only
    converted to Decimal/date by our own parsing helpers once validated,
    so a single odd format from the model doesn't fail the whole schema.
    """

    model_config = ConfigDict(extra="ignore")  # discard anything off-schema

    invoice_no: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    po_reference: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    tax: str | None = None
    discount: str | None = None
    total: str | None = None


class LLMLineItemOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    qty: str
    unit_price: str
    amount: str


class LLMLinesOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lines: list[LLMLineItemOutput] = []
