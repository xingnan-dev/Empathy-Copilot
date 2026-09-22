import { AlertTriangle, Check, CircleDashed, ShieldCheck } from 'lucide-react'

export function WhyThisAction() {
  return (
    <section className="why-this-action" aria-labelledby="why-action-title">
      <header><span><AlertTriangle size={15} />Recommended action</span><h2 id="why-action-title">Why escalate?</h2><strong>Escalate</strong></header>
      <div className="why-this-action__columns">
        <div><h3>Supported by</h3><ul><li><Check size={12} />Consumer reports facial swelling</li><li><Check size={12} />Medical attention reported</li><li><Check size={12} />Medical material received</li><li><Check size={12} />Adverse-reaction service case exists</li></ul></div>
        <div><h3>Unresolved</h3><ul><li><CircleDashed size={12} />Exact product usage unverified</li><li><CircleDashed size={12} />Actual first-use time unknown</li><li><CircleDashed size={12} />Recent routine changes unknown</li></ul></div>
        <div><h3>Boundary</h3><ul><li><ShieldCheck size={12} />Causality is not established</li><li><ShieldCheck size={12} />Not a medical diagnosis</li><li><ShieldCheck size={12} />Human approval required</li></ul></div>
      </div>
    </section>
  )
}
