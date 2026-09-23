import { AlertTriangle, EqualNot, ShieldCheck } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function DecisionContext() {
  const { presentation } = useCaseRuntime()
  return <section className="response-decision" aria-labelledby="response-decision-title"><div className="response-decision__action"><span><AlertTriangle size={14} />Current decision</span><h1 id="response-decision-title">{presentation.currentAction}</h1><p>Reported facial swelling + reported medical attention + existing adverse-reaction service record.</p></div><div className="response-decision__boundary"><span><ShieldCheck size={14} />Attribution</span><h2>{presentation.attributionStatus.replaceAll('_', ' ')}</h2><p><EqualNot size={13} />Enough evidence to escalate. Not enough to establish causality.</p></div></section>
}
