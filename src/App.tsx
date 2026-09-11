import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useDataChannel,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from '@livekit/components-react'
import { ConnectionState, type Room } from 'livekit-client'
import {
  MEDIA_TOPIC, TEXT_TOPIC, fetchPublishedMedia, fetchSession,
  type MediaItem, type SessionConfig,
} from './lib/config'

/* ------------------------------------------------------------------ helpers */

function useClock() {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  return now
}

function stamp(ms: number) {
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function b64ToUrl(mime: string, data: string) {
  try {
    const bin = atob(data)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return URL.createObjectURL(new Blob([bytes], { type: mime }))
  } catch {
    return ''
  }
}

/* ------------------------------------------------------------------ connect screen */

function ConnectScreen({ onConnect, error }: { onConnect: (room: string) => void; error: string | null }) {
  const [room, setRoom] = useState('vex-voice')
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    await onConnect(room)
    setBusy(false)
  }
  return (
    <div className="gate">
      <div className="gate-inner">
        <div className="mark">
          <span className="glyph">▚</span>
          <h1>JIMSKY</h1>
          <p className="sub">VOICE LINK <b>·</b> REALTIME <b>·</b> SELF-HOSTED</p>
        </div>
        <p className="pitch">
          Talk to JIMSKY. It hears you through LiveKit, runs on Hermes — your sessions, your memory,
          your tools — and what it builds lands on the stage in front of you.
        </p>
        <div className="gate-row">
          <label htmlFor="room">ROOM</label>
          <input id="room" value={room} onChange={(e) => setRoom(e.target.value)}
                 spellCheck={false} autoComplete="off" />
          <button className="cta" onClick={go} disabled={busy}>
            {busy ? 'LINKING…' : 'INITIALIZE LINK'}
          </button>
        </div>
        {error && <p className="err">⚠ {error}</p>}
        <p className="tiny">
          Mic access is requested on connect. Audio never leaves the room; tokens are minted server-side
          and scoped to one room for two hours.
        </p>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ media stage */

function MediaStage({ items, state, audioTrack, onClear }: {
  items: MediaItem[]
  state: string
  audioTrack: MediaStreamTrack | undefined
  onClear: () => void
}) {
  const urls = useMemo(
    () => items.map((m) => ({
      ...m,
      src: m.url ?? (m.data && m.kind !== 'text' ? b64ToUrl(m.mime, m.data) : ''),
      fromNetwork: Boolean(m.url),
    })),
    [items],
  )
  // Only object URLs we created need revoking; published files are plain https URLs.
  useEffect(() => () => urls.forEach((u) => { if (u.src && !u.fromNetwork) URL.revokeObjectURL(u.src) }), [urls])

  const [hero, ...rest] = urls
  return (
    <section className="stage">
      <div className="stage-head">
        <span className="tag">STAGE</span>
        <span className="count">{items.length ? `${items.length} ITEM${items.length > 1 ? 'S' : ''}` : 'IDLE'}</span>
        <span className="spacer" />
        {items.length > 0 && <button className="mini" onClick={onClear}>CLEAR</button>}
      </div>

      {hero ? (
        <div className="hero">
          {hero.kind === 'image' && <img src={hero.src} alt={hero.caption ?? 'agent output'} />}
          {hero.kind === 'video' && <video src={hero.src} controls autoPlay playsInline />}
          {hero.kind === 'audio' && <audio src={hero.src} controls autoPlay />}
          <div className="hero-cap">
            <span className="kind">{hero.kind.toUpperCase()}</span>
            <span className="cap">{hero.caption ?? '—'}</span>
            <span className="ts">{hero.fromNetwork ? '← hermes' : '← agent'} · {stamp(hero.at)}</span>
          </div>
        </div>
      ) : (
        <div className="idle">
          <div className="orb" data-state={state} />
          <p className="idle-text">
            {state === 'speaking' ? 'JIMSKY IS SPEAKING'
              : state === 'thinking' ? 'JIMSKY IS THINKING'
              : state === 'listening' ? 'LISTENING — ASK FOR SOMETHING'
              : 'WAITING FOR THE AGENT'}
          </p>
          <p className="idle-sub">Ask for an image, a video, a track, a lookup. It shows up here.</p>
        </div>
      )}

      {rest.length > 0 && (
        <div className="thumbs">
          {rest.map((m) => (
            <div key={m.id} className="thumb" title={m.caption}>
              {m.kind === 'image' && <img src={m.src} alt={m.caption ?? ''} />}
              {m.kind === 'video' && <video src={m.src} muted playsInline />}
              {m.kind === 'audio' && <div className="aud">♪</div>}
              <span className="t">{m.kind.slice(0, 3).toUpperCase()}</span>
            </div>
          ))}
        </div>
      )}

      <div className="viz">
        <BarVisualizer state={state as never} track={audioTrack} barCount={32} barSize={4} minHeight={6} />
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ in-room shell */

function RoomShell({ onLeave }: { onLeave: () => void }) {
  const room = useRoomContext()
  const connState = useConnectionState()
  const { state, audioTrack } = useVoiceAssistant()
  const { localParticipant } = useLocalParticipant()
  const { microphoneTrack, isMicrophoneEnabled } = localParticipant
  const segments = useTranscriptions()

  const [media, setMedia] = useState<MediaItem[]>([])
  const [log, setLog] = useState<string[]>([])
  const [typed, setTyped] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  const note = useCallback((line: string) => {
    setLog((l) => [...l.slice(-80), `${stamp(Date.now())}  ${line}`])
  }, [])

  // Media pushed by the agent arrives on the data channel, not as a file to fetch.
  useDataChannel(MEDIA_TOPIC, (msg) => {
    try {
      const text = new TextDecoder().decode(msg.payload)
      const parsed = JSON.parse(text) as Partial<MediaItem> & { type?: string }
      const kind = (parsed.kind ?? parsed.type ?? 'image') as MediaItem['kind']
      if (!parsed.data) { note(`media packet without data (${kind})`); return }
      const item: MediaItem = {
        id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        kind, mime: parsed.mime ?? 'image/png', data: parsed.data,
        caption: parsed.caption, at: Date.now(),
      }
      setMedia((m) => [item, ...m].slice(0, 40))
      note(`← ${kind} received (${(parsed.data.length / 1365).toFixed(0)} KB)`)
    } catch (e) {
      note(`media decode failed: ${(e as Error).message}`)
    }
  })

  // Poll what Hermes published. Cheap (one small JSON), and it means the stage works with
  // the full Hermes agent and Comfy Cloud without any agent-side protocol changes.
  useEffect(() => {
    let stop = false
    let lastCount = -1
    const tick = async () => {
      try {
        const found = await fetchPublishedMedia()
        if (stop) return
        if (found.length !== lastCount) {
          if (lastCount >= 0 && found.length > lastCount) note(`← ${found.length - lastCount} new item(s) published`)
          lastCount = found.length
        }
        setMedia((current) => {
          const local = current.filter((m) => m.id.startsWith('local-'))
          const seen = new Set(local.map((m) => m.id))
          const merged = [...found.filter((f) => !seen.has(f.id)), ...local]
          return merged.sort((a, b) => b.at - a.at).slice(0, 40)
        })
      } catch { /* media host unreachable is not a call failure */ }
    }
    void tick()
    const t = setInterval(tick, 4000)
    return () => { stop = true; clearInterval(t) }
  }, [note])

  useEffect(() => { logRef.current?.scrollTo({ top: 1e9 }) }, [log])
  useEffect(() => {
    note(`connected to ${room.name} as ${localParticipant.identity}`)
    const onPart = (p: { identity: string }) => note(`participant joined: ${p.identity}`)
    const onLeft = (p: { identity: string }) => note(`participant left: ${p.identity}`)
    room.on('participantConnected', onPart)
    room.on('participantDisconnected', onLeft)
    return () => { room.off('participantConnected', onPart); room.off('participantDisconnected', onLeft) }
  }, [room, localParticipant.identity, note])

  const toggleMic = async () => {
    try {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)
      note(`mic ${!isMicrophoneEnabled ? 'live' : 'muted'}`)
    } catch (e) { note(`mic toggle failed: ${(e as Error).message}`) }
  }

  const sendText = async () => {
    const value = typed.trim()
    if (!value) return
    setTyped('')
    try {
      await room.localParticipant.sendText(value, { topic: TEXT_TOPIC })
      note(`→ text sent: ${value.slice(0, 48)}`)
    } catch (e) { note(`text send failed: ${(e as Error).message}`) }
  }

  const agents = room.remoteParticipants.size
  return (
    <div className="shell">
      <header className="hud">
        <span className="glyph">▚</span>
        <h1>JIMSKY</h1>
        <span className="room">ROOM {room.name}</span>
        <span className={`chip state-${state}`}>{String(state).toUpperCase()}</span>
        <span className={`chip conn conn-${connState}`}>{connState.toUpperCase()}</span>
        <span className="spacer" />
        <span className="peers">{agents} REMOTE · {room.numParticipants} IN ROOM</span>
        <button className="mini danger" onClick={onLeave}>DISCONNECT</button>
      </header>

      <main className="body">
        <MediaStage items={media} state={String(state)} audioTrack={audioTrack ?? undefined} onClear={() => setMedia([])} />

        <aside className="side">
          <div className="panel">
            <div className="panel-head"><span className="tag">TRANSCRIPT</span></div>
            <div className="scroller">
              {segments.length === 0 && <p className="muted">Nothing transcribed yet. Start talking.</p>}
              {segments.map((s, i) => (
                <p key={i} className={`seg ${s.participantInfo?.identity === localParticipant.identity ? 'me' : 'them'}`}>
                  <span className="who">{(s.participantInfo?.identity ?? 'unknown').slice(0, 14)}</span>
                  {s.text}
                </p>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head"><span className="tag">CONTROL LOG</span></div>
            <div className="scroller mono" ref={logRef}>
              {log.map((l, i) => <p key={i} className="logline">{l}</p>)}
            </div>
          </div>
        </aside>
      </main>

      <footer className="controls">
        <button className={`pill ${isMicrophoneEnabled ? 'on' : ''}`} onClick={toggleMic}>
          {isMicrophoneEnabled ? '● MIC LIVE' : '○ MIC MUTED'}
        </button>
        <div className="typebox">
          <input
            placeholder="…or type here (Enter sends)"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void sendText() }}
          />
          <button className="mini" onClick={() => void sendText()}>SEND</button>
        </div>
        <span className="hint">tracks: {microphoneTrack ? 'mic' : 'none'} · media channel: {MEDIA_TOPIC}</span>
      </footer>

      <RoomAudioRenderer />
    </div>
  )
}

/* ------------------------------------------------------------------ app */

export default function App() {
  const [session, setSession] = useState<SessionConfig | null>(null)
  const [error, setError] = useState<string | null>(null)

  const connect = async (room: string) => {
    setError(null)
    try {
      setSession(await fetchSession(room))
    } catch (e) {
      setError((e as Error).message)
      throw e
    }
  }

  if (!session) return <ConnectScreen onConnect={connect} error={error} />

  return (
    <LiveKitRoom
      token={session.token}
      serverUrl={session.url}
      connect
      audio
      video={false}
      onDisconnected={() => setSession(null)}
      onError={(e) => setError(e.message)}
      data-lk-theme="default"
      style={{ height: '100%' }}
    >
      <RoomShell onLeave={() => setSession(null)} />
    </LiveKitRoom>
  )
}
