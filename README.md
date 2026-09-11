# JIMSKY — VOICE LINK

Realtime voice front end for the **JIMSKY** character over LiveKit, talking to a Hermes agent
running on our own hardware. Talk to it, ask it to make something, and watch the result land
on the stage.

**Live:** https://jimsky-voice.netlify.app

## What this is

A Vite + React + TypeScript app built on `@livekit/components-react`. There is no vendor
backend: the browser joins a room on **our self-hosted LiveKit server** (`vex.<ip>.nip.io`,
fronted by Caddy for TLS) and speaks to whatever agent is dispatched into that room.

Two things arrive on screen:

1. **Media the agent published** — polled from the media host, which is a plain directory that
   Caddy serves. `publish-media.py` (in this repo) copies a finished file into that directory
   and appends a record to `index.json`. This is how "make me an image" becomes an image on
   the stage, and it works with the full Hermes agent and Comfy Cloud without any agent-side
   protocol work.
2. **Media pushed over the LiveKit data channel** on topic `jimsky.media` — base64 payloads
   with `{kind, mime, data, caption}`. Used by agents that want to push directly.

## Image making and editing

The flare image stack (text-to-image and image-edit via `OpenAIGPTImageNodeV2`) is documented in
[IMAGE-STACK.md](IMAGE-STACK.md), with `flair-image.py` as the helper. Note the split: the paid
node can only be submitted through the OAuth-backed MCP session, so the helper builds and prints
the payload while the MCP client submits it.

## Layout

    src/App.tsx              connect gate, room HUD, media stage, transcript, control log
    src/lib/config.ts        session fetch, media polling, data-channel topics
    src/styles.css           the cyberpunk HUD theme
    netlify/functions/token.ts   mints short-lived room-scoped LiveKit JWTs
    netlify.toml             build, /api/* rewrite, SPA fallback, headers
    IMAGE-STACK.md           the gpt-image-2.5-flare recipe (text-to-image + edit)
    flair-image.py           build/upload/fetch/publish helpers for that recipe
    qa_frontend.py           real-browser check: joins, agent dispatches, media renders
    qa_idle.py               proves the client-side idle hangup
    qa_agent_idle.py         proves the agent hangs up on silence with the client still connected

## Idle failsafe

Nothing should stay live while nobody is talking. Three layers, all verified:

1. **The agent hangs up on silence** (`VEX_IDLE_TIMEOUT_SEC`, default 300s) and when the room
   empties (`VEX_EMPTY_ROOM_GRACE_SEC`, 30s), with `VEX_MAX_SESSION_SEC` as an absolute cap.
2. **The client hangs up too** and shows a countdown (`IDLE · HANGUP IN Ns`) inside the last
   minute, so a forgotten tab cannot hold a session open. Override with `?idle=<seconds>`.
3. **The SDK closes the session when your tab dies** (`close_on_disconnect`), so a crash or a
   closed browser never leaves a billing session behind.

The agent also disconnects the room explicitly when it ends. Relying on job teardown alone left a
ghost publisher sitting in the room, and LiveKit then refused to dispatch a new agent into it.

## Why the token lives server-side

The LiveKit API secret must never reach a browser. The client asks `/api/token`, and the
function returns a JWT scoped to one room with a two-hour TTL. Identities are generated
server-side so a caller cannot impersonate another participant, and room names are checked
against an allowlist — an unlisted room gets a 403.

The same function sets `roomConfig.agents`, so joining the room dispatches the named agent
automatically instead of relying on whatever worker happens to be free.

### Environment variables (Netlify)

    LIVEKIT_URL            wss://<your-livekit-host>
    LIVEKIT_API_KEY        server-side only
    LIVEKIT_API_SECRET     server-side only
    LIVEKIT_ALLOWED_ROOMS  comma-separated allowlist, e.g. vex-voice
    LIVEKIT_AGENT_NAME     agent to dispatch on join; "-" disables explicit dispatch
    VITE_MEDIA_BASE        public media host, e.g. https://jimsky-media.<ip>.nip.io

## Local development

    npm install
    npm run dev          # http://localhost:5199, proxies /api/token to TOKEN_ORIGIN

Run the Netlify function locally with `netlify dev` if you need the token path without a
deploy. QA with a browser: `qa_frontend.py` drives the deployed app with a fake microphone
and asserts the room joins, the agent dispatches, and published media renders.

## Publishing media (agent side)

    ./publish-media.py out.png --caption "WOOZLE at the drive-in" --kind image

Writes into `JIMSKY_MEDIA_ROOT` (default `/mnt/forge/jimsky-media`) and prints the public URL.
Set `JIMSKY_MEDIA_BASE` so Hermes gets a URL it can speak out loud.

## License

MIT for this front end. LiveKit's `agent-starter-react-native` (Apache-2.0) informed the
mobile sibling repo `jimsky-voice-mobile`.
