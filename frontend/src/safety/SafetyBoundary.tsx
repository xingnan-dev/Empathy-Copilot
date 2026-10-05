import { ShieldCheck } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'
import { evidenceBasisLabel } from '../presentation/caseTruth'

export function SafetyBoundary() {
  const { caseView } = useCaseRuntime()
  return (
    <aside className="safety-boundary" aria-label="Safety boundary">
      <ShieldCheck size={16} aria-hidden="true" />
      <p><strong>Safety boundary</strong>Based on {evidenceBasisLabel(caseView)}. Not a medical diagnosis.</p>
    </aside>
  )
}
