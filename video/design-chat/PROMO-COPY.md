# PROMO COPY — the ten-voice design chat

Distribution kit for the HyperFrames video. Render is the work; this is how it goes out.
Stills pulled from the delivered encode (`out/design-chat.mp4`), not from a preview.

**Status line that must survive into every version:** source alpha on my own hardware, nothing shipped.
**The voices are TTS auditions** of the same entities the live duplex agent runs on — not ten live
agents in a room. Say it plainly. **The art under review is a generated image (concept art)**, labelled
as such in the video itself.

---

## 1. Short post (X / Bluesky / Threads) — 243 chars body, 290 with tags

gave ten ai voices separate personalities and told them to review a design for a minute.

they argued about a bus, someone counted lens flares, and one said "cathedral of teeth."

72s · all ten speak · laughs in. 1080p, rendered on my own box.

`#ai #voiceai #generativeart #gamedev #indiedev`

## 2. Alternative hooks

**Punchy:**
> ten ai voices. one design. one minute. they still couldn't agree about the rain.

**For the people building this:**
> if you're wiring multi-agent voice: i gave ten voices separate personalities, roles and acting
> directions, then let them interrupt each other for a minute. two things made it work and one bug
> fooled me for an entire render. 🧵

## 3. Instagram / TikTok caption

ten voices, one design, one minute 🎙️

· ten separate characters — host, engineer, observer, poet, operator, performer, narrator, teacher, assistant, spark
· 72 seconds of dialogue, 15 lines, every one of the ten speaks
· laughs written as spoken vocalisation, never as a stage direction
· a chip rail that lights whoever is talking, so you can read the room
· every caption timed to that voice's real clip length — not eyeballed
· the art on the wall is the actual image they're arguing about
· 1080p, 2169 frames, rendered in 2m 12.8s on my own hardware

the voices here are auditions — same entities the live voice agent runs on, rendered as TTS so you can
hear the character before you pick one. source alpha, nothing shipped.

`#ai #voiceai #generativeart #creativecoding #gamedev #indiedev #sounddesign #hyperframes`

## 4. YouTube

**Title:** ten voices argue about one design · 72s · made with HyperFrames (source alpha)

**Description:**

I gave ten AI voices separate personalities, roles and acting directions, then pointed them at one
design and let them argue about it for a minute.

72 seconds, 15 lines, all ten voices speak. Every caption is timed to that voice's real clip length,
and the speaker rail lights whoever is talking, so you can read the room instead of just hearing it.

**Scene breakdown**

- `0:00` title card, MARINA opens the review
- `0:05` CEDAR — "Emotionally, he looks like he's waiting for a bus in the rain."
- `0:10` ECHO — "I'll note the figure occupies eleven percent of the frame."
- `0:14` SHIMMER laughs at ECHO — "you absolute robot."
- `0:20` VERSE — "The rain doesn't touch him. That's the line that matters."
- `0:24` BALLAD — "Everything needs a spotlight."
- `0:30` CORAL picks up CEDAR's bus joke — the first real ensemble moment
- `0:37` ASH — "Look at the shoulders."
- `0:43` MARINA — "Okay, but do we ship it?"
- `0:45` SHIMMER — "Ship it before somebody adds a lens flare."
- `0:48` SAGE catches that this is the most VERSE thing anyone has ever said
- `0:54` ALLOY — "Retaining it costs nothing. Retained."
- `0:58` MARINA — "Good. Rooftop ships. Who's making the next one?"
- `1:03` SHIMMER — "Me. Cathedral of teeth. I've said it, I stand by it."
- `1:09` ASH closes — "Ha. And there it is."

**Credits:** LiveKit (Apache-2.0) for the self-hosted realtime server · HyperFrames (HeyGen) for the
render · Comfy-Org/workflow_templates for the workflow library · Three.js · Netlify · voice synthesis
via OpenAI TTS. The art under review is a generated image, labelled as concept art in the video.

**Status:** source alpha on self-hosted hardware. Nothing shipped, nothing for sale.

## 5. Reddit / forum maker post

**Disclaimers first, because that is the deal:**

- Source alpha, self-hosted, **nothing shipped** and nothing for sale.
- The ten voices are **TTS auditions** of the entities my live voice agent runs on. They are not ten
  live agents talking in real time — the dialogue is written, then rendered per line.
- The design they discuss is a **generated image** (concept art), which the video labels as such.
- Built on LiveKit (Apache-2.0) and HyperFrames; credits in the description.

**What it is:** ten AI voices with distinct personalities, roles and acting directions review one design
for 72 seconds — 15 lines, every voice speaks, laughs included. On screen: the art under review, a rail
of ten name chips that lights the current speaker, and one caption per line.

**What's new here for me:**

1. **Identity keyed to the entity, not the position.** My first render lit the wrong chip on 12 of 15
   lines because I indexed the highlight by line order. Lines 0, 5 and 9 lined up by luck, so a spot
   check looked fine. Frame-by-frame review caught it.
2. **Per-line timing measured, not estimated.** I ffprobe'd every clip and built the timeline from real
   durations, so captions land on the audio instead of near it.
3. **Laughter as vocalisation.** Writing the laugh inline ("Haha, eleven percent?") rather than as a
   parenthetical, with an emotion direction to the model — parentheticals get read aloud and kill the joke.

**Feedback I want:** does the speaker rail read at a glance on a phone? And for anyone doing ensembles:
how do you handle crosstalk — does your stack let two voices overlap at all?

## 6. Discord / community one-liner

ten voices, one design, 72 seconds — and the trick was keying the speaker highlight to the character
instead of the line order. does your ensemble stack allow real crosstalk, or is everything turn-based?

## 7. Optional 3-post thread

1. ten ai voices, one design, one minute. i gave each one a job and let them interrupt each other —
   here's the result. *(attach: title still)*
2. the thing that made it work: every caption is timed to that voice's real clip length, and the rail
   lights whoever is talking. keyed to the *character*, never to the line order. *(attach: ship-it still)*
3. the bug that fooled me: my first render had the wrong chip lit on 12 of 15 lines, and it looked
   perfect in a spot check. three lines just happened to line up. pulled frames and caught it.
   *(attach: laugh still)*

## 8. Thumbnail guidance

- **Primary: `stills/thumb-title.jpg`** (t=2.8s) — the title card. Biggest, most legible type at feed
  size, and it states the premise without a caption to read.
- **Follow-up: `stills/thumb-shipit.jpg`** (t=46.2s) — SHIMMER's chip lit with "Ship it before somebody
  adds a lens flare." Shows the mechanism, not just the title.
- **Close: `stills/thumb-endcard.jpg`** (t=70.6s) — `ROOFTOP SHIPS`.
- Also usable: `stills/thumb-laugh.jpg` (t=18.6s) — the eleven-percent laugh.
