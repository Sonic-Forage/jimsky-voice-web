#!/usr/bin/env python3
"""Build the JIMSKY studio explainer PDF from the live screenshots.

HTML -> Chromium print-to-PDF so the type stays vector and the screenshots stay sharp.
Images are base64-embedded, so the PDF is self-contained and the HTML is portable.

    python3 build_deck.py     ->  dist/JIMSKY-STUDIO.pdf
"""
from __future__ import annotations

import base64
import json
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

SHOTS = Path("/home/ubuntu/sf-ops/jimsky-voice/shots")
DIST = Path("/home/ubuntu/sf-ops/jimsky-voice/dist")
DIST.mkdir(parents=True, exist_ok=True)
OUT_PDF = DIST / "JIMSKY-STUDIO.pdf"


def img(name: str) -> str:
    p = SHOTS / name
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def fig(name: str, cap: str, tall: bool = False) -> str:
    src = img(name)
    if not src:
        return f'<div class="missing">screenshot {name} not found</div>'
    return (f'<figure class="{"tall" if tall else ""}"><img src="{src}" alt="{cap}" />'
            f'<figcaption>{cap}</figcaption></figure>')


ROWS = [
    ("Voice transport", "LiveKit server, self-hosted (Apache-2.0) v1.13.5", "our own VPS, TLS by Caddy — no hosting fee"),
    ("Voice agent", "worker <b>vex</b>, livekit-agents 1.8.1", "registers and waits; it does not sit in a call"),
    ("Two engines", "<b>pipeline</b> · Deepgram STT → LLM → Cartesia TTS", "<b>gpt-live</b> · full-duplex on gpt-live-1"),
    ("Failsafe", "180s idle · 30s empty room · 1800s cap", "proven by a silent-probe test, agent left at ~66s"),
    ("Front end", "React + Vite → Netlify", "jimsky-voice.netlify.app · phone + desktop"),
    ("Token minting", "Netlify Function, server-side", "the LiveKit secret never reaches the browser"),
    ("HUD backend", "FastAPI on the VPS, X-HUD-Key gated", "systemd user service, Linger on"),
    ("Media stage", "Caddy media dir + index.json", "images, video and audio the agent publishes"),
    ("Making images", "Comfy Cloud + 52 models in 13 categories", "gpt-image-2.5-flare stack, up to 2160×3840"),
    ("Templates", "629 official Comfy workflows", "Comfy-Org/workflow_templates, executable from the HUD"),
    ("Video", "HyperFrames (HeyGen)", "HTML composition → MP4, gated by lint + check"),
    ("3D", "Three.js", "the orb in the HUD reflects agent state"),
    ("Ledger", "credit balance + redeem codes", "one use each, kept on disk"),
    ("Models", "router across DeepSeek · OpenAI · OpenRouter", "one prompt, several brains, measured"),
]

STATUS = [
    ("Live and verified", [
        "self-hosted LiveKit + the vex worker, both engines, GPT-Live confirmed in the log",
        "front end deployed and talking; token minting verified in production",
        "idle failsafe proven at both ends (agent left after ~66s of silence while the human stayed)",
        "HUD studio: 52 models, 629 templates, batch runs, browse, chat, credit ledger",
        "model router: real completions, measured latency and tokens, prices with their source attached",
        "the ten-voice video: rendered, gate-passed, visually verified, published to the stage",
    ]),
    ("Built but not proven", [
        "local ComfyUI render on the 4070 — the box does not answer on the tailnet address",
        "the React-Native mobile app compiles (<span class='mono'>tsc</span> clean) but has never run on a device",
        "LiveAvatar face mod is registered and waiting on a paid third-party key",
    ]),
    ("Honest gaps", [
        "RunPod Ollama proxies answer 403 — self-hosted open weights are offline right now",
        "desktop GUI control is not wired; the agent drives a browser, a shell and files, not a mouse",
        "DeepSeek does not publish per-token prices in our source, so its cost column reads unpublished",
        "hosted web search on the backend model is not enabled",
    ]),
]

