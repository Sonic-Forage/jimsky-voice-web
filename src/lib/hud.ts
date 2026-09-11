// Client for the JIMSKY HUD backend. The key is stored in localStorage and sent as X-HUD-Key:
// that backend can spend money, so it refuses anonymous calls by design.

export interface HudModel {
  alias: string
  id: string
  partner: string
  category: string
  mode: string
  summary: string
  price: number
  tier?: 'new' | 'current' | 'legacy'
}

export interface HudTemplate {
  id: string
  name: string
  category: string
  prompt: string
  hint: string
}

export interface HudJob {
  id: string
  model: string
  category: string
  prompt: string
  state: 'queued' | 'running' | 'done' | 'error'
  price: number
  at: number
  url?: string
  bytes?: number
  error?: string
  title?: string
  reply?: string
}

export const HUD_BASE =
  (import.meta.env.VITE_HUD_BASE as string | undefined)?.replace(/\/$/, '')
  || 'https://jimsky-hud.15-204-82-198.nip.io'

const KEY_STORE = 'jimsky.hud.key'

export function getKey(): string {
  return localStorage.getItem(KEY_STORE) ?? ''
}

export function setKey(value: string): void {
  localStorage.setItem(KEY_STORE, value.trim())
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${HUD_BASE}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      'x-hud-key': getKey(),
      ...(init?.headers ?? {}),
    },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: string }).detail ?? `HTTP ${res.status}`
    throw new Error(detail)
  }
  return body as T
}

export interface Catalog {
  models: HudModel[]
  templates: HudTemplate[]
  counts: { models: number; templates: number }
  credits: number
  max_batch: number
}

export const fetchCatalog = () => call<Catalog>('/api/catalog')
export const fetchJobs = () => call<{ jobs: HudJob[]; credits: number }>('/api/jobs?limit=40')
export const createJobs = (payload: {
  model: string; prompt: string; n?: number; image?: string | null; caption?: string
}) => call<{ jobs: HudJob[]; credits: number }>('/api/create', {
  method: 'POST', body: JSON.stringify(payload),
})
export const browseUrl = (url: string, full_page = false) =>
  call<{ job: HudJob; credits: number }>('/api/browse', {
    method: 'POST', body: JSON.stringify({ url, full_page }),
  })
export const redeemCode = (code: string) =>
  call<{ balance: number; added: number }>('/api/credits/redeem', {
    method: 'POST', body: JSON.stringify({ code }),
  })
export interface HudMod {
  id: string
  name: string
  status: string
  what: string
  requires?: string[]
  missing?: string[]
  run?: string
  path?: string
  persona?: string
  overlays?: string
  docs?: string
  source?: string
  verified?: string
  console?: string
}

export interface HudWorkflow {
  id: string
  name: string
  model: string
  prompt: string
  notes?: string
  builtin?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  at: number
  seconds?: number
  error?: boolean
}

export const fetchChat = () =>
  call<{ messages: ChatMessage[]; session: string }>('/api/chat')
export const sendChat = (message: string) =>
  call<{ job: HudJob }>('/api/chat', { method: 'POST', body: JSON.stringify({ message }) })
export const clearChat = () =>
  call<{ messages: ChatMessage[] }>('/api/chat/clear', { method: 'POST', body: '{}' })

export interface HudSettings {
  comfy_endpoint: string
  comfy_endpoint_label?: string
  livekit_url: string
  media_base: string
  default_model: string
  default_batch: number
  new_stack_only: boolean
  auto_publish: boolean
  chat_dock: 'float' | 'column'
  accent: 'teal' | 'magenta' | 'amber'
  panels: Record<string, boolean>
}

export interface ComfyPreset { id: string; label: string; url: string; note: string }
export interface ComfyProbe {
  ok: boolean; url: string; detail?: string; comfyui_version?: string
  device?: string; vram_total_gb?: number; vram_free_gb?: number; nodes?: number | null
}
export interface HudTemplate {
  name: string; title: string; category: string; group: string; media: string
  description: string; tags: string[]; models: string[]; tutorial: string; date: string
  json_url: string
}

export const fetchSettings = () => call<{ settings: HudSettings }>('/api/settings')
export const saveSettings = (settings: Partial<HudSettings>) =>
  call<{ settings: HudSettings }>('/api/settings', { method: 'POST', body: JSON.stringify({ settings }) })
export const fetchComfyPresets = () =>
  call<{ presets: ComfyPreset[]; current: string }>('/api/comfy/presets')
export const testComfy = (url: string) =>
  call<ComfyProbe>('/api/comfy/test', { method: 'POST', body: JSON.stringify({ url }) })
export const fetchTemplates = (q = '', limit = 300) =>
  call<{ templates: HudTemplate[]; count: number; categories: string[]; shown: number }>(
    `/api/templates?q=${encodeURIComponent(q)}&limit=${limit}`)
export const fetchTemplateJson = (name: string) =>
  call<{ name: string; workflow: unknown }>(`/api/templates/json?name=${encodeURIComponent(name)}`)

export const fetchMods = () => call<{ mods: HudMod[] }>('/api/mods')
export const fetchWorkflows = () => call<{ workflows: HudWorkflow[] }>('/api/workflows')
export const saveWorkflow = (workflow: Partial<HudWorkflow>) =>
  call<{ workflow: HudWorkflow; workflows: HudWorkflow[] }>('/api/workflows', {
    method: 'POST', body: JSON.stringify({ workflow }),
  })
export const deleteWorkflow = (id: string) =>
  call<{ workflows: HudWorkflow[] }>('/api/workflows/delete', {
    method: 'POST', body: JSON.stringify({ id }),
  })
export const runWorkflow = (id: string, subject?: string, n = 1) =>
  call<{ jobs: HudJob[]; credits: number }>('/api/workflows/run', {
    method: 'POST', body: JSON.stringify({ id, subject, n }),
  })

export const askAgent = (prompt: string) =>
  call<{ job: HudJob }>('/api/agent', { method: 'POST', body: JSON.stringify({ prompt }) })
