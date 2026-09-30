"""Read-only service strategy projection over authoritative investigation state."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .agent import InvestigationState
from .safety import SafetyAssessment, SafetyGate


class SignalSource(StrEnum):
    LLM_AUXILIARY = "LLM_AUXILIARY"
    DETERMINISTIC_LANGUAGE_CUE = "DETERMINISTIC_LANGUAGE_CUE"
    NONE = "NONE"


class HumanAttention(StrEnum):
    NORMAL_HANDLING = "NORMAL_HANDLING"
    PRIORITY_REVIEW = "PRIORITY_REVIEW"
    SAFETY_ESCALATION = "SAFETY_ESCALATION"


class ConsumerSignal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    source: SignalSource
    semantic_type: str


class ServiceStrategy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_signal: ConsumerSignal
    communication: list[str]
    investigation: list[str]
    human_attention: HumanAttention
    critical_gap: str | None = None
    next_question: str | None = None


class ServiceStrategyPolicy:
    """Translate existing signals into guidance without changing case truth or routing."""

    _URGENT_EMOTIONS = frozenset({"ANGRY", "DISTRESSED", "FRUSTRATED"})
    _URGENT_CUES = ("急", "赶紧", "尽快", "快点", "怎么回事", "啥情况", "搞什么", "搞啥")

    def project(
        self,
        state: InvestigationState,
        *,
        safety: SafetyAssessment,
        critical_gap: str | None,
        next_question: str | None,
        emotion: str | None = None,
    ) -> ServiceStrategy:
        signal = self._consumer_signal(state, emotion)
        communication = self._communication(signal, safety)
        investigation: list[str] = []
        if any(item.key == "previous_service_contact" for item in state.evidence):
            investigation.append(
                "Use restored service context and avoid repeating known questions."
            )
        if critical_gap and next_question:
            investigation.extend(
                [
                    f"Ask one highest-value unresolved question: {next_question}",
                    f"Explain that resolving {critical_gap} matters while preserving uncertainty.",
                ]
            )
        else:
            investigation.append("Do not ask for facts already grounded in the case.")

        attention = {
            SafetyGate.SAFETY: HumanAttention.SAFETY_ESCALATION,
            SafetyGate.INVESTIGATION: HumanAttention.PRIORITY_REVIEW,
            SafetyGate.NORMAL: HumanAttention.NORMAL_HANDLING,
        }[safety.gate]
        return ServiceStrategy(
            consumer_signal=signal,
            communication=communication,
            investigation=investigation,
            human_attention=attention,
            critical_gap=critical_gap,
            next_question=next_question,
        )

    def _consumer_signal(self, state: InvestigationState, emotion: str | None) -> ConsumerSignal:
        normalized = (emotion or "").upper()
        if normalized in self._URGENT_EMOTIONS:
            return ConsumerSignal(
                label="Language suggests urgency or distress.",
                source=SignalSource.LLM_AUXILIARY,
                semantic_type="AI_INFERENCE",
            )
        if normalized == "CONCERNED":
            return ConsumerSignal(
                label="Language suggests concern.",
                source=SignalSource.LLM_AUXILIARY,
                semantic_type="AI_INFERENCE",
            )
        if normalized == "CALM":
            return ConsumerSignal(
                label="Language appears calm.",
                source=SignalSource.LLM_AUXILIARY,
                semantic_type="AI_INFERENCE",
            )
        consumer_text = " ".join(
            str(item.value)
            for item in state.evidence
            if item.key == "consumer_message" and isinstance(item.value, str)
        )
        if any(cue in consumer_text for cue in self._URGENT_CUES):
            return ConsumerSignal(
                label="Language suggests urgency or distress.",
                source=SignalSource.DETERMINISTIC_LANGUAGE_CUE,
                semantic_type="AI_INFERENCE",
            )
        return ConsumerSignal(
            label="No explicit emotion signal available.",
            source=SignalSource.NONE,
            semantic_type="AUXILIARY_SIGNAL",
        )

    @staticmethod
    def _communication(signal: ConsumerSignal, safety: SafetyAssessment) -> list[str]:
        guidance = []
        if safety.gate is SafetyGate.SAFETY:
            guidance.append(
                "Acknowledge the reported impact and explain the human-reviewed safety path."
            )
        elif "urgency" in signal.label:
            guidance.append("Acknowledge frustration and urgency without admitting causality.")
        else:
            guidance.append("Use calm, concise, resolution-focused communication.")
        guidance.append("Preserve evidence boundaries and do not imply causality.")
        return guidance
