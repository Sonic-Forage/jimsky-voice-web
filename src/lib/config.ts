// Runtime configuration. The token endpoint is the only thing the client has to know about
// the deployment; room + identity are decided server-side.
export interface SessionConfig {
  url: string
  token: string
  room: string
  identity: string
  agent: string | null
}

// Data channel the agent can push media down (Vex publishes here; Hermes may too).
export const MEDIA_TOPIC = 'jimsky.media'
export const TEXT_TOPIC = 'jimsky.text'

// Hermes publishes finished files to the media host, which the stage polls. This is the path
// that works with the full Hermes agent: it generates with Comfy Cloud, drops the file, and
// the browser renders it. Override at build time with VITE_MEDIA_BASE.
export const MEDIA_BASE =
  (import.meta.env.VITE_MEDIA_BASE as string | undefined)?.replace(/\/$/, '')
  || 'https://jimsky-media.15-204-82-198.nip.io'

export async function fetchSession(room?: string): Promise<SessionConfig> {
  const qs = room ? `?room=${encodeURIComponent(room)}` : ''
  const res = await fetch(`/api/token${qs}`, { headers: { accept: 'application/json' } })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: string; error?: string }).detail
      ?? (body as { error?: string }).error ?? `HTTP ${res.status}`
    throw new Error(detail)
  }
  return body as SessionConfig
}

// One item on the stage. Arrives either as base64 over the data channel (`data`) or as a
// file the agent published (`url`).
export interface MediaItem {
  id: string
  kind: 'image' | 'video' | 'audio' | 'text'
  mime: string
  data?: string
  url?: string
  caption?: string
  at: number
}

interface IndexRecord {
  id: string
  kind: MediaItem['kind']
  mime: string
  file: string
  caption?: string
  at: number
}

export async function fetchPublishedMedia(): Promise<MediaItem[]> {
  const res = await fetch(`${MEDIA_BASE}/index.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`media index HTTP ${res.status}`)
  const body = (await res.json()) as { items?: IndexRecord[] }
  return (body.items ?? []).map((r) => ({
    id: `hf-${r.id}`,
    kind: r.kind,
    mime: r.mime,
    url: `${MEDIA_BASE}/${encodeURIComponent(r.file)}`,
    caption: r.caption,
    at: r.at,
  }))
}
