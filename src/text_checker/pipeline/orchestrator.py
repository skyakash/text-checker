import time
from uuid import uuid4

from ..api.schemas import (
    CorrectMetrics,
    CorrectRequest,
    CorrectResponse,
    RagContext,
)
from ..config import settings
from ..glossary.store import get_store as get_glossary_store
from ..observability.metrics import rag_retrieval_score
from ..providers.base import GenerationRequest
from ..providers.registry import ProviderRegistry
from ..rag.embeddings import EmbeddingsClient
from ..rag.retriever import retrieve as rag_retrieve
from ..rag.store import StoredChunk, get_store as get_rag_store
from . import postprocess, preprocess, prompts


async def run(req: CorrectRequest, registry: ProviderRegistry) -> CorrectResponse:
    glossary_terms = set(get_glossary_store().terms())
    masked = preprocess.preprocess(req.text, glossary_terms=glossary_terms)

    rag_results: list[StoredChunk] = []
    use_rag = settings.rag_enabled if req.use_rag is None else req.use_rag
    if use_rag and req.use_rag is None and req.mode.value in settings.rag_skip_modes_set:
        use_rag = False
    if use_rag:
        store = get_rag_store()
        if store.count() > 0:
            embedder = EmbeddingsClient(
                base_url=settings.rag_embedding_base_url or settings.ollama_base_url,
                model=settings.rag_embedding_model,
            )
            # Retrieve unfiltered so we can observe the full score distribution
            # for operators tuning RAG_MIN_SCORE from real traffic; then apply
            # the floor before returning chunks to the prompt builder.
            all_results = await rag_retrieve(
                req.text,
                k=settings.rag_top_k,
                store=store,
                embedder=embedder,
                min_score=0.0,
            )
            for chunk in all_results:
                rag_retrieval_score.labels(mode=req.mode.value).observe(chunk.score)
            rag_results = [c for c in all_results if c.score >= settings.rag_min_score]

    sys_prompt_base = prompts.system_prompt(req.mode)
    if rag_results:
        context_tuples = [
            (
                c.source,
                c.section,
                preprocess.reapply_glossary_masks(
                    c.text, masked.masks, masked.glossary_placeholders
                ),
            )
            for c in rag_results
        ]
        sys_prompt = prompts.with_context(sys_prompt_base, context_tuples)
    else:
        sys_prompt = sys_prompt_base

    route = registry.route(req.quality_tier, req.model)
    provider = registry.get(route.provider_name)

    gen_req = GenerationRequest(
        model=route.model,
        system_prompt=sys_prompt,
        user_prompt=prompts.user_prompt(masked.text),
    )

    start = time.perf_counter()
    gen_resp = await provider.generate(gen_req)
    latency_ms = int((time.perf_counter() - start) * 1000)

    raw = gen_resp.text.strip()
    candidate = preprocess.unmask(raw, masked.masks)
    candidate = postprocess.canonicalize_glossary_terms(
        candidate, masked.masks, masked.glossary_placeholders
    )

    passed, reason = postprocess.hallucination_guard(
        req.text, candidate, req.mode, masked.masks
    )
    if passed:
        corrected = candidate
        diff = postprocess.structured_diff(req.text, candidate)
        flagged = False
        flag_reason: str | None = None
        model_output: str | None = None
    else:
        corrected = req.text
        diff = []
        flagged = True
        flag_reason = reason
        model_output = candidate

    rag_context_used = [
        RagContext(
            source=r.source,
            section=r.section,
            score=r.score,
            preview=r.text.strip()[:120],
        )
        for r in rag_results
    ]

    return CorrectResponse(
        request_id=str(uuid4()),
        corrected_text=corrected,
        diff=diff,
        model_used=gen_resp.model,
        flagged=flagged,
        flag_reason=flag_reason,
        model_output=model_output,
        rag_context_used=rag_context_used,
        metrics=CorrectMetrics(
            latency_ms=latency_ms,
            tokens_in=gen_resp.tokens_in,
            tokens_out=gen_resp.tokens_out,
            edit_ratio=postprocess.edit_ratio(req.text, corrected),
        ),
    )
