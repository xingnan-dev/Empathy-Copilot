import { ArrowUpRight } from 'lucide-react'
import type { EvidenceRecord as EvidenceRecordModel } from '../demo/cases/S00154'
import { EvidenceTypeBadge } from '../evidence/EvidenceTypeBadge'

export function EvidenceRecord({ record }: { record: EvidenceRecordModel }) {
  return (
    <article className="expanded-evidence-record">
      <div className="expanded-evidence-record__identity"><EvidenceTypeBadge type={record.type} />{record.timestamp && <time>{record.timestamp}</time>}</div>
      <h3>{record.fact}</h3>
      <dl>
        <div><dt>Source</dt><dd>{record.source}</dd></div>
        <div><dt>Provenance</dt><dd>{record.provenance}<ArrowUpRight size={12} aria-hidden="true" /></dd></div>
      </dl>
    </article>
  )
}
