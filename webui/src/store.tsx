import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { ACTIVE, api, errorText, subscribeEvents, type EngineEvent, type Job, type Status } from "@/lib/api"

export type Tab = "download" | "queue" | "library" | "account" | "settings"

interface AppState {
  status: Status | null
  refreshStatus: () => Promise<void>
  jobs: Job[]
  activeCount: number
  connected: boolean
  tab: Tab
  setTab: (t: Tab) => void
  /** tăng mỗi khi 1 job kết thúc → màn Thư viện / xem trước tự tải lại */
  libraryVersion: number
  /** link đang mở ở màn Tải truyện (giữ khi chuyển tab) */
  pendingUrl: string
  openUrl: (url: string) => void
}

const Ctx = createContext<AppState | null>(null)

export function useApp() {
  const v = useContext(Ctx)
  if (!v) throw new Error("useApp ngoài AppProvider")
  return v
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [jobs, setJobs] = useState<Record<number, Job>>({})
  const [connected, setConnected] = useState(true)
  const [tab, setTab] = useState<Tab>(() => (location.hash.slice(1) as Tab) || "download")
  const [libraryVersion, setLibraryVersion] = useState(0)
  const [pendingUrl, setPendingUrl] = useState("")
  const seen = useRef(new Set<number>())

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.status())
    } catch (e) {
      toast.error(errorText(e))
    }
  }, [])

  useEffect(() => {
    refreshStatus()
    api.jobs().then((list) => setJobs(Object.fromEntries(list.map((j) => [j.id, j])))).catch(() => {})
  }, [refreshStatus])

  useEffect(() => {
    history.replaceState(null, "", `#${tab}`)
  }, [tab])

  useEffect(() => {
    const onEvent = (ev: EngineEvent) => {
      const snap = ev.snapshot
      if (!snap) return
      setJobs((prev) => ({ ...prev, [snap.id]: snap }))
      if (ev.type === "job_finished" && !seen.current.has(snap.id)) {
        seen.current.add(snap.id)
        setLibraryVersion((v) => v + 1)
        const name = snap.title.length > 48 ? snap.title.slice(0, 47) + "…" : snap.title
        if (snap.status === "done" && !snap.failed && !snap.hint) toast.success(`Đã tải xong: ${name}`)
        else if (snap.status === "done") toast.warning(`Tải xong nhưng còn thiếu: ${name}`, { description: snap.hint || `${snap.failed} chương lỗi` })
        else if (snap.status === "failed") toast.error(`Không tải được: ${name}`, { description: snap.error })
      }
    }
    return subscribeEvents(onEvent, setConnected)
  }, [])

  const jobList = useMemo(() => Object.values(jobs).sort((a, b) => b.id - a.id), [jobs])
  const activeCount = jobList.filter((j) => ACTIVE.includes(j.status)).length
  const openUrl = useCallback((url: string) => {
    setPendingUrl(url)
    setTab("download")
  }, [])

  return (
    <Ctx.Provider
      value={{ status, refreshStatus, jobs: jobList, activeCount, connected, tab, setTab, libraryVersion, pendingUrl, openUrl }}
    >
      {children}
    </Ctx.Provider>
  )
}
