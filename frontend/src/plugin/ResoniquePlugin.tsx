import { useState } from 'react'
import { IntelligenceExpanded } from '../intelligence/IntelligenceExpanded'
import { CompactCopilot } from './CompactCopilot'

export function ResoniquePlugin() {
  const [expanded, setExpanded] = useState(false)

  return (
    <aside className={`resonique-plugin ${expanded ? 'resonique-plugin--expanded' : ''}`} aria-label="Resonique evidence-aware copilot">
      {expanded ? <IntelligenceExpanded onCollapse={() => setExpanded(false)} /> : <CompactCopilot onExpand={() => setExpanded(true)} />}
    </aside>
  )
}
