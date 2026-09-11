import { useEffect, useRef, useState } from 'react'
import { clearChat, fetchChat, sendChat, type ChatMessage } from './lib/hud'

/**
 * A chat panel that pops up over whatever you are looking at. Same agent as the column: real
 * Hermes turns in a continuing session, no voice required. Docked bottom-right so it can be
 * summoned while the voice view is running.
 */
export default function FloatingChat({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState('jimsky-hud')
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    void (async () => {
      try {
        const r = await fetchChat()
        setMessages(r.messages)
        setSession(r.session)
      } catch { /* the key may not be set yet */ }
    })()
  }, [open])

  useEffect(() => { boxRef.current?.scrollTo({ top: 1e9 }) }, [messages.length, open])

  const send = async () => {
    const text = draft.trim()
    if (!text) return
    setDraft('')
    setMessages((m) => [...m, { role: 'user', text, at: Date.now() }])
    setBusy(true)
    try { await sendChat(text) } catch { /* surfaced by the next poll */ }
    const started = Date.now()
    while (Date.now() - started < 900000) {
      await new Promise((r) => setTimeout(r, 4000))
      try {
        const r = await fetchChat()
        setMessages(r.messages)
        const last = r.messages[r.messages.length - 1]
        if (last?.role === 'assistant') break
      } catch { /* keep waiting */ }
    }
    setBusy(false)
  }

  return (
    <>
      <button className={`chatfab ${open ? 'on' : ''}`} onClick={onToggle}
              title={open ? 'close the chat' : 'talk to the agent'}>
        {open ? '▾' : '▚'} {open ? '' : 'ASK'}
      </button>
      {open && (
        <div className="chatfloat">
          <div className="chatfloat-head">
            <span className="tag">AGENT</span>
            <span className="muted">{session}</span>
            {busy && <span className="chip thinking-chip">WORKING…</span>}
            <span className="spacer" />
            <button className="mini" onClick={async () => { await clearChat(); setMessages([]) }}>CLEAR</button>
            <button className="mini" onClick={onToggle}>×</button>
          </div>
          <div className="chattranscript" ref={boxRef}>
            {messages.length === 0 && <p className="muted">Ask for anything. It can make images,
              video, music, 3D, datasets — and drop them on the stage.</p>}
            {messages.map((m, i) => (
              <div key={i} className={`chatline ${m.role}${m.error ? ' bad' : ''}`}>
                <span className="who">{m.role === 'user' ? 'you' : 'hermes'}</span>
                <span className="chattext">{m.text}</span>
              </div>
            ))}
          </div>
          <div className="chatbox">
            <textarea rows={2} value={draft} placeholder="ask — Enter sends"
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }} />
            <button className="cta" disabled={busy || !draft.trim()} onClick={() => void send()}>SEND</button>
          </div>
        </div>
      )}
    </>
  )
}
