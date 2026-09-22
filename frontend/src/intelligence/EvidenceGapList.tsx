import { ArrowRight, CircleDashed } from 'lucide-react'
import { s00154 } from '../demo/cases/S00154'

export function EvidenceGapList() {
  return (
    <section className="expanded-gaps" aria-labelledby="open-gaps-title">
      <div className="intelligence-section-heading"><div><span>Unknown is useful</span><h2 id="open-gaps-title">Open evidence gaps</h2></div><em>{s00154.gaps.length} open</em></div>
      <div className="expanded-gap-list">
        {s00154.gaps.map((gap) => (
          <article key={gap.id}>
            <div className="expanded-gap-list__title"><CircleDashed size={16} /><div><small>{gap.id}</small><h3>{gap.label}</h3></div><span>Open</span></div>
            <dl><div><dt>Why it matters</dt><dd>{gap.why}</dd></div><div><dt>Resolve</dt><dd>{gap.resolve}<ArrowRight size={12} /></dd></div></dl>
          </article>
        ))}
      </div>
    </section>
  )
}
