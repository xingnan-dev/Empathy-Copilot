import { CircleDashed } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function UncertaintyRetained() {
  return <section className="response-support" aria-labelledby="uncertainty-title"><span>Uncertainty retained</span><h2 id="uncertainty-title">The response does not erase what remains unknown.</h2><ul>{s00154.response.retainedUncertainty.map((item) => <li key={item}><CircleDashed size={12} />{item}</li>)}</ul></section>
}
