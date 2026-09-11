import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  askAgent, browseUrl, createJobs, fetchCatalog, fetchJobs, getKey, redeemCode, setKey,
  type Catalog, type HudJob, type HudModel,
} from './lib/hud'

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

function ModelPicker({ models, value, onChange, onTemplate }: {
  models: HudModel[]
  value: string
  onChange: (alias: string) => void
  onTemplate: (category: string) => void
}) {
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const by: Record<string, HudModel[]> = {}
    for (const m of models) {
      if (q && !`${m.alias} ${m.partner} ${m.category}`.toLowerCase().includes(q.toLowerCase())) continue
      ;(by[m.category] ||= []).push(m)
    }
    return by
  }, [models, q])
  return (
    <section className="panel">
      <div className="panel-head"><span className="tag">MODEL</span>
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

  const refresh = useCallback(async () => {
    try {
      const [c, j] = await Promise.all([fetchCatalog(), fetchJobs()])
      setCat(c)
      setJobs(j.jobs)
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
        <ModelPicker
          models={cat?.models ?? []}
          value={model}
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

          <Jobs jobs={jobs} onPick={setPreview} />
        </div>
      </div>
    </div>
  )
}
