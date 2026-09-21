import { CircleDashed } from 'lucide-react'

export function EvidenceGap({ gaps }: { gaps: readonly string[] }) {
  return (
    <div className="gap-list" aria-label={`${gaps.length} open evidence gaps`}>
      {gaps.map((gap) => <div key={gap}><CircleDashed size={13} aria-hidden="true" /><span>{gap}</span></div>)}
    </div>
  )
}
