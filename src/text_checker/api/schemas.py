from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    GRAMMAR = "grammar"
    STYLE = "style"
    JIRA_STORY = "jira-story"
    RELEASE_NOTE = "release-note"


class QualityTier(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    HIGH = "high"


class CorrectRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    mode: Mode = Mode.GRAMMAR
    model: str | None = None
    quality_tier: QualityTier = QualityTier.BALANCED
    idempotency_key: str | None = None


class CorrectMetrics(BaseModel):
    latency_ms: int
    tokens_in: int
    tokens_out: int
    edit_ratio: float


class CorrectResponse(BaseModel):
    request_id: str
    corrected_text: str
    diff: list[dict] = Field(default_factory=list)
    model_used: str
    flagged: bool = False
    flag_reason: str | None = None
    model_output: str | None = None
    metrics: CorrectMetrics
