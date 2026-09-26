from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.domain.scenarios import InvestigationScenario


class CaseSource(StrEnum):
    OFFICIAL = "OFFICIAL"
    CONTROLLED_VARIANT = "CONTROLLED_VARIANT"
    ADVERSARIAL = "ADVERSARIAL"


class EvaluationSystem(StrEnum):
    BASELINE = "BASELINE"
    RESONIQUE = "RESONIQUE"


class GroundingStatus(StrEnum):
    EXPLICIT = "EXPLICIT"
    VERIFIABLE = "VERIFIABLE"
    ABSENT = "ABSENT"


class QuestionRelevance(StrEnum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    MISMATCH = "MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GoldenLabels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label_sources: set[str] = Field(min_length=1)
    critical_gaps: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    expected_evidence_types: list[str] = Field(default_factory=list)
    expected_safety_level: str
    expected_action_class: str
    already_known_facts: list[str] = Field(default_factory=list)
    expected_tool_class: str | None = None
    attribution_must_not_be_supported: bool = True
    expected_nbq_gap: str | None = None
    question_expected: bool = True


class EvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    source: CaseSource
    scenario: InvestigationScenario
    messages: list[str] = Field(min_length=1)
    business_context: list[str] = Field(default_factory=list)
    golden: GoldenLabels
    multimodal_required: bool = False
    repeat_contact_required: bool = False
    synthetic: bool = False

    @model_validator(mode="after")
    def validate_source_boundary(self) -> "EvaluationCase":
        if self.source is CaseSource.OFFICIAL and self.synthetic:
            raise ValueError("official cases cannot be marked synthetic")
        if self.source is not CaseSource.OFFICIAL and not self.synthetic:
            raise ValueError("controlled and adversarial cases must be marked synthetic")
        return self


class EvaluatedClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    factual: bool = True
    supported: bool
    grounding: GroundingStatus
    source_ids: list[str] = Field(default_factory=list)
    violation: str | None = None


class RunInstrumentation(BaseModel):
    run_id: str
    case_id: str
    system: EvaluationSystem
    provider: str
    model: str
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    vision_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    retrieval_calls: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    estimated_cost: float | None = None
    model_latency_ms: int = Field(default=0, ge=0)
    retrieval_latency_ms: int = Field(default=0, ge=0)
    tool_latency_ms: int = Field(default=0, ge=0)
    vision_latency_ms: int = Field(default=0, ge=0)
    context_items_before: int = Field(default=0, ge=0)
    context_items_after: int = Field(default=0, ge=0)


class EvaluationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    system: EvaluationSystem
    response_text: str
    claims: list[EvaluatedClaim] = Field(default_factory=list)
    detected_gaps: list[str] = Field(default_factory=list)
    next_question_gap: str | None = None
    safety_level: str
    action_class: str
    asked_facts: list[str] = Field(default_factory=list)
    attribution_status: str
    instrumentation: RunInstrumentation
    safety_decision_available: bool
    question_loop_available: bool


class PricingProfile(BaseModel):
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)
    vision_per_call: float | None = Field(default=None, ge=0)


class AggregateMetrics(BaseModel):
    case_count: int
    unsupported_claim_rate: float
    factual_claims: int
    unsupported_claims: int
    grounding_explicit: int
    grounding_verifiable: int
    grounding_absent: int
    critical_gap_recall: float
    nbq: dict[str, int]
    safety_violation_rate: float
    safety_violations: int
    context_repetition_rate: float
    repeated_questions: int
    model_calls: int
    vision_calls: int
    tool_calls: int
    retrieval_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    estimated_cost: float | None
    safety_decision_available: bool
    safety_decision_accuracy: float | None
    question_loop_available: bool


class CaseComparison(BaseModel):
    case_id: str
    source: CaseSource
    scenario: InvestigationScenario
    baseline: EvaluationRun
    resonique: EvaluationRun


class EvaluationReport(BaseModel):
    benchmark_version: str
    generated_at: str
    execution_mode: str
    provider: str
    model: str
    case_count: int
    source_distribution: dict[str, int]
    scenario_distribution: dict[str, int]
    baseline_metrics: AggregateMetrics
    resonique_metrics: AggregateMetrics
    cases: list[CaseComparison]
    failures: list[str] = Field(default_factory=list)
    pricing_status: str
    limitations: list[str]
    headline_metrics: dict[str, float | int | None]
    real_model_subset: list[CaseComparison] = Field(default_factory=list)
    real_baseline_metrics: AggregateMetrics | None = None
    real_resonique_metrics: AggregateMetrics | None = None
