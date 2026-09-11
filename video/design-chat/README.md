# DESIGN CHAT — the video

Ten voices argue about one design. 72 seconds, 1920×1080, 30 fps, rendered with HyperFrames.

**Watch:** https://jimsky-media.15-204-82-198.nip.io/ (the JIMSKY stage) · `design-chat-720p.mp4` in this folder
**Source of truth for the audio:** `../voice-lab/design_chat.py` (per-line script, voice, expression, gaps)

## What is on screen

- **The piece under review** — the rooftop design, wall-mounted, with a slow 4% drift across the whole run.
- **A ten-chip speaker rail** — every voice as a named entity. The active speaker's chip lights teal for exactly
  the length of their line. This is the part that matters: it makes the ensemble legible.
- **One caption clip per spoken line**, timed to the *real* clip durations (measured with ffprobe, not estimated).
- **A laugh cue** — lines that open with a laugh flash their caption rule magenta, then settle back to teal.
- **Title card** `DESIGN CHAT / TEN VOICES · ONE DESIGN` and **end card** `ROOFTOP SHIPS`.

## Re-render

```bash
cd video/design-chat
npx hyperframes check          # lint + runtime + layout + motion + contrast
npx hyperframes render -q high -o out/design-chat.mp4 --strict
```

Roughly 2.5 minutes on this box at 4 workers. Deliverable is ~36 MB at 1080p.

## Two bugs worth remembering

1. **Speaker-chip IDs keyed by line index instead of by voice.** Lines 0, 5 and 9 happened to line up, so the
   first render *looked* fine in a spot check while 12 of 15 lines lit the wrong chip. Always key identity off
   the entity, never off the order it appears in.
2. **A 0.35 s tail on every caption** made consecutive captions overlap, which the layout gate caught as
   `content_overlap`. Captions now hold their exact line length (the final line keeps a 0.95 s dwell).

Also: `.design-meta` (the small spec line under the panel) collided with every caption box. Folded into the
panel label as `UNDER REVIEW · gpt-image-2.5-flare · 1024×1024`.

## Gate results

- `hyperframes lint` — 0 errors, 0 warnings
- `hyperframes check` — check passed; contrast **125/125 text checks pass WCAG AA**; motion 0 errors
- Verified visually at t=2.5s, 18.6s, 46.0s, 70.5s **and** corrected frames re-verified after the chip fix
- Audio verified present: mean −23.6 dB, peak −3.8 dB (a silent track is the classic HyperFrames failure —
  every `<audio>` needs an `id`)
