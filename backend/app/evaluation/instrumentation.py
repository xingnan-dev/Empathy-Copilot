from backend.app.llm.schemas import ModelCallRecord

from .schemas import EvaluationSystem, PricingProfile, RunInstrumentation


def summarize_calls(
    *,
    run_id: str,
    case_id: str,
    system: EvaluationSystem,
    provider: str,
    model: str,
    calls: list[ModelCallRecord],
    latency_ms: int,
    tool_calls: int = 0,
    vision_calls: int = 0,
    retrieval_calls: int = 0,
    pricing: PricingProfile | None = None,
    context_items_before: int = 0,
    context_items_after: int = 0,
) -> RunInstrumentation:
    input_tokens = sum(item.usage.input_tokens or 0 for item in calls)
    output_tokens = sum(item.usage.output_tokens or 0 for item in calls)
    total_tokens = sum(item.usage.total_tokens or 0 for item in calls)
    estimated = None
    if pricing is not None:
        estimated = (input_tokens * pricing.input_per_million / 1_000_000) + (
            output_tokens * pricing.output_per_million / 1_000_000
        )
        if pricing.vision_per_call is not None:
            estimated += vision_calls * pricing.vision_per_call
    return RunInstrumentation(
        run_id=run_id,
        case_id=case_id,
        system=system,
        provider=provider,
        model=model,
        model_calls=len(calls),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        vision_calls=vision_calls,
        tool_calls=tool_calls,
        retrieval_calls=retrieval_calls,
        latency_ms=latency_ms,
        fallback_count=sum(item.fallback_used for item in calls),
        error_count=sum(item.status != "COMPLETED" for item in calls),
        estimated_cost=estimated,
        model_latency_ms=sum(item.latency_ms for item in calls),
        context_items_before=context_items_before,
        context_items_after=context_items_after,
    )
