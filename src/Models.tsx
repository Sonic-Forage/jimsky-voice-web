// MODELS — pick the brain, not the app.
//
// Hermes is provider-agnostic, so the studio does not have to be loyal to one model:
// luna is the voice agent's own backend, deepseek-flash is the default workhorse, the
// open-weights shelf is the fallback when a bill must stay at zero, and the RunPod
// Ollama pods are where a fully private model would run.
//
// The comparison is not a vibe check. It runs the same prompt through several models
// at once and reports measured latency, token counts and cost, with the source of every
// price printed underneath. Where a price is not published, it says so rather than
// guessing.

import { useCallback, useEffect, useState } from 'react'
import { fetchRouterModels, routerCompare, type RouterModel, type RouterResult } from './lib/hud'

const TIERS: { key: string; label: string; blurb: string }[] = [
  { key: 'frontier', label: 'FRONTIER', blurb: 'the expensive brains. luna is what the voice agent runs on.' },
  { key: 'fast', label: 'FAST + CHEAP', blurb: 'the everyday workhorses. this is where most calls should land.' },
  { key: 'open', label: 'OPEN WEIGHTS', blurb: 'no vendor lock. the honest test of whether we still need closed models.' },
  { key: 'free', label: 'FREE TIER', blurb: 'listed at $0 per token. for testing without spending anything.' },
]

// The ACTUAL tools wired into the voice agent (from apps/voice/vex-agent/agent.py, ALL_TOOLS).
// This used to be an aspirational list; these are the ten that exist in the code.
const AGENT_TOOLS = [
  { k: 'IMG', n: 'make_an_image', v: 'describe a picture out loud and it renders, then lands on the stage' },
  { k: 'VOICE', n: 'switch_voice', v: 'change its own voice mid-conversation (cascade engine only)' },
  { k: 'WEB', n: 'browse_the_web', v: 'opens a real Chromium on a page and screenshots it to the stage' },
  { k: 'BOX', n: 'run_on_my_machine', v: 'drives the full agent: shell, files, services, generation' },
  { k: 'STUDIO', n: 'query_studio_projects', v: 'reads the studio\u2019s live project list' },
  { k: 'CAST', n: 'query_studio_characters', v: 'reads the character universe roster' },
  { k: 'STATS', n: 'query_studio_info', v: 'studio stats and figures' },
  { k: 'POD', n: 'gpu_pod_status', v: 'is the GPU box up, and what is it costing' },
  { k: 'POD', n: 'gpu_pod_boot', v: 'boots the ComfyUI GPU pod when heavy work is needed' },
  { k: 'POD', n: 'gpu_pod_terminate', v: 'kills the pod so billing stops' },
]

