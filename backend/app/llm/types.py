import enum

from pydantic import BaseModel


class LLMTask(enum.StrEnum):
    header = "header"
    lines = "lines"
    vision = "vision"


class LLMResult(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    provider: str
    model: str
