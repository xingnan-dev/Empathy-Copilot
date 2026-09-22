export type IntelligenceView = 'evidence' | 'timeline' | 'memory' | 'activity'

const views: { id: IntelligenceView; label: string }[] = [
  { id: 'evidence', label: 'Evidence' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'memory', label: 'Memory' },
  { id: 'activity', label: 'Activity' },
]

export function IntelligenceNavigation({ active, onChange }: { active: IntelligenceView; onChange: (view: IntelligenceView) => void }) {
  return (
    <nav className="intelligence-navigation" aria-label="Intelligence views">
      {views.map((view) => <button key={view.id} type="button" className={active === view.id ? 'active' : ''} aria-current={active === view.id ? 'page' : undefined} onClick={() => onChange(view.id)}>{view.label}</button>)}
    </nav>
  )
}
