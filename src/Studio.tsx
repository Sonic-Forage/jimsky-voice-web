import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  askAgent, browseUrl, clearChat, createJobs, deleteWorkflow, fetchCatalog, fetchChat,
  fetchJobs, fetchMods, fetchWorkflows, getKey, redeemCode, runWorkflow, saveWorkflow, sendChat,
  setKey, type Catalog, type ChatMessage, type HudJob, type HudModel, type HudMod, type HudWorkflow,
} from './lib/hud'
import { MEDIA_BASE } from './lib/config'

/**
 * The studio half of the HUD: pick a model, pick a template, make something. Deliberately usable
 * without a live voice session - "stop the bot and just make art" is a first-class mode, and the
 * voice shell is one tab away.
 *
 * Layout is mobile-first: one column on a phone, two on a tablet, three on a desktop, so it works
 * stood up in a kitchen as well as on a big screen.
 */

function KeyGate({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState('')
  return (
    <div className="keygate">
      <h2>HUD KEY REQUIRED</h2>
      <p className="muted">
        This backend can spend money, so it only answers callers holding the key. It lives in
        <code> ~/.hermes/profiles/jimsky/.env</code> as <code>JIMSKY_HUD_KEY</code>.
      </p>
      <div className="row">
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="paste the key"
               spellCheck={false} autoComplete="off" />
        <button className="cta" onClick={() => { setKey(value); onSaved() }}>UNLOCK</button>
      </div>
    </div>
  )
}

function ModelPicker({ models, value, onChange, onTemplate, newOnly, onNewOnly }: {
  models: HudModel[]
  value: string
  onChange: (alias: string) => void
  onTemplate: (category: string) => void
  newOnly: boolean
  onNewOnly: (v: boolean) => void
}) {
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const by: Record<string, HudModel[]> = {}
    for (const m of models) {
      if (newOnly && m.tier === 'legacy') continue
      if (q && !`${m.alias} ${m.partner} ${m.category}`.toLowerCase().includes(q.toLowerCase())) continue
      ;(by[m.category] ||= []).push(m)
    }
    return by
  }, [models, q, newOnly])
  return (
    <section className="panel">
      <div className="panel-head"><span className="tag">MODEL</span>
        <button className={`tierbtn ${newOnly ? 'on' : ''}`}
                onClick={() => onNewOnly(!newOnly)}
                title="hide the older flux-1.x era models">
          NEW STACK
        </button>
        <input className="mini-input" placeholder="filter" value={q}
               onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="scroller">
        {Object.entries(groups).sort().map(([cat, list]) => (
          <div key={cat} className="pickgroup">
            <button className="grouplabel" onClick={() => onTemplate(cat)} title="see templates for this">
              {cat.replace(/-/g, ' ').toUpperCase()}
            </button>
            {list.map((m) => (
              <button key={m.alias} className={`chipmodel ${value === m.alias ? 'on' : ''}`}
                      onClick={() => onChange(m.alias)} title={m.summary}>
                {m.tier === 'new' ? <span className="newdot" title="newest generation" /> : null}
                <span className="alias">{m.alias}</span>
                <span className="partner">{m.partner}</span>
                <span className="cost">{m.price}c</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}

function Chat({ messages, session, onSend, onClear, busy, watching }: {
  messages: ChatMessage[]
  session: string
  onSend: (text: string) => void
  onClear: () => void
  busy: boolean
  watching: string | null
}) {
  const [draft, setDraft] = useState('')
  const boxRef = useRef<HTMLDivElement>(null)
  useEffect(() => { boxRef.current?.scrollTo({ top: 1e9 }) }, [messages.length])
  const submit = () => {
    const v = draft.trim()
    if (!v) return
    setDraft('')
    onSend(v)
  }
  return (
    <section className="panel chatpanel">
      <div className="panel-head">
        <span className="tag">AGENT</span>
        <span className="muted">{session}</span>
        {busy && <span className="chip thinking-chip">WORKING…</span>}
        <button className="mini" onClick={onClear}>CLEAR</button>
      </div>
      <div className="chattranscript" ref={boxRef}>
        {messages.length === 0 && (
          <p className="muted">
            Talk to the full agent — every tool it has, no voice needed. Ask it to make something and
            watch the stage fill up.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chatline ${m.role}${m.error ? ' bad' : ''}`}>
            <span className="who">{m.role === 'user' ? 'you' : 'hermes'}</span>
            <span className="chattext">{m.text}</span>
            {m.seconds ? <span className="chatmeta">{m.seconds}s</span> : null}
          </div>
        ))}
      </div>
      {watching && <div className="watching">◉ new on stage: {watching.slice(0, 70)}</div>}
      <div className="chatbox">
        <textarea rows={2} value={draft} placeholder="ask for anything — type, don't talk"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
                  }} />
        <button className="cta" disabled={busy || !draft.trim()} onClick={submit}>SEND</button>
      </div>
    </section>
  )
}

function Jobs({ jobs, onPick }: { jobs: HudJob[]; onPick: (url: string) => void }) {
  return (
    <section className="panel">
      <div className="panel-head"><span className="tag">QUEUE</span>
        <span className="muted">{jobs.length ? `${jobs.length} recent` : 'idle'}</span>
      </div>
      <div className="scroller">
        {jobs.length === 0 && <p className="muted">Nothing yet. Pick a model and hit create.</p>}
        {jobs.map((j) => (
          <div key={j.id} className={`job ${j.state}`}>
            <div className="jobline">
              <span className={`dot ${j.state}`} />
              <span className="jmodel">{j.model}</span>
              <span className="jstate">{j.state}</span>
              {j.bytes ? <span className="jbytes">{(j.bytes / 1024).toFixed(0)}K</span> : null}
            </div>
            <div className="jprompt">{j.prompt}</div>
            {j.error && <div className="jerr">{j.error.slice(0, 180)}</div>}
            {j.url && (
              <button className="jlink" onClick={() => onPick(j.url!)}>show on stage</button>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export default function Studio() {
  const [hasKey, setHasKey] = useState(Boolean(getKey()))
  const [cat, setCat] = useState<Catalog | null>(null)
  const [jobs, setJobs] = useState<HudJob[]>([])
  const [model, setModel] = useState('flux-2')
  const [prompt, setPrompt] = useState('')
  const [batch, setBatch] = useState(1)
  const [source, setSource] = useState('')
  const [url, setUrl] = useState('https://')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [mods, setMods] = useState<HudMod[]>([])
  const [workflows, setWorkflows] = useState<HudWorkflow[]>([])
  const [newOnly, setNewOnly] = useState(true)
  const [wfName, setWfName] = useState('')
  const [wfSubject, setWfSubject] = useState('')
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [chatSession, setChatSession] = useState('jimsky-hud')
  const [chatBusy, setChatBusy] = useState(false)
  const [watching, setWatching] = useState<string | null>(null)
  const lastMedia = useRef<number>(0)

  const refresh = useCallback(async () => {
    try {
      const [c, j, m, w, ch] = await Promise.all([
        fetchCatalog(), fetchJobs(), fetchMods(), fetchWorkflows(), fetchChat(),
      ])
      setChat(ch.messages)
      setChatSession(ch.session)
      setCat(c)
      setJobs(j.jobs)
      setMods(m.mods)
      setWorkflows(w.workflows)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    if (!hasKey) return
    void refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [hasKey, refresh])

  // Escape closes the preview. Clicking anywhere does too - standard lightbox behaviour, and the
  // overlay covers the controls so there must be more than one way out.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPreview(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // "Watch it generate": while a chat turn is running, notice new items landing on the stage.
  useEffect(() => {
    if (!chatBusy) return
    let stop = false
    const tick = async () => {
      try {
        const res = await fetch(`${MEDIA_BASE}/index.json`, { cache: 'no-store' })
        if (!res.ok || stop) return
        const body = await res.json()
        const n = (body.items ?? []).length
        if (lastMedia.current && n > lastMedia.current) {
          const top = body.items[0]
          setWatching(`${top.caption ?? top.file}`)
          setPreview(`${MEDIA_BASE}/${encodeURIComponent(top.file)}`)
        }
        lastMedia.current = n
      } catch { /* fine */ }
    }
    void tick()
    const t = setInterval(tick, 4000)
    return () => { stop = true; clearInterval(t) }
  }, [chatBusy])

  const isEdit = model.includes('kontext') || model.includes('edit') || model.includes('reframe')
    || model.includes('remix') || model.includes('i2i') || model.includes('fill')
    || model.includes('expand') || model.includes('bg') || model.includes('upscale')

  const submit = async () => {
    setBusy(true); setError(null); setNote(null)
    try {
      const r = await createJobs({
        model, prompt, n: batch, image: isEdit && source ? source : null,
        caption: `${model} · ${prompt.slice(0, 70)}`,
      })
      setNote(`${r.jobs.length} job${r.jobs.length > 1 ? 's' : ''} queued · ${r.credits} credits left`)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!hasKey) return <KeyGate onSaved={() => setHasKey(Boolean(getKey()))} />

  return (
    <div className="studio">
      {preview && (
        <div className="preview" onClick={() => setPreview(null)} role="button" tabIndex={0}
             title="click anywhere to close">
          <img src={preview} alt="latest" />
          <button className="mini" onClick={() => setPreview(null)}>CLOSE</button>
          <span className="tiny preview-hint">click anywhere to close</span>
        </div>
      )}
      <div className="studio-grid">
        <div className="chatwrap">
          <Chat
            messages={chat}
            session={chatSession}
            busy={chatBusy}
            watching={watching}
            onClear={async () => { await clearChat(); setChat([]); setWatching(null) }}
            onSend={async (text) => {
              setChat((prev) => [...prev, { role: 'user', text, at: Date.now() }])
              setChatBusy(true)
              setWatching(null)
              try { await sendChat(text) } catch (e) { setError((e as Error).message) }
              // poll until the assistant entry appears
              const started = Date.now()
              while (Date.now() - started < 900000) {
                await new Promise((r) => setTimeout(r, 4000))
                try {
                  const r = await fetchChat()
                  setChat(r.messages)
                  const last = r.messages[r.messages.length - 1]
                  if (last && last.role === 'assistant') break
                } catch { /* keep waiting */ }
              }
              setChatBusy(false)
              await refresh()
            }}
          />
        </div>
        <ModelPicker
          models={cat?.models ?? []}
          value={model}
          newOnly={newOnly}
          onNewOnly={setNewOnly}
          onChange={setModel}
          onTemplate={(c) => {
            const t = cat?.templates.find((x) => x.category === c)
            if (t) { setPrompt(t.prompt); setModel(c === 'image-edit' ? 'flux-kontext' : 'flux-2') }
          }}
        />

        <section className="panel compose">
          <div className="panel-head">
            <span className="tag">MAKE</span>
            <span className="muted">{model}{isEdit ? ' · needs a source image' : ''}</span>
          </div>
          <div className="scroller">
            <div className="templates">
              {(cat?.templates ?? []).map((t) => (
                <button key={t.id} className="tchip" title={t.hint}
                        onClick={() => { setPrompt(t.prompt); if (t.category === 'image-edit') setModel('flux-kontext') }}>
                  {t.name}
                </button>
              ))}
            </div>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={7}
                      placeholder="Describe it. Templates above fill this in; edit it freely." />
            {isEdit && (
              <label className="srcrow">
                <span className="tiny">SOURCE IMAGE (path on the box or a URL)</span>
                <input value={source} onChange={(e) => setSource(e.target.value)}
                       placeholder="/tmp/jimsky_gen/jimsky_rooftop.jpg" spellCheck={false} />
              </label>
            )}
            <div className="row">
              <label className="stepper">
                <span className="tiny">BATCH</span>
                <button onClick={() => setBatch(Math.max(1, batch - 1))}>−</button>
                <b>{batch}</b>
                <button onClick={() => setBatch(Math.min(cat?.max_batch ?? 8, batch + 1))}>+</button>
              </label>
              <button className="cta grow" disabled={busy || !prompt.trim()} onClick={submit}>
                {busy ? 'WORKING…' : `CREATE${batch > 1 ? ` ×${batch}` : ''}`}
              </button>
            </div>
            <div className="row">
              <input className="mini-input grow" placeholder="save this setup as a workflow named…"
                     value={wfName} onChange={(e) => setWfName(e.target.value)} />
              <button className="mini" disabled={!wfName.trim() || !prompt.trim()}
                      onClick={async () => {
                        try {
                          await saveWorkflow({ name: wfName.trim(), model, prompt })
                          setNote(`saved workflow: ${wfName.trim()}`); setWfName('')
                          await refresh()
                        } catch (e) { setError((e as Error).message) }
                      }}>SAVE</button>
            </div>
            {note && <p className="ok">{note}</p>}
            {error && <p className="err">⚠ {error}</p>}
            <div className="credits">
              <span className="tag">CREDITS</span>
              <b>{cat?.credits ?? '—'}</b>
              <input className="mini-input" placeholder="redeem code" value={code}
                     onChange={(e) => setCode(e.target.value)} />
              <button className="mini" onClick={async () => {
                try {
                  const r = await redeemCode(code)
                  setNote(`+${r.added} credits — ${r.balance} now`); setCode(''); await refresh()
                } catch (e) { setError((e as Error).message) }
              }}>GO</button>
            </div>
          </div>
        </section>

        <div className="stack">
          <section className="panel">
            <div className="panel-head"><span className="tag">BROWSE</span>
              <span className="muted">real Chromium</span>
            </div>
            <div className="browsebox">
              <input value={url} onChange={(e) => setUrl(e.target.value)} spellCheck={false} />
              <button className="mini" onClick={async () => {
                try {
                  const r = await browseUrl(url)
                  setNote(`opening ${url} — lands on the stage`)
                  if (r.job.url) setPreview(r.job.url)
                  await refresh()
                } catch (e) { setError((e as Error).message) }
              }}>OPEN</button>
            </div>
            <p className="tiny">Screenshots a page and puts it on the stage — look at a trend
              board, a chart, a competitor, whatever you are pointing at.</p>
          </section>

          <section className="panel">
            <div className="panel-head"><span className="tag">AGENT</span>
              <span className="muted">MCP-only work</span>
            </div>
            <div className="browsebox">
              <input placeholder="ask hermes, e.g. run the flare turnaround on woozle"
                     onKeyDown={async (e) => {
                       if (e.key !== 'Enter') return
                       const v = (e.target as HTMLInputElement).value
                       try { await askAgent(v); setNote('handed to the agent'); await refresh() }
                       catch (err) { setError((err as Error).message) }
                       ;(e.target as HTMLInputElement).value = ''
                     }} />
            </div>
            <p className="tiny">Anything the MCP only reaches — the gpt-image flare node, saved
              workflows, batch submits. Runs as a real Hermes turn.</p>
          </section>

          <section className="panel">
            <div className="panel-head"><span className="tag">WORKFLOWS</span>
              <span className="muted">run a recipe</span>
            </div>
            <div className="scroller">
              {workflows.map((w) => (
                <div key={w.id} className="wf">
                  <div className="wfline">
                    <b>{w.name}</b>
                    <span className="wfm">{w.model}</span>
                  </div>
                  {w.notes && <div className="wfnote">{w.notes}</div>}
                  <div className="wfrow">
                    <input placeholder="subject (optional)" value={wfSubject}
                           onChange={(e) => setWfSubject(e.target.value)} />
                    <button className="mini" onClick={async () => {
                      try {
                        const r = await runWorkflow(w.id, wfSubject, 1)
                        setNote(`running ${w.name} · ${r.credits} credits left`)
                        await refresh()
                      } catch (e) { setError((e as Error).message) }
                    }}>RUN</button>
                    {!w.builtin && (
                      <button className="mini danger" onClick={async () => {
                        await deleteWorkflow(w.id); await refresh()
                      }}>×</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><span className="tag">MODS</span>
              <span className="muted">{mods.filter((m) => m.status === 'built-in').length} built in</span>
            </div>
            <div className="scroller">
              {mods.map((m) => (
                <div key={m.id} className={`mod ${m.status}`}>
                  <div className="modline">
                    <span className={`dot ${m.status === 'ready' || m.status === 'built-in' ? 'done'
                      : m.status === 'needs-key' ? 'running' : 'idle'}`} />
                    <b>{m.name}</b>
                    <span className="modstatus">{m.status}</span>
                  </div>
                  <div className="modwhat">{m.what}</div>
                  {m.missing?.length ? <div className="modneed">needs {m.missing.join(', ')}</div> : null}
                  {m.run ? <code className="modrun">{m.run}</code> : null}
                  {m.verified ? <div className="modok">✓ {m.verified}</div> : null}
                </div>
              ))}
            </div>
          </section>

          <Jobs jobs={jobs} onPick={setPreview} />
        </div>
      </div>
    </div>
  )
}
