"""Thin application boundary between HTTP events and the authoritative agent state."""

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.agent.guardrails import assess_attribution
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import AgentAction, AgentStatus, InvestigationState
from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.gaps import GapType, evaluate_p0_gaps, evaluate_scenario_gaps
from backend.app.domain.regimen import build_regimen_changes
from backend.app.domain.safety import SafetyGateService
from backend.app.knowledge import IngredientContextChecker, KnowledgeItem, LocalKnowledgeRetriever
from backend.app.llm.provider import ModelProviderError
from backend.app.llm.schemas import GeneratedDraft
from backend.app.llm.service import ModelService
from backend.app.official_dataset.cases import OfficialCaseFactory
from backend.app.official_dataset.models import OfficialDataset
from backend.app.services.checkpoints import CheckpointStore, StateConflictError
from backend.app.services.context_passport import ContextPassportService
from backend.app.services.transitions import InvalidStateTransitionError, StateTransitionService
from backend.app.vision import VisionService
from backend.app.vision.schemas import ImageCategory, VisionSourceIdentity

from ..fixtures import s00154_waiting_for_human
from ..schemas.cases import (
    ActivityView,
    CaseView,
    EvidenceView,
    GapView,
    HumanCheckpointView,
    ResponseContextView,
    ResumeRequest,
)


