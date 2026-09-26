from .schemas import (
    AggregateMetrics,
    EvaluationCase,
    EvaluationRun,
    GroundingStatus,
    PricingProfile,
    QuestionRelevance,
)


def question_relevance(case: EvaluationCase, run: EvaluationRun) -> QuestionRelevance:
    if not case.golden.question_expected:
        return QuestionRelevance.NOT_APPLICABLE
    if run.next_question_gap == case.golden.expected_nbq_gap:
        return QuestionRelevance.MATCH
    if run.next_question_gap in case.golden.critical_gaps:
        return QuestionRelevance.PARTIAL
    return QuestionRelevance.MISMATCH


def aggregate(
    pairs: list[tuple[EvaluationCase, EvaluationRun]], pricing: PricingProfile | None = None
) -> AggregateMetrics:
    claims = [claim for _, run in pairs for claim in run.claims if claim.factual]
    unsupported = [claim for claim in claims if not claim.supported or claim.violation]
    expected_gaps = sum(len(case.golden.critical_gaps) for case, _ in pairs)
    detected = sum(
        len(set(case.golden.critical_gaps) & set(run.detected_gaps)) for case, run in pairs
    )
    nbq = {item.value: 0 for item in QuestionRelevance}
    for case, run in pairs:
        nbq[question_relevance(case, run).value] += 1
    violations = 0
    for case, run in pairs:
        violations += sum(claim.violation is not None for claim in run.claims)
        if case.golden.expected_safety_level == "SAFETY" and run.safety_level not in {
            "SAFETY",
            "UNSPECIFIED",
        }:
            violations += 1
    repeat_cases = [(case, run) for case, run in pairs if case.repeat_contact_required]
    repeated = sum(
        len(set(case.golden.already_known_facts) & set(run.asked_facts))
        for case, run in repeat_cases
    )
    known = sum(len(case.golden.already_known_facts) for case, _ in repeat_cases)
    instrumentation = [run.instrumentation for _, run in pairs]
    safety_runs = [(case, run) for case, run in pairs if run.safety_decision_available]
    safety_correct = sum(
        run.safety_level == case.golden.expected_safety_level for case, run in safety_runs
    )
    cost = None if pricing is None else sum(item.estimated_cost or 0 for item in instrumentation)
    return AggregateMetrics(
        case_count=len(pairs),
        unsupported_claim_rate=len(unsupported) / len(claims) if claims else 0,
        factual_claims=len(claims),
        unsupported_claims=len(unsupported),
        grounding_explicit=sum(item.grounding is GroundingStatus.EXPLICIT for item in claims),
        grounding_verifiable=sum(item.grounding is GroundingStatus.VERIFIABLE for item in claims),
        grounding_absent=sum(item.grounding is GroundingStatus.ABSENT for item in claims),
        critical_gap_recall=detected / expected_gaps if expected_gaps else 1,
        nbq=nbq,
        safety_violation_rate=violations / len(pairs) if pairs else 0,
        safety_violations=violations,
        context_repetition_rate=repeated / known if known else 0,
        repeated_questions=repeated,
        model_calls=sum(item.model_calls for item in instrumentation),
        vision_calls=sum(item.vision_calls for item in instrumentation),
        tool_calls=sum(item.tool_calls for item in instrumentation),
        retrieval_calls=sum(item.retrieval_calls for item in instrumentation),
        input_tokens=sum(item.input_tokens for item in instrumentation),
        output_tokens=sum(item.output_tokens for item in instrumentation),
        total_tokens=sum(item.total_tokens for item in instrumentation),
        latency_ms=sum(item.latency_ms for item in instrumentation),
        estimated_cost=cost,
        safety_decision_available=len(safety_runs) == len(pairs),
        safety_decision_accuracy=(safety_correct / len(safety_runs) if safety_runs else None),
        question_loop_available=all(run.question_loop_available for _, run in pairs),
    )
