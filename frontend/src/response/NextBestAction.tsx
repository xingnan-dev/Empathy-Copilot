import { ArrowUpRight, Check } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function NextBestAction() {
  const { caseView } = useCaseRuntime()
  return <section className="next-best-action" aria-labelledby="next-action-title"><header><span>Next best action</span><small>{caseView.human_checkpoint.state === 'APPROVED' ? 'Human approval recorded' : 'Human approval required'}</small></header><div><ArrowUpRight size={23} /><h2 id="next-action-title">{s00154.response.nextBestAction}</h2></div><ul>{s00154.response.secondaryActions.map((item) => <li key={item}><Check size={12} />{item}</li>)}</ul></section>
}
