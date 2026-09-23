import { ChevronDown, ChevronUp, Eye } from 'lucide-react'
import { useCaseRuntime } from '../../runtime/CaseRuntime'
import { EvidenceGap } from '../../evidence/EvidenceGap'
import { EvidenceSummary } from '../../evidence/EvidenceSummary'
import { EvidenceTypeBadge } from '../../evidence/EvidenceTypeBadge'
import { SectionFrame } from './SectionFrame'

export function MeaningSection({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) {
  const { presentation: s00154 } = useCaseRuntime()
  return (
    <SectionFrame index="03" label="MEANING" question="What do we actually know?">
      <div className="meaning-label"><span>Known</span><small>Type and source remain separate</small></div>
      <div className="known-summary">
        {s00154.evidence.slice(0, 3).map((item) => <div key={item.id}><EvidenceTypeBadge type={item.type} /><p>{item.fact}</p></div>)}
      </div>
      <div className="meaning-label meaning-label--gaps"><span>Evidence gaps</span><small>{s00154.unknowns.length} open</small></div>
      <EvidenceGap gaps={s00154.unknowns} />
      <button className="text-button" type="button" onClick={onToggle} aria-expanded={expanded} aria-controls="evidence-list">
        <Eye size={14} aria-hidden="true" />{expanded ? 'Hide evidence' : 'View evidence'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {expanded && <EvidenceSummary evidence={[...s00154.evidence]} />}
    </SectionFrame>
  )
}
