#!/usr/bin/env python3
"""Voices as entities: audition GPT-Live's voice roster.

Each voice in GPT-Live's roster becomes a named entity with a persona, an expression direction and
two tasks, then gets rendered so you can hear it and decide which one to run.

Honest scope: this renders through `gpt-4o-mini-tts` using the SAME voice names GPT-Live exposes,
which is the cheap way to A/B the timbres and the acting. It is not the duplex model's live audio -
GPT-Live decides its own pacing, interruptions and emotion inside a live session, and that part can
only be judged by talking to it. Treat these as the audition, not the performance.

    voice_lab.py            # renders every voice, publishes to the stage, writes the manifest
    voice_lab.py marin      # just one
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("/home/ubuntu/sf-ops/voice-lab")
SAMPLES = OUT / "samples"
MEDIA_BASE = "https://jimsky-media.15-204-82-198.nip.io"
PUBLISHER = "/home/ubuntu/sf-ops/jimsky-voice/publish-media.py"
TTS_MODEL = os.environ.get("VOICE_LAB_TTS_MODEL", "gpt-4o-mini-tts")

# One entity per voice. The persona is what you'd wire into an agent; the direction is the acting
# note, which is the part that actually distinguishes them when you listen back.
VOICES = [
    {"voice": "marin", "entity": "MARINA", "role": "host, warm authority",
     "direction": "Warm, grounded, genuinely pleased to see someone. Relaxed pace, real breath, "
                  "slight smile in the voice. Never salesy.",
     "task1": "Open the night. One sentence, in character.",
     "task2": "Read back a render that just finished and say whether it is good enough to keep."},
    {"voice": "cedar", "entity": "CEDAR", "role": "engineer, low and steady",
     "direction": "Calm, low, unhurried. Sounds like someone who has fixed this before. Dry "
                  "delivery, no hype, slight amusement when something goes wrong.",
     "task1": "Introduce yourself as the one who watches the machines.",
     "task2": "Report a failed render honestly, and say what you would change."},
    {"voice": "alloy", "entity": "ALLOY", "role": "neutral operator",
     "direction": "Neutral, clear, efficient. Almost no colour. Precise consonants, even pace, "
                  "completely unbothered.",
     "task1": "State your name and function in one flat sentence.",
     "task2": "Read a three-line status report: queue, credits, time."},
    {"voice": "ash", "entity": "ASH", "role": "late-night narrator",
     "direction": "Low, intimate, close to the microphone. Slow, smoky, a little melancholic. "
                  "Pauses where a sentence would breathe.",
     "task1": "Open a night-time show, one line, like the room is dark.",
     "task2": "Describe an image you are looking at as if no one else can see it."},
    {"voice": "ballad", "entity": "BALLAD", "role": "performer, theatrical",
     "direction": "Theatrical, musical, larger than the room. Big dynamics, playful, delighted by "
                  "its own drama.",
     "task1": "Announce yourself like a stage entrance.",
     "task2": "Introduce a band to a crowd of thousands."},
    {"voice": "coral", "entity": "CORAL", "role": "bright assistant",
     "direction": "Bright, quick, friendly, upbeat without being shrill. Crisp and helpful, a "
                  "slight upward lilt at the end of statements.",
     "task1": "Say hello and offer to make something.",
     "task2": "Confirm a batch of four images is queued and what happens next."},
    {"voice": "echo", "entity": "ECHO", "role": "detached observer",
     "direction": "Detached, even, slightly clinical. Speaks as though reporting from a distance. "
                  "Long even phrases, minimal inflection.",
     "task1": "Introduce yourself as an observer of the system.",
     "task2": "Describe what changed on screen and why it matters."},
    {"voice": "sage", "entity": "SAGE", "role": "patient teacher",
     "direction": "Patient, kind, thoughtful. Explains rather than announces. Warm mid-range, "
                  "generous pauses, never condescending.",
     "task1": "Greet a learner and set them at ease.",
     "task2": "Explain what a subgraph is in two short sentences, without jargon."},
    {"voice": "shimmer", "entity": "SHIMMER", "role": "mischievous spark",
     "direction": "Playful, quick, conspiratorial. Sounds like it is enjoying itself and about to "
                  "suggest something it should not. Bright, bouncy rhythm.",
     "task1": "Introduce yourself as trouble with good intentions.",
     "task2": "Suggest something absurd to generate, then immediately commit to it."},
    {"voice": "verse", "entity": "VERSE", "role": "spoken-word poet",
     "direction": "Rhythmic, deliberate, poetic. Treats sentences as lines. Rich tone, deliberate "
                  "stress, lets images land before moving on.",
     "task1": "Introduce yourself in a single line of verse.",
     "task2": "Describe a finished piece the way a poet would, without naming it."},
]


def api_key() -> str:
    for path in ("/home/ubuntu/.hermes/profiles/jimsky/.env", "/home/ubuntu/.hermes/.env"):
        try:
            for line in open(path):
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    sys.exit("no OPENAI_API_KEY found")


def render(voice: str, text: str, direction: str, dest: Path) -> int:
    payload = json.dumps({
        "model": TTS_MODEL,
        "voice": voice,
        "input": text,
        "instructions": direction,
        "response_format": "mp3",
    }).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=payload,
                                 headers={"Authorization": f"Bearer {api_key()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"    HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
        return 0
    return dest.stat().st_size if dest.exists() else 0


def publish(path: Path, caption: str) -> str:
    out = subprocess.run([sys.executable, PUBLISHER, str(path), "--caption", caption,
                          "--kind", "audio", "--agent", "voice-lab"],
                         capture_output=True, text=True, timeout=180,
                         env={**os.environ, "JIMSKY_MEDIA_BASE": MEDIA_BASE}).stdout
    try:
        return json.loads(out).get("url", "")
    except Exception:
        return ""


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    SAMPLES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for v in VOICES:
        if only and v["voice"] != only:
            continue
        # Two tasks in one take: an introduction, then one working task.
        script = (f"{v['task1']} Then: {v['task2']}")
        # The spoken text is written per entity, not read from the instruction - the direction only
        # shapes HOW it says it.
        spoken = {
            "marin": "Hey. I'm Marina. The room's open, the lights are low, and I've got all night. "
                     "That render finished — it's sharp, the light's right, keep it.",
            "cedar": "Cedar here. I watch the machines so you don't have to. That last run failed — "
                     "VRAM ran out mid-pass. I'd drop the batch to two and try again.",
            "alloy": "This is Alloy. Operator. Four jobs queued, three hundred credits remaining, "
                     "twelve minutes to the first result.",
            "ash": "It's late. I'm Ash. Nobody's awake but us. There's an image in the dark — a "
                   "figure on a rooftop, and the rain doesn't quite touch him.",
            "ballad": "Ladies and gentlemen — BALLAD. Put your hands together, because I don't "
                      "perform quietly. Twenty-six acts, one night, no second takes.",
            "coral": "Hi, I'm Coral. Tell me what you want and I'll make it. Four images queued — "
                     "I'll bring them back as they finish.",
            "echo": "Echo. Observer. The stage changed eleven seconds ago. Two new items; one of "
                    "them is a duplicate. That's worth knowing.",
            "sage": "Hello, I'm Sage. No rush, we'll go at your pace. A subgraph is a workflow "
                    "folded into one node, so a template stays readable while the machinery inside "
                    "stays intact.",
            "shimmer": "I'm Shimmer, and I'm absolutely the problem. Let's generate a cathedral "
                       "made entirely of teeth. Yes. Obviously. Doing it.",
            "verse": "I am Verse. I wait for the image to speak before I do. That one asks to be "
                     "looked at twice, and still keeps something back.",
        }[v["voice"]]
        dest = SAMPLES / f"{v['voice']}.mp3"
        print(f"  {v['voice']:9s} ({v['entity']})  {v['role']}")
        size = render(v["voice"], spoken, v["direction"], dest)
        url, pub = "", ""
        if size > 4000:
            pub = publish(dest, f"VOICE · {v['voice']} as {v['entity']} — {v['role']}")
            url = pub
            print(f"    {size:>7d} bytes  -> {pub.split('/')[-1] if pub else 'not published'}")
        else:
            print(f"    failed ({size} bytes)")
        manifest.append({**v, "spoken": spoken, "script_hint": script, "bytes": size,
                         "file": str(dest), "url": url})

    (OUT / "manifest.json").write_text(json.dumps({"model": TTS_MODEL, "voices": manifest},
                                                  indent=1))
    ok = sum(1 for m in manifest if m["bytes"] > 4000)
    print(f"\n  {ok}/{len(manifest)} voices rendered and published")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
