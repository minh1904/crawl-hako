"""Hiển thị event của engine trong terminal (dùng chung cho CLI và menu)."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from lnget.util import ensure_utf8_stdio

ensure_utf8_stdio()
console = Console(highlight=False)


class ProgressView:
    """Listener cho Engine: 1 thanh tiến độ cho mỗi job + dòng thông báo khi xuất file / lỗi."""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
            MofNCompleteColumn(), TextColumn("[dim]{task.fields[info]}"), TimeElapsedColumn(),
            console=console, transient=False,
        )
        self.tasks: dict[int, int] = {}

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, *exc):
        self.progress.stop()

    def __call__(self, ev: dict) -> None:
        job, snap, t = ev.get("job"), ev.get("snapshot") or {}, ev["type"]
        p = self.progress
        if job is not None and job not in self.tasks:
            self.tasks[job] = p.add_task(_short(snap.get("title", "")), total=None, info="")
        task = self.tasks.get(job)
        if task is None:
            return
        info = snap.get("volume", "")
        if snap.get("images_failed"):
            info += f" · ảnh lỗi {snap['images_failed']}"
        p.update(task, description=_short(snap.get("title", "")), total=snap.get("total") or None,
                 completed=snap.get("done", 0) + snap.get("failed", 0), info=info)
        if t == "log":
            p.console.print(f"  [dim]{ev['message']}[/]")
        elif t == "chapter_failed":
            p.console.print(f"  [red]✗[/] {ev['chapter']}: [dim]{ev['error']}[/]")
        elif t == "export_done":
            extra = f" [yellow](thiếu {ev['missing_chapters']} chương)[/]" if ev.get("missing_chapters") else ""
            p.console.print(f"  [green]✓[/] [{ev['format'].upper()}] {Path(ev['path']).name}{extra}")
        elif t == "export_failed":
            p.console.print(f"  [red]✗ Lỗi xuất {ev['format'].upper()} {ev['volume']}:[/] {ev['error']}")
        elif t == "job_finished":
            p.update(task, info={"done": "[green]xong", "failed": "[red]lỗi",
                                 "cancelled": "[yellow]đã huỷ"}.get(snap["status"], snap["status"]))


def print_summary(snap: dict) -> None:
    status = snap["status"]
    color = {"done": "green", "failed": "red", "cancelled": "yellow"}.get(status, "white")
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Truyện", snap["title"])
    t.add_row("Chương", f"{snap['done']}/{snap['total']}" + (f" · [red]lỗi {snap['failed']}[/]" if snap["failed"] else ""))
    t.add_row("Ảnh", f"{snap['images_ok']} mới" + (f" · [red]lỗi {snap['images_failed']}[/]" if snap["images_failed"] else ""))
    if snap["path"]:
        t.add_row("Thư mục", snap["path"])
    if snap["error"]:
        t.add_row("Lỗi", f"[red]{snap['error']}[/]")
    if snap["hint"]:
        t.add_row("Gợi ý", f"[yellow]{snap['hint']}[/]")
    title = {"done": "Hoàn tất", "failed": "Thất bại", "cancelled": "Đã dừng"}.get(status, status)
    console.print(Panel(t, title=f"[bold {color}]{title}[/]", border_style=color, expand=False))


def novel_table(info: dict) -> Table:
    t = Table(title=None, show_lines=False, header_style="bold")
    t.add_column("#", justify="right", style="dim")
    t.add_column("Tập")
    t.add_column("Chương", justify="right")
    t.add_column("Đã có", justify="right")
    t.add_column("File")
    for i, v in enumerate(info["volumes"], 1):
        locked = sum(1 for c in v["chapters"] if c["locked"])
        n = f"{len(v['chapters'])}" + (f" [yellow](🔒{locked})[/]" if locked else "")
        cached = v["cached"]
        t.add_row(str(i), v["title"], n,
                  f"[green]{cached}[/]" if cached == len(v["chapters"]) else str(cached or "-"),
                  ", ".join(f.upper() for f in v["formats"]) or "-")
    return t


def novel_header(info: dict) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Site", info["source_name"])
    if info.get("author"):
        t.add_row("Tác giả", info["author"])
    if info.get("translator"):
        t.add_row("Nhóm dịch", info["translator"])
    t.add_row("Tình trạng", info.get("status") or "?")
    if info.get("genres"):
        t.add_row("Thể loại", ", ".join(info["genres"][:8]))
    t.add_row("Số tập", f"{len(info['volumes'])} tập · {sum(len(v['chapters']) for v in info['volumes'])} chương")
    if info.get("path"):
        t.add_row("Đã tải tại", info["path"])
    return Panel(t, title=f"[bold cyan]{info['title']}[/]", border_style="cyan", expand=False)


def _short(s: str, n: int = 40) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
