import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Minimize2, ShieldAlert } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'
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
  const { presentation: s00154, caseView, approve, approving, requestDraft } = useCaseRuntime()
  const [draft, setDraft] = useState<string>(s00154.response.drafts[0])
  const [draftKind, setDraftKind] = useState<'GENERATED' | 'HUMAN_EDITED' | 'FALLBACK'>('FALLBACK')
  const [draftLoading, setDraftLoading] = useState(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const backRef = useRef<HTMLButtonElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const draftRequestedRef = useRef(false)

  useEffect(() => {
    const shell = backRef.current?.closest('.demo-shell')
    if (shell) shell.scrollTop = 0
    backRef.current?.focus({ preventScroll: true })
    if (!draftRequestedRef.current) {
      draftRequestedRef.current = true
      setDraftLoading(true)
      void requestDraft().then((result) => { setDraft(result.text); setDraftKind(result.kind) }).catch(() => setDraftKind('FALLBACK')).finally(() => setDraftLoading(false))
    }
  }, [requestDraft])
  const regenerate = () => { setDraftLoading(true); void requestDraft().then((result) => { setDraft(result.text); setDraftKind(result.kind) }).catch(() => setDraftKind('FALLBACK')).finally(() => setDraftLoading(false)) }
  const reset = () => { setDraft(s00154.response.drafts[0]); setDraftKind('FALLBACK') }
  const edit = () => { editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); window.setTimeout(() => editorRef.current?.querySelector('textarea')?.focus(), 300) }

  const approved = caseView.human_checkpoint.state === 'APPROVED'
  const submitApproval = async () => { setApprovalError(null); try { await approve() } catch { setApprovalError('Case updated elsewhere. Refresh current state.') } }
  return <div className="response-studio"><header className="studio-header"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true"><i /><i /></span><div><strong>RESONIQUE</strong><small>Response Studio</small></div></div><div className="studio-header__context"><span>Case <strong>{s00154.caseId}</strong></span><span className="studio-safety"><ShieldAlert size={12} />Safety path · {s00154.safetyPath}</span></div><div className="studio-header__actions"><button ref={backRef} type="button" onClick={onBack}><ArrowLeft size={15} />Intelligence</button><button type="button" onClick={onCollapse} aria-label="Collapse to compact copilot"><Minimize2 size={16} /></button></div></header><div className="studio-scroll"><section className="studio-intro"><span>Response Studio</span><h1>Prepare the action before the answer.</h1><p>Current intent · Prepare human-reviewed response</p></section><ResponseProgress /><DecisionContext /><div className="studio-primary-work"><NextBestAction /><NextBestQuestion /></div><div ref={editorRef}><SuggestedResponse value={draft} kind={draftKind} loading={draftLoading} onChange={(value) => { setDraft(value); setDraftKind('HUMAN_EDITED') }} onRegenerate={regenerate} onReset={reset} /></div><div className="studio-evidence-layer"><ResponseEvidence onReview={onBack} /><div><UncertaintyRetained /><AvoidedClaims /></div></div>{approvalError && <p className="runtime-conflict" role="alert">{approvalError}</p>}<HumanCheckpoint approved={approved} approving={approving} onApprove={() => void submitApproval()} onEdit={edit} onReviewEvidence={onBack} /></div><footer className="expanded-footer"><span>Human decides · Resonique prepares</span><em>No external send · Human approval required · Evidence boundaries retained</em></footer></div>
}
