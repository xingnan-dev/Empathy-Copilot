import { MessageSquareText, Search, ShoppingBag } from 'lucide-react'
import { useState } from 'react'
import { ResoniquePlugin } from '../plugin/ResoniquePlugin'
import { useCaseRuntime } from '../runtime/CaseRuntime'

const contacts = ['蒋a**', '林c**', '周e**', '杨c**']

export function DemoHostShell() {
  const { ingestMessage, processingMessage } = useCaseRuntime()
  const [message, setMessage] = useState('')
  const [sentMessage, setSentMessage] = useState<string | null>(null)
  const [messageError, setMessageError] = useState<string | null>(null)
  const send = async () => { const content = message.trim(); if (!content) return; setMessageError(null); try { await ingestMessage(content); setSentMessage(content); setMessage('') } catch { setMessageError('Model understanding unavailable. Please retry.') } }
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
          <div className="service-context"><span>Service context</span><i />Adverse-reaction case linked<i />Order verified</div>
          <div className="host-date">11 May 2026</div>
          <div className="message message--consumer"><p>你们这产品啥情况！我用了面霜整张脸肿了，今天去医院挂了皮肤科……</p><time>16:20</time></div>
          <div className="message message--agent"><p>非常抱歉，您的情况我们高度重视。请先遵医嘱治疗，方便的话请上传相关材料……</p><time>16:21</time></div>
          <div className="message message--consumer message--attachment"><span><MessageSquareText size={18} /></span><div><strong>Medical material uploaded</strong><small>Image attachment · consumer provided</small></div></div>
          <div className="host-event"><i /><span>Service record linked to this conversation</span><time>16:22</time></div>
          <div className="message message--agent message--compact"><p>资料已收到，正在为您升级至专项处理。</p><time>16:22</time></div>
          {sentMessage && <div className="message message--consumer"><p>{sentMessage}</p><time>Now</time></div>}
          {messageError && <div className="host-event"><i /><span>{messageError}</span><time>Now</time></div>}
          <div className="host-composer"><input aria-label="Consumer message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void send() }} placeholder="Consumer message for understanding…" /><button type="button" disabled={processingMessage} onClick={() => void send()}>{processingMessage ? 'Reading…' : 'Send'}</button></div>
        </main>
        <ResoniquePlugin />
      </div>
    </div>
  )
}
