import { AlertTriangle, CircleDashed, ShieldCheck } from 'lucide-react'
import { evidenceBasisLabel } from '../presentation/caseTruth'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function InvestigationSummary() {
  const { presentation: s00154, caseView } = useCaseRuntime()
  return (
    <section className="investigation-summary" aria-label="Investigation summary">
      <div><span><ShieldCheck size={15} />Known</span><strong>{s00154.evidence.length} grounded signals</strong><p>Based on {evidenceBasisLabel(caseView)}</p></div>
      <div><span><CircleDashed size={15} />Unknown</span><strong>{s00154.gaps.length} open evidence gaps</strong><p>Usage and current condition remain incomplete</p></div>
      <div className="investigation-summary__action"><span><AlertTriangle size={15} />Current action</span><strong>{s00154.currentAction}</strong><p>{caseView.human_checkpoint.state === 'APPROVED' ? 'Human approval recorded' : 'Human approval required'}</p></div>
    </section>
  )
}
