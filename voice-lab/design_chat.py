#!/usr/bin/env python3
"""A ten-voice conversation about a design. ~1 minute, with laughs.

Each line is rendered with its own voice and its own emotion direction, then stitched with short
gaps so it reads as people talking over each other rather than a series of announcements.

Laughter is written as spoken vocalisation ("haha", "ha!") plus a direction to the model, NOT as a
parenthetical stage direction - parentheticals get read out loud, which kills the joke.

    design_chat.py            # render + stitch + publish
    design_chat.py --dry      # show the script and the timing estimate, render nothing
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
CHAT = OUT / "design-chat"
TTS_MODEL = os.environ.get("VOICE_LAB_TTS_MODEL", "gpt-4o-mini-tts")
MEDIA_BASE = "https://jimsky-media.15-204-82-198.nip.io"
PUBLISHER = "/home/ubuntu/sf-ops/jimsky-voice/publish-media.py"

# (voice, line, direction, gap_after_seconds)
# The gaps are the acting: short for interruptions, longer where someone lets a line land.
SCRIPT: list[tuple[str, str, str, float]] = [
    ("marin", "All right, everyone's here. Look at the rooftop piece. What do we think?",
     "Warm, hosting, genuinely curious. Someone opening a room.", 0.35),
    ("cedar", "Structurally it's fine. Emotionally, he looks like he's waiting for a bus in the rain.",
     "Low, dry, completely deadpan. No joke signposting.", 0.30),
    ("echo", "I'll note the figure occupies eleven percent of the frame.",
     "Detached, clinical, reporting from a distance. Slight pause before the number.", 0.25),
    ("shimmer", "Haha, eleven percent? He's the whole mood, you absolute robot.",
     "Opens with a real delighted laugh, then teasing, quick and bouncy.", 0.25),
    ("verse", "The rain doesn't touch him. That's the line that matters.",
     "Poetic, deliberate, rich. Let the image land before moving on.", 0.45),
    ("ballad", "It needs a spotlight. Everything needs a spotlight.",
     "Theatrical, big, delighted by its own drama.", 0.30),
    ("sage", "Mm-hm, not everything, Ballad. Sometimes the dark does the work.",
     "Warm, patient, a soft chuckle under the words. Kind, never condescending.", 0.35),
    ("alloy", "Contrast ratio is acceptable. The teal reads at distance.",
     "Flat, efficient, unbothered. Almost no inflection.", 0.30),
    ("coral", "Sorry, sorry. Cedar's bus thing is all I can hear now. That's it, that's the piece.",
     "Bright, giggling, apologetic but delighted. Quick and light.", 0.30),
    ("ash", "Ha. That's because he's right. Look at the shoulders.",
     "Low, intimate, short real laugh then smoky and slow. Close to the mic.", 0.45),
    ("marin", "Okay, but do we ship it?",
     "Direct, warm, moving the room along.", 0.30),
    ("shimmer", "Ship it before somebody adds a lens flare.",
     "Urgent, mischievous, half-laughing.", 0.20),
    ("cedar", "Too late. I count three.",
     "Deadpan. Absolutely flat.", 0.25),
    ("echo", "Correcting: four.",
     "Neutral, immediate, no humour acknowledged.", 0.25),
    ("verse", "Four lights, and still the dark holds.",
     "Poetic, quiet, unhurried.", 0.45),
    ("ballad", "Oh, that's beautiful. Say it again.",
     "Genuinely moved, theatrical, laughing at itself.", 0.30),
    ("verse", "No. It's spent.",
     "Final, gentle, no drama.", 0.35),
    ("sage", "Hah. That is the most Verse thing anyone has ever said.",
     "Warm open laugh at the start, then fond.", 0.35),
    ("coral", "Can we keep the glitch band? I really like the glitch band.",
     "Bright, hopeful, a little pleading.", 0.30),
    ("alloy", "Retaining it costs nothing. Retained.",
     "Flat, final, administrative.", 0.35),
    ("marin", "Good. Rooftop ships. Who's making the next one?",
     "Warm, decisive, a smile in it.", 0.25),
    ("shimmer", "Me. Cathedral of teeth. I've said it, I stand by it.",
     "Proud, absurd, delighted with itself.", 0.35),
    ("ash", "Ha. And there it is.",
     "Low, fond, a short dry laugh. Fading out.", 0.0),
]


def api_key() -> str:
    for path in ("/home/ubuntu/.hermes/profiles/jimsky/.env", "/home/ubuntu/.hermes/.env"):
        try:
            for line in open(path):
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    sys.exit("no OPENAI_API_KEY")


def render(voice: str, text: str, direction: str, dest: Path) -> int:
    payload = json.dumps({"model": TTS_MODEL, "voice": voice, "input": text,
                          "instructions": direction, "response_format": "mp3"}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=payload,
                                 headers={"Authorization": f"Bearer {api_key()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"    HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:160]}")
        return 0
    return dest.stat().st_size if dest.exists() else 0


def silence(seconds: float, dest: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{seconds}",
                    "-i", "anullsrc=r=24000:cl=mono", "-c:a", "libmp3lame", "-b:a", "96k",
                    str(dest)], check=False)


def main() -> int:
    if "--dry" in sys.argv:
        words = sum(len(t.split()) for _, t, _, _ in SCRIPT)
        gaps = sum(g for *_ , g in SCRIPT)
        print(f"  {len(SCRIPT)} lines, {words} words, {gaps:.1f}s of gaps")
        print(f"  estimated speech {words/2.6:.0f}s + gaps -> ~{words/2.6 + gaps:.0f}s total")
        return 0

    CHAT.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    total_bytes = 0
    for i, (voice, text, direction, gap) in enumerate(SCRIPT):
        clip = CHAT / f"{i:02d}-{voice}.mp3"
        size = render(voice, text, direction, clip)
        if size < 2000:
            print(f"  {i:02d} {voice}: FAILED")
            continue
        total_bytes += size
        parts.append(clip)
        print(f"  {i:02d} {voice:8s} {size:>6d}B  {text[:58]}")
        if gap > 0:
            sil = CHAT / f"{i:02d}-gap.mp3"
            silence(gap, sil)
            parts.append(sil)

    if not parts:
        print("  nothing rendered"); return 1

    # One continuous take
    listfile = CHAT / "parts.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in parts))
    final = OUT / "design_chat.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listfile), "-c:a", "libmp3lame", "-b:a", "96k", "-ar", "24000",
                    "-ac", "1", str(final)], check=False)
    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(final)], capture_output=True, text=True).stdout.strip() or 0)
    print(f"\n  stitched: {final.stat().st_size/1024:.0f} KB, {duration:.1f} seconds, "
          f"{len(parts)} segments")

    out = subprocess.run([sys.executable, PUBLISHER, str(final),
                          "--caption", f"DESIGN CHAT · ten voices, {duration:.0f}s — laughing about "
                                       f"the rooftop piece", "--kind", "audio"],
                         capture_output=True, text=True, timeout=180,
                         env={**os.environ, "JIMSKY_MEDIA_BASE": MEDIA_BASE}).stdout
    print("  published:", out.strip()[:160])
    (OUT / "design_chat.json").write_text(json.dumps(
        {"duration_s": round(duration, 1), "segments": len(parts),
         "lines": [{"voice": v, "text": t, "direction": d} for v, t, d, _ in SCRIPT]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
