import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { s00154 } from '../../demo/cases/S00154'
import { SectionFrame } from './SectionFrame'

export function SignalSection() {
  return (
    <SectionFrame index="02" label="SIGNAL" question="What needs attention?" tone="attention">
      <div className="attention-heading"><span><AlertTriangle size={15} aria-hidden="true" />High attention</span><em>Safety path · Escalation</em></div>
      <ul className="signal-list">{s00154.signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
      <p className="signal-source">From consumer report and service evidence <ArrowUpRight size={11} aria-hidden="true" /></p>
    </SectionFrame>
  )
}
