import { Bot, FileImage, MessageSquareText, PackageCheck, TicketCheck } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

const icons = { ORDER: PackageCheck, CONSUMER_MESSAGE: MessageSquareText, MATERIAL_UPLOAD: FileImage, SERVICE_RECORD: TicketCheck, AGENT_ACTION: Bot }

export function ServiceTimeline() {
  const { presentation: s00154 } = useCaseRuntime()
  return (
    <div className="intelligence-view timeline-view">
      <div className="view-intro"><span>Service timeline</span><h2>What happened, in source order</h2><p>Events preserve their original source and available time precision.</p></div>
      <div className="service-timeline">
        {s00154.timeline.map((event) => { const Icon = icons[event.type]; return <article key={event.id}><div className="timeline-time"><strong>{event.date}</strong>{event.time && <span>{event.time}</span>}</div><span className={`timeline-icon timeline-icon--${event.type.toLowerCase()}`}><Icon size={17} /></span><div><small>{event.type.replaceAll('_', ' ')}</small><h3>{event.title}</h3><p>{event.detail}</p><em>{event.source}</em></div></article> })}
      </div>
    </div>
  )
}
