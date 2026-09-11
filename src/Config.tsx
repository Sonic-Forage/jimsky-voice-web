import { useEffect, useState } from 'react'
import Orb from './Orb'
import {
  deleteWorkflow, fetchComfyPresets, fetchMods, fetchSettings, fetchTemplateJson,
  fetchTemplates, fetchWorkflows, saveSettings, testComfy,
  type ComfyPreset, type ComfyProbe, type HudMod, type HudSettings, type HudTemplate,
  type HudWorkflow,
} from './lib/hud'

/**
 * The config screen: the "make it my machine" half. Connections (including your own ComfyUI),
 * defaults, which panels exist, and the whole official Comfy template catalogue to raid.
 */

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head"><span className="tag">{title}</span>
        {hint && <span className="muted">{hint}</span>}
      </div>
      <div className="scroller">{children}</div>
    </section>
  )
}

export default function Config({ accent, onAccent }: { accent: string; onAccent: (a: string) => void }) {
  const [s, setS] = useState<HudSettings | null>(null)
  const [presets, setPresets] = useState<ComfyPreset[]>([])
  const [probe, setProbe] = useState<ComfyProbe | null>(null)
  const [probing, setProbing] = useState(false)
  const [tpl, setTpl] = useState<HudTemplate[]>([])
  const [tplCount, setTplCount] = useState(0)
  const [cats, setCats] = useState<string[]>([])
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const [mods, setMods] = useState<HudMod[]>([])
  const [flows, setFlows] = useState<HudWorkflow[]>([])
  const [json, setJson] = useState<{ name: string; text: string } | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const [st, pr, md, wf, tp] = await Promise.all([
          fetchSettings(), fetchComfyPresets(), fetchMods(), fetchWorkflows(), fetchTemplates('', 400),
        ])
        setS(st.settings)
        setPresets(pr.presets)
        setMods(md.mods)
        setFlows(wf.workflows)
        setTpl(tp.templates); setTplCount(tp.count); setCats(tp.categories)
      } catch (e) { setNote((e as Error).message) }
    })()
  }, [])

  const patch = async (delta: Partial<HudSettings>) => {
    try {
      const r = await saveSettings(delta)
      setS(r.settings)
      setNote('saved')
    } catch (e) { setNote((e as Error).message) }
  }

  const search = async (text: string, category: string) => {
    try {
      const tp = await fetchTemplates(text, 400)
      setTpl(category ? tp.templates.filter((t) => t.category === category) : tp.templates)
      setTplCount(tp.count); setCats(tp.categories)
    } catch (e) { setNote((e as Error).message) }
  }

  return (
    <div className="config">
      <div className="config-grid">
        <Section title="CONNECTIONS" hint="where things run">
          <div className="row">
            <span className="tiny">COMFYUI ENDPOINT</span>
          </div>
          <div className="presets">
            {presets.map((p) => (
              <button key={p.id} className={`tchip ${(s?.comfy_endpoint ?? '') === p.url ? 'on' : ''}`}
                      title={p.note}
                      onClick={() => { patch({ comfy_endpoint: p.url, comfy_endpoint_label: p.label }); setProbe(null) }}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="row">
            <input className="mini-input grow" placeholder="http://host:8188"
                   value={s?.comfy_endpoint ?? ''}
                   onChange={(e) => setS(s ? { ...s, comfy_endpoint: e.target.value } : s)} />
            <button className="mini" disabled={probing} onClick={async () => {
              if (!s) return
              setProbing(true); setProbe(null)
              try { await patch({ comfy_endpoint: s.comfy_endpoint }); setProbe(await testComfy(s.comfy_endpoint)) }
              catch (e) { setNote((e as Error).message) }
              setProbing(false)
            }}>{probing ? '…' : 'TEST'}</button>
          </div>
          {probe && (
            <p className={probe.ok ? 'ok' : 'err'}>
              {probe.ok
                ? `✓ ${probe.device || 'device'} · ${probe.comfyui_version || ''} · VRAM ${probe.vram_free_gb ?? '?'}/${probe.vram_total_gb ?? '?'} GB · nodes ${probe.nodes ?? '?'}`
                : `✗ ${probe.detail}`}
            </p>
          )}
          <p className="tiny">Empty means Comfy Cloud through the CLI (which is what the Studio uses
            today). Pointing this at your own ComfyUI is for free local runs.</p>

          <div className="row"><span className="tiny">LIVEKIT URL</span></div>
          <input className="mini-input wide" value={s?.livekit_url ?? ''} readOnly />
          <div className="row"><span className="tiny">MEDIA HOST</span></div>
          <input className="mini-input wide" value={s?.media_base ?? ''} readOnly />
        </Section>

        <Section title="DEFAULTS" hint="how it behaves">
          <div className="row"><span className="tiny">ACCENT</span>
            {['teal', 'magenta', 'amber'].map((a) => (
              <button key={a} className={`tchip ${accent === a ? 'on' : ''}`}
                      onClick={() => { onAccent(a); patch({ accent: a as HudSettings['accent'] }) }}>{a}</button>
            ))}
          </div>
          <div className="row"><span className="tiny">DEFAULT BATCH</span>
            <input className="mini-input" type="number" min={1} max={8} value={s?.default_batch ?? 1}
                   onChange={(e) => patch({ default_batch: Number(e.target.value) })} />
          </div>
          <div className="row">
            <button className={`tchip ${s?.new_stack_only ? 'on' : ''}`}
                    onClick={() => patch({ new_stack_only: !s?.new_stack_only })}>
              NEW STACK ONLY {s?.new_stack_only ? 'ON' : 'OFF'}
            </button>
            <button className={`tchip ${s?.auto_publish ? 'on' : ''}`}
                    onClick={() => patch({ auto_publish: !s?.auto_publish })}>
              AUTO-PUBLISH TO STAGE {s?.auto_publish ? 'ON' : 'OFF'}
            </button>
          </div>
          <div className="row"><span className="tiny">CHAT</span>
            {(['float', 'column'] as const).map((d) => (
              <button key={d} className={`tchip ${s?.chat_dock === d ? 'on' : ''}`}
                      onClick={() => patch({ chat_dock: d })}>{d}</button>
            ))}
          </div>
          <div className="orb-row">
            <Orb state="listening" accent={accent} size={150} />
            <p className="tiny">Reactive orb (three.js). State-driven: idle, listening, thinking,
              speaking — readable across a room.</p>
          </div>
        </Section>

        <Section title="TEMPLATE LIBRARY" hint={`${tplCount} official templates`}>
          <div className="row">
            <input className="mini-input grow" placeholder="search 629 templates"
                   value={q} onChange={(e) => { setQ(e.target.value); void search(e.target.value, cat) }} />
          </div>
          <div className="presets">
            <button className={`tchip ${cat === '' ? 'on' : ''}`} onClick={() => { setCat(''); void search(q, '') }}>all</button>
            {cats.map((c) => (
              <button key={c} className={`tchip ${cat === c ? 'on' : ''}`}
                      onClick={() => { setCat(c); void search(q, c) }}>{c}</button>
            ))}
          </div>
          <div className="tpllist">
            {tpl.slice(0, 120).map((t) => (
              <div key={t.name} className="tplrow">
                <div className="tpltitle">{t.title}</div>
                <div className="tplmeta">{t.category}{t.media ? ` · ${t.media}` : ''}{t.models?.length ? ` · ${t.models.slice(0, 3).join(', ')}` : ''}</div>
                {t.description ? <div className="tpldesc">{t.description}</div> : null}
                <div className="tplrow-actions">
                  <button className="mini" onClick={async () => {
                    try {
                      const r = await fetchTemplateJson(t.name)
                      setJson({ name: t.name, text: JSON.stringify(r.workflow, null, 1).slice(0, 6000) })
                    } catch (e) { setNote((e as Error).message) }
                  }}>VIEW JSON</button>
                  {t.tutorial && (
                    <a className="mini linky" href={t.tutorial} target="_blank" rel="noreferrer">TUTORIAL</a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>

        <div className="config-right">
          <Section title="WORKFLOWS" hint={`${flows.length} saved`}>
            {flows.map((w) => (
              <div key={w.id} className="wf">
                <div className="wfline"><b>{w.name}</b><span className="wfm">{w.model}</span></div>
                {!w.builtin && (
                  <button className="mini danger" onClick={async () => {
                    await deleteWorkflow(w.id); setFlows((f) => f.filter((x) => x.id !== w.id))
                  }}>delete</button>
                )}
              </div>
            ))}
          </Section>
          <Section title="MODS" hint={`${mods.length} available`}>
            {mods.map((m) => (
              <div key={m.id} className={`mod ${m.status}`}>
                <div className="modline"><b>{m.name}</b><span className="modstatus">{m.status}</span></div>
                <div className="modwhat">{m.what}</div>
              </div>
            ))}
          </Section>
        </div>
      </div>

      {json && (
        <div className="preview" onClick={() => setJson(null)} role="button" tabIndex={0}>
          <pre className="jsonview">{json.text}</pre>
          <button className="mini" onClick={() => setJson(null)}>CLOSE</button>
          <span className="tiny preview-hint">{json.name}.json — click anywhere to close</span>
        </div>
      )}
      {note && <div className="confignote">{note}</div>}
    </div>
  )
}
