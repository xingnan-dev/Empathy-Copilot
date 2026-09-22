import { AlertTriangle, CircleDashed, ShieldCheck } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function InvestigationSummary() {
  return (
    <section className="investigation-summary" aria-label="Investigation summary">
      <div><span><ShieldCheck size={15} />Known</span><strong>{s00154.evidence.length} grounded signals</strong><p>Consumer, order, upload, and service sources</p></div>
      <div><span><CircleDashed size={15} />Unknown</span><strong>{s00154.gaps.length} open evidence gaps</strong><p>Usage and current condition remain incomplete</p></div>
      <div className="investigation-summary__action"><span><AlertTriangle size={15} />Current action</span><strong>Escalate</strong><p>Human approval required</p></div>
    </section>
  )
}
