import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Minimize2, Waves } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'
import { AgentActivity } from './AgentActivity'
import { ConsumerMemory } from './ConsumerMemory'
import { EvidenceView } from './EvidenceView'
import { InvestigationSummary } from './InvestigationSummary'
import { IntelligenceNavigation, type IntelligenceView } from './IntelligenceNavigation'
import { ServiceTimeline } from './ServiceTimeline'
import { WhyThisAction } from './WhyThisAction'

export function IntelligenceExpanded({ onCollapse }: { onCollapse: () => void }) {
  const [view, setView] = useState<IntelligenceView>('evidence')
  const collapseRef = useRef<HTMLButtonElement>(null)

  useEffect(() => { collapseRef.current?.focus({ preventScroll: true }) }, [])

  return (
    <div className="intelligence-expanded">
      <header className="expanded-header">
        <div className="brand-lockup"><span className="brand-mark" aria-hidden="true"><i /><i /></span><div><strong>RESONIQUE</strong><small>Intelligence Expanded</small></div></div>
        <div className="expanded-header__context"><div><span>Case</span><strong>{s00154.caseId}</strong></div><div><span>Lifecycle</span><strong className="expanded-state"><Waves size={12} />Investigating</strong></div><div><span>Safety path</span><strong className="expanded-safety"><AlertTriangle size={12} />Escalation</strong></div></div>
        <button ref={collapseRef} className="collapse-button" type="button" onClick={onCollapse} aria-label="Collapse intelligence view"><Minimize2 size={17} /><span>Collapse</span></button>
      </header>
      <div className="expanded-scroll">
        <section className="expanded-intro"><span>Evidence investigation space</span><h1>Understand the action before taking it.</h1><p>Trace the evidence, preserve uncertainty, and keep consequential decisions human.</p></section>
        <InvestigationSummary />
        <IntelligenceNavigation active={view} onChange={setView} />
        <div className="expanded-view-stage">
          {view === 'evidence' && <EvidenceView />}
          {view === 'timeline' && <ServiceTimeline />}
          {view === 'memory' && <ConsumerMemory />}
          {view === 'activity' && <AgentActivity />}
        </div>
        <WhyThisAction />
      </div>
      <footer className="expanded-footer"><span>No evidence → No attribution</span><em>Based on consumer report and service records · Not a medical diagnosis</em></footer>
    </div>
  )
}
