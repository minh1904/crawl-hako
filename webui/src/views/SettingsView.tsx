import { useEffect, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { FormatPicker } from "@/components/FormatPicker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { api, errorText, type Settings } from "@/lib/api"
import { useApp } from "@/store"

export function SettingsView() {
  const { status, refreshStatus } = useApp()
  const [s, setS] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (status) setS(structuredClone(status.settings))
  }, [status])

  if (!s || !status) return null
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS({ ...s, [k]: v })
  const dirty = JSON.stringify(s) !== JSON.stringify(status.settings)

  const save = async () => {
    setSaving(true)
    try {
      await api.saveSettings(s)
      await refreshStatus()
      toast.success("Đã lưu cài đặt")
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl pb-10">
      <h1 className="font-serif text-2xl font-semibold">Cài đặt</h1>

      <Group title="Lưu file">
        <Field label="Thư mục lưu truyện" hint="Đường dẫn đầy đủ, ví dụ D:\Truyen. Thư mục sẽ được tạo nếu chưa có." htmlFor="output">
          <Input id="output" value={s.output} onChange={(e) => set("output", e.target.value)} className="font-mono text-sm" />
        </Field>
        <Field label="Định dạng mặc định">
          <FormatPicker value={s.formats} onChange={(v) => set("formats", v.length ? v : s.formats)} />
        </Field>
        <Toggle
          label="Chia thư mục theo tình trạng"
          hint="Tách truyện vào “Đã hoàn thành” và “Chưa hoàn thành”."
          checked={s.split_by_status}
          onChange={(v) => set("split_by_status", v)}
        />
        <Toggle
          label="Giữ ảnh đã tải"
          hint="Build thêm định dạng sau này không phải tải lại ảnh. Tắt để tiết kiệm dung lượng."
          checked={s.keep_image_cache}
          onChange={(v) => set("keep_image_cache", v)}
        />
      </Group>

      <Group title="Tốc độ tải">
        <p className="text-sm text-muted-foreground">Tải nhanh quá dễ bị site chặn tạm thời. lnget tự chậm lại khi bị chặn.</p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Chờ giữa request (giây)" htmlFor="delay">
            <Input id="delay" type="number" min={0} max={30} step={0.1} value={s.delay} onChange={(e) => set("delay", Number(e.target.value))} />
          </Field>
          <Field label="Chương song song" htmlFor="cw">
            <Input id="cw" type="number" min={1} max={8} value={s.chapter_workers} onChange={(e) => set("chapter_workers", Number(e.target.value))} />
          </Field>
          <Field label="Ảnh song song" htmlFor="iw">
            <Input id="iw" type="number" min={1} max={16} value={s.image_workers} onChange={(e) => set("image_workers", Number(e.target.value))} />
          </Field>
        </div>
      </Group>

      <Group title="Domain">
        <p className="text-sm text-muted-foreground">Khi site chuyển sang domain mới, nhập domain mới ở đây. Link domain cũ vẫn dùng được.</p>
        {status.sources.map((src) => (
          <Field key={src.id} label={src.name} htmlFor={`dom-${src.id}`}>
            <Input
              id={`dom-${src.id}`}
              placeholder={src.domain}
              value={s.domains[src.id] ?? ""}
              onChange={(e) => {
                const domains = { ...s.domains }
                if (e.target.value.trim()) domains[src.id] = e.target.value.trim()
                else delete domains[src.id]
                set("domains", domains)
              }}
              className="font-mono text-sm"
            />
          </Field>
        ))}
      </Group>

      <div className="sticky bottom-0 mt-8 flex items-center justify-end gap-3 border-t bg-background/90 py-3 backdrop-blur">
        {dirty && <span className="text-sm text-muted-foreground">Có thay đổi chưa lưu</span>}
        <Button variant="ghost" disabled={!dirty} onClick={() => setS(structuredClone(status.settings))}>
          Hoàn tác
        </Button>
        <Button disabled={!dirty || saving} onClick={save}>
          Lưu cài đặt
        </Button>
      </div>
      <p className="mt-4 text-right font-mono text-xs text-muted-foreground">lnget {status.version}</p>
    </div>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-4 text-xs font-semibold tracking-[0.14em] text-sakura uppercase">{title}</h2>
      <div className="space-y-5 rounded-xl border bg-card p-5">{children}</div>
    </section>
  )
}

function Field({ label, hint, htmlFor, children }: { label: string; hint?: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <span>
        <span className="text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  )
}
