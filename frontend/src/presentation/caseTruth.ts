import type { ApiEvidence, CaseView } from '../api/types'

type CaseTruthView = Pick<
  CaseView,
  'evidence' | 'previous_service_history' | 'restored_context'
>

export function restoredServiceHistory(view: CaseTruthView): Record<string, unknown>[] {
  if (!view.restored_context) return []
  return view.previous_service_history ?? []
}

export function currentServiceRecordEvidence(view: CaseTruthView): ApiEvidence[] {
  return view.evidence.filter((item) =>
    item.type === 'VERIFIED_BUSINESS_FACT' &&
    (item.source === 'Service record' || item.source.startsWith('Official service record '))
  )
}

export function decisionSupportLabels(view: CaseTruthView): string[] {
  const labels: string[] = []
  const consumerReports = view.evidence.filter((item) => item.type === 'CONSUMER_REPORTED')
  if (consumerReports.some((item) => item.fact === 'SEVERE')) {
    labels.push('Severe impact reported by consumer')
  }
  if (consumerReports.some((item) => item.fact === 'reported medical attention')) {
    labels.push('Medical attention reported by consumer')
  }
  if (view.evidence.some((item) => item.fact === 'image reference')) {
    labels.push('Consumer-provided image reference recorded')
  }
  if (currentServiceRecordEvidence(view).length > 0) {
    labels.push('Current service record available')
  }
  return labels
}

export function evidenceBasisLabel(view: CaseTruthView): string {
  const parts = ['consumer reports']
  if (view.evidence.some((item) => item.fact === 'image reference')) {
    parts.push('message metadata')
  }
  if (currentServiceRecordEvidence(view).length > 0) {
    parts.push('service records')
  }
  return parts.join(' and ')
}
