// Mints a LiveKit join token. The API secret stays server-side — the browser only ever
// receives a short-lived JWT scoped to one room.
//
//   GET /api/token            -> { url, token, room, identity, agent }
//
// Env (Netlify > Site settings > Environment variables):
//   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET   (required)
//   LIVEKIT_ALLOWED_ROOMS   comma list, default "vex-voice"
//   LIVEKIT_AGENT_NAME      explicit agent dispatch, default "vex"; set to "-" to disable
import type { Handler } from '@netlify/functions'
import { AccessToken, RoomConfiguration } from 'livekit-server-sdk'

const ALLOWED = (process.env.LIVEKIT_ALLOWED_ROOMS ?? 'vex-voice')
  .split(',').map((s) => s.trim()).filter(Boolean)

function json(statusCode: number, body: unknown) {
  return {
    statusCode,
    headers: {
      'content-type': 'application/json',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    },
    body: JSON.stringify(body),
  }
}

export const handler: Handler = async (event) => {
  const url = process.env.LIVEKIT_URL
  const apiKey = process.env.LIVEKIT_API_KEY
  const apiSecret = process.env.LIVEKIT_API_SECRET

  if (!url || !apiKey || !apiSecret) {
    // Fail loudly rather than handing the client a broken session.
    return json(503, {
      error: 'not_configured',
      detail: 'LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are not set in this deployment.',
    })
  }

  const wanted = (event.queryStringParameters?.room ?? ALLOWED[0] ?? 'vex-voice').trim()
  if (!ALLOWED.includes(wanted)) {
    return json(403, { error: 'room_not_allowed', detail: `allowed: ${ALLOWED.join(', ')}` })
  }

  // Identity is generated here, never taken from the query string: a caller cannot
  // impersonate another participant.
  const identity = `jimsky-${Math.random().toString(36).slice(2, 10)}`

  const at = new AccessToken(apiKey, apiSecret, {
    identity,
    name: 'JIMSKY',
    ttl: '2h',
    metadata: JSON.stringify({ app: 'jimsky-voice-web' }),
  })
  at.addGrant({
    roomJoin: true,
    room: wanted,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  })

  // Explicit agent dispatch: as soon as this participant joins, LiveKit puts the named
  // agent into the room. Disable with LIVEKIT_AGENT_NAME="-" for automatic dispatch.
  const agent = (process.env.LIVEKIT_AGENT_NAME ?? 'vex').trim()
  if (agent && agent !== '-') {
    // emptyTimeout keeps a room from lingering after everyone leaves. That matters for agent
    // dispatch: a fresh room triggers a room-level job the worker definitely accepts, while a
    // long-lived empty room can leave a just-restarted worker unable to take the job
    // ("no worker is available"). 5 minutes is plenty for a voice session to start.
    at.roomConfig = new RoomConfiguration({
      agents: [{ agentName: agent }],
      emptyTimeout: 300,
    })
  }

  const token = await at.toJwt()
  // `url`/`token` are what our web front end reads; `serverUrl`/`participantToken` are the
  // shape LiveKit's own TokenSource.endpoint() expects, so the mobile app can use this exact
  // same endpoint instead of hardcoding a second token path.
  return json(200, {
    url, token, room: wanted, identity, agent: agent === '-' ? null : agent,
    serverUrl: url, participantToken: token,
  })
}
