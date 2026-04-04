"""
ui.py — Menu UI tương tác cho crawl-hako
Chạy: python ui.py
"""
import io
import sys

# Fix Unicode output trên Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import fetcher as _fetcher
import crawler as _crawler

console = Console()

_MENU_STYLE = Style([
    ("qmark",        "fg:#00d7ff bold"),
    ("question",     "bold"),
    ("answer",       "fg:#00d7ff bold"),
    ("pointer",      "fg:#00d7ff bold"),
    ("highlighted",  "fg:#00d7ff bold"),
    ("selected",     "fg:#00ff87"),
    ("separator",    "fg:#444444"),
    ("instruction",  "fg:#888888"),
])

FORMAT_CHOICES = [
    questionary.Choice("EPUB",  value="epub"),
    questionary.Choice("DOCX",  value="docx"),
    questionary.Choice("PDF",   value="pdf"),
]


# ─── Banner ──────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    cfg = _crawler._load_config()
    domain  = cfg.get("domain",  "docln.sbs")
    delay   = cfg.get("delay",   1.5)
    output  = cfg.get("output",  "./output")
    fmts    = cfg.get("format",  ["epub"])

    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Domain",  f"[cyan]{domain}[/]")
    t.add_row("Output",  f"[green]{output}[/]")
    t.add_row("Format",  f"[yellow]{', '.join(f.upper() for f in fmts)}[/]")
    t.add_row("Delay",   f"{delay}s")

    console.print(Panel(t, title="[bold cyan]Crawl Hako[/]", border_style="cyan", width=52))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ask_output(default: str) -> str:
    val = questionary.text(
        f"Thư mục lưu file:",
        default=default,
        style=_MENU_STYLE,
    ).ask()
    return (val or default).strip()


def _ask_formats(defaults: list[str]) -> list[str]:
    default_choices = [questionary.Choice(f.upper(), value=f, checked=(f in defaults))
                       for f in ["epub", "docx", "pdf"]]
    result = questionary.checkbox(
        "Format output (Space để chọn):",
        choices=default_choices,
        style=_MENU_STYLE,
    ).ask()
    return result or defaults


def _ask_delay(default: float) -> float:
    val = questionary.text(
        "Delay giữa request (giây):",
        default=str(default),
        style=_MENU_STYLE,
        validate=lambda v: True if _is_float(v) else "Nhập số thực, vd: 1.5",
    ).ask()
    return float(val) if val and _is_float(val) else default


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ─── Actions ─────────────────────────────────────────────────────────────────

def _action_crawl_url() -> None:
    cfg = _crawler._load_config()
    delay = cfg.get("delay", 1.5)

    url = questionary.text(
        "URL truyện:",
        style=_MENU_STYLE,
        validate=lambda v: True if v.startswith("http") else "Cần URL hợp lệ bắt đầu bằng http",
    ).ask()
    if not url:
        return

    # Fetch danh sách tập
    _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))
    console.print("[dim]Đang tải thông tin truyện...[/]")
    try:
        novel_info, volumes = _crawler.fetch_novel_preview(url, delay)
    except Exception as e:
        console.print(f"[red]Không lấy được thông tin: {e}[/]")
        questionary.press_any_key_to_continue(style=_MENU_STYLE).ask()
        return

    # Hiển thị thông tin truyện
    console.print()
    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Tên",    f"[bold]{novel_info.get('title', '?')}[/]")
    t.add_row("Tác giả", novel_info.get("author", "?"))
    t.add_row("Số tập", str(len(volumes)))
    console.print(Panel(t, border_style="cyan"))

    # Checkbox chọn tập
    vol_choices = [
        questionary.Choice(
            f"Tập {i}: {v.get('volume_title', '(không có tên)')}  "
            f"[dim]{len(v.get('chapters', []))} chương[/dim]",
            value=i,
            checked=True,
        )
        for i, v in enumerate(volumes, 1)
    ]
    selected = questionary.checkbox(
        "Chọn tập muốn tải (Space bỏ chọn, Enter xác nhận):",
        choices=vol_choices,
        style=_MENU_STYLE,
    ).ask()
    if selected is None:
        return
    if not selected:
        console.print("[yellow]Không có tập nào được chọn.[/]")
        return

    # Chuyển thành volumes_spec
    if len(selected) == len(volumes):
        volumes_spec = None  # tất cả
    else:
        volumes_spec = ",".join(str(i) for i in sorted(selected))

    fmts   = _ask_formats(cfg.get("format", ["epub"]))
    if not fmts:
        console.print("[red]Chưa chọn format nào.[/]")
        return
    output = _ask_output(cfg.get("output", "./output"))

    # Xác nhận
    console.print()
    vol_label = "Tất cả" if volumes_spec is None else f"Tập {volumes_spec}"
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Truyện", novel_info.get("title", "?"))
    t.add_row("Tập",    vol_label)
    t.add_row("Format", ", ".join(f.upper() for f in fmts))
    t.add_row("Output", output)
    console.print(Panel(t, title="Xác nhận", border_style="yellow"))

    ok = questionary.confirm("Bắt đầu crawl?", default=True, style=_MENU_STYLE).ask()
    if not ok:
        return

    from pathlib import Path
    Path(output).mkdir(parents=True, exist_ok=True)
    _crawler._save_config(output, delay, fmts, cfg.get("domain", "docln.sbs"))

    console.print()
    try:
        _crawler.crawl_novel(url, fmts, output, delay, volumes_spec)
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã dừng.[/]")
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/]")

    questionary.press_any_key_to_continue(style=_MENU_STYLE).ask()


