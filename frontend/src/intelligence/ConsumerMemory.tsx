import { Check, CircleDashed, History, PackageCheck, TicketCheck } from 'lucide-react'
import { useCaseRuntime } from '../runtime/CaseRuntime'

export function ConsumerMemory() {
  const { presentation: s00154 } = useCaseRuntime()
  return (
    <div className="intelligence-view memory-view">
      <div className="view-intro"><span>Context passport</span><h2>Current case context, restored</h2><p>Use what is already grounded. Do not ask the consumer to repeat it.</p></div>
      <div className="context-restored"><Check size={15} /><span>Context restored</span><p>Only current-case evidence is shown.</p></div>
      <div className="memory-sections">
        <section><header><PackageCheck size={17} /><div><span>Relevant order</span><h3>{s00154.product}</h3></div></header><dl><div><dt>Order</dt><dd>{s00154.orderId}</dd></div><div><dt>Paid</dt><dd>{s00154.paid}</dd></div><div><dt>Boundary</dt><dd>Purchase verified · usage unknown</dd></div></dl></section>
        <section><header><TicketCheck size={17} /><div><span>Relevant service history</span><h3>Adverse-reaction case</h3></div></header><dl><div><dt>Ticket</dt><dd>{s00154.ticketId}</dd></div><div><dt>Status</dt><dd>Record exists</dd></div></dl></section>
        <section className="memory-sections__wide"><header><History size={17} /><div><span>Already known</span><h3>Grounded current-case context</h3></div></header><ul>{s00154.evidence.slice(0, 4).map((item) => <li key={item.id}><Check size={12} />{item.fact}</li>)}</ul></section>
        <section className="memory-sections__wide"><header><CircleDashed size={17} /><div><span>Not yet known</span><h3>Do not infer or repeat as fact</h3></div></header><ul>{s00154.gaps.map((gap) => <li key={gap.id}><CircleDashed size={12} />{gap.label}</li>)}</ul></section>
      </div>
    </div>
  )
}
