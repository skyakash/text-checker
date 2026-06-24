import time
from uuid import uuid4

from ..api.schemas import CorrectMetrics, CorrectRequest, CorrectResponse
from ..providers.base import GenerationRequest
from ..providers.registry import ProviderRegistry
from . import postprocess, preprocess, prompts


async def run(req: CorrectRequest, registry: ProviderRegistry) -> CorrectResponse:
    masked = preprocess.preprocess(req.text)
    route = registry.route(req.quality_tier, req.model)
    provider = registry.get(route.provider_name)

    gen_req = GenerationRequest(
        model=route.model,
        system_prompt=prompts.system_prompt(req.mode),
        user_prompt=prompts.user_prompt(masked.text),
    )

    start = time.perf_counter()
    gen_resp = await provider.generate(gen_req)
    latency_ms = int((time.perf_counter() - start) * 1000)

    raw = gen_resp.text.strip()
    candidate = preprocess.unmask(raw, masked.masks)

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

    return CorrectResponse(
        request_id=str(uuid4()),
        corrected_text=corrected,
        diff=diff,
        model_used=gen_resp.model,
        flagged=flagged,
        flag_reason=flag_reason,
        model_output=model_output,
        metrics=CorrectMetrics(
            latency_ms=latency_ms,
            tokens_in=gen_resp.tokens_in,
            tokens_out=gen_resp.tokens_out,
            edit_ratio=postprocess.edit_ratio(req.text, corrected),
        ),
    )
