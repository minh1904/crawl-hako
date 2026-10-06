// Client cho API local của lnget (lnget/web/server.py)

export type Format = "epub" | "docx" | "pdf" | "images"

export interface Settings {
  output: string
  formats: Format[]
  delay: number
  chapter_workers: number
  image_workers: number
  split_by_status: boolean
  keep_image_cache: boolean
  domains: Record<string, string>
}

export interface SourceInfo {
  id: string
  name: string
  domain: string
  supports_login: boolean
  supports_listing: boolean
  has_session: boolean
}

export interface Status {
  version: string
  settings: Settings
  formats: Format[]
  sources: SourceInfo[]
}

export interface PreviewVolume {
  id: string
  title: string
  cover_url: string
  chapters: { id: string; title: string; locked: boolean }[]
  cached: number
  formats: Format[]
}

export interface Preview {
  source: string
  source_name: string
  id: string
  url: string
  title: string
  author: string
  status: string
  completed: boolean
  kind: "translation" | "machine" | "original"
  translator: string
  description: string
  genres: string[]
  cover_url: string
  volumes: PreviewVolume[]
  path: string
  logged_in: boolean
}

export type JobStatus = "queued" | "running" | "paused" | "done" | "failed" | "cancelled"

export interface Job {
  id: number
  status: JobStatus
  title: string
  url: string
  source: string
  path: string
  formats: Format[]
  error: string
  hint: string
  created: number
  finished: number
  total: number
  done: number
  failed: number
  images_ok: number
  images_failed: number
  volume: string
  outputs: string[]
  login_needed: number
  rebuild: boolean
}

export interface LibraryVolume {
  id: string
  title: string
  chapters: number
  cached: number
  formats: Format[]
}

export interface LibraryItem {
  path: string
  source: string
  id: string
  title: string
  url: string
  status: string
  completed: boolean
  kind: string
  has_cover: boolean
  updated: number
  volumes: LibraryVolume[]
}

export interface EngineEvent {
  type: string
  job: number | null
  ts: number
  snapshot?: Job
  [key: string]: unknown
}

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-Lnget": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = `Lỗi ${res.status}`
    try {
      const data = await res.json()
      if (typeof data.detail === "string") msg = data.detail
    } catch {
      /* phản hồi không phải JSON */
    }
    throw new ApiError(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  status: () => request<Status>("GET", "/api/status"),
  saveSettings: (s: Partial<Settings>) => request<Settings>("PUT", "/api/settings", s),
  whoami: (sid: string) => request<{ user: string | null }>("GET", `/api/accounts/${sid}`),
  login: (sid: string, username: string, password: string) =>
    request<{ user: string }>("POST", `/api/accounts/${sid}/login`, { username, password }),
  browserLogin: (sid: string) => request<{ user: string }>("POST", `/api/accounts/${sid}/browser-login`),
  logout: (sid: string) => request<{ user: null }>("POST", `/api/accounts/${sid}/logout`),
  preview: (url: string) => request<Preview>("POST", "/api/preview", { url }),
  jobs: () => request<Job[]>("GET", "/api/jobs"),
  createJob: (body: { url: string; formats: Format[]; volume_ids?: string[]; refetch?: boolean }) =>
    request<Job>("POST", "/api/jobs", body),
  jobAction: (id: number, action: "pause" | "resume" | "cancel" | "retry") =>
    request<Job>("POST", `/api/jobs/${id}/${action}`),
  deleteJob: (id: number) => request<{ ok: boolean }>("DELETE", `/api/jobs/${id}`),
  clearJobs: () => request<{ ok: boolean }>("POST", "/api/jobs/clear"),
  library: () => request<{ root: string; items: LibraryItem[] }>("GET", "/api/library"),
  rebuild: (body: { path: string; formats: Format[]; volume_ids?: string[] }) =>
    request<Job>("POST", "/api/library/rebuild", body),
  open: (path: string) => request<{ ok: boolean }>("POST", "/api/open", { path }),
}

export const imageUrl = (url: string, source: string) =>
  `/api/image?url=${encodeURIComponent(url)}&source=${encodeURIComponent(source)}`

export const coverUrl = (path: string) => `/api/library/cover?path=${encodeURIComponent(path)}`

export const FORMATS: Format[] = ["epub", "docx", "pdf", "images"]
export const FORMAT_LABEL: Record<Format, string> = { epub: "EPUB", docx: "DOCX", pdf: "PDF", images: "Ảnh" }
export const FORMAT_HINT: Record<Format, string> = {
  epub: "Máy đọc sách, app đọc truyện",
  docx: "Mở bằng Word, sửa được",
  pdf: "Đọc trên máy tính, in ra giấy",
  images: "Thư mục ảnh minh hoạ",
}

export const ACTIVE: JobStatus[] = ["queued", "running", "paused"]

export function subscribeEvents(onEvent: (ev: EngineEvent) => void, onState: (ok: boolean) => void) {
  const es = new EventSource("/api/events")
  es.onopen = () => onState(true)
  es.onerror = () => onState(false)
  es.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data))
    } catch {
      /* bỏ qua event hỏng */
    }
  }
  return () => es.close()
}

export const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e))
