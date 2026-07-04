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
    use_rag: bool | None = None
    idempotency_key: str | None = None


class CorrectMetrics(BaseModel):
    latency_ms: int
    tokens_in: int
    tokens_out: int
    edit_ratio: float


class RagContext(BaseModel):
    source: str
    section: str | None = None
    score: float
    preview: str


class CorrectResponse(BaseModel):
    request_id: str
    corrected_text: str
    diff: list[dict] = Field(default_factory=list)
    model_used: str
    flagged: bool = False
    flag_reason: str | None = None
    model_output: str | None = None
    rag_context_used: list[RagContext] = Field(default_factory=list)
    metrics: CorrectMetrics


# ----- RAG ingestion API -----

# Bigger than the pipeline's 5000-char cap — ingested docs are legitimately
# large. Cap at 200KB to prevent a single request from monopolizing the
# embedding pipeline or blowing out Chroma.
RAG_INGEST_MAX_BYTES = 200_000


class RagIngestRequest(BaseModel):
    content: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=200)
    section: str | None = None


class RagIngestResponse(BaseModel):
    source: str
    chunks_indexed: int


class RagSourceInfo(BaseModel):
    source: str
    chunks: int