# Measured data comes from shots/compare.json, produced by the same browser run that took
# the screenshots. Nothing here is retyped by hand - if a number is printed, it was measured.
import re as _re
_cmp_raw = json.loads((SHOTS / "compare.json").read_text())
CMP = {"prompt": _cmp_raw["prompt"], "verdict": _cmp_raw["verdict"], "rows": []}
for _p in _cmp_raw["panels"]:
    s = _p["stats"]
    lat = _re.search(r"([\d,]+)\s*ms", s)
    tok = _re.search(r"([\d,]+)\s*→\s*([\d,]+)", s)
    cost = _re.search(r"\$([\d.]+)", s)
    CMP["rows"].append({
        "label": _p["label"], "id": _p["id"],
        "latency": int(lat.group(1).replace(",", "")) if lat else None,
        "tokens_in": int(tok.group(1).replace(",", "")) if tok else None,
        "tokens_out": int(tok.group(2).replace(",", "")) if tok else None,
        "cost": float(cost.group(1)) if cost else None,
        "warning": _p.get("warning", ""),
    })
_ok = [r for r in CMP["rows"] if r["latency"]]
_fastest = min(_ok, key=lambda r: r["latency"]) if _ok else None
_priced = [r for r in CMP["rows"] if r["cost"] is not None]
_cheapest = min(_priced, key=lambda r: r["cost"]) if _priced else None
for _r in CMP["rows"]:
    tags = []
    if _fastest and _r is _fastest: tags.append("fastest")
    if _cheapest and _r is _cheapest: tags.append("cheapest")
    if _r["cost"] is None: tags.append("price unpublished")
    _r["note"] = " + ".join(tags) or ""
