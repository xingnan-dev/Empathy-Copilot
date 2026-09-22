import { EqualNot, Shield } from 'lucide-react'

export function AttributionBoundary() {
  return (
    <section className="attribution-boundary" aria-labelledby="attribution-title">
      <div className="attribution-boundary__status"><Shield size={20} /><div><span>Attribution status</span><h2 id="attribution-title">Insufficient evidence</h2></div></div>
      <div className="attribution-boundary__copy"><p><strong>Evidence supports service escalation.</strong> It does not establish product causality.</p><div><span><EqualNot size={14} />Purchase ≠ Usage</span><span><EqualNot size={14} />Temporal association ≠ Causality</span></div></div>
    </section>
  )
}
