import { Minus } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function AvoidedClaims() {
  return <section className="response-support response-support--avoided" aria-labelledby="avoided-title"><span>Intentionally not claimed</span><h2 id="avoided-title">Evidence discipline preserved</h2><ul>{s00154.response.avoidedClaims.map((item) => <li key={item}><Minus size={12} />{item}</li>)}</ul></section>
}
