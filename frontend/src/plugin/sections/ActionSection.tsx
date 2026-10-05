import { ArrowRight, FileSearch, ShieldAlert } from 'lucide-react'
import { SectionFrame } from './SectionFrame'
import { useCaseRuntime } from '../../runtime/CaseRuntime'
import { decisionSupportLabels } from '../../presentation/caseTruth'

export function ActionSection({ onReview, onPrepare }: { onReview: () => void; onPrepare: () => void }) {
  const { presentation, caseView } = useCaseRuntime()
  const strategy = caseView.service_strategy
  const support = decisionSupportLabels(caseView)
  return (
    <SectionFrame index="04" label="ACTION" question="What should the human agent do next?">
      <div className="action-callout">
        <span><ShieldAlert size={17} aria-hidden="true" /></span>
        <div><small>Recommended action</small><h3>{presentation.currentAction}</h3><p>Adverse-reaction handling path</p></div>
      </div>
      {support.length > 0 && <div className="why-row"><span>Why</span><p>{support.join(' + ')}</p></div>}
      <div className="service-strategy" aria-label="Consumer signal to service action">
        <div><small>Consumer signal · {strategy.consumer_signal.semantic_type}</small><p>{strategy.consumer_signal.label}</p></div>
        <i>↓</i>
        <div><small>Service strategy</small><p>{strategy.communication[0]} {strategy.critical_gap ? `One question: ${strategy.critical_gap}.` : ''}</p></div>
        <i>↓</i>
        <div><small>Action</small><p>{strategy.human_attention.replaceAll('_', ' ')}</p></div>
      </div>
      <p className="approval-note"><i />{presentation.lifecycle === 'ESCALATED' ? 'Human approval recorded' : 'Human approval required before consequential action'}</p>
      <div className="action-buttons">
        <button type="button" onClick={onReview}><FileSearch size={15} />Review evidence</button>
        <button className="primary-button" type="button" onClick={onPrepare}>Prepare response<ArrowRight size={15} /></button>
      </div>
    </SectionFrame>
  )
}
