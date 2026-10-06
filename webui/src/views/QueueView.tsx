import { FileText, FolderOpen, Pause, Play, RotateCcw, Square, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { api, errorText, type Job, type JobStatus } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useApp } from "@/store"

const STATUS: Record<JobStatus, { label: string; cls: string }> = {
  queued: { label: "Đang chờ", cls: "bg-secondary text-muted-foreground" },
  running: { label: "Đang tải", cls: "bg-sakura/12 text-sakura" },
  paused: { label: "Tạm dừng", cls: "bg-amber/12 text-amber" },
  done: { label: "Xong", cls: "bg-leaf/12 text-leaf" },
  failed: { label: "Lỗi", cls: "bg-destructive/12 text-destructive" },
  cancelled: { label: "Đã huỷ", cls: "bg-secondary text-muted-foreground" },
}

export function QueueView() {
  const { jobs, setTab } = useApp()
  const finished = jobs.filter((j) => ["done", "failed", "cancelled"].includes(j.status)).length

  if (!jobs.length) {
    return (
      <div className="mx-auto max-w-md pt-[14vh] text-center">
        <h2 className="font-serif text-2xl font-semibold">Chưa có lượt tải nào</h2>
        <p className="mt-2 text-muted-foreground">Dán link truyện ở mục Tải truyện, chọn tập rồi bấm Tải.</p>
        <Button className="mt-6" onClick={() => setTab("download")}>
          Tải truyện
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-end justify-between">
        <h1 className="font-serif text-2xl font-semibold">Hàng đợi</h1>
        {finished > 0 && (
          <Button variant="ghost" size="sm" onClick={() => api.clearJobs().catch((e) => toast.error(errorText(e)))}>
            <Trash2 /> Xoá mục đã xong
          </Button>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">Tải lần lượt từng truyện. Đóng trang này không làm dừng tải. Nếu tắt lnget giữa chừng, lần sau tải lại truyện đó sẽ bỏ qua các chương đã có.</p>
      <ul className="mt-6 space-y-3">
        {jobs.map((j) => (
          <JobCard key={j.id} job={j} />
        ))}
      </ul>
    </div>
  )
}

function JobCard({ job }: { job: Job }) {
  const st = STATUS[job.status]
  const pct = job.total ? Math.round(((job.done + job.failed) / job.total) * 100) : 0
  const act = (a: "pause" | "resume" | "cancel" | "retry") => api.jobAction(job.id, a).catch((e) => toast.error(errorText(e)))
  const live = job.status === "running" || job.status === "paused"

  return (
    <li className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", st.cls)}>{st.label}</span>
            <span className="font-mono text-xs text-muted-foreground uppercase">
              {job.rebuild ? "build lại · " : ""}
              {job.formats.join(" · ")}
            </span>
          </div>
          <h3 className="mt-1.5 truncate font-serif text-lg font-semibold" title={job.title}>
            {job.title}
          </h3>
          {job.volume && live && <p className="text-sm text-muted-foreground">{job.volume}</p>}
        </div>
        <div className="flex gap-1">
          {job.status === "running" && (
            <Button variant="ghost" size="icon-sm" aria-label="Tạm dừng" onClick={() => act("pause")}>
              <Pause />
            </Button>
          )}
          {job.status === "paused" && (
            <Button variant="ghost" size="icon-sm" aria-label="Tiếp tục" onClick={() => act("resume")}>
              <Play />
            </Button>
          )}
          {["queued", "running", "paused"].includes(job.status) && (
            <Button variant="ghost" size="icon-sm" aria-label="Huỷ" onClick={() => act("cancel")}>
              <Square />
            </Button>
          )}
          {["failed", "cancelled", "done"].includes(job.status) && (job.failed > 0 || job.status !== "done") && (
            <Button variant="outline" size="sm" onClick={() => act("retry")}>
              <RotateCcw /> Thử lại
            </Button>
          )}
          {job.path && (
            <Button variant="ghost" size="icon-sm" aria-label="Mở thư mục" onClick={() => api.open(job.path).catch((e) => toast.error(errorText(e)))}>
              <FolderOpen />
            </Button>
          )}
          {!live && job.status !== "queued" && (
            <Button variant="ghost" size="icon-sm" aria-label="Xoá khỏi danh sách" onClick={() => api.deleteJob(job.id)}>
              <Trash2 />
            </Button>
          )}
        </div>
      </div>

      {job.total > 0 && (
        <div className="mt-4">
          <Progress value={pct} className="h-1.5 *:data-[slot=progress-indicator]:bg-sakura" />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground">
            <span>
              {job.done}/{job.total} chương
            </span>
            {job.failed > 0 && <span className="text-destructive">{job.failed} chương lỗi</span>}
            {job.images_ok > 0 && <span>{job.images_ok} ảnh mới</span>}
            {job.images_failed > 0 && <span className="text-amber">{job.images_failed} ảnh lỗi</span>}
          </div>
        </div>
      )}

      {(job.error || job.hint) && (
        <Alert variant={job.error ? "destructive" : "default"} className={cn("mt-4", !job.error && "border-amber/40 bg-amber/5")}>
          <AlertDescription className={cn(!job.error && "text-foreground")}>
            {job.error && <p>{job.error}</p>}
            {job.hint && <p className={cn(job.error && "mt-1 text-foreground")}>{job.hint}</p>}
          </AlertDescription>
        </Alert>
      )}

      {job.outputs.length > 0 && (
        <ul className="mt-4 space-y-1 border-t pt-3">
          {job.outputs.map((p) => (
            <li key={p} className="flex items-center gap-2 text-sm">
              <FileText className="size-3.5 shrink-0 text-leaf" />
              <span className="truncate" title={p}>
                {p.split(/[\\/]/).pop()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
