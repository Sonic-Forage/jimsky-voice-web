# JIMSKY — continuation file

Everything needed to pick this up cold: what exists, how the halves connect, where the secrets
live, and what is genuinely unfinished. Last updated when the voice lab landed.

## What this is

A voice-first studio machine. You talk to it, or type at it, and it makes things — images, video,
voice, 3D — which land on a shared stage in front of you. It runs on our own hardware, with a
self-hosted LiveKit server for the realtime half and our own HTTP service for the studio half.

## The two halves

**Front end** — `Sonic-Forage/jimsky-voice-web` → https://jimsky-voice.netlify.app
Vite + React + TypeScript, deployed on Netlify. Three views, one shell:

- **VOICE** — LiveKit room: agent state, live transcript, mic, idle countdown, the stage.
- **STUDIO** — model catalog (54 models, new-stack-first), templates, batches, image edits,
  workflows, the job queue, MODS, web browse, and the agent chat column.
- **CONFIG** — connections (ComfyUI endpoint + live probe), defaults, accent, panel prefs, and the
  full official Comfy template library (629) with RUN ON ENDPOINT.

A floating chat is available in every view. `npm run dev` locally, `netlify deploy --build --prod`
to ship; `qa_hud.py` drives it in a real browser.

**Back end** — `/home/ubuntu/sf-ops/jimsky-hud/hud_server.py`
FastAPI on `127.0.0.1:8099`, fronted by Caddy at `https://jimsky-hud.15-204-82-198.nip.io`, running
as the systemd user service `jimsky-hud.service` (enabled, `Linger=yes`, so it survives logout).
**Every route requires `X-HUD-Key`** because it can spend money.

    /api/health /api/catalog /api/create /api/jobs
    /api/browse          real Chromium screenshot -> stage
    /api/chat            full Hermes agent, continuing session, stdin-safe
    /api/mods /api/workflows[...]  /api/settings
    /api/comfy/presets|test|run    /api/templates[...]
    /api/credits /api/credits/redeem

Companion module `comfy_runner.py`: subgraph expansion, UI→API conversion against the endpoint's own
`/object_info`, queue/poll/download, and model-requirement reporting.

## Connections (what it is wired to)

- **LiveKit** `wss://vex.15-204-82-198.nip.io` — self-hosted, docker compose in
  `/home/ubuntu/apps/voice` (livekit + caddy). Agent worker: `vex-agent.service`.
- **Media host** `https://jimsky-media.15-204-82-198.nip.io` — `/mnt/forge/jimsky-media`, served by
  the same Caddy (mounted into the container as `/srv/jimsky-media`). `publish-media.py` writes a
  file plus an atomic `index.json` record; every front end polls it.
- **Comfy Cloud** — via the `comfy` CLI for generation, and via the `gpt-image-2.5-flare` node
  through the agent (MCP only; the API key cannot reach paid partner nodes over REST).
- **Own ComfyUI endpoint** — configurable; the template runner works against any ComfyUI URL.
- **Hermes agent** — the chat panel runs real `hermes chat --query-file -` turns in a named session.
- **LiveAvatar** (mod, `needs-key`) — GPT-Live driving a talking avatar with HTML overlays.

## Secrets (names only, never values)

`~/.hermes/profiles/jimsky/.env` — `OPENAI_API_KEY`, `JIMSKY_HUD_KEY`, LiveKit URL/key/secret.
`~/.hermes/.env` — `COMFY_CLOUD_API_KEY`, `GITHUB_TOKEN`, `NETLIFY_PERSONAL_ACCESS_TOKEN`.
`/home/ubuntu/apps/voice/livekit.yaml` — LiveKit API key/secret used by the server.

## Services on the box

    jimsky-hud.service                     studio back end            :8099
    vex-agent.service                      LiveKit agent worker
    voice-livekit-1 / voice-caddy-1        docker, self-hosted realtime + media/TLS
    sonic-forage-kick-broadcast.service    Kick station — STOPPED and disabled
    sonic-forage-desk.service              broadcast control desk — still running
    remote-void-publisher                  Stopped (freed ~1 core)

## Verified with real artifacts

- Voice call: agent dispatch, transcript, LISTENING/SPEAKING states, idle hangup both halves
  (client countdown fired at 39.7s; agent watchdog: "hanging up - silent for 49s").
- Generation: flux-2 and flux-kontext edit through the HUD (4s and 51s), flare text2image and edit
  through the agent, credits charged per job.
- Templates: `image_flux2_text_to_image` expanded 3→20 nodes, converted to 19 API nodes with zero
  unconnected inputs, ran in 51s, output visually correct.
- Chat: real Hermes turn answering with every toolset.
- QA: 0 page errors at 390 / 834 / 1440; browser + hit-testing caught two real mobile bugs.

## Unfinished, honestly

1. **Hermes is not in the voice room yet.** Needs a one-off gateway restart from a shell outside
   the gateway process. Until then the voice agent is Vex, not the memory-connected agent.
2. **LiveAvatar needs `LIVEAVATAR_API_KEY`** (paid, third-party — a decision, not a task). Mod code
   installs and type-checks with no keys; it is ready to run the moment the key exists.
3. **Own-ComfyUI template execution is unproven on real hardware.** The code path is endpoint
   agnostic and the only live run so far used Comfy Cloud, because the tailnet 4070 was not
   answering. Starting ComfyUI on the desktop is the test.
4. **Voice lab renders are TTS, not the live duplex model.** Same voice names, real acting
   directions on the timbre — an audition, not a performance. The duplex model sets its own pacing
   and interruptions inside a live session. `voice-lab/` has the roster and the generator.
5. **Not started:** publishing/trends pipeline, prepaid cards/real payments, games, autonomous
   workflow inventing, installable PWA.

## How to keep going

    # back end
    systemctl --user restart jimsky-hud.service
    # front end
    cd /home/ubuntu/sf-ops/jimsky-voice/web && netlify deploy --build --prod
    # voices
    cd /home/ubuntu/sf-ops/voice-lab && python3 voice_lab.py [voice]
    # QA
    cd /home/ubuntu/sf-ops/jimsky-voice && python3 qa_hud.py

## Gotchas that cost time, so they don't again

- `--create-if-missing` belongs to `hermes chat`, not one-shot mode; use `--query-file -` and the
  message arrives on stdin with nothing shell-interpreted.
- The Comfy flare node is **OAuth-only**; only the MCP session can submit it.
- `/api/view` on Comfy **302s** — `curl -L` or you save a 0-byte file.
- A systemd unit has a minimal `PATH`; `comfy` lives in `~/.local/bin`. Missing it made every model
  look unknown.
- Caddy cannot see host paths — mount media into the container or you get a 404 that looks like TLS.
- Ghost agent publishers left in a room block future dispatch; disconnect the room explicitly.
- `pgrep -f <pattern>` matches your own command line — split patterns when counting processes.
