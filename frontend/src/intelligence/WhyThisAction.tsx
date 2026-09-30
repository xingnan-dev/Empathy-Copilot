import { AlertTriangle, ArrowRight, Check, CircleDashed, ShieldCheck } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function WhyThisAction({ onPrepare }: { onPrepare: () => void }) {
  const { presentation } = useCaseRuntime()
  return (
    <section className="why-this-action" aria-labelledby="why-action-title">
      <header><span><AlertTriangle size={15} />Recommended action</span><h2 id="why-action-title">Why escalate?</h2><strong>Escalate</strong></header>
      <div className="why-this-action__columns">
        <div><h3>Supported by</h3><ul><li><Check size={12} />Consumer reports facial swelling</li><li><Check size={12} />Medical attention reported</li><li><Check size={12} />Medical material received</li><li><Check size={12} />Adverse-reaction service case exists</li></ul></div>
        <div><h3>Unresolved</h3><ul>{presentation.gaps.slice(0, 3).map((gap) => <li key={gap.id}><CircleDashed size={12} />{gap.label}</li>)}</ul></div>
        <div><h3>Boundary</h3><ul><li><ShieldCheck size={12} />Causality is not established</li><li><ShieldCheck size={12} />Not a medical diagnosis</li><li><ShieldCheck size={12} />Human approval required</li></ul></div>
      </div>
      <button className="why-this-action__prepare" type="button" onClick={onPrepare}>Prepare human-reviewed response<ArrowRight size={14} /></button>
    </section>
  )
}