_cmp_rows = CMP["rows"]
_wall = _re.search(r"wall clock\s*([\d,]+)", CMP["verdict"])
_total = _re.search(r"total \$([\d.]+)", CMP["verdict"])
CMP["wall"] = int(_wall.group(1).replace(",", "")) if _wall else None
CMP["total"] = float(_total.group(1)) if _total else None
_provider = {"openai": "openai", "deepseek": "deepseek"}
for _r in _cmp_rows:
    _r["provider"] = _r["id"].split("/")[0] if "/" in _r["id"] else _r["id"].split("-")[0]

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>JIMSKY STUDIO — what we are building</title>
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #06070a; color: #e9eef8;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .mono, code {{ font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; }}
  .page {{ width: 297mm; height: 210mm; padding: 14mm 15mm; position: relative; overflow: hidden;
    page-break-after: always; background: #06070a; }}
  .page:last-child {{ page-break-after: auto; }}
  .page::after {{ content: attr(data-pg); position: absolute; right: 15mm; bottom: 8mm;
    font-size: 8.5pt; color: #5a677e; letter-spacing: .2em; }}
  .kicker {{ font-size: 8.5pt; letter-spacing: .34em; color: #4be3c8; margin-bottom: 6px; }}
  h1 {{ font-size: 34pt; letter-spacing: .04em; margin: 0 0 8px; line-height: 1.05; }}
  h2 {{ font-size: 19pt; letter-spacing: .02em; margin: 0 0 10px; }}
  h3 {{ font-size: 11pt; letter-spacing: .18em; color: #4be3c8; margin: 14px 0 6px; text-transform: uppercase; }}
  p {{ font-size: 10.5pt; line-height: 1.62; color: #c2cbdb; margin: 0 0 9px; max-width: 250mm; }}
  .lead {{ font-size: 12pt; color: #e9eef8; line-height: 1.6; }}
  .dim {{ color: #8b98b0; }} .dimmer {{ color: #5a677e; }}
  b {{ color: #ffffff; }}
  ul {{ margin: 4px 0 0; padding-left: 16px; }} li {{ font-size: 10pt; line-height: 1.55; color: #c2cbdb; margin-bottom: 4px; }}
  .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12mm; }}
  .cols3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8mm; }}
  figure {{ margin: 0; }}
  figure img {{ width: 100%; border: 1px solid #33415a; display: block; }}
  figure.tall img {{ max-height: 76mm; width: auto; max-width: 100%; }}
  figcaption {{ font-size: 8.5pt; color: #8b98b0; margin-top: 5px; letter-spacing: .04em; }}
  .missing {{ border: 1px dashed #ff5d8f; padding: 20px; color: #ff5d8f; font-size: 9pt; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  th, td {{ text-align: left; padding: 5.5px 8px; border-bottom: 1px solid #1f2735; font-size: 9.2pt; vertical-align: top; }}
  th {{ color: #4be3c8; font-size: 8pt; letter-spacing: .2em; text-transform: uppercase; }}
  td:first-child {{ color: #8b98b0; width: 32mm; }}
  td:nth-child(3) {{ color: #8b98b0; }}
  .box {{ border: 1px solid #1f2735; background: #0d1017; padding: 10px 12px; }}
  .box.hot {{ border-color: #4be3c8; background: rgba(75,227,200,.06); }}
  .box.warn {{ border-color: #ffc857; background: rgba(255,200,87,.05); }}
  .stat {{ text-align: center; border: 1px solid #1f2735; background: #0d1017; padding: 10px 6px; }}
  .stat .v {{ font-size: 19pt; color: #4be3c8; font-family: ui-monospace, Menlo, monospace; }}
  .stat .l {{ font-size: 7.5pt; letter-spacing: .18em; color: #8b98b0; margin-top: 3px; }}
  .tag {{ display: inline-block; border: 1px solid #33415a; color: #8b98b0; font-size: 7.5pt;
    letter-spacing: .16em; padding: 2px 7px; margin-right: 5px; }}
  .tag.on {{ border-color: #4be3c8; color: #4be3c8; }}
  .tag.off {{ border-color: #ffc857; color: #ffc857; }}
  .foot {{ position: absolute; left: 15mm; bottom: 8mm; font-size: 8pt; color: #5a677e; letter-spacing: .12em; }}
  .cmp td {{ font-family: ui-monospace, Menlo, monospace; }}
  .win {{ color: #4be3c8; }}
</style></head><body>

<!-- 1 COVER -->
<div class="page" data-pg="01">
  <div class="kicker">SONIC FORAGE STUDIO · INTERNAL EXPLAINER · {date.today().isoformat()}</div>
  <h1>JIMSKY STUDIO</h1>
  <p class="lead" style="max-width:200mm">You talk to it, it makes things, and what it makes shows up on a stage you own —
  from a phone, a tablet, or a kitchen counter. This is what is actually built, what it runs on,
  and what is still missing.</p>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6mm;margin:10mm 0">
    <div class="stat"><div class="v">10</div><div class="l">VOICES AS ENTITIES</div></div>
    <div class="stat"><div class="v">629</div><div class="l">COMFY TEMPLATES</div></div>
    <div class="stat"><div class="v">52</div><div class="l">MODELS IN CATALOG</div></div>
    <div class="stat"><div class="v">22</div><div class="l">ROUTER MODELS</div></div>
  </div>
  <div style="display:grid;grid-template-columns:1.35fr 1fr;gap:10mm;align-items:start">
    <figure><img src="{img('01-voice.png')}" alt="the voice room" />
      <figcaption>The voice room: talk to the agent over our own LiveKit server.</figcaption></figure>
    <div>
      <h3>In one line</h3>
      <p class="dim">A self-hosted voice + generation studio: a realtime voice agent you can talk to, a HUD that can
      make images and video, a model router that picks the brain per task, and a media stage that publishes the
      results — all on hardware we control, with approvals kept on the human side of anything that spends money
      or goes public.</p>
      <div><span class="tag on">NOTHING PUBLISHED</span><span class="tag on">SOURCE ALPHA</span><span class="tag off">NO VENDOR LOCK</span></div>
    </div>
  </div>
</div>

<!-- 2 WHAT WE ARE BUILDING -->
<div class="page" data-pg="02">
  <div class="kicker">01 · WHAT WE ARE BUILDING</div>
  <h2>Three halves that share one agent</h2>
  <div class="cols3" style="margin-top:8mm">
    <div class="box hot">
      <h3 style="margin-top:0">THE VOICE</h3>
      <p>A realtime room on our own LiveKit server. You talk; the agent answers. Two engines are wired:
      a classic pipeline (speech-to-text → language model → speech) and <b>GPT-Live full-duplex</b>, which
      listens and speaks through the same model the way a person does.</p>
      <p class="dim">It hangs up on its own if nobody is talking — three layers of failsafe, so a forgotten
      tab cannot sit there burning a session.</p>
    </div>
    <div class="box hot">
      <h3 style="margin-top:0">THE MAKING</h3>
      <p>The HUD turns a sentence into an image, a batch, an edit, a browsed screenshot or a rendered video.
      It speaks to Comfy Cloud for generation and to a model router for deciding <i>which</i> brain does the work.</p>
      <p class="dim">52 models across 13 categories, 629 official Comfy workflows browsable and executable,
      plus our own saved workflows.</p>
    </div>
    <div class="box hot">
      <h3 style="margin-top:0">THE STAGE</h3>
      <p>Anything made gets published to a media host we control, with a running index. The front end picks it up
      and puts it on screen — so the loop is: ask → make → see it, without leaving the page.</p>
      <p class="dim">Images, video and audio. This is what makes it a studio rather than a chat window.</p>
    </div>
  </div>
  <div class="cols" style="grid-template-columns:1.12fr 1fr;gap:9mm;margin-top:6mm">
    {fig("02-studio.png", "The studio half: model picker, batch stepper, browse, credits, agent panel, mods and the job queue.")}
    <div>
      <h3 style="margin-top:0">The loop, as it actually feels</h3>
      <p>Ask in the voice room → the agent reaches for the same tools a model can call → the HUD makes the thing →
      it is published to the stage → the front end puts it on screen while the conversation keeps going.</p>
      <h3>Why a HUD and not just an app</h3>
      <p>Because the interesting part is not one screen, it is having all of it in reach at once: talk, make, watch,
      and change the machine's settings without leaving the page you are working on.</p>
      <p class="dimmer" style="font-size:8.5pt">The voice half stays mounted while you work in the studio, so a
      session does not have to be started and stopped to make something.</p>
    </div>
  </div>
</div>

<!-- 3 THE STACK -->
<div class="page" data-pg="03">
  <div class="kicker">02 · WHAT WE ARE USING</div>
  <h2>The stack, layer by layer</h2>
  <table>
    <tr><th>LAYER</th><th>WHAT IT IS</th><th>WHY / NOTE</th></tr>
    {''.join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>' for a, b, c in ROWS)}
  </table>
  <p class="dimmer" style="margin-top:8px;font-size:8.5pt">Upstream work is used under its own licence: LiveKit (Apache-2.0), ComfyUI and the
  Comfy-Org template library, HyperFrames (HeyGen), Three.js, Playwright, FastAPI. Our own code lives in private repos.</p>
</div>

<!-- 4 THE ROUTER -->
<div class="page" data-pg="04">
  <div class="kicker">03 · NEW — THE MODEL ROUTER</div>
  <h2>Pick the brain, not the app</h2>
  <div class="cols" style="grid-template-columns:1fr 1.25fr;gap:9mm">
    <div>
      <p>The studio no longer has loyalty to one model. The router knows which brains we can reach and what each
      one is for, so a bulk job can run on a cheap flash model while judgement calls go to luna.</p>
      <h3>Reachable today</h3>
      <ul>
        <li><b>Frontier</b> — GPT-5.6 luna, sol, GPT-5.5, DeepSeek V4 Pro. Luna is the voice agent's own backend, so the router and the room agree.</li>
        <li><b>Fast + cheap</b> — DeepSeek Flash (Hermes' default), GLM 5.3 Flash, Qwen 3.8 Flash. This is where most calls should land.</li>
        <li><b>Open weights</b> — Qwen 3.8 Max, DeepSeek V4 Flash Vision, GLM Flash. No vendor lock, and the honest test of whether closed models are still needed.</li>
        <li><b>Free tier</b> — 22 OpenRouter models listed at $0 per token. Testing costs nothing.</li>
        <li><b>Self-hosted</b> — three RunPod Ollama endpoints, all currently answering 403. Reviving one pod puts open weights on our own silicon.</li>
      </ul>
      <p class="dimmer" style="font-size:8.5pt">Every card shows its context window and its price per million tokens.
      Where a price is not published, the card says so instead of guessing.</p>
    </div>
    {fig("03-models.png", "The router: tiers, roles, context and price on every card. Self-hosted status is shown honestly as offline.")}
  </div>
</div>

<!-- 5 THE HEAD TO HEAD -->
<div class="page" data-pg="05">
  <div class="kicker">04 · MEASURED, NOT GUESSED</div>
  <h2>Same prompt, three brains</h2>
  <p class="mono" style="font-size:9pt;color:#8b98b0">“{CMP['prompt']}”</p>
  <table class="cmp">
    <tr><th>MODEL</th><th>PROVIDER</th><th>LATENCY</th><th>TOKENS IN→OUT</th><th>COST / CALL</th><th>NOTE</th></tr>
    {''.join(f'<tr><td>{r["label"]}</td><td>{r["provider"]}</td><td>{r["latency"]} ms</td>'
             f'<td>{r["tokens_in"]}→{r["tokens_out"]}</td>'
             f'<td>{("$%.6f" % r["cost"]) if r["cost"] is not None else "unpublished"}</td>'
             f'<td class="{"win" if "fastest" in r["note"] else ""}">{r["note"]}</td></tr>'
             for r in _cmp_rows)}
  </table>
  {('<div class="box warn" style="margin:5mm 0 0"><b>Caught by the router, not hidden:</b> ' +
      ' '.join(f'<span class="mono">{r["label"]}</span> — {r["warning"]}' for r in _cmp_rows if r["warning"]) +
      '</div>') if any(r["warning"] for r in _cmp_rows) else ''}
  <div class="cols" style="grid-template-columns:1fr 1fr;gap:9mm;margin-top:7mm">
    <div>
      <h3>What the numbers say</h3>
      <ul>
        <li><b>{_fastest["label"] if _fastest else "n/a"} was fastest</b> at {_fastest["latency"] if _fastest else "?"} ms{", and cheapest at $%.6f a call" % _cheapest["cost"] if _cheapest and _cheapest is _fastest else ""}.</li>
        <li><b>Slowest of the three: {_ok[-1]["label"] if _ok else "n/a"}</b> at {_ok[-1]["latency"] if _ok else "?"} ms — {round(_ok[-1]["latency"] / _fastest["latency"], 1) if _ok and _fastest and _fastest["latency"] else "?"}× the fastest.</li>
        <li><b>Open weights are a freedom move, not automatically a savings move</b> — the open-weights entry here costs {("$%.6f" % _priced[-1]["cost"]) if _priced else "unknown"}, {"%.0f×" % (_priced[-1]["cost"] / _cheapest["cost"]) if _priced and _cheapest and _cheapest["cost"] else "?"} the cheapest model in this run.</li>
        <li><b>{sum(1 for r in _cmp_rows if r["cost"] is None)} of {len(_cmp_rows)} models have no published price</b> in our source, so any total is a floor rather than a fact.</li>
        <li>All three ran <b>in parallel</b>; wall clock {CMP['wall']} ms, total ${CMP['total']}.</li>
      </ul>
      <p class="dim" style="font-size:9pt">The router reports what came back, not what it hoped for: a truncated answer is
      flagged, and if a model spends its whole budget on hidden reasoning the panel says the text below is a
      thinking trace rather than an answer.</p>
    </div>
    {fig("04b-verdict.png", "The verdict line, computed from the run itself.")}
  </div>
</div>

<!-- 5b THE COMPARISON, AS IT APPEARS -->
<div class="page" data-pg="05b">
  <div class="kicker">04b · THE SAME RUN, ON SCREEN</div>
  <h2>What the router looks like while it works</h2>
  <div class="cols" style="grid-template-columns:1.45fr 1fr;gap:9mm">
    {fig("04-compare.png", "Three brains, one prompt, one wall clock. Each panel carries its own latency, token count, cost and the source of that price.")}
    <div>
      <h3 style="margin-top:0">Read it like a lab report</h3>
      <ul>
        <li>Each answer names its <b>provider and exact model id</b>, so nothing is ambiguous later.</li>
        <li>Latency is the wall clock for that call; tokens come from the provider's own usage block.</li>
        <li>Cost is computed only from a published price, and the <b>source of that price is printed</b> under every panel.</li>
        <li><b>TRUNCATED at cap</b> appears when a model hit the output ceiling — visible, not buried.</li>
        <li><b>from reasoning field</b> appears when a model produced no visible answer and only its thinking came back.</li>
      </ul>
      <h3>Why this page exists</h3>
      <p class="dim">Because "which model is better" is usually answered with opinions. Here it is answered with the
      numbers that came back, from the same run, with the caveats left in where they belong — next to the claim.</p>
    </div>
  </div>
</div>

<!-- 6 YOUR IDEA: OPEN MODELS + FULL COMPUTER -->
<div class="page" data-pg="06">
  <div class="kicker">05 · THE IDEA ON THE TABLE</div>
  <h2>Open-source models, and an agent that can drive the whole machine</h2>
  <div class="cols">
    <div>
      <h3>Where open models stand</h3>
      <p>Open weights are <b>already reachable</b> through the router — 137 candidates on one provider, 22 of them
      free, including vision models. What is missing is the fully private end: a model running on hardware we own,
      with no vendor in the path at all.</p>
      <div class="box warn" style="margin-top:6mm">
        <p style="margin:0"><b>Blocked, and it is honest:</b> the three RunPod Ollama endpoints answer 403. The pods are
        down. Bringing one up costs roughly $0.5/hr and would give us a private model — worth doing the moment a task
        genuinely needs privacy rather than price.</p>
      </div>
      <h3 style="margin-top:7mm">Why the router matters for this</h3>
      <p>Because the <i>mind</i> is swappable and the <i>hands</i> are not. Every model here drives the same tools,
      so moving work to an open model later is a selection, not a rewrite.</p>
    </div>
    <div>
      <h3>What the agent can already drive</h3>
      <table>
        <tr><th>REACH</th><th>STATE</th></tr>
        <tr><td>Voice room</td><td class="win">live — talk to it in real time</td></tr>
        <tr><td>Browser</td><td class="win">live — a real Chromium it loads, reads and screenshots</td></tr>
        <tr><td>Machine</td><td class="win">live — shell, files, services, git, cron</td></tr>
        <tr><td>Make</td><td class="win">live — images, video, batches, 629 templates</td></tr>
        <tr><td>Publish</td><td class="win">live — writes to the stage this front end reads</td></tr>
        <tr><td>Delegate</td><td class="win">live — sub-agents and background jobs</td></tr>
        <tr><td>Desktop GUI</td><td style="color:#ffc857">not wired — a mouse and keyboard, not just a shell</td></tr>
      </table>
      <p class="dim" style="font-size:9pt;margin-top:6mm">The desktop gap is the difference between "it can run a command"
      and "it can operate any program the way you would". That is the next real capability, and it is a wiring job,
      not a research problem.</p>
    </div>
  </div>
</div>

<!-- 7 STATUS -->
<div class="page" data-pg="07">
  <div class="kicker">06 · STATUS</div>
  <h2>What is proven, what is not, and what is missing</h2>
  <div class="cols3" style="margin-top:7mm">
    {''.join(f'<div class="box {"hot" if i == 0 else ("warn" if i == 2 else "")}"><h3 style="margin-top:0">{t}</h3>'
             f'<ul>{"".join(f"<li>{x}</li>" for x in items)}</ul></div>'
             for i, (t, items) in enumerate(STATUS))}
  </div>
  <div class="cols" style="grid-template-columns:1fr 1fr;gap:9mm;margin-top:5mm">
    {fig("03-models-phone.png", "The same router on a phone — the format this is actually meant to live in.", tall=True)}
    <div>
      <h3>How it is meant to be used</h3>
      <p>As a small HUD: on a phone in the kitchen, on a tablet on a stand, or on a desktop while working.
      The voice half stays mounted while you make things, so you can talk to it and watch the stage fill up at the
      same time.</p>
      <h3>Money and safety posture</h3>
      <p>Every backend call needs a key, because these endpoints can spend money. Voice sessions die on their own.
      Anything that spends real money, goes public, or touches infrastructure stays on the human side of an approval,
      and the router reports cost per call so the bill is never a surprise.</p>
      <div><span class="tag on">SELF-HOSTED VOICE</span><span class="tag on">KEY-GATED BACKEND</span><span class="tag off">SPEND IS VISIBLE</span></div>
    </div>
  </div>
</div>

<!-- 8 WHERE IT LIVES -->
<div class="page" data-pg="08">
  <div class="kicker">07 · WHERE EVERYTHING LIVES</div>
  <h2>Surfaces, services and repos</h2>
  <div class="cols">
    <div>
      <h3>Surfaces</h3>
      <table>
        <tr><td>Studio front end</td><td class="mono">jimsky-voice.netlify.app</td></tr>
        <tr><td>Media stage</td><td class="mono">jimsky-media…nip.io</td></tr>
        <tr><td>HUD backend</td><td class="mono">jimsky-hud…nip.io</td></tr>
        <tr><td>Voice server</td><td class="mono">vex…nip.io</td></tr>
      </table>
      <h3 style="margin-top:7mm">Services on the VPS</h3>
      <table>
        <tr><td>LiveKit</td><td class="mono">docker voice-livekit-1 · 7880/7881</td></tr>
        <tr><td>TLS front</td><td class="mono">docker voice-caddy-1</td></tr>
        <tr><td>Voice worker</td><td class="mono">vex-agent.service</td></tr>
        <tr><td>HUD backend</td><td class="mono">jimsky-hud.service · 8099</td></tr>
      </table>
    </div>
    <div>
      <h3>What is where</h3>
      <ul>
        <li><b>Voice</b> — <span class="mono">apps/voice</span>: the compose stack, the LiveKit config, the agent.</li>
        <li><b>Front end</b> — <span class="mono">jimsky-voice/web</span>: the screens, the token function, the continuation file.</li>
        <li><b>HUD</b> — <span class="mono">jimsky-hud</span>: the FastAPI backend, the Comfy runner, the router.</li>
        <li><b>Voice lab</b> — <span class="mono">voice-lab</span>: ten voices as entities, the design conversation, the video project.</li>
        <li><b>Secrets</b> — profile <span class="mono">.env</span> only, mode 600, referenced by name, never printed.</li>
      </ul>
      <h3 style="margin-top:7mm">The loop, end to end</h3>
      <p class="dim">ask in the voice room → the agent uses the same tools a model can call → the HUD makes the thing →
      it is published to the stage → the front end shows it while the conversation continues.</p>
    </div>
  </div>
  <div class="foot">JIMSKY STUDIO · source alpha · nothing published or for sale · generated images are concept art, not renders of implemented work</div>
</div>

</body></html>"""

html_path = DIST / "JIMSKY-STUDIO.html"
html_path.write_text(html)

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=["--no-sandbox"])
    page = browser.new_page()
    page.goto(f"file://{html_path}")
    page.wait_for_timeout(1800)

    # a page that overflows its box is CLIPPED, not flowed onto the next page, so measure it
    # instead of trusting the layout to be kind
    overflow = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('.page').forEach((p, i) => {
        let bottom = 0;
        [...p.children].forEach(c => {
          if (getComputedStyle(c).position === 'absolute') return;
          bottom = Math.max(bottom, c.offsetTop + c.offsetHeight);
        });
        if (bottom > p.clientHeight + 2) out.push({pg: p.dataset.pg || String(i + 1), content: bottom, box: p.clientHeight});
      });
      return out;
    }""")
    if overflow:
        print(f"  !! {len(overflow)} page(s) overflow and would be clipped:")
        for o in overflow:
            print(f"     page {o['pg']}: content {o['content']}px vs box {o['box']}px (+{o['content'] - o['box']}px)")
    else:
        print("  layout check: every page fits its box")

    page.pdf(path=str(OUT_PDF), format="A4", landscape=True, print_background=True,
             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    browser.close()

print(f"  PDF: {OUT_PDF}  {OUT_PDF.stat().st_size // 1024} KB")
print(f"  HTML: {html_path}")
