import { ArrowUpRight } from 'lucide-react'
import type { EvidenceRecord } from '../demo/cases/S00154'
import { EvidenceTypeBadge } from './EvidenceTypeBadge'

export function EvidenceSummary({ evidence }: { evidence: EvidenceRecord[] }) {
  return (
    <div className="evidence-list" id="evidence-list">
      {evidence.map((item) => (
        <article className="evidence-record" key={item.id}>
          <div className="evidence-record__top">
            <EvidenceTypeBadge type={item.type} />
            {item.timestamp && <time>{item.timestamp}</time>}
          </div>
          <h4>{item.fact}</h4>
          <p>{item.source}</p>
          <span>{item.provenance}<ArrowUpRight size={11} aria-hidden="true" /></span>
        </article>
      ))}
    </div>
  )
}
