import { useState } from 'react'
import { Check } from 'lucide-react'
import { SafetyBoundary } from '../safety/SafetyBoundary'
import { PluginHeader } from './PluginHeader'
import { ActionSection } from './sections/ActionSection'
import { MeaningSection } from './sections/MeaningSection'
import { PersonSection } from './sections/PersonSection'
import { SignalSection } from './sections/SignalSection'

export function CompactCopilot({ onExpand, onPrepare }: { onExpand: () => void; onPrepare: () => void }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false)

  return (
    <div className="compact-copilot">
      <PluginHeader onExpand={onExpand} />
      <main className="plugin-content">
        <div className="case-intro"><span>Current case</span><strong>Adverse reaction · Medical attention</strong><p>Understand before answer.</p></div>
        <PersonSection />
        <SignalSection />
        <MeaningSection expanded={evidenceOpen} onToggle={() => setEvidenceOpen((value) => !value)} />
        <ActionSection onReview={onExpand} onPrepare={onPrepare} />
        <SafetyBoundary />
      </main>
      <footer className="plugin-footer"><span><Check size={12} />Evidence boundary active</span><em>AI assists · Human decides</em></footer>
    </div>
  )
}
