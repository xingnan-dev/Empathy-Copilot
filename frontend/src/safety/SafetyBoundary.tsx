import { ShieldCheck } from 'lucide-react'

export function SafetyBoundary() {
  return (
    <aside className="safety-boundary" aria-label="Safety boundary">
      <ShieldCheck size={16} aria-hidden="true" />
      <p><strong>Safety boundary</strong>Based on consumer report and service records. Not a medical diagnosis.</p>
    </aside>
  )
}
