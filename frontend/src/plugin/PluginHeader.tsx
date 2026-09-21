import { Expand, Waves } from 'lucide-react'

export function PluginHeader({ onExpand }: { onExpand: () => void }) {
  return (
    <header className="plugin-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true"><i /><i /></span>
        <div><strong>RESONIQUE</strong><small>Evidence-aware Copilot</small></div>
      </div>
      <div className="plugin-header__actions">
        <span className="investigating"><Waves size={12} aria-hidden="true" />Investigating</span>
        <button className="icon-button" type="button" onClick={onExpand} aria-label="Expand intelligence view"><Expand size={17} /></button>
      </div>
    </header>
  )
}
