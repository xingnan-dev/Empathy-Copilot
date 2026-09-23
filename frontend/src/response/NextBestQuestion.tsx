import { CircleHelp } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function NextBestQuestion() {
  const { presentation: s00154 } = useCaseRuntime()
  return <section className="next-best-question" aria-labelledby="next-question-title"><header><span><CircleHelp size={14} />Next best question</span><small>Resolves · {s00154.response.questionResolvesGap}</small></header><blockquote id="next-question-title">“{s00154.response.nextBestQuestion}”</blockquote><p><strong>Why</strong>{s00154.response.questionWhy}</p></section>
}
