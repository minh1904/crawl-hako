import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import { ArrowRight, Check, FolderOpen, Loader2, Lock, LogIn, RotateCw } from "lucide-react"
import { toast } from "sonner"
import { BookCover } from "@/components/BookCover"
import { FormatPicker } from "@/components/FormatPicker"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { ACTIVE, api, errorText, imageUrl, type Format, type Preview, type PreviewVolume } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useApp } from "@/store"

const KIND_LABEL = { translation: "Truyện dịch", machine: "AI dịch", original: "Sáng tác" } as const

export function DownloadView() {
  const { status, pendingUrl, libraryVersion, setTab, jobs } = useApp()
  const [url, setUrl] = useState(pendingUrl)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [novel, setNovel] = useState<Preview | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [formats, setFormats] = useState<Format[]>([])
  const [refetch, setRefetch] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (status && formats.length === 0) setFormats(status.settings.formats)
  }, [status, formats.length])

  const load = async (target: string, keepSelection = false) => {
    if (!target.trim()) return
    setLoading(true)
    setError("")
    try {
      const n = await api.preview(target.trim())
      setNovel(n)
      if (!keepSelection) {
        // mặc định chọn các tập chưa tải đủ; tải đủ hết rồi thì chọn tất cả
        const missing = n.volumes.filter((v) => v.cached < v.chapters.length).map((v) => v.id)
        setSelected(new Set(missing.length ? missing : n.volumes.map((v) => v.id)))
      }
    } catch (e) {
      setError(errorText(e))
      setNovel(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (pendingUrl) {
      setUrl(pendingUrl)
      load(pendingUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingUrl])

  // job của truyện này xong → cập nhật số chương đã có / file đã xuất
  useEffect(() => {
    if (novel && libraryVersion) load(novel.url, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libraryVersion])

  const activeJob = useMemo(
    () => (novel ? jobs.find((j) => ACTIVE.includes(j.status) && !j.rebuild && j.title === novel.title) : undefined),
    [jobs, novel],
  )
  const chosen = novel?.volumes.filter((v) => selected.has(v.id)) ?? []
  const chapterCount = chosen.reduce((n, v) => n + v.chapters.length, 0)
  const source = status?.sources.find((s) => s.id === novel?.source)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    await load(url)
  }

  const start = async () => {
    if (!novel || !chosen.length || !formats.length) return
    setSubmitting(true)
    try {
      await api.createJob({ url: novel.url, formats, volume_ids: chosen.map((v) => v.id), refetch })
      toast.success(`Đã thêm vào hàng đợi: ${chosen.length} tập`, {
        action: { label: "Xem tiến độ", onClick: () => setTab("queue") },
      })
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setSubmitting(false)
    }
  }

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <div className={cn("pb-28", !novel && "pb-0")}>
      {/* Ô dán link */}
      <form onSubmit={submit} className={cn("max-w-3xl transition-all", novel ? "pt-2" : "mx-auto pt-[12vh]")}>
        {!novel && (
          <h1 className="mb-6 font-serif text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Dán link truyện, chọn tập, <span className="text-sakura italic">nhận sách.</span>
          </h1>
        )}
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onPaste={(e) => {
              const text = e.clipboardData.getData("text").trim()
              if (text.startsWith("http")) {
                e.preventDefault()
                setUrl(text)
                load(text)
              }
            }}
            placeholder="https://docln.sbs/truyen/…"
            aria-label="Link truyện"
            className="h-12 bg-card text-base"
            autoFocus
          />
          <Button type="submit" size="lg" className="h-12 px-5" disabled={loading || !url.trim()}>
            {loading ? <Loader2 className="animate-spin" /> : <ArrowRight />}
            Xem truyện
          </Button>
        </div>
        {!novel && !loading && (
          <p className="mt-3 text-sm text-muted-foreground">
            Hỗ trợ:{" "}
            {status?.sources.map((s, i) => (
              <span key={s.id}>
                {i > 0 && ", "}
                <span className="font-medium text-foreground">{s.name}</span> <span className="font-mono text-xs">({s.domain})</span>
              </span>
            ))}
            . Dán link là tự mở.
          </p>
        )}
        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </form>

      {loading && !novel && <PreviewSkeleton />}

      {novel && (
        <div className={cn("mt-8 transition-opacity", loading && "opacity-60")}>
          <NovelHeader novel={novel} />

          {source?.supports_login && !novel.logged_in && (
            <Alert className="mt-6 border-amber/40 bg-amber/5">
              <Lock className="text-amber" />
              <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-foreground">
                <span>Một số chương và ảnh trên {source.name} chỉ tải được khi đã đăng nhập.</span>
                <Button size="sm" variant="outline" onClick={() => setTab("account")}>
                  <LogIn /> Đăng nhập
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Kệ sách */}
          <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
            <h2 className="font-serif text-xl font-semibold">
              {novel.volumes.length} tập
              <span className="ml-2 font-sans text-sm font-normal text-muted-foreground">bấm vào bìa để chọn</span>
            </h2>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set(novel.volumes.map((v) => v.id)))}>
                Chọn tất cả
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelected(new Set(novel.volumes.filter((v) => v.cached < v.chapters.length).map((v) => v.id)))}
              >
                Chỉ tập còn thiếu
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                Bỏ chọn
              </Button>
            </div>
          </div>
          {novel.volumes.length === 0 ? (
            <p className="mt-6 text-muted-foreground">Truyện này chưa có chương nào.</p>
          ) : (
            <ul className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(100px,1fr))] gap-x-3 gap-y-6 sm:grid-cols-[repeat(auto-fill,minmax(128px,1fr))] sm:gap-x-4">
              {novel.volumes.map((v) => (
                <VolumeBook
                  key={v.id}
                  v={v}
                  source={novel.source}
                  selected={selected.has(v.id)}
                  downloading={activeJob?.volume === v.title}
                  onToggle={() => toggle(v.id)}
                />
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Thanh hành động */}
      {novel && novel.volumes.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3">
            <div className="min-w-0 text-sm">
              {chosen.length ? (
                <>
                  <span className="font-semibold">{chosen.length} tập</span>
                  <span className="text-muted-foreground"> · {chapterCount} chương</span>
                </>
              ) : (
                <span className="text-muted-foreground">Chưa chọn tập nào</span>
              )}
              {activeJob && (
                <span className="ml-3 inline-flex items-center gap-1 text-sakura">
                  <Loader2 className="size-3.5 animate-spin" /> đang tải {activeJob.done}/{activeJob.total}
                </span>
              )}
            </div>
            <FormatPicker value={formats} onChange={setFormats} />
            <div className="flex items-center gap-2">
              <Checkbox id="refetch" checked={refetch} onCheckedChange={(c) => setRefetch(c === true)} />
              <Label htmlFor="refetch" className="text-sm font-normal text-muted-foreground">
                Tải lại chương đã có
              </Label>
            </div>
            <Button className="ml-auto bg-sakura text-white hover:bg-sakura/90" size="lg" disabled={!chosen.length || !formats.length || submitting} onClick={start}>
              {submitting ? <Loader2 className="animate-spin" /> : null}
              {chosen.length ? `Tải ${chosen.length} tập` : "Tải"}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function NovelHeader({ novel }: { novel: Preview }) {
  const [more, setMore] = useState(false)
  const chapters = novel.volumes.reduce((n, v) => n + v.chapters.length, 0)
  return (
    <section className="grid gap-6 sm:grid-cols-[160px_1fr]">
      <BookCover src={novel.cover_url ? imageUrl(novel.cover_url, novel.source) : undefined} title={novel.title} className="w-32 sm:w-40" />
      <div className="min-w-0">
        <p className="text-xs font-semibold tracking-[0.14em] text-sakura uppercase">
          {KIND_LABEL[novel.kind]} · {novel.source_name}
        </p>
        <h1 className="mt-2 font-serif text-2xl leading-tight font-semibold text-balance sm:text-3xl">{novel.title}</h1>
        <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {novel.author && <Meta k="Tác giả" v={novel.author} />}
          {novel.translator && <Meta k="Nhóm dịch" v={novel.translator} />}
          <Meta k="Tình trạng" v={novel.status || "Không rõ"} />
          <Meta k="Quy mô" v={`${novel.volumes.length} tập · ${chapters} chương`} />
        </dl>
        {novel.genres.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {novel.genres.map((g) => (
              <Badge key={g} variant="secondary" className="font-normal">
                {g}
              </Badge>
            ))}
          </div>
        )}
        {novel.description && (
          <div className="mt-4 max-w-prose text-sm leading-relaxed text-muted-foreground">
            <p className={cn("whitespace-pre-line", !more && "line-clamp-3")}>{novel.description}</p>
            <button className="mt-1 text-xs font-medium text-foreground underline-offset-4 hover:underline" onClick={() => setMore(!more)}>
              {more ? "Thu gọn" : "Xem thêm"}
            </button>
          </div>
        )}
        {novel.path && (
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline" className="border-leaf/40 text-leaf">
              <Check /> Đã có trong thư viện
            </Badge>
            <Button variant="ghost" size="sm" onClick={() => api.open(novel.path).catch((e) => toast.error(errorText(e)))}>
              <FolderOpen /> Mở thư mục
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-1.5">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-medium">{v}</dd>
    </div>
  )
}

function VolumeBook({
  v,
  source,
  selected,
  downloading,
  onToggle,
}: {
  v: PreviewVolume
  source: string
  selected: boolean
  downloading: boolean
  onToggle: () => void
}) {
  const total = v.chapters.length
  const complete = v.cached >= total
  const locked = v.chapters.filter((c) => c.locked).length
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        aria-pressed={selected}
        className="group block w-full text-left outline-none"
      >
        <div
          className={cn(
            "relative rounded-md ring-offset-2 ring-offset-background transition-all duration-200",
            selected ? "-translate-y-1 ring-2 ring-sakura" : "opacity-80 group-hover:opacity-100",
            "group-focus-visible:ring-2 group-focus-visible:ring-ring",
          )}
        >
          <BookCover src={v.cover_url ? imageUrl(v.cover_url, source) : undefined} title={v.title} />
          <span
            className={cn(
              "absolute top-2 right-2 grid size-6 place-items-center rounded-full border-2 transition-colors",
              selected ? "border-sakura bg-sakura text-white" : "border-white/80 bg-black/30 text-transparent",
            )}
          >
            <Check className="size-3.5" strokeWidth={3} />
          </span>
          {downloading && (
            <span className="absolute inset-x-0 bottom-0 h-1 overflow-hidden rounded-b-md bg-black/30">
              <span className="block h-full w-1/3 animate-[slide_1.2s_ease-in-out_infinite] bg-sakura" />
            </span>
          )}
        </div>
        <p className="mt-2 line-clamp-2 text-sm leading-snug font-medium">{v.title}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          <span className={cn("font-mono", complete && "text-leaf")}>
            {v.cached ? `${v.cached}/${total}` : total} ch.
          </span>
          {locked > 0 && (
            <span className="inline-flex items-center gap-0.5 text-amber">
              <Lock className="size-3" />
              {locked}
            </span>
          )}
          {downloading && (
            <span className="inline-flex items-center gap-1 text-sakura">
              <RotateCw className="size-3 animate-spin" /> đang tải
            </span>
          )}
        </p>
        {v.formats.length > 0 && (
          <p className="mt-1 flex flex-wrap gap-1">
            {v.formats.map((f) => (
              <span key={f} className="rounded bg-secondary px-1 py-px font-mono text-[10px] text-muted-foreground uppercase">
                {f === "images" ? "ảnh" : f}
              </span>
            ))}
          </p>
        )}
      </button>
    </li>
  )
}

function PreviewSkeleton() {
  return (
    <div className="mt-8 grid gap-6 sm:grid-cols-[160px_1fr]">
      <Skeleton className="aspect-book w-32 sm:w-40" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-16 w-full max-w-prose" />
      </div>
    </div>
  )
}
