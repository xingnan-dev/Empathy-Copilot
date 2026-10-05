import { History, PackageCheck } from 'lucide-react'
import { useCaseRuntime } from '../../runtime/CaseRuntime'
import { restoredServiceHistory } from '../../presentation/caseTruth'
import { SectionFrame } from './SectionFrame'

export function PersonSection() {
  const { presentation: s00154, caseView } = useCaseRuntime()
  const history = restoredServiceHistory(caseView)
  return (
    <SectionFrame index="01" label="PERSON" question="Who is this consumer?">
      <div className="person-line"><div><strong>{s00154.consumer}</strong>{history.length > 0 && <span>Returning consumer</span>}</div><span className="case-id">{s00154.caseId}</span></div>
      <div className="context-row">
        <PackageCheck size={16} aria-hidden="true" />
        <div><small>Current order</small><strong>{s00154.product}</strong><span>{s00154.paid} · Purchased</span></div>
      </div>
      {history.length > 0 && <div className="context-row context-row--muted">
        <History size={15} aria-hidden="true" />
        <div><small>Relevant service history</small><strong>{history.length} previous service contact{history.length === 1 ? '' : 's'}</strong></div>
      </div>}
    </SectionFrame>
  )
}