def _action_crawl_listing() -> None:
    cfg = _crawler._load_config()

    page_start = questionary.text(
        "Trang bắt đầu:",
        default="1",
        style=_MENU_STYLE,
        validate=lambda v: True if v.isdigit() else "Nhập số nguyên",
    ).ask()
    if not page_start:
        return

    page_end = questionary.text(
        "Trang kết thúc (số hoặc 'auto'):",
        default="auto",
        style=_MENU_STYLE,
        validate=lambda v: True if v == "auto" or v.isdigit() else "Nhập số hoặc 'auto'",
    ).ask()
    if not page_end:
        return

    fmts   = _ask_formats(cfg.get("format", ["epub"]))
    output = _ask_output(cfg.get("output", "./output"))
    delay  = cfg.get("delay", 1.5)

    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Trang",  f"{page_start} → {page_end}")
    t.add_row("Format", ", ".join(f.upper() for f in fmts))
    t.add_row("Output", output)
    console.print(Panel(t, title="Xác nhận", border_style="yellow"))

    ok = questionary.confirm("Bắt đầu crawl?", default=True, style=_MENU_STYLE).ask()
    if not ok:
        return

    from pathlib import Path
    Path(output).mkdir(parents=True, exist_ok=True)
    _crawler._save_config(output, delay, fmts, cfg.get("domain", "docln.sbs"))
    _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))

    page_end_val = "auto" if page_end == "auto" else int(page_end)
    console.print()
    try:
        _crawler.crawl_listing(int(page_start), page_end_val, fmts, output, delay)
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã dừng.[/]")
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/]")

    questionary.press_any_key_to_continue(style=_MENU_STYLE).ask()


def _action_settings() -> None:
    cfg = _crawler._load_config()

    domain = questionary.text(
        "Domain site:",
        default=cfg.get("domain", "docln.sbs"),
        style=_MENU_STYLE,
    ).ask()
    if domain is None:
        return
    domain = domain.strip() or "docln.sbs"

    fmts   = _ask_formats(cfg.get("format", ["epub"]))
    delay  = _ask_delay(cfg.get("delay", 1.5))
    output = _ask_output(cfg.get("output", "./output"))

    _crawler._save_config(output, delay, fmts, domain)
    _fetcher.set_base_url(domain)
    console.print("[green]✓ Đã lưu cài đặt.[/]")
    questionary.press_any_key_to_continue(style=_MENU_STYLE).ask()


# ─── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    while True:
        console.clear()
        _print_banner()
        console.print()

        choice = questionary.select(
            "Chọn chế độ:",
            choices=[
                questionary.Choice("🔗  Crawl 1 truyện (URL)",         value="url"),
                questionary.Choice("📄  Crawl danh sách (nhiều trang)", value="listing"),
                questionary.Choice("⚙️   Cài đặt",                       value="settings"),
                questionary.Separator(),
                questionary.Choice("❌  Thoát",                          value="exit"),
            ],
            style=_MENU_STYLE,
        ).ask()

        if choice is None or choice == "exit":
            console.print("[dim]Tạm biệt![/]")
            break
        elif choice == "url":
            _action_crawl_url()
        elif choice == "listing":
            _action_crawl_listing()
        elif choice == "settings":
            _action_settings()


if __name__ == "__main__":
    main()
