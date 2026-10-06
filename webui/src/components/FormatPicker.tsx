import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { FORMAT_HINT, FORMAT_LABEL, FORMATS, type Format } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Chọn nhiều định dạng — các nút bật/tắt, có chú thích dùng để làm gì. */
export function FormatPicker({ value, onChange, className }: { value: Format[]; onChange: (v: Format[]) => void; className?: string }) {
  const toggle = (f: Format) => onChange(value.includes(f) ? value.filter((x) => x !== f) : FORMATS.filter((x) => x === f || value.includes(x)))
  return (
    <div role="group" aria-label="Định dạng" className={cn("inline-flex rounded-lg border bg-card p-0.5", className)}>
      {FORMATS.map((f) => {
        const on = value.includes(f)
        return (
          <Tooltip key={f}>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => toggle(f)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-semibold tracking-wide transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  on ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {FORMAT_LABEL[f]}
              </button>
            </TooltipTrigger>
            <TooltipContent>{FORMAT_HINT[f]}</TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}
