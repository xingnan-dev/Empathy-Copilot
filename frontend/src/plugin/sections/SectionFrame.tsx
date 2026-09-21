import type { ReactNode } from 'react'

export function SectionFrame({ index, label, question, tone = 'neutral', children }: { index: string; label: string; question: string; tone?: 'neutral' | 'attention'; children: ReactNode }) {
  return (
    <section className={`plugin-section plugin-section--${tone}`} aria-labelledby={`section-${label.toLowerCase()}`}>
      <header><span>{index}</span><div><h2 id={`section-${label.toLowerCase()}`}>{label}</h2><p>{question}</p></div></header>
      <div className="plugin-section__body">{children}</div>
    </section>
  )
}
