import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { useCaseRuntime } from '../../runtime/CaseRuntime'
import { SectionFrame } from './SectionFrame'

export function SignalSection() {
  const { presentation: s00154 } = useCaseRuntime()
  return (
    <SectionFrame index="02" label="SIGNAL" question="What needs attention?" tone="attention">
      <div className="attention-heading"><span><AlertTriangle size={15} aria-hidden="true" />High attention</span><em>Safety path · {s00154.safetyPath}</em></div>
      <ul className="signal-list">{s00154.signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
      <p className="signal-source">From consumer report and service evidence <ArrowUpRight size={11} aria-hidden="true" /></p>
    </SectionFrame>
  )
}
