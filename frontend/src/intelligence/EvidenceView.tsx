import { useCaseRuntime } from '../runtime/CaseRuntime'
import { AttributionBoundary } from './AttributionBoundary'
import { EvidenceGapList } from './EvidenceGapList'
import { EvidenceRecord } from './EvidenceRecord'

export function EvidenceView() {
  const { presentation: s00154 } = useCaseRuntime()
  return (
    <div className="intelligence-view evidence-view">
      <section aria-labelledby="evidence-map-title">
        <div className="intelligence-section-heading"><div><span>Evidence composition</span><h2 id="evidence-map-title">What we know, and where it came from</h2></div><p>Sources remain distinct from interpretation.</p></div>
        <div className="evidence-composition">
          <div className="evidence-composition__source"><span>Evidence sources</span><strong>Conversation · Order · Upload · Service record</strong></div>
          <div className="evidence-composition__line" aria-hidden="true"><i /><i /><i /></div>
          <div className="evidence-composition__understanding"><span>Current understanding</span><strong>Service escalation is warranted</strong><p>Based on reported impact and supporting service evidence—not a causal conclusion.</p></div>
        </div>
        <div className="expanded-evidence-grid">{s00154.evidence.map((record) => <EvidenceRecord key={record.id} record={record} />)}</div>
      </section>
      <EvidenceGapList />
      <AttributionBoundary />
    </div>
  )
}
