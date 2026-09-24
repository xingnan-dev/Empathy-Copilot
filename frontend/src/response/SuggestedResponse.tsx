import { RotateCcw, Sparkles } from 'lucide-react'

export function SuggestedResponse({ value, kind, loading, onChange, onRegenerate, onReset }: { value: string; kind: 'GENERATED' | 'HUMAN_EDITED' | 'FALLBACK'; loading: boolean; onChange: (value: string) => void; onRegenerate: () => void; onReset: () => void }) {
  const label = loading ? 'Generating…' : kind === 'GENERATED' ? 'Generated Draft' : kind === 'HUMAN_EDITED' ? 'Human Edited Draft' : 'Fallback Draft'
  return <section className="suggested-response" aria-labelledby="suggested-response-title"><header><div><span>Suggested response</span><h2 id="suggested-response-title">Grounded wording for human review</h2></div><em>{label}</em></header><label htmlFor="response-draft">Response draft</label><textarea id="response-draft" value={value} onChange={(event) => onChange(event.target.value)} rows={6} /><div className="response-editor-actions"><span>Warm, concise, evidence-bounded</span><button type="button" onClick={onReset}><RotateCcw size={13} />Reset</button><button type="button" disabled={loading} onClick={onRegenerate}><Sparkles size={13} />Alternative wording</button></div></section>
}
