# Voice lab — the GPT-Live roster as entities

Ten voices, ten characters, rendered so you can hear them and choose.

    python3 voice_lab.py            # render all, publish to the stage
    python3 voice_lab.py ash        # one voice

**Honest scope.** These render through `gpt-4o-mini-tts` using the **same voice names GPT-Live
exposes**, with an acting direction per entity. That is the cheap way to A/B timbre and delivery
before putting a voice into a live agent. It is **not** the duplex model's own audio: in a live
session GPT-Live decides its own pacing, interruptions and emotional colour, and that can only be
judged by talking to it. Treat this as the audition, not the performance.

## The roster

| voice | entity | role |
|---|---|---|
| marin | MARINA | host, warm authority |
| cedar | CEDAR | engineer, low and steady |
| alloy | ALLOY | neutral operator |
| ballad | BALLAD | performer, theatrical |
| coral | CORAL | bright assistant |
| ash | ASH | late-night narrator |
| echo | ECHO | detached observer |
| sage | SAGE | patient teacher |
| shimmer | SHIMMER | mischievous spark |
| verse | VERSE | spoken-word poet |

Each entity is written with a persona (what you'd wire into an agent) and a direction (the acting
note). `manifest.json` holds every script, direction and published URL.

The audition file is `samples/voice_lineup.mp3` — all ten, 111 seconds, in roster order.

## Wiring one into the live agent

    VEX_LIVE_VOICE=ash          # then restart vex-agent.service

That voice then handles the live GPT-Live session, where the duplex behaviour (barge-in, its own
turn-taking) becomes part of the character rather than something scripted.
