import { ArrowRight, FileSearch, ShieldAlert } from 'lucide-react'
import { SectionFrame } from './SectionFrame'
import { useCaseRuntime } from '../../runtime/CaseRuntime'

export function ActionSection({ onReview, onPrepare }: { onReview: () => void; onPrepare: () => void }) {
  const { presentation } = useCaseRuntime()
  return (
    <SectionFrame index="04" label="ACTION" question="What should the human agent do next?">
      <div className="action-callout">
        <span><ShieldAlert size={17} aria-hidden="true" /></span>
        <div><small>Recommended action</small><h3>{presentation.currentAction}</h3><p>Adverse-reaction handling path</p></div>
      </div>
      <div className="why-row"><span>Why</span><p>Medical attention reported <b>+</b> supporting service evidence</p></div>
      <p className="approval-note"><i />{presentation.lifecycle === 'ESCALATED' ? 'Human approval recorded' : 'Human approval required before consequential action'}</p>
      <div className="action-buttons">
        <button type="button" onClick={onReview}><FileSearch size={15} />Review evidence</button>
        <button className="primary-button" type="button" onClick={onPrepare}>Prepare response<ArrowRight size={15} /></button>
      </div>
    </SectionFrame>
  )
}
