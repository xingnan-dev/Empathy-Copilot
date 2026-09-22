import { Check, Circle, Pause } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function AgentActivity() {
  return (
    <div className="intelligence-view activity-view">
      <div className="view-intro"><span>Investigation activity</span><h2>How Resonique reached this action</h2><p>Business-readable progress with technical state kept secondary.</p></div>
      <div className="agent-activity-list">
        {s00154.activity.map((step, index) => <article key={step.id} className={step.status === 'CURRENT' ? 'current' : ''}><span className="activity-index">{String(index + 1).padStart(2, '0')}</span><span className="activity-state">{step.status === 'CURRENT' ? <Pause size={13} /> : <Check size={13} />}</span><div><h3>{step.label}</h3><p>{step.technical}</p></div><em>{step.status === 'CURRENT' ? <><Circle size={8} />Current</> : 'Complete'}</em></article>)}
      </div>
    </div>
  )
}
