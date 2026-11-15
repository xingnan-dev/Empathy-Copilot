import { MessageSquareText, Search, ShoppingBag } from 'lucide-react'
import { useState, useRef } from 'react'
import { ResoniquePlugin } from '../plugin/ResoniquePlugin'
import { currentServiceRecordEvidence } from '../presentation/caseTruth'
import { CaseApiError } from '../api/client'
import { useCaseRuntime } from '../runtime/CaseRuntime'

const contacts = ['蒋a**', '林c**', '周e**', '杨c**']

export function DemoHostShell() {
  const { caseView, ingestMessage, processingMessage } = useCaseRuntime()
  const hasServiceRecord = currentServiceRecordEvidence(caseView).length > 0
  const [message, setMessage] = useState('')
  const sending = useRef(false)
  const [messageError, setMessageError] = useState<string | null>(null)
  const send = async () => {
    if (sending.current || !message.trim()) return
    sending.current = true; setMessageError(null)
    try { await ingestMessage(message); setMessage('') }
    catch (reason) {
      const code = reason instanceof CaseApiError ? reason.code : 'UNKNOWN'
      const feedback: Record<string, string> = {
        MODEL_UNAVAILABLE: 'Model understanding unavailable. Message was not accepted. Please retry.',
        STATE_CONFLICT: 'Case updated elsewhere. Message was not accepted. Refresh and check before retrying.',
        MESSAGE_ID_CONFLICT: 'Message identity was used for different content. Refresh and check history.',
        MESSAGE_PERSISTENCE_UNAVAILABLE: 'Message was not accepted: storage unavailable. Please retry.',
        MESSAGE_COMMIT_UNCERTAIN: 'Message receipt is unconfirmed. Retry the original request or refresh and check history.',
        BACKEND_UNAVAILABLE: 'Message receipt is unconfirmed. Retry the original request or refresh and check history.',
      }
      setMessageError(feedback[code] ?? (reason instanceof CaseApiError ? reason.message : 'Message receipt is unconfirmed. Refresh and check history.'))
    } finally { sending.current = false }
  }

  return (
    <div className="demo-page antialiased">
      <header className="demo-topbar"><div><span className="host-logo">Q</span><strong>Customer Service Workspace</strong></div><span>Demo host context</span></header>
      <div className="demo-shell">
        <aside className="host-contacts" aria-label="Host customer list preview">
          <div className="host-title"><span>Customers</span><small>4 active</small></div>
          <div className="host-search"><Search size={14} /><span>Search</span></div>
          {contacts.map((contact, index) => <div className={`host-contact ${index === 0 ? 'active' : ''}`} key={contact}><i>{contact.slice(0, 1)}</i><span><strong>{contact}</strong><small>{index === 0 ? 'Adverse reaction follow-up' : 'Customer message'}</small></span><time>{index === 0 ? 'Now' : `${index + 1}h`}</time></div>)}
        </aside>
        <main className="host-conversation">
          <header><div><strong>蒋a**</strong><small>Conversation · S00154</small></div><span><ShoppingBag size={14} />Current order</span></header>
          <section className="host-product"><div><ShoppingBag size={18} /></div><span><small>Current order</small><strong>Firming Gift Set</strong><em>¥1,398</em></span></section>
          <div className="service-context"><span>Service context</span><i />Order verified{hasServiceRecord && <><i />Service record linked</>}</div>
          <div className="host-date">11 May 2026</div>
          {caseView.messages.map(item => {
            const time = item.received_at ?? item.sent_at
            const label = item.origin === 'LIVE' ? 'Newly received' : item.origin === 'OFFICIAL' ? 'Historical record' : 'Historical demo fixture'
            return <div className={item.content_type === 'IMAGE' ? 'message message--attachment message--centered' : `message ${item.role === 'CONSUMER' ? 'message--consumer' : item.role === 'AGENT' ? 'message--agent' : 'message--unknown'}`}
              data-message-id={item.id} data-origin={item.origin} data-role={item.role} key={`${item.origin}:${item.id}`}>
              {item.content_type === 'IMAGE' && <span><MessageSquareText size={18} /></span>}
              <div><small>{label} · {item.role}</small><p style={{ whiteSpace: 'pre-wrap' }}>{item.text}</p><time>{time ? new Date(time).toLocaleString() : 'Time unavailable'}</time></div>
            </div>
          })}
          {messageError && <div className="host-event" role="alert"><i /><span>{messageError}</span><time>Now</time></div>}
          <div className="host-composer"><input aria-label="Consumer message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void send() }} placeholder="Consumer message for understanding…" /><button type="button" disabled={processingMessage} onClick={() => void send()}>{processingMessage ? 'Reading…' : 'Send'}</button></div>
        </main>
        <ResoniquePlugin />
      </div>
    </div>
  )
}
