import { useEffect, useState, type FormEvent } from "react"
import { Globe, Loader2, LogOut } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { api, errorText, type SourceInfo } from "@/lib/api"
import { useApp } from "@/store"

export function AccountView() {
  const { status } = useApp()
  const sources = status?.sources ?? []
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-serif text-2xl font-semibold">Tài khoản</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Một số site chỉ cho tải ảnh hoặc truyện khi đã đăng nhập. lnget chỉ lưu phiên đăng nhập trên máy này, không lưu mật khẩu.
      </p>
      <div className="mt-6 space-y-4">
        {sources.map((s) => (
          <SourceAccount key={s.id} source={s} />
        ))}
      </div>
    </div>
  )
}

function SourceAccount({ source }: { source: SourceInfo }) {
  const { refreshStatus } = useApp()
  const [user, setUser] = useState<string | null | undefined>(undefined)
  const [waitingBrowser, setWaitingBrowser] = useState(false)
  const [busy, setBusy] = useState(false)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  useEffect(() => {
    if (!source.supports_login) return
    api.whoami(source.id).then((r) => setUser(r.user)).catch(() => setUser(null))
  }, [source.id, source.supports_login])

  const done = async (who: string) => {
    setUser(who)
    setPassword("")
    toast.success(`Đã đăng nhập ${source.name}: ${who}`)
    await refreshStatus()
  }

  const browser = async () => {
    setWaitingBrowser(true)
    try {
      await done((await api.browserLogin(source.id)).user)
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setWaitingBrowser(false)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await done((await api.login(source.id, username.trim(), password)).user)
    } catch (err) {
      toast.error(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const logout = async () => {
    await api.logout(source.id)
    setUser(null)
    toast(`Đã đăng xuất ${source.name}`)
    await refreshStatus()
  }

  return (
    <section className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">{source.name}</h2>
          <p className="font-mono text-xs text-muted-foreground">{source.domain}</p>
        </div>
        {!source.supports_login ? (
          <span className="text-sm text-muted-foreground">Không cần đăng nhập</span>
        ) : user === undefined ? (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        ) : user ? (
          <div className="flex items-center gap-3">
            <span className="text-sm">
              <span className="mr-1.5 inline-block size-2 rounded-full bg-leaf" />
              {user}
            </span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut /> Đăng xuất
            </Button>
          </div>
        ) : (
          <span className="text-sm text-amber">Chưa đăng nhập</span>
        )}
      </div>

      {source.supports_login && user === null && (
        <>
          <div className="mt-5">
            <Button onClick={browser} disabled={waitingBrowser} className="w-full sm:w-auto">
              {waitingBrowser ? <Loader2 className="animate-spin" /> : <Globe />}
              {waitingBrowser ? "Đang chờ bạn đăng nhập trong cửa sổ trình duyệt…" : "Đăng nhập bằng trình duyệt"}
            </Button>
            <p className="mt-2 text-xs text-muted-foreground">
              Mở Edge/Chrome ở trang đăng nhập của {source.name}. Đăng nhập xong, cửa sổ tự đóng.
            </p>
          </div>
          <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
            <Separator className="flex-1" /> hoặc nhập tài khoản <Separator className="flex-1" />
          </div>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor={`${source.id}-user`}>Tên đăng nhập</Label>
              <Input id={`${source.id}-user`} autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`${source.id}-pass`}>Mật khẩu</Label>
              <Input id={`${source.id}-pass`} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <Button type="submit" variant="outline" disabled={busy || !username.trim() || !password}>
              {busy && <Loader2 className="animate-spin" />}
              Đăng nhập
            </Button>
          </form>
        </>
      )}
    </section>
  )
}
