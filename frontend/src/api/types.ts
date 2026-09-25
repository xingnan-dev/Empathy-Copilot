import type { EvidenceType } from '../demo/cases/S00154'

export interface ApiEvidence { id: string; fact: string; type: EvidenceType; source: string; provenance: string; timestamp: string }
export interface ApiGap { id: string; label: string; why: string; resolve: string; status: 'OPEN' | 'RESOLVED' }
export interface ApiActivity { id: string; label: string; status: string; technical: string }
export interface CaseView {
  case_id: string
  consumer: string
  lifecycle: string
  current_action: string
  safety_path: string
  attribution_status: string
  evidence: ApiEvidence[]
  gaps: ApiGap[]
  questions: unknown[]
  tool_activity: ApiActivity[]
  context_passport: Record<string, unknown>
  human_checkpoint: { state: 'REQUIRED' | 'APPROVED' | 'NOT_REQUIRED'; can_approve: boolean }
  response_context: { evidence_used_ids: string[]; next_best_question?: string; question_resolves_gap?: string }
  updated_at: string
  revision: number
  scenario?: 'ADVERSE_REACTION' | 'PRODUCT_DAMAGE' | 'LOGISTICS_EXCEPTION' | 'AFTER_SALES'
  official_data?: boolean
  restored_context?: boolean
  previous_service_history?: Record<string, unknown>[]
  evidence_conflicts?: Record<string, unknown>[]
}

export interface ApiError { code: string; message: string }
export interface ResponseDraft { text: string; kind: 'GENERATED' | 'FALLBACK'; fallback_reason?: string }
