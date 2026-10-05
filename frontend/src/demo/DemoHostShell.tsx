import { MessageSquareText, Search, ShoppingBag } from 'lucide-react'
import { useState } from 'react'
import { ResoniquePlugin } from '../plugin/ResoniquePlugin'
import { currentServiceRecordEvidence } from '../presentation/caseTruth'
import { useCaseRuntime } from '../runtime/CaseRuntime'

const contacts = ['蒋a**', '林c**', '周e**', '杨c**']

type OfficialMessageRole = '买家' | '客服'

interface HostMessage {
  id: string
  role: OfficialMessageRole
  sender: string
  contentType: '文本' | '图片'
  content: string
  time: string
  compact?: boolean
}

const hostMessages: HostMessage[] = [
  { id: '94422222481506.PNM', role: '买家', sender: '蒋a**', contentType: '文本', content: '你们这产品啥情况！我用了面霜整张脸肿了，今天去医院挂了皮肤科……', time: '16:20' },
  { id: '26089175581339.PNM', role: '客服', sender: '测试美妆旗舰店:薇薇', contentType: '文本', content: '非常抱歉，您的情况我们高度重视。请先遵医嘱治疗，方便的话请上传相关材料……', time: '16:21' },
  { id: '25581855302692.PNM', role: '买家', sender: '蒋a**', contentType: '图片', content: 'Medical material uploaded', time: '16:21' },
  { id: '25330006295860.PNM', role: '客服', sender: '测试美妆旗舰店:薇薇', contentType: '文本', content: '资料已收到，正在为您升级至专项处理。', time: '16:22', compact: true },
]

function messageClassName(message: HostMessage) {
  if (message.contentType === '图片') return 'message message--attachment message--centered'
  return `message ${message.role === '买家' ? 'message--consumer' : 'message--agent'}${message.compact ? ' message--compact' : ''}`
}

export function DemoHostShell() {
  const { caseView, ingestMessage, processingMessage } = useCaseRuntime()
  const hasServiceRecord = currentServiceRecordEvidence(caseView).length > 0
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
          <div className="service-context"><span>Service context</span><i />Order verified{hasServiceRecord && <><i />Service record linked</>}</div>
          <div className="host-date">11 May 2026</div>
          {hostMessages.slice(0, 3).map((item) => <div className={messageClassName(item)} data-message-id={item.id} data-role={item.role} data-sender={item.sender} key={item.id}>{item.contentType === '图片' ? <><span><MessageSquareText size={18} /></span><div><strong>{item.content}</strong><small>Image attachment · consumer provided</small></div></> : <><p>{item.content}</p><time>{item.time}</time></>}</div>)}
          {hasServiceRecord && <div className="host-event"><i /><span>Service record linked to this conversation</span><time>16:22</time></div>}
          {hostMessages.slice(3).map((item) => <div className={messageClassName(item)} data-message-id={item.id} data-role={item.role} data-sender={item.sender} key={item.id}><p>{item.content}</p><time>{item.time}</time></div>)}
          {sentMessage && <div className="message message--consumer"><p>{sentMessage}</p><time>Now</time></div>}
          {messageError && <div className="host-event"><i /><span>{messageError}</span><time>Now</time></div>}
          <div className="host-composer"><input aria-label="Consumer message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void send() }} placeholder="Consumer message for understanding…" /><button type="button" disabled={processingMessage} onClick={() => void send()}>{processingMessage ? 'Reading…' : 'Send'}</button></div>
        </main>
        <ResoniquePlugin />
      </div>
    </div>
  )
}
