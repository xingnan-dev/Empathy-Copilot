import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { useCaseRuntime } from '../../runtime/CaseRuntime'
import { decisionSupportLabels, evidenceBasisLabel } from '../../presentation/caseTruth'
import { SectionFrame } from './SectionFrame'

export function SignalSection() {
  const { presentation: s00154, caseView } = useCaseRuntime()
  const signals = decisionSupportLabels(caseView)
  return (
    <SectionFrame index="02" label="SIGNAL" question="What needs attention?" tone="attention">
      <div className="attention-heading"><span><AlertTriangle size={15} aria-hidden="true" />High attention</span><em>Safety path · {s00154.safetyPath}</em></div>
      <ul className="signal-list">{signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
      <p className="signal-source">From {evidenceBasisLabel(caseView)} <ArrowUpRight size={11} aria-hidden="true" /></p>
    </SectionFrame>
  )
}
