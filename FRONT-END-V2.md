# FRONT END V2 — the cooler studio

Brainstorm + spec. Written after the first working version proved the loop; this is what makes it
a place someone *wants* to open.

## The modes (the spine of the whole thing)

| Mode | Engine | Cost | Latency | Voice switching |
|---|---|---|---|---|
| **CASCADE** | Deepgram STT -> LLM -> OpenAI TTS | cheap, per-word | ~1s | **live, mid-sentence** |
| **REALTIME** | GPT-Live full duplex (gpt-live-1) | higher | instant overlap | fixed per call |
| **LOCAL** | open weights on our own box | ~$0.5/hr pod | variable | live (cascade) |

One switch in the HUD sets which engine the room runs. Cascade is the everyday setting (cheap,
customisable, and the only one where "switch your voice to shimmer" works *while you talk*).
Realtime is the show-off mode for conversation that overlaps like two people. Local is privacy.

Switching engines must restart the worker; the HUD can own that once the unit is fixed.

## Everything the agent should be able to touch (with one key)

All of it behind `X-HUD-Key`, same gate as today:
- **BROWSER** — a real Chromium: open, read, screenshot to the stage. Playwright already there.
- **TERMINAL** — shell on the box, through a full Hermes turn. Already reachable; needs the
  HUD agent endpoint fixed (see below).
- **MACHINE** — files, git, services, cron, generation, publishing.
- **SSH / remote boxes** — the same idea pointed at the 4070 and any rented GPU.
- **TOP MODELS** — the router, always visible: frontier, fast, open weights, free tier.

The honest rule: reach is gated by a key, and anything that spends or publishes still asks.

## The canvas (what you meant by "it popped up ready to go")

- Opens **blank and ready**, not a modal to dismiss. First stroke starts a session.
- **Save canvas** — write the sketch + its prompt history to disk, list them, reopen one later.
- **Continue a session** — a canvas belongs to a session, so the agent's memory of "the rooftop
  piece" survives a reload.
- **Comfy hands** — the sketch feeds `flux-canny` / `flux-depth` (already in the catalog), so
  "put a square here" becomes structure in the render, not a suggestion in a prompt.
- **Game mode** — same canvas, different rules: guess-the-prompt (it shows a render, you guess),
  draw-and-it-guesses, and a scored round per session. Cheat codes already exist.

## Session memory that actually continues

The strip we have shows recent work. V2 adds named sessions the agent can recall by voice
("pull up the rooftop thread"), each with its canvas, prompts, chosen model and mode.

## Cool, concretely (least effort, most feel)

1. **Live mode indicator** that changes the whole room's colour: cascade = teal, realtime = magenta,
   local = amber. You know the mode from across the kitchen.
2. **Stage as a proper lightbox** with keyboard nav and a timeline scrub.
3. **Model crown** — the router's current pick rendered as the room's identity, not a dropdown.
4. **Terminal drawer** — xterm.js over the existing agent endpoint; SSH tabs for other boxes.
5. **Sparkline of the money** — per-call cost from the router, visible always.

## Repos worth borrowing from

- **xterm.js** — the terminal drawer (MIT).
- **tldraw** / **Excalidraw** — canvas engine with save/load if we do not hand-roll it (both MIT).
- **browser-use** + the Playwright MCP server — agentic browsing beyond one screenshot.
- **LiveKit agents UI kit** — already in use; keep upgrading for room chrome.
- Anything adopted gets its licence and upstream credited, same as LiveKit and HyperFrames today.

## Known broken right now (do first)

1. **The worker does not start** — the systemd unit's entry point silently exits; `run_worker.py`
   is the verified fix, waiting on approval to edit the unit.
2. **The HUD's `/api/agent` reply path** — that tool is written, but the endpoint it calls needs
   checking end to end before the voice agent can report machine results.
