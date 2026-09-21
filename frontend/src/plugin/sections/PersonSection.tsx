import { History, PackageCheck } from 'lucide-react'
import { s00154 } from '../../demo/cases/S00154'
import { SectionFrame } from './SectionFrame'

export function PersonSection() {
  return (
    <SectionFrame index="01" label="PERSON" question="Who is this consumer?">
      <div className="person-line"><div><strong>{s00154.consumer}</strong><span>Returning consumer</span></div><span className="case-id">{s00154.caseId}</span></div>
      <div className="context-row">
        <PackageCheck size={16} aria-hidden="true" />
        <div><small>Current order</small><strong>{s00154.product}</strong><span>{s00154.paid} · Purchased</span></div>
      </div>
      <div className="context-row context-row--muted">
        <History size={15} aria-hidden="true" />
        <div><small>Relevant service history</small><strong>Adverse-reaction case on record</strong></div>
      </div>
    </SectionFrame>
  )
}
