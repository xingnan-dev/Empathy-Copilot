import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { SafetyBoundary } from '../safety/SafetyBoundary'
import { PluginHeader } from './PluginHeader'
import { ActionSection } from './sections/ActionSection'
import { MeaningSection } from './sections/MeaningSection'
import { PersonSection } from './sections/PersonSection'
import { SignalSection } from './sections/SignalSection'

export function CompactCopilot({ onExpand }: { onExpand: () => void }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const notify = (message: string) => {
    setNotice(message)
    window.setTimeout(() => setNotice(null), 2800)
  }

  return (
    <div className="compact-copilot">
      <PluginHeader onExpand={onExpand} />
      <main className="plugin-content">
        <div className="case-intro"><span>Current case</span><strong>Adverse reaction · Medical attention</strong><p>Understand before answer.</p></div>
        <PersonSection />
        <SignalSection />
        <MeaningSection expanded={evidenceOpen} onToggle={() => setEvidenceOpen((value) => !value)} />
        <ActionSection onReview={onExpand} onPrepare={() => notify('Response preparation is gated until human review.')} />
        <SafetyBoundary />
      </main>
      <footer className="plugin-footer"><span><Check size={12} />Evidence boundary active</span><em>AI assists · Human decides</em></footer>
      {notice && <div className="toast" role="status"><span>{notice}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button></div>}
    </div>
  )
}
