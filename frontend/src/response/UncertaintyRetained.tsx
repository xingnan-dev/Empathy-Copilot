import { CircleDashed } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function UncertaintyRetained() {
  const { presentation } = useCaseRuntime()
  return <section className="response-support" aria-labelledby="uncertainty-title"><span>Uncertainty retained</span><h2 id="uncertainty-title">The response does not erase what remains unknown.</h2><ul>{presentation.response.retainedUncertainty.map((item) => <li key={item}><CircleDashed size={12} />{item}</li>)}</ul></section>
}
