import { Check, Circle } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function ResponseProgress() {
  const { caseView } = useCaseRuntime()
  const steps = [
    { label: 'Understand', state: 'Complete' },
    { label: 'Investigate', state: 'Gaps retained' },
    { label: 'Decide', state: caseView.current_action },
    { label: 'Respond', state: caseView.human_checkpoint.state === 'APPROVED' ? 'Approved' : 'Human review' },
  ]
  return <ol className="response-progress" aria-label="Response workflow progress">{steps.map((step, index) => <li className={index === 3 ? 'current' : ''} key={step.label}>{index < 2 ? <Check size={12} /> : <Circle size={10} />}<div><strong>{step.label}</strong><span>{step.state}</span></div></li>)}</ol>
}
