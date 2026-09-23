import { ArrowUpRight } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'
import { EvidenceTypeBadge } from '../evidence/EvidenceTypeBadge'

export function ResponseEvidence({ onReview }: { onReview: () => void }) {
  const { presentation: s00154 } = useCaseRuntime()
  const evidenceIds = new Set<string>(s00154.response.evidenceUsedIds)
  const evidence = s00154.evidence.filter((record) => evidenceIds.has(record.id))
  return <section className="response-support response-support--evidence" aria-labelledby="response-evidence-title"><header><span>Evidence used</span><button type="button" onClick={onReview}>Review full evidence<ArrowUpRight size={12} /></button></header><h2 id="response-evidence-title">Grounded in four records</h2><ul>{evidence.map((record) => <li key={record.id}><EvidenceTypeBadge type={record.type} /><strong>{record.fact}</strong><small>{record.source} · {record.provenance}</small></li>)}</ul></section>
}
