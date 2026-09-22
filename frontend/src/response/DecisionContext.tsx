import { AlertTriangle, EqualNot, ShieldCheck } from 'lucide-react'

export function DecisionContext() {
  return <section className="response-decision" aria-labelledby="response-decision-title"><div className="response-decision__action"><span><AlertTriangle size={14} />Current decision</span><h1 id="response-decision-title">Escalate</h1><p>Reported facial swelling + reported medical attention + existing adverse-reaction service record.</p></div><div className="response-decision__boundary"><span><ShieldCheck size={14} />Attribution</span><h2>Insufficient evidence</h2><p><EqualNot size={13} />Enough evidence to escalate. Not enough to establish causality.</p></div></section>
}
