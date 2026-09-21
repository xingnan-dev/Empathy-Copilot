import type { EvidenceType } from '../demo/cases/S00154'

const labels: Record<EvidenceType, string> = {
  VERIFIED_BUSINESS_FACT: 'Verified business fact',
  CONSUMER_REPORTED: 'Consumer reported',
  AI_OBSERVATION: 'AI observation',
  AI_INFERENCE: 'AI inference',
  UNKNOWN: 'Unknown',
}

export function EvidenceTypeBadge({ type }: { type: EvidenceType }) {
  return <span className={`evidence-type evidence-type--${type.toLowerCase()}`}>{labels[type]}</span>
}
