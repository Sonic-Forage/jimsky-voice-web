# Room security — the token endpoint hole, and its fix

**Status: closed and verified.** Kept as a record because the failure mode was subtle and the
next front end, mobile build, or bot that touches this room can reintroduce it.

## What was wrong

`/api/token` — the Netlify function that mints LiveKit join tokens — required **no caller
authentication of any kind**. Any anonymous request to the public site received a valid,
publish-capable token.

Proved with a plain curl, no credentials, on 2026-09-11:

```
$ curl -s https://jimsky-voice.netlify.app/api/token
HTTP 200
{"room":"vex-voice","agent":"vex", "token":"eyJ..."}
grants: {"roomJoin":true,"room":"vex-voice","canPublish":true,"canSubscribe":true,"canPublishData":true}
```

The room allowlist worked (only `vex-voice`), the identity was minted server-side (so no
impersonation), and the LiveKit API secret never left the server. None of that mattered: the door
was unlocked.

## Why it mattered

- **A live microphone.** `canPublish: true` means a stranger who found the URL could join the room
  and be heard, and could hear everyone in it.
- **It also spends money.** Every join triggers explicit agent dispatch (`agentName: vex`), so an
  anonymous visitor starts a real agent session on our hardware.
- The site is public and crawlable. Nobody had to guess anything.

## What the logs actually showed

Audit of every participant identity in the LiveKit server logs, with device and remote address:

- **Ours, expected:** 9 `agent-*` sessions (the vex worker), `silent-probe` (the failsafe test),
  and headless-Chrome sessions from our own VPS during front-end QA.
- **The owner's devices:** `jimsky-*` identities from a Windows PC (Tailscale `100.114.245.*` +
  LAN), an iPhone (Tailscale `100.103.238.*`, plus a residential address), same ISP block.
- **Four `caller-*` sessions** — an identity prefix our token function cannot produce — on
  **2026-08-26, in a different room (`vex-console`)**. Older console work, not this room.
- **One session we cannot attribute:** `jimsky-xx3cgw5a`, **Mac OS X / Chrome, 2026-09-11 20:57,
  from `104.28.230.*`** (a Cloudflare WARP egress address).

So: no proof that a stranger was in `vex-voice`, and one session that is not obviously account-able
to the owner. What *is* proven is that anyone could have walked in, because nothing stopped them.

## The fix

1. **`JIMSKY_ACCESS_CODE` is required**, supplied as an `x-jimsky-code` header or `?code=`, compared
   with `crypto.timingSafeEqual` so the endpoint cannot be used as a guessing oracle.
2. **Fail closed.** If the code is not configured, the function refuses to mint (`503`) rather than
   reopening the hole. An unset gate must never mean "open to the world".
3. **Token TTL cut to 1 hour** (was 2). A leaked token is no longer a standing invitation.
4. Unchanged good parts: server-side identity minting, room allowlist, explicit agent dispatch.
5. The code lives in the profile `.env` (mode 600) and as a Netlify environment variable. It is
   **never printed, never committed, never spoken** — read it with
   `grep '^JIMSKY_ACCESS_CODE=' ~/.hermes/profiles/jimsky/.env`.

## Verification (same day)

| Caller | Result |
|---|---|
| anonymous curl, no code | **401** `access_denied` |
| wrong code | **401** |
| correct code | **200**, token for `vex-voice`, `canPublish` true, expires in 59.9 minutes |

## Residual risk and what to do about it

- **Everyone who joins now needs the code.** Share it deliberately; rotate it if it spreads.
- **Rotating the code** is intended to be cheap: replace `JIMSKY_ACCESS_CODE` in the Netlify
  environment and in the profile `.env`, then redeploy. Everyone re-enters it once.
- **The LiveKit API key/secret is still the root credential.** Anyone holding it can mint their own
  tokens, bypassing this gate entirely. Keeping it server-side is the whole defence.
- **Not yet done:** per-person codes (so one leak does not require rotating for everybody), and rate
  limiting on the endpoint. Neither is urgent now that a code is required.
- **Any new client** (a new front end, the mobile app, a bot) must send the code. That is the thing
  to check first if the room ever looks empty to a legitimate user.
