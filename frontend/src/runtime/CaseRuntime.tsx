import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { approveCase, generateResponseDraft, getCase, ingestConsumerMessage } from '../api/cases'
import { CaseApiError } from '../api/client'
import type { CaseView, ResponseDraft } from '../api/types'
import { s00154, type CasePresentation } from '../demo/cases/S00154'

interface RuntimeValue { caseView: CaseView; presentation: CasePresentation; approving: boolean; processingMessage: boolean; approve: () => Promise<void>; requestDraft: () => Promise<ResponseDraft>; ingestMessage: (message: string) => Promise<void> }
const RuntimeContext = createContext<RuntimeValue | null>(null)

function present(view: CaseView): CasePresentation {
  const evidence = view.evidence.map((item) => ({ ...item, timestamp: new Date(item.timestamp).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }))
  const openGaps = view.gaps.filter((gap) => gap.status === 'OPEN')
  const questionGap = openGaps.find((gap) => gap.id === view.response_context.question_resolves_gap)
  const nextQuestion = view.response_context.next_best_question ?? 'No additional question is required.'
  const fallbackDraft = `看到您反馈使用后出现面部肿胀，并已就医，我们会优先按不良反应服务流程继续处理。${view.response_context.next_best_question ?? '我们会基于现有证据继续核对。'}`
  const timeline = view.evidence.map((item) => {
    const date = new Date(item.timestamp)
    const type = item.type === 'CONSUMER_REPORTED' ? 'CONSUMER_MESSAGE' : item.type === 'AI_OBSERVATION' ? 'MATERIAL_UPLOAD' : item.provenance.startsWith('Order') ? 'ORDER' : 'SERVICE_RECORD'
    return { id: `timeline-${item.id}`, date: date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }), time: date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }), type, title: item.fact, detail: item.type === 'VERIFIED_BUSINESS_FACT' ? 'Verified source record; no usage or causality inference.' : 'Source semantics retained from the backend Evidence.', source: item.provenance } as CasePresentation['timeline'][number]
  }).sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`))
  return {
    ...s00154,
    caseId: view.case_id,
    consumer: view.consumer,
    lifecycle: view.lifecycle,
    currentAction: view.current_action,
    safetyPath: view.safety_path,
    attributionStatus: view.attribution_status,
    evidence,
    timeline,
    gaps: openGaps,
    unknowns: openGaps.map((gap) => gap.label),
    activity: view.tool_activity.map((item) => ({ ...item, status: item.status === 'CURRENT' ? 'CURRENT' : 'COMPLETED' })),
    response: { ...s00154.response, nextBestQuestion: nextQuestion, questionResolvesGap: view.response_context.question_resolves_gap ?? 'NONE', questionWhy: questionGap?.why ?? 'No unresolved critical gap remains.', drafts: [fallbackDraft], evidenceUsedIds: view.response_context.evidence_used_ids, retainedUncertainty: openGaps.map((gap) => `${gap.label} remains unknown`) },
  }
}

export function CaseRuntime({ children }: { children: ReactNode }) {
  const [caseView, setCaseView] = useState<CaseView | null>(null)
  const [error, setError] = useState<CaseApiError | null>(null)
  const [fixtureMode, setFixtureMode] = useState(false)
  const [approving, setApproving] = useState(false)
  const [processingMessage, setProcessingMessage] = useState(false)
  const load = async () => { setError(null); try { setCaseView(await getCase('S00154')) } catch (reason) { setError(reason instanceof CaseApiError ? reason : new CaseApiError('BACKEND_UNAVAILABLE', 'Unable to load live case state.', 0)) } }
  useEffect(() => { void load() }, [])
  const fixtureView = useMemo<CaseView>(() => ({ case_id: s00154.caseId, consumer: s00154.consumer, lifecycle: 'WAITING_FOR_HUMAN', current_action: 'ESCALATE', safety_path: 'ESCALATION', attribution_status: 'INSUFFICIENT_EVIDENCE', evidence: s00154.evidence.map((item) => ({ ...item, timestamp: new Date().toISOString() })), gaps: s00154.gaps.map((item) => ({ ...item, status: 'OPEN' })), questions: [], tool_activity: [...s00154.activity], context_passport: {}, human_checkpoint: { state: 'REQUIRED', can_approve: false }, response_context: { evidence_used_ids: [...s00154.response.evidenceUsedIds], next_best_question: s00154.response.nextBestQuestion, question_resolves_gap: s00154.response.questionResolvesGap }, service_strategy: { consumer_signal: { label: 'Language suggests urgency or distress.', source: 'DETERMINISTIC_LANGUAGE_CUE', semantic_type: 'AI_INFERENCE' }, communication: ['Acknowledge the reported impact and explain the human-reviewed safety path.', 'Preserve evidence boundaries and do not imply causality.'], investigation: ['Ask one highest-value unresolved question.', 'Preserve uncertainty.'], human_attention: 'SAFETY_ESCALATION', critical_gap: s00154.response.questionResolvesGap, next_question: s00154.response.nextBestQuestion }, updated_at: new Date().toISOString(), revision: 0 }), [])
  const active = caseView ?? fixtureView
  const requestDraft = useCallback(async () => fixtureMode ? { text: s00154.response.drafts[0], kind: 'FALLBACK' as const, fallback_reason: 'FIXTURE_MODE' } : generateResponseDraft(active.case_id, active.revision), [active.case_id, active.revision, fixtureMode])
  if (!caseView && !fixtureMode && !error) return <div className="runtime-state"><span>Live agent state</span><h2>Loading case intelligence…</h2><p>Restoring evidence and checkpoint context.</p></div>
  if (!caseView && !fixtureMode && error) return <div className="runtime-state runtime-state--error" role="alert"><span>{error.code}</span><h2>Unable to load live case state.</h2><p>{error.message}</p><div><button type="button" onClick={() => void load()}>Retry</button><button type="button" onClick={() => setFixtureMode(true)}>Enter Demo Fixture Mode</button></div></div>
  const approve = async () => { if (fixtureMode) return; setApproving(true); try { setCaseView(await approveCase(active.case_id, active.revision)) } catch (reason) { setError(reason instanceof CaseApiError ? reason : null); throw reason } finally { setApproving(false) } }
  const ingestMessage = async (message: string) => { if (fixtureMode) throw new CaseApiError('MODEL_UNAVAILABLE', 'Model unavailable in fixture mode.', 503); setProcessingMessage(true); try { setCaseView(await ingestConsumerMessage(active.case_id, message, `web-${crypto.randomUUID()}`, active.revision)) } finally { setProcessingMessage(false) } }
  return <RuntimeContext.Provider value={{ caseView: active, presentation: present(active), approving, processingMessage, approve, requestDraft, ingestMessage }}><div className={`runtime-shell ${fixtureMode ? 'runtime-shell--fixture' : ''}`}>{fixtureMode && <div className="fixture-banner">Demo Fixture Mode · Backend state unavailable</div>}{children}</div></RuntimeContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCaseRuntime() { const value = useContext(RuntimeContext); if (!value) throw new Error('CaseRuntime is required'); return value }
