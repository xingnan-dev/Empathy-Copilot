import { CircleHelp } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function NextBestQuestion() {
  return <section className="next-best-question" aria-labelledby="next-question-title"><header><span><CircleHelp size={14} />Next best question</span><small>Resolves · {s00154.response.questionResolvesGap}</small></header><blockquote id="next-question-title">“{s00154.response.nextBestQuestion}”</blockquote><p><strong>Why</strong>{s00154.response.questionWhy}</p></section>
}