export default function Models() {
  const [models, setModels] = useState<RouterModel[]>([])
  const [free, setFree] = useState<RouterModel[]>([])
  const [hosted, setHosted] = useState<{ id: string; label: string; url: string; status: string; note: string }[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [picked, setPicked] = useState<string[]>(['deepseek-flash', 'gpt-5.6-luna'])
  const [prompt, setPrompt] = useState(
    'In exactly two sentences: what makes a rooftop at night feel alive? Be specific. No adjectives like beautiful.')
  const [maxTokens, setMaxTokens] = useState(900)
  const [busy, setBusy] = useState(false)
  const [run, setRun] = useState<{
    results: RouterResult[]; wall_ms: number; total_cost_usd: number; cost_known: boolean
  } | null>(null)

  const load = useCallback(() => {
    fetchRouterModels()
      .then(d => { setModels(d.models); setFree(d.free); setHosted(d.self_hosted); setErr(null) })
      .catch(e => setErr(String(e.message ?? e)))
  }, [])
  useEffect(load, [load])

  const toggle = (id: string) =>
    setPicked(p => p.includes(id) ? p.filter(x => x !== id) : (p.length >= 4 ? p : [...p, id]))

  const go = async () => {
    setBusy(true); setErr(null)
    try {
      setRun(await routerCompare(prompt, picked, maxTokens))
    } catch (e) { setErr(String((e as Error).message ?? e)) } finally { setBusy(false) }
  }

  // verdicts measured from the run itself, never asserted
  const fastest = run?.results.filter(r => r.ok).sort((a, b) => (a.latency_ms ?? 9e9) - (b.latency_ms ?? 9e9))[0]
  const cheapest = run?.results.filter(r => r.ok && r.cost_usd !== null)
    .sort((a, b) => (a.cost_usd ?? 9e9) - (b.cost_usd ?? 9e9))[0]

  return (
    <div className="rt">
      <style>{`
        .rt { display: grid; gap: 14px; }
        .rt h2 { font-size: 15px; letter-spacing: .28em; color: var(--ink); margin: 0 0 2px; }
        .rt .blurb { font-size: 12px; color: var(--dim); letter-spacing: .04em; }
        .rt-sec { border: 1px solid var(--line); background: var(--panel); padding: 12px 14px; }
        .rt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 9px; margin-top: 10px; }
        .rt-card { border: 1px solid var(--line); background: var(--panel2); padding: 10px 11px; cursor: pointer;
          transition: border-color .12s, background .12s; }
        .rt-card:hover { border-color: var(--line-hot); }
        .rt-card.on { border-color: var(--accent); background: rgba(75,227,200,.07); }
        .rt-card.off { opacity: .5; cursor: not-allowed; }
        .rt-name { font-size: 13px; letter-spacing: .1em; color: var(--ink); display: flex; justify-content: space-between; gap: 8px; }
        .rt-role { font-size: 10.5px; letter-spacing: .16em; color: var(--accent); margin-top: 5px; text-transform: uppercase; }
        .rt-note { font-size: 11.5px; color: var(--dim); margin-top: 7px; line-height: 1.45; }
        .rt-meta { font-size: 10.5px; color: var(--dimmer); margin-top: 8px; font-family: var(--mono); display: flex; flex-wrap: wrap; gap: 10px; }
        .rt-tick { width: 7px; height: 7px; border-radius: 50%; background: var(--line-hot); flex: 0 0 auto; margin-top: 5px; }
        .rt-tick.on { background: var(--accent); }
        .rt-tick.miss { background: var(--warn); }
        .rt-compose { display: grid; gap: 9px; border: 1px solid var(--line-hot); background: var(--panel); padding: 12px 14px; }
        .rt-compose textarea { width: 100%; min-height: 68px; background: var(--bg); color: var(--ink);
          border: 1px solid var(--line); padding: 9px 10px; font-family: var(--mono); font-size: 12.5px; resize: vertical; }
        .rt-runrow { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .rt-run { background: var(--accent); color: #04120f; border: 0; padding: 9px 18px; letter-spacing: .18em;
          font-size: 12px; cursor: pointer; font-family: var(--mono); }
        .rt-run:disabled { opacity: .45; cursor: default; }
        .rt-out { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; margin-top: 4px; }
        .rt-ans { border: 1px solid var(--line); background: var(--panel2); padding: 11px 12px; }
        .rt-ans.win { border-color: var(--accent); }
        .rt-ans.bad { border-color: var(--accent2); }
        .rt-anshead { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 8px; }
        .rt-anstext { font-size: 12.5px; line-height: 1.6; color: var(--ink); white-space: pre-wrap; }
        .rt-stats { display: flex; flex-wrap: wrap; gap: 9px; font-family: var(--mono); font-size: 10.5px;
          color: var(--dim); margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--line); }
        .rt-verdict { font-size: 11.5px; color: var(--dim); line-height: 1.6; }
        .rt-cap { display: grid; grid-template-columns: repeat(auto-fill, minmax(258px, 1fr)); gap: 7px; margin-top: 10px; }
        .rt-caprow { border: 1px solid var(--line); background: var(--panel2); padding: 8px 10px; display: flex; gap: 9px; }
        .rt-capk { font-size: 10.5px; letter-spacing: .18em; color: var(--accent); flex: 0 0 86px; }
        .rt-capv { font-size: 11.5px; color: var(--dim); line-height: 1.45; }
        .rt-off { font-size: 11.5px; color: var(--warn); }
        .rt-warn { font-size: 11px; letter-spacing: .04em; color: var(--warn); border-left: 2px solid var(--warn);
          padding: 5px 0 5px 9px; margin-bottom: 9px; line-height: 1.5; }
      `}</style>

      <div className="rt-sec">
        <h2>THE ROUTER</h2>
        <div className="blurb">
          One agent, many brains. Pick up to four, give them the same prompt, and compare what actually came back —
          measured latency, token counts and cost. Nothing here is an estimate.
        </div>
        {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}

        {TIERS.map(t => {
          const list = t.key === 'free' ? free : models.filter(m => m.tier === t.key)
          if (!list.length) return null
          return (
            <div key={t.key} style={{ marginTop: 14 }}>
              <div className="grouplabel">{t.label} <span className="blurb" style={{ letterSpacing: 0 }}>· {t.blurb}</span></div>
              <div className="rt-grid">
                {list.map(m => {
                  const on = picked.includes(m.id)
                  const full = !on && picked.length >= 4
                  return (
                    <div key={m.id} className={`rt-card${on ? ' on' : ''}${full ? ' off' : ''}`}
                         onClick={() => !full && toggle(m.id)} title={m.id}>
                      <div className="rt-name">
                        <span>{m.label}</span>
                        <span className={`rt-tick${m.key_present === false ? ' miss' : (on ? ' on' : '')}`} />
                      </div>
                      <div className="rt-role">{m.role}</div>
                      <div className="rt-note">{m.note}</div>
                      <div className="rt-meta">
                        <span>{m.provider}</span>
                        {m.context ? <span>{(m.context / 1000).toFixed(0)}k ctx</span> : null}
                        {m.price_per_mtok_in !== null && m.price_per_mtok_in !== undefined
                          ? <span>${m.price_per_mtok_in}/${m.price_per_mtok_out} per Mtok</span>
                          : <span>price unpublished</span>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}

        {hosted.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className="grouplabel">SELF-HOSTED · our own silicon</div>
            {hosted.map(h => (
              <div key={h.id} className="rt-off" style={{ marginTop: 6 }}>
                {h.label} — {h.status.toUpperCase()} · {h.note}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rt-compose">
        <div className="grouplabel">SAME PROMPT, DIFFERENT BRAINS — {picked.length}/4 SELECTED</div>
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} spellCheck={false} />
        <div className="rt-runrow">
          <button className="rt-run" disabled={busy || !picked.length || !prompt.trim()} onClick={go}>
            {busy ? 'RUNNING…' : 'RUN COMPARISON'}
          </button>
          <label className="muted" style={{ fontSize: 11.5 }}>
            max tokens <input className="mini-input" style={{ width: 74, marginLeft: 6 }} type="number"
              value={maxTokens} onChange={e => setMaxTokens(Number(e.target.value) || 900)} />
          </label>
          <span className="muted" style={{ fontSize: 11.5 }}>
            picked: {picked.join(' · ') || 'none'}
          </span>
        </div>
      </div>

      {run && (
        <div className="rt-sec">
          <h2>RESULTS</h2>
          <div className="rt-verdict">
            {run.results.length} model{run.results.length === 1 ? '' : 's'} ran in parallel — wall clock {run.wall_ms} ms
            · total ${run.total_cost_usd.toFixed(6)}
            {!run.cost_known && ' (some prices are unpublished, so this total is a floor)'}
            <br />
            {fastest && <>fastest: <b>{fastest.label}</b> at {fastest.latency_ms} ms · </>}
            {cheapest ? <>cheapest: <b>{cheapest.label}</b> at ${(cheapest.cost_usd ?? 0).toFixed(6)} per call</>
                      : <>no model in this run has a published price</>}
          </div>
          <div className="rt-out">
            {run.results.map(r => (
              <div key={r.id} className={`rt-ans${r.ok ? (r.id === fastest?.id ? ' win' : '') : ' bad'}`}>
                <div className="rt-anshead">
                  <span className="chipmodel">{r.label}</span>
                  <span className="tiny muted">{r.id}</span>
                </div>
                {r.from_reasoning && (
                  <div className="rt-warn">
                    no visible answer came back — this model ran out of output budget inside its reasoning,
                    so what follows is its thinking trace, not its answer. raise max tokens.
                  </div>
                )}
                {r.ok
                  ? <div className="rt-anstext">{r.text.trim()}</div>
                  : <div className="err">{r.error}</div>}
                <div className="rt-stats">
                  <span>{r.latency_ms} ms</span>
                  <span>{r.tokens_in}→{r.tokens_out} tok</span>
                  <span>{r.cost_usd !== null ? `$${r.cost_usd.toFixed(6)}` : 'cost n/a'}</span>
                  {r.truncated && <span style={{ color: 'var(--warn)' }}>TRUNCATED at cap</span>}
                  {r.from_reasoning && <span style={{ color: 'var(--warn)' }}>from reasoning field</span>}
                </div>
                <div className="tiny muted" style={{ marginTop: 6 }}>price: {r.price_source}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rt-sec">
        <h2>ONE BRAIN, MANY HANDS</h2>
        <div className="blurb">
          Whichever model answers, the agent drives the same {AGENT_TOOLS.length} tools. This list is read from
          the agent itself — not a plan. The voice worker is stopped right now, so these are wired but not
          listening until it is started.
        </div>
        <div className="rt-cap">
          {AGENT_TOOLS.map(t => (
            <div key={t.n} className="rt-caprow">
              <span className="rt-capk">{t.k}</span>
              <span className="rt-capv">
                <span className="mono" style={{ color: 'var(--accent)' }}>{t.n}</span>
                <br />{t.v}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
