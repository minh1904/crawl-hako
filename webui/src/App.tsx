import { useEffect, useState } from "react"
import { Monitor, Moon, Sun, Unplug } from "lucide-react"
import { Toaster } from "sonner"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { TooltipProvider } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { AppProvider, useApp, type Tab } from "@/store"
import { AccountView } from "@/views/AccountView"
import { DownloadView } from "@/views/DownloadView"
import { LibraryView } from "@/views/LibraryView"
import { QueueView } from "@/views/QueueView"
import { SettingsView } from "@/views/SettingsView"

type Theme = "light" | "dark" | "system"

function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem("lnget-theme") as Theme) || "system"
    } catch {
      return "system"
    }
  })
  const [dark, setDark] = useState(false)
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      const d = theme === "dark" || (theme === "system" && mq.matches)
      document.documentElement.classList.toggle("dark", d)
      setDark(d)
    }
    apply()
    mq.addEventListener("change", apply)
    try {
      localStorage.setItem("lnget-theme", theme)
    } catch {
      /* chế độ riêng tư */
    }
    return () => mq.removeEventListener("change", apply)
  }, [theme])
  return { theme, setTheme, dark }
}

const NAV: { id: Tab; label: string }[] = [
  { id: "download", label: "Tải truyện" },
  { id: "queue", label: "Hàng đợi" },
  { id: "library", label: "Thư viện" },
  { id: "account", label: "Tài khoản" },
  { id: "settings", label: "Cài đặt" },
]

export function App() {
  const { theme, setTheme, dark } = useTheme()
  return (
    <AppProvider>
      <TooltipProvider delayDuration={300}>
        <Shell theme={theme} setTheme={setTheme} />
        <Toaster theme={dark ? "dark" : "light"} position="top-right" richColors closeButton />
      </TooltipProvider>
    </AppProvider>
  )
}

function Shell({ theme, setTheme }: { theme: Theme; setTheme: (t: Theme) => void }) {
  const { tab, setTab, activeCount, connected } = useApp()
  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4">
          <button onClick={() => setTab("download")} className="flex items-baseline gap-0.5 py-3 font-serif text-xl font-semibold tracking-tight outline-none focus-visible:ring-2 focus-visible:ring-ring">
            ln<span className="text-sakura">get</span>
          </button>
          <nav className="-mb-px flex flex-1 gap-1 overflow-x-auto" aria-label="Điều hướng">
            {NAV.map((n) => (
              <button
                key={n.id}
                onClick={() => setTab(n.id)}
                aria-current={tab === n.id ? "page" : undefined}
                className={cn(
                  "relative shrink-0 border-b-2 px-3 py-3.5 text-sm font-medium transition-colors outline-none focus-visible:text-foreground",
                  tab === n.id ? "border-sakura text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {n.label}
                {n.id === "queue" && activeCount > 0 && (
                  <span className="ml-1.5 inline-grid min-w-5 place-items-center rounded-full bg-sakura px-1.5 font-mono text-[11px] leading-5 text-white">
                    {activeCount}
                  </span>
                )}
              </button>
            ))}
          </nav>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Giao diện sáng/tối">
                <ThemeIcon />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
                <DropdownMenuRadioItem value="system">Theo hệ thống</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="light">Sáng</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="dark">Tối</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {!connected && (
        <div role="alert" className="flex items-center justify-center gap-2 bg-destructive px-4 py-2 text-sm text-white">
          <Unplug className="size-4" /> Mất kết nối với lnget. Kiểm tra cửa sổ lnget còn chạy không — trang sẽ tự kết nối lại.
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 py-8">
        {tab === "download" && <DownloadView />}
        {tab === "queue" && <QueueView />}
        {tab === "library" && <LibraryView />}
        {tab === "account" && <AccountView />}
        {tab === "settings" && <SettingsView />}
      </main>
    </div>
  )
}
