import { useState } from "react"
import { cn } from "@/lib/utils"

/** Bìa sách tỉ lệ A6. Không có ảnh (hoặc ảnh lỗi) → gáy sách vẽ bằng CSS với tên tập. */
export function BookCover({ src, title, className }: { src?: string; title: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  const show = src && !failed
  return (
    <div className={cn("aspect-book relative overflow-hidden rounded-md bg-muted shadow-sm", className)}>
      {show ? (
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className="size-full object-cover" />
      ) : (
        <div className="flex size-full flex-col justify-between bg-[linear-gradient(160deg,var(--ink),color-mix(in_oklab,var(--ink)_70%,var(--sakura)))] p-3 text-[var(--paper)]">
          <span className="h-0.5 w-6 bg-sakura" />
          <span className="font-serif text-sm leading-snug line-clamp-4">{title}</span>
        </div>
      )}
      {/* gáy sách: viền sáng bên trái */}
      <span className="pointer-events-none absolute inset-y-0 left-0 w-1.5 bg-gradient-to-r from-black/25 to-transparent" />
    </div>
  )
}
