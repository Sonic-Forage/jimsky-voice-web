# OVERNIGHT — research, monetization, next tools, UI

Written autonomously while the owner slept. Nothing external was published, nothing was spent, no
infrastructure was changed, and the voice worker was left stopped as requested.

---

## 1. The single most important find

**Hermes Agent v0.20.0 "The Herald Release" (Aug 3, 2026) ships real-time streaming voice natively.**
Source: https://dev.to/lukeocodes/open-source-voice-agents-get-real-time-speech-in-hermes-v0200-1pkp

We have been hand-rolling a LiveKit worker (`vex-agent.service`) that currently has a broken child
spawn — and the framework we already run on has had first-class realtime voice for over a month.

**Action:** before debugging my launcher further, check `hermes --version` against 0.20.0 and read the
voice-mode docs. If the built-in path covers duplex conversation, the custom worker may be redundant —
or worth keeping only for the parts Hermes does not do (our ten-voice roster, the studio tools). This
could turn a multi-hour debugging session into a config change.

## 2. Voice: what changed in the field

| Thing | Why it matters to us |
|---|---|
| **Hugging Face + Cerebras open voice model** (Jul 2026) — "rivals OpenAI Realtime", local-first, runs on a MacBook | A real candidate for the LOCAL mode we specced: private, no per-minute bill |
| **ByteDance SeedRealtime** — native audio-visual full-duplex LLM | Interesting for avatars later (audio + video in one model) |
| **Microsoft VibeVoice** — 51.5k stars, the biggest open voice project | Mature open option for TTS/voice cloning exploration |
| **Breeze TTS 2** (Aug 25, 2026) — #1 open-weight TTS on Artificial Analysis | Direct upgrade path for our ten-voice roster. Our audition used `gpt-4o-mini-tts`; this is the current best open weight |

**Concrete move:** audition Breeze TTS 2 against our roster. If it wins, the ten voices get better *and*
the voice lab stops costing per render.

## 3. MCP: the protocol changed shape

**The MCP spec went stateless on 2026-07-28** (release candidate), and the GitHub MCP Server already
supports it. Our Unreal/remote-MCP plan should target the stateless spec, not the older stateful
assumption — it simplifies the tunnel story and the long-lived session handling.

Also spotted, worth a look when picking Unreal tooling:
- `vibheksoni/stealth-browser-mcp` — browser automation that bypasses anti-bot walls (relevant: our
  `browse_the_web` tool would stop failing on protected pages)
- `HKUDS/nanobot` — ultra-lightweight self-hosted agent framework
- `templetwo/sovereign-stack` — MCP server for AI memory + governance

## 4. Monetization — what actually fits this studio

Read across the current pricing literature (Metronome's 50+ AI pricing models, Bessemer's playbook,
Krea's credit packs): the winning shape for creative AI in 2026 is **hybrid** — a small subscription for
access plus **metered credits** for generation, with **one-time credit packs** as the upsell. Nobody
credible is selling unlimited generation.

**We already have the hard parts built:** a credits ledger, redeem codes (`SUNBURST`, `HYPERBLOOM`,
`JIMSKY`, `RASCALVEX`, `ENFOREST`), per-call cost reporting from the model router, and a key-gated
backend. What is missing is packaging and a payment path.

**Proposed ladder (subject to the owner's approval — nothing here is published):**

1. **FREE / DEMO** — the ten-voice roster, the model router comparison, a handful of generations.
   This is the thing that sells the studio: people hear it and want it.
2. **HOBBY — small monthly + monthly credits.** Target the person who wants a voice studio, not a
   chatbot. This is the tier that replaces the $1,111/month problem.
3. **CREATOR — larger credit allotment + the multi-voice ensemble tools** (the design-chat engine:
   put ten characters in a room and get a scene). Nothing else on the market does this yet.
4. **CUSTOM WORK — done-with-you voice/character production**, priced per finished piece. Highest
   margin, needs no new tech, and it is exactly what the studio's canon already demonstrates.
5. **CREDIT PACKS** — one-time top-ups. The cheapest thing to sell to someone already inside.

**What to sell first, honestly:** the *ensemble*. A hosted "ten voices argue about your thing" tool,
with the video render included, is a product nobody else ships and we have already built end to end
(a 72-second ten-voice video, gate-passed and published). That is the wedge.

**Payment path:** Stripe is the boring correct answer. It is a spend/account action, so it needs the
owner's explicit go-ahead before anything is created.

## 5. Tools I would add next (ranked by value per hour)

1. **`remember_this`** — the agent writes a durable note (session memory the owner asked for).
2. **`make_a_song`** — the music/DJ work already exists on the pod side; exposing it as a tool is
   mostly wiring, and it opens the DJ stream.
3. **`save_canvas` / `list_canvases`** — the canvas the owner described most vividly. Sketch → Comfy
   `flux-canny`/`flux-depth` is already possible; what is missing is persistence.
4. **`check_health`** — expose `healthcheck.py` as a tool so the agent can answer "is everything up?"
   by voice instead of guessing.
5. **`send_to_owner`** — a gated notification channel (approval required, it is messaging).

Tools 1, 3 and 4 need no new external access and no spend, so they are the safe ones to build first.

## 6. UI — the next increment

Already specced in `FRONT-END-V2.md`. The highest-value additions, in order:

1. **Mode badge + room accent** (CASCADE / REALTIME / LOCAL) — one glance tells you what you are talking to.
2. **A TOOLS panel** listing the agent's wired tools with live status. Right now that reach is invisible;
   showing it is what makes the studio feel powerful.
3. **Save/restore canvas** with a named session list.
4. **Money sparkline** — per-call cost from the router, always visible, so spend is never a surprise.
5. **Game mode** — guess-the-prompt and draw-and-it-guesses, scored per session. Cheap to build on the
   canvas and it turns the studio into something you open for fun.

## 7. Still open from before tonight

- **Voice worker**: stopped and disabled by request. The child-spawn bug is undiagnosed; §1 may make it moot.
- **`jimsky-live-director.service`**: active, 2,023 restarts, failing since Sep 6 — a second thrash loop.
- **Unreal MCP**: waiting on the installed engine version (5.8+ → VibeUE, 5.5–5.7 → bridge). Secure
  topology is `orchestrator → Tailscale → local MCP → editor`, loopback only, never public.
- **Backup push**: the 9.2 GB encrypted snapshot is complete locally but unpushed (owner's call).