class CaseApplicationService:
    def __init__(
        self,
        workflow: InvestigationWorkflow,
        checkpoints: CheckpointStore,
        model_service: ModelService | None = None,
        vision_service: VisionService | None = None,
    ) -> None:
        self.workflow = workflow
        self.checkpoints = checkpoints
        self.transitions = StateTransitionService()
        self.passports = ContextPassportService()
        self.model_service = model_service
        self.vision_service = vision_service
        self.knowledge = LocalKnowledgeRetriever()
        self.safety = SafetyGateService()
        self.ingredients = IngredientContextChecker()

    def ensure_integration_fixture(self) -> None:
        if not self.checkpoints.exists("S00154"):
            self.checkpoints.save(s00154_waiting_for_human())

    def register_official_cases(
        self, dataset: OfficialDataset, case_ids: list[str] | None = None
    ) -> None:
        factory = OfficialCaseFactory()
        selected = case_ids or [item.session_id for item in dataset.sessions if item.scenario]
        for case_id in selected:
            if not self.checkpoints.exists(case_id):
                self.checkpoints.save(factory.build(dataset, case_id))

    def get_case(self, case_id: str) -> CaseView:
        return self._project(self.checkpoints.load(case_id))

    def approve(self, case_id: str, expected_revision: int) -> CaseView:
        current = self.checkpoints.load(case_id)
        if current.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        if current.status is not AgentStatus.WAITING_FOR_HUMAN:
            raise InvalidStateTransitionError("case is not waiting for human approval")
        approved = self.transitions.transition(
            current,
            to_status=AgentStatus.ESCALATED,
            action=AgentAction.ESCALATE,
            reason="Human approved the recommended escalation.",
        )
        self.checkpoints.save(approved, expected_revision=expected_revision)
        return self._project(approved)

    def resume(self, case_id: str, request: ResumeRequest) -> CaseView:
        current = self.checkpoints.load(case_id)
        if current.state_revision != request.expected_revision:
            raise StateConflictError(
                f"case {case_id} no longer has revision {request.expected_revision}"
            )
        evidence = Evidence.model_validate(
            {
                "id": f"api-{uuid4()}",
                "case_id": case_id,
                "key": request.gap.casefold(),
                "value": request.value,
                "evidence_type": EvidenceType.CONSUMER_REPORTED,
                "source": {
                    "source_type": SourceType.CONSUMER_MESSAGE,
                    "source_id": request.source_id,
                    "source_label": f"Consumer message · {request.source_id}",
                },
                "observed_at": datetime.now(UTC),
                "created_at": datetime.now(UTC),
                "extraction_confidence": 1.0,
            }
        )
        return self._project(self.workflow.resume_with_evidence(current, [evidence]))

    def ingest_message(
        self, case_id: str, *, message: str, message_id: str, expected_revision: int
    ) -> CaseView:
        if self.model_service is None:
            raise ModelProviderError("UNAVAILABLE", "model provider is not configured")
        current = self.checkpoints.load(case_id)
        if current.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        if current.status in {AgentStatus.ESCALATED, AgentStatus.CONCLUDED, AgentStatus.TERMINATED}:
            raise InvalidStateTransitionError("terminal case cannot ingest a consumer message")
        now = datetime.now(UTC)
        evidence, intent, emotion = self.model_service.understand(
            case_id=case_id,
            message_id=message_id,
            message=message,
            observed_at=now,
            context={
                "open_gaps": [gap.id for gap in self._presentation_gaps(current)],
                "reference_date": now.date().isoformat(),
            },
        )
        if not evidence:
            return self._project(current)
        if current.status is AgentStatus.WAITING_FOR_USER:
            return self._project(self.workflow.resume_with_evidence(current, evidence))
        all_evidence = [*current.evidence, *evidence]
        gaps = (
            evaluate_scenario_gaps(case_id, current.scenario, all_evidence)
            if current.scenario
            else evaluate_p0_gaps(case_id, all_evidence)
        )
        resumed = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=None,
            reason="Validated model candidates from consumer message.",
            updates={
                "evidence": all_evidence,
                "evidence_gaps": gaps,
                "next_question": None,
            },
        )
        result = self.workflow.run(resumed, expected_revision=current.state_revision)
        projected = self._project(result)
        projected.context_passport["model_signals"] = {"intent": intent, "emotion": emotion}
        return projected

    def generate_response_draft(self, case_id: str, expected_revision: int) -> GeneratedDraft:
        if self.model_service is None:
            raise ModelProviderError("UNAVAILABLE", "model provider is not configured")
        state = self.checkpoints.load(case_id)
        if state.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        projected = self._project(state)
        fallback = (
            "看到您反馈使用后出现面部肿胀，并已就医，"
            "我们会优先按不良反应服务流程继续处理。"
            "为了准确核对本次情况，想再确认一下，您实际使用的是礼盒中的哪一款产品？"
        )
        return self.model_service.response(
            {
                "current_action": projected.current_action,
                "safety_path": projected.safety_path,
                "attribution": projected.attribution_status,
                "evidence": [
                    item.fact
                    for item in projected.evidence
                    if item.id in projected.response_context.evidence_used_ids
                ],
                "open_uncertainty": [gap.label for gap in projected.gaps],
                "human_checkpoint": projected.human_checkpoint.state,
                "next_question": projected.response_context.next_best_question,
            },
            fallback,
        )

    def analyze_image(
        self,
        case_id: str,
        *,
        image_uri: str,
        image_id: str,
        message_id: str,
        expected_revision: int,
    ) -> CaseView:
        if self.vision_service is None:
            raise ModelProviderError("UNAVAILABLE", "vision provider is not configured")
        current = self.checkpoints.load(case_id)
        if current.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        image_reference = next(
            (
                item
                for item in current.evidence
                if item.key == "image_reference"
                and item.source.source_id == message_id
                and isinstance(item.value, dict)
                and item.value.get("asset_available") is True
                and str(item.value.get("path", "")).endswith(image_id)
            ),
            None,
        )
        if image_reference is None:
            raise ValueError("image source is not grounded in the current case")
        observation = self.vision_service.analyze(
            case_id=case_id,
            image_uri=image_uri,
            image_id=image_id,
            message_id=message_id,
            case_context=current.current_issue,
            observed_at=datetime.now(UTC),
        )
        return self._record_visual_observation(current, observation, expected_revision)

    def analyze_demo_fixture(
        self,
        case_id: str,
        *,
        image_uri: str,
        asset_id: str,
        message_id: str,
        expected_revision: int,
    ) -> CaseView:
        """Analyze an independent product-damage fixture, never an official case image."""

        if self.vision_service is None:
            raise ModelProviderError("UNAVAILABLE", "vision provider is not configured")
        current = self.checkpoints.load(case_id)
        if current.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        if any(item.metadata.get("official_data") is True for item in current.evidence):
            raise ValueError("demo fixtures cannot be attached to official cases")
        identity = VisionSourceIdentity(
            asset_id=asset_id,
            source="DEMO_FIXTURE",
            fixture=True,
            scenario=ImageCategory.PRODUCT_DAMAGE,
        )
        observation = self.vision_service.analyze(
            case_id=case_id,
            image_uri=image_uri,
            image_id=asset_id,
            message_id=message_id,
            case_context=current.current_issue,
            observed_at=datetime.now(UTC),
            source_identity=identity,
        )
        return self._record_visual_observation(current, observation, expected_revision)

    def _record_visual_observation(
        self,
        current: InvestigationState,
        observation: Evidence | None,
        expected_revision: int,
    ) -> CaseView:
        if observation is None:
            return self._project(current)
        evidence = [*current.evidence, observation]
        gaps = (
            evaluate_scenario_gaps(current.case_id, current.scenario, evidence)
            if current.scenario
            else evaluate_p0_gaps(current.case_id, evidence)
        )
        investigating = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=None,
            reason="Validated a bounded visual observation.",
            updates={"evidence": evidence, "evidence_gaps": gaps},
        )
        reviewed = self.transitions.transition(
            investigating,
            to_status=AgentStatus.WAITING_FOR_HUMAN,
            action=AgentAction.WAIT_FOR_HUMAN,
            reason="Visual observations require human-reviewed service action.",
        )
        self.checkpoints.save(reviewed, expected_revision=expected_revision)
        return self._project(reviewed)

    def _project(self, state: InvestigationState) -> CaseView:
        primary_product = next(
            (
                item.value.get("product_id")
                for item in state.evidence
                if item.key == "first_purchase" and isinstance(item.value, dict)
            ),
            "unknown_product",
        )
        attribution = assess_attribution(
            state, str(primary_product), build_regimen_changes(state.case_id, state.evidence)
        ).decision.value
        evidence = [
            self._project_evidence(item)
            for item in state.evidence
            if item.key != "human_review_required"
        ]
        approved = state.status is AgentStatus.ESCALATED
        passport = self.passports.build(state)
        projected_gaps = self._presentation_gaps(state)
        question_gap, next_question = self._next_question(projected_gaps, state.next_question)
        safety = self.safety.assess(state)
        knowledge_query = {
            "ADVERSE_REACTION": "adverse reaction safety swelling medical attention",
            "PRODUCT_DAMAGE": "damaged product policy visible damage eligibility",
            "LOGISTICS_EXCEPTION": "logistics investigation",
            "AFTER_SALES": "service policy eligibility",
        }.get(state.scenario.value if state.scenario else "", state.current_issue)
        knowledge = self.knowledge.retrieve(knowledge_query)
        return CaseView(
            case_id=state.case_id,
            consumer=state.consumer_id,
            lifecycle=state.status.value,
            current_action="ESCALATE"
            if state.status in {AgentStatus.WAITING_FOR_HUMAN, AgentStatus.ESCALATED}
            else (state.current_action.value if state.current_action else "NONE"),
            safety_path="ESCALATION"
            if state.status in {AgentStatus.WAITING_FOR_HUMAN, AgentStatus.ESCALATED}
            else "STANDARD",
            attribution_status=attribution,
            evidence=evidence,
            gaps=projected_gaps,
            questions=[item.model_dump(mode="json") for item in state.asked_questions],
            tool_activity=[
                ActivityView(
                    id=f"transition-{index}",
                    label=item.reason,
                    status="CURRENT"
                    if index == len(state.transition_events) - 1 and not approved
                    else "COMPLETED",
                    technical=item.action.value if item.action else item.to_status.value,
                )
                for index, item in enumerate(state.transition_events)
            ],
            context_passport=passport.model_dump(mode="json"),
            human_checkpoint=HumanCheckpointView(
                state="APPROVED"
                if approved
                else (
                    "REQUIRED" if state.status is AgentStatus.WAITING_FOR_HUMAN else "NOT_REQUIRED"
                ),
                can_approve=state.status is AgentStatus.WAITING_FOR_HUMAN,
            ),
            response_context=ResponseContextView(
                evidence_used_ids=[
                    item.id for item in state.evidence if item.id != "order-purchase"
                ],
                next_best_question=next_question,
                question_resolves_gap=question_gap,
            ),
            updated_at=state.updated_at,
            revision=state.state_revision,
            scenario=state.scenario.value if state.scenario else None,
            official_data=any(
                item.metadata.get("official_data") is True for item in state.evidence
            ),
            restored_context=any(item.key == "previous_service_contact" for item in state.evidence),
            previous_service_history=[
                item.value
                for item in state.evidence
                if item.key == "previous_service_contact" and isinstance(item.value, dict)
            ],
            evidence_conflicts=self._evidence_conflicts(state),
            visual_observations=[
                {
                    **item.value,
                    "source": item.metadata.get("source"),
                    "fixture": item.metadata.get("fixture", False),
                    "asset_id": item.metadata.get("asset_id", item.source.source_id),
                    "scenario": item.metadata.get("scenario"),
                    "evidence_type": item.evidence_type.value,
                }
                for item in state.evidence
                if item.evidence_type is EvidenceType.AI_OBSERVATION
                and isinstance(item.value, dict)
            ],
            knowledge_context=[item.model_dump(mode="json") for item in knowledge],
            safety_gate=safety.gate.value,
            ingredient_context=self._ingredient_context(state),
            why_sources=self._why_sources(state, knowledge),
        )

    def _ingredient_context(self, state: InvestigationState) -> list[dict[str, object]]:
        sensitivities = [
            item
            for item in state.evidence
            if item.key == "known_sensitivity" and isinstance(item.value, str)
        ]
        products = [
            item
            for item in state.evidence
            if item.key == "product_ingredients" and isinstance(item.value, dict)
        ]
        matches = []
        for sensitivity in sensitivities:
            for product in products:
                product_value = product.value
                if not isinstance(product_value, dict):
                    continue
                ingredients = product_value.get("ingredients")
                product_id = product_value.get("product_id")
                if isinstance(ingredients, list) and isinstance(product_id, str):
                    matches.extend(
                        self.ingredients.match(
                            product_id=product_id,
                            ingredients=[str(item) for item in ingredients],
                            sensitivity=str(sensitivity.value),
                            ingredient_source_id=product.source.source_id,
                            sensitivity_source_id=sensitivity.source.source_id,
                            fixture=bool(product.metadata.get("fixture")),
                        )
                    )
        return [item.model_dump(mode="json") for item in matches]

    @staticmethod
    def _why_sources(
        state: InvestigationState, knowledge: list[KnowledgeItem]
    ) -> list[dict[str, object]]:
        sources: list[dict[str, object]] = [
            {
                "kind": item.evidence_type.value,
                "source_id": item.source.source_id,
                "label": item.source.source_label,
            }
            for item in state.evidence
        ]
        sources.extend(
            {
                "kind": "KNOWLEDGE_CONTEXT",
                "source_id": item.document_id,
                "label": item.title,
            }
            for item in knowledge
        )
        return sources

    @staticmethod
    def _project_evidence(item: Evidence) -> EvidenceView:
        fact: object
        if isinstance(item.value, str):
            fact = item.value
        elif isinstance(item.value, dict):
            fact = item.value.get("summary") or (
                f"{item.value.get('product_name')} purchased · {item.value.get('paid')}"
                if item.key == "first_purchase"
                else item.key.replace("_", " ")
            )
        else:
            fact = item.key.replace("_", " ")
        source_type = item.source.source_type.value.replace("_", " ").title()
        return EvidenceView(
            id=item.id,
            fact=str(fact),
            type=item.evidence_type.value,
            source=item.source.source_label,
            provenance=f"{source_type} · {item.source.source_id}",
            timestamp=item.observed_at,
        )

    @staticmethod
    def _presentation_gaps(state: InvestigationState) -> list[GapView]:
        if state.scenario is not None:
            labels = {gap.value: gap.value.replace("_", " ").title() for gap in GapType}
            return [
                GapView(
                    id=item.gap_type.value,
                    label=labels[item.gap_type.value],
                    why="Required by the deterministic scenario gap policy.",
                    resolve="Ground supporting evidence",
                    status=item.status.value,
                )
                for item in state.evidence_gaps
            ]
        first_use_open = not any(item.key == "actual_first_use_time" for item in state.evidence)
        regimen_open = not any(item.key == "recent_regimen_changes" for item in state.evidence)
        specs = [
            (
                "EXACT_PRODUCT_USED",
                "Exact product used",
                "Purchase of a gift set does not prove which item was actually used.",
                "Ask consumer",
                not any(item.key == "exact_product_used" for item in state.evidence),
            ),
            (
                "ACTUAL_FIRST_USE_TIME",
                "Actual first-use time",
                "Purchase date does not prove actual usage date.",
                "Ask consumer",
                first_use_open,
            ),
            (
                "RECENT_REGIMEN_CHANGES",
                "Recent routine changes",
                "Other recent product changes may affect attribution.",
                "Ask consumer",
                regimen_open,
            ),
            (
                "CURRENT_SYMPTOM_PROGRESSION",
                "Current symptom progression",
                "Current symptom direction is absent from available records.",
                "Human follow-up",
                True,
            ),
        ]
        return [
            GapView(
                id=gap_id,
                label=label,
                why=why,
                resolve=resolve,
                status="OPEN" if is_open else "RESOLVED",
            )
            for gap_id, label, why, resolve, is_open in specs
        ]

    @staticmethod
    def _evidence_conflicts(state: InvestigationState) -> list[dict[str, object]]:
        system_delivered = [
            item.id
            for item in state.evidence
            if item.key == "logistics_status" and item.value == "SYSTEM_MARKED_DELIVERED"
        ]
        consumer_not_received = [
            item.id
            for item in state.evidence
            if item.key == "consumer_receipt_status" and item.value == "NOT_RECEIVED"
        ]
        if not system_delivered or not consumer_not_received:
            return []
        return [
            {
                "type": "DELIVERY_STATUS_CONFLICT",
                "verified_evidence_ids": system_delivered,
                "consumer_reported_evidence_ids": consumer_not_received,
                "status": "RETAINED",
            }
        ]

    @staticmethod
    def _next_question(
        gaps: list[GapView], agent_question: str | None
    ) -> tuple[str | None, str | None]:
        open_gap = next((gap.id for gap in gaps if gap.status == "OPEN"), None)
        if open_gap is None:
            return None, None
        if agent_question:
            return open_gap, agent_question
        fallbacks = {
            "EXACT_PRODUCT_USED": (
                "为了继续帮您处理，想确认一下，您实际使用的是礼盒中的哪一款产品？"
            ),
            "ACTUAL_FIRST_USE_TIME": "想再确认一下，您第一次使用这款产品的具体日期是什么时候？",
            "RECENT_REGIMEN_CHANGES": "近期是否还新增或更换过其他护肤产品？",
            "CURRENT_SYMPTOM_PROGRESSION": "目前症状是在缓解、稳定，还是仍在加重？",
        }
        return open_gap, fallbacks.get(open_gap)
