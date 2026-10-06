import { useEffect, useMemo, useState } from "react"
import { Download, FolderOpen, Hammer, Search } from "lucide-react"
import { toast } from "sonner"
import { BookCover } from "@/components/BookCover"
import { FormatPicker } from "@/components/FormatPicker"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, coverUrl, errorText, FORMAT_LABEL, FORMATS, type Format, type LibraryItem } from "@/lib/api"
import { useApp } from "@/store"

export function LibraryView() {
  const { libraryVersion, setTab, openUrl } = useApp()
  const [data, setData] = useState<{ root: string; items: LibraryItem[] } | null>(null)
  const [q, setQ] = useState("")
  const [open, setOpen] = useState<LibraryItem | null>(null)

  useEffect(() => {
    api.library().then(setData).catch((e) => toast.error(errorText(e)))
  }, [libraryVersion])

  const items = useMemo(() => {
    const term = q.trim().toLowerCase()
    return (data?.items ?? []).filter((i) => !term || i.title.toLowerCase().includes(term))
  }, [data, q])

  if (!data) {
    return (
      <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="aspect-book" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold">Thư viện</h1>
          <p className="mt-1 font-mono text-xs break-all text-muted-foreground">{data.root}</p>
        </div>
        {data.items.length > 0 && (
          <div className="relative w-full sm:w-72">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm theo tên truyện" className="bg-card pl-9" aria-label="Tìm truyện" />
          </div>
        )}
      </div>

      {data.items.length === 0 ? (
        <div className="mx-auto max-w-md pt-[10vh] text-center">
          <h2 className="font-serif text-xl font-semibold">Thư viện đang trống</h2>
          <p className="mt-2 text-muted-foreground">Truyện bạn tải sẽ nằm ở đây, kèm các file đã xuất. Đổi thư mục lưu trong Cài đặt.</p>
          <Button className="mt-6" onClick={() => setTab("download")}>
            Tải truyện đầu tiên
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="mt-10 text-center text-muted-foreground">Không có truyện nào khớp “{q}”.</p>
      ) : (
        <ul className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(110px,1fr))] gap-x-4 gap-y-7 sm:grid-cols-[repeat(auto-fill,minmax(140px,1fr))] sm:gap-x-5">
          {items.map((it) => {
            const fmts = FORMATS.filter((f) => it.volumes.some((v) => v.formats.includes(f)))
            const cached = it.volumes.reduce((n, v) => n + v.cached, 0)
            const total = it.volumes.reduce((n, v) => n + v.chapters, 0)
            return (
              <li key={it.path}>
                <button onClick={() => setOpen(it)} className="group block w-full text-left outline-none">
                  <BookCover
                    src={it.has_cover ? coverUrl(it.path) : undefined}
                    title={it.title}
                    className="transition-transform duration-200 group-hover:-translate-y-1 group-focus-visible:ring-2 group-focus-visible:ring-ring"
                  />
                  <p className="mt-2 line-clamp-2 text-sm leading-snug font-medium">{it.title}</p>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                    {it.volumes.length} tập · {cached}/{total} ch.
                  </p>
                  <p className="mt-1 flex flex-wrap gap-1">
                    {fmts.map((f) => (
                      <span key={f} className="rounded bg-secondary px-1 py-px font-mono text-[10px] text-muted-foreground uppercase">
                        {f === "images" ? "ảnh" : f}
                      </span>
                    ))}
                  </p>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      <NovelDialog
        item={open}
        onClose={() => setOpen(null)}
        onUpdate={(url) => {
          setOpen(null)
          openUrl(url)
        }}
      />
    </div>
  )
}

function NovelDialog({ item, onClose, onUpdate }: { item: LibraryItem | null; onClose: () => void; onUpdate: (url: string) => void }) {
  const { setTab } = useApp()
  const [formats, setFormats] = useState<Format[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => setFormats([]), [item])

  const rebuild = async () => {
    if (!item || !formats.length) return
    setBusy(true)
    try {
      await api.rebuild({ path: item.path, formats })
      toast.success(`Đang build ${formats.map((f) => FORMAT_LABEL[f]).join(", ")}`, {
        action: { label: "Xem tiến độ", onClick: () => setTab("queue") },
      })
      onClose()
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={!!item} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        {item && (
          <>
            <DialogHeader>
              <DialogTitle className="pr-6 font-serif text-xl leading-snug">{item.title}</DialogTitle>
              <DialogDescription>{item.status || "Không rõ tình trạng"}</DialogDescription>
            </DialogHeader>
            <ul className="divide-y rounded-lg border text-sm">
              {item.volumes.map((v) => (
                <li key={v.id} className="flex items-center gap-3 px-3 py-2">
                  <span className="min-w-0 flex-1 truncate">{v.title}</span>
                  <span className={v.cached >= v.chapters ? "font-mono text-xs text-leaf" : "font-mono text-xs text-muted-foreground"}>
                    {v.cached}/{v.chapters}
                  </span>
                  <span className="w-28 text-right font-mono text-[10px] text-muted-foreground uppercase">
                    {v.formats.map((f) => (f === "images" ? "ảnh" : f)).join(" ") || "—"}
                  </span>
                </li>
              ))}
            </ul>
            <div className="space-y-2">
              <p className="text-sm font-medium">Build thêm định dạng từ chương đã tải</p>
              <p className="text-xs text-muted-foreground">Không tải lại chương; chỉ tải ảnh nếu cache ảnh đã bị xoá. Tập chưa có chương nào sẽ bỏ qua.</p>
              <FormatPicker value={formats} onChange={setFormats} />
            </div>
            <DialogFooter className="gap-2 sm:justify-between">
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => api.open(item.path).catch((e) => toast.error(errorText(e)))}>
                  <FolderOpen /> Mở thư mục
                </Button>
                <Button variant="outline" onClick={() => onUpdate(item.url)}>
                  <Download /> Tải chương mới
                </Button>
              </div>
              <Button disabled={!formats.length || busy} onClick={rebuild}>
                <Hammer /> Build
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
