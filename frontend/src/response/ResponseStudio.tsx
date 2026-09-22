import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Minimize2, ShieldAlert } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'
import { AvoidedClaims } from './AvoidedClaims'
import { DecisionContext } from './DecisionContext'
import { HumanCheckpoint } from './HumanCheckpoint'
import { NextBestAction } from './NextBestAction'
import { NextBestQuestion } from './NextBestQuestion'
import { ResponseEvidence } from './ResponseEvidence'
import { ResponseProgress } from './ResponseProgress'
import { SuggestedResponse } from './SuggestedResponse'
import { UncertaintyRetained } from './UncertaintyRetained'

export function ResponseStudio({ onBack, onCollapse }: { onBack: () => void; onCollapse: () => void }) {
  const [draftIndex, setDraftIndex] = useState(0)
  const [draft, setDraft] = useState<string>(s00154.response.drafts[0])
  const [approved, setApproved] = useState(false)
  const backRef = useRef<HTMLButtonElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const shell = backRef.current?.closest('.demo-shell')
    if (shell) shell.scrollTop = 0
    backRef.current?.focus({ preventScroll: true })
  }, [])
  const regenerate = () => { const next = (draftIndex + 1) % s00154.response.drafts.length; setDraftIndex(next); setDraft(s00154.response.drafts[next]) }
  const reset = () => { setDraftIndex(0); setDraft(s00154.response.drafts[0]) }
  const edit = () => { editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); window.setTimeout(() => editorRef.current?.querySelector('textarea')?.focus(), 300) }

  return <div className="response-studio"><header className="studio-header"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true"><i /><i /></span><div><strong>RESONIQUE</strong><small>Response Studio</small></div></div><div className="studio-header__context"><span>Case <strong>{s00154.caseId}</strong></span><span className="studio-safety"><ShieldAlert size={12} />Safety path · Escalation</span></div><div className="studio-header__actions"><button ref={backRef} type="button" onClick={onBack}><ArrowLeft size={15} />Intelligence</button><button type="button" onClick={onCollapse} aria-label="Collapse to compact copilot"><Minimize2 size={16} /></button></div></header><div className="studio-scroll"><section className="studio-intro"><span>Response Studio</span><h1>Prepare the action before the answer.</h1><p>Current intent · Prepare human-reviewed response</p></section><ResponseProgress /><DecisionContext /><div className="studio-primary-work"><NextBestAction /><NextBestQuestion /></div><div ref={editorRef}><SuggestedResponse value={draft} onChange={setDraft} onRegenerate={regenerate} onReset={reset} /></div><div className="studio-evidence-layer"><ResponseEvidence onReview={onBack} /><div><UncertaintyRetained /><AvoidedClaims /></div></div><HumanCheckpoint approved={approved} onApprove={() => setApproved(true)} onEdit={edit} onReviewEvidence={onBack} /></div><footer className="expanded-footer"><span>Human decides · Resonique prepares</span><em>No external send · No model call · Evidence boundaries retained</em></footer></div>
}
