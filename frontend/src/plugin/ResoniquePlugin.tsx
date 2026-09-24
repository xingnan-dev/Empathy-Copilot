import { useState } from 'react'
import { IntelligenceExpanded } from '../intelligence/IntelligenceExpanded'
import { ResponseStudio } from '../response/ResponseStudio'
import { CompactCopilot } from './CompactCopilot'

export function ResoniquePlugin() {
  const [view, setView] = useState<'compact' | 'intelligence' | 'response'>('compact')
  const expanded = view !== 'compact'

  return (
    <aside className={`resonique-plugin ${expanded ? 'resonique-plugin--expanded' : ''}`} aria-label="Resonique evidence-aware copilot">
      {view === 'compact' && <CompactCopilot onExpand={() => setView('intelligence')} onPrepare={() => setView('response')} />}
      {view === 'intelligence' && <IntelligenceExpanded onCollapse={() => setView('compact')} onPrepare={() => setView('response')} />}
      {view === 'response' && <ResponseStudio onBack={() => setView('intelligence')} onCollapse={() => setView('compact')} />}
    </aside>
  )
}
