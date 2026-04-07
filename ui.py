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
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich import box

import fetcher as _fetcher
import crawler as _crawler
import parser as _parser

console = Console()


def _fmt_size(n: int) -> str:
    """Định dạng bytes → chuỗi dễ đọc."""
    if n < 1024:        return f"{n} B"
    if n < 1024 ** 2:   return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:   return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"

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
    questionary.Choice("EPUB",   value="epub"),
    questionary.Choice("DOCX",   value="docx"),
    questionary.Choice("PDF",    value="pdf"),
    questionary.Choice("Images", value="images"),
]


# ─── Banner ──────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    cfg = _crawler._load_config()
    domain     = cfg.get("domain",     "docln.sbs")
    delay      = cfg.get("delay",      1.5)
    output     = cfg.get("output",     "./output")
    fmts       = cfg.get("format",     ["epub"])
    split_mode = cfg.get("split_mode", False)

    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Domain",  f"[cyan]{domain}[/]")
    t.add_row("Output",  f"[green]{output}[/]")
    t.add_row("Format",  f"[yellow]{', '.join(f.upper() for f in fmts)}[/]")
    t.add_row("Delay",   f"{delay}s")
    t.add_row("Folder",  "[magenta]Split HT/CHT[/]" if split_mode else "Single")
    if _fetcher.is_logged_in():
        t.add_row("Auth", "[green]Đã đăng nhập[/]")
    else:
        t.add_row("Auth", "[red]Chưa đăng nhập[/]")

    console.print(Panel(t, title="[bold cyan]Crawl Hako[/]", border_style="cyan", width=52))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ask_output(default: str) -> str:
    val = questionary.text(
        f"Thư mục lưu file:",
        default=default,
        style=_MENU_STYLE,
    ).ask()
    return (val or default).strip()


def _ask_split_mode(default: bool = False) -> bool:
    ans = questionary.select(
        "Cấu trúc folder output:",
        choices=[
            questionary.Choice("📁  1 folder chung (không chia)", value=False),
            questionary.Choice("📂  Chia 2 folder: Đã hoàn thành / Chưa hoàn thành", value=True),
        ],
        default=True if default else False,
        style=_MENU_STYLE,
    ).ask()
    return bool(ans)


def _ask_formats(defaults: list[str]) -> list[str]:
    default_choices = [questionary.Choice(f.upper() if f != "images" else "Images", value=f, checked=(f in defaults))
                       for f in ["epub", "docx", "pdf", "images"]]
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


def _confirm_or_back(start_label: str = "▶  Bắt đầu") -> bool:
    """Hiện menu xác nhận 2 nút. Trả về True nếu người dùng chọn Bắt đầu."""
    choice = questionary.select(
        "Tiếp theo:",
        choices=[
            questionary.Choice(start_label,                  value="ok"),
            questionary.Choice("←  Quay lại (về menu chính)", value="back"),
        ],
        style=_MENU_STYLE,
    ).ask()
    return choice == "ok"


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
        input("\nNhấn Enter để tiếp tục...")
        return

    # Hiển thị thông tin truyện
    console.print()
    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Tên",       f"[bold]{novel_info.get('title', '?')}[/]")
    t.add_row("Tác giả",   novel_info.get("author", "?"))
    t.add_row("Dịch giả",  novel_info.get("translator", "?") or "?")
    t.add_row("Loại dịch", "[red]Máy dịch[/]" if novel_info.get("translation_type") == "machine" else "[green]Người dịch[/]")
    t.add_row("Tình trạng", novel_info.get("status", "?") or "?")
    t.add_row("Số tập",    str(len(volumes)))
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
    output     = _ask_output(cfg.get("output", "./output"))
    split_mode = _ask_split_mode(cfg.get("split_mode", False))

    # ── Ước tính dung lượng (tuỳ chọn) ──────────────────────────────────────
    est = None
    _est_ans = input("Ước tính dung lượng output trước khi crawl? [Y/n]: ").strip().lower()
    if _est_ans != "n":
        sel_idx       = _crawler.parse_volumes_arg(volumes_spec or "all", len(volumes))
        selected_vols = [v for i, v in enumerate(volumes, 1)
                         if sel_idx is None or i in sel_idx]
        total_chaps   = sum(len(v.get("chapters", [])) for v in selected_vols)
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("chương"),
            console=console, transient=True,
        ) as prog:
            task = prog.add_task("Phân tích chapters...", total=total_chaps)
            est  = _crawler.estimate_novel_size(
                volumes     = selected_vols,
                fmts        = fmts,
                delay       = delay,
                progress_cb = lambda done, _: prog.update(task, completed=done),
            )

        # Hiển thị kết quả ước tính
        et = Table(box=None, show_header=False, padding=(0, 1))
        et.add_column(style="dim")
        et.add_column(justify="right")
        et.add_row("Tổng chương", str(est["chapters"]))
        et.add_row("Tổng ảnh",   str(est["images"]))
        et.add_row("", "")
        for fmt, sz in est["per_fmt"].items():
            et.add_row(fmt.upper(), f"~{_fmt_size(sz)}")
        et.add_row("[bold]Tổng cộng[/]", f"[bold green]~{_fmt_size(est['total'])}[/]")
        console.print(Panel(et, title="Ước tính dung lượng (±30%)", border_style="green"))

    # ── Xác nhận ─────────────────────────────────────────────────────────────
    console.print()
    vol_label = "Tất cả" if volumes_spec is None else f"Tập {volumes_spec}"
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Truyện", novel_info.get("title", "?"))
    t.add_row("Tập",    vol_label)
    if est:
        t.add_row("Ảnh",    f"~{est['images']} ảnh")
        t.add_row("Est.",   f"~{_fmt_size(est['total'])}")
    t.add_row("Format", ", ".join(f.upper() for f in fmts))
    t.add_row("Output", output)
    console.print(Panel(t, title="Xác nhận", border_style="yellow"))

    if not _confirm_or_back("▶  Bắt đầu crawl"):
        return

    from pathlib import Path
    Path(output).mkdir(parents=True, exist_ok=True)
    _crawler._save_config(output, delay, fmts, cfg.get("domain", "docln.sbs"),
                          cfg.get("workers"), split_mode)

    console.print()
    try:
        _crawler.crawl_novel(url, fmts, output, delay, volumes_spec)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏸  Đã tạm dừng![/]")
        console.print("[dim]Tiến trình đã lưu tự động. Chạy lại cùng URL để tiếp tục — các chương đã tải sẽ không tải lại.[/]")
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/]")

    input("\nNhấn Enter để tiếp tục...")


def _action_crawl_batch_urls() -> None:
    """Crawl nhiều truyện từ danh sách URL nhập tay, file local, hoặc URL online."""
    cfg   = _crawler._load_config()
    delay = cfg.get("delay", 1.5)

    input_mode = questionary.select(
        "Cách nhập danh sách URL:",
        choices=[
            questionary.Choice("✏️   Nhập URL trực tiếp (Enter sau mỗi URL)", value="manual"),
            questionary.Choice("📄  Đọc từ file local (.txt)",                 value="file"),
            questionary.Choice("🌐  Tải từ URL link (file .txt online)",       value="url_file"),
            questionary.Separator(),
            questionary.Choice("←  Quay lại",                                  value="back"),
        ],
        style=_MENU_STYLE,
    ).ask()
    if not input_mode or input_mode == "back":
        return

    urls: list[str] = []

    if input_mode == "manual":
        console.print("[dim]Nhập từng URL. Dòng trống để kết thúc.[/]")
        while True:
            try:
                line = input(f"  URL {len(urls) + 1}: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            if not line.startswith("http"):
                console.print("[yellow]  ⚠ URL phải bắt đầu bằng http, bỏ qua.[/]")
                continue
            urls.append(line)

    elif input_mode == "file":
        from pathlib import Path
        file_path_str = questionary.text(
            "Đường dẫn file URL:",
            style=_MENU_STYLE,
            validate=lambda v: True if v.strip() else "Cần nhập đường dẫn",
        ).ask()
        if not file_path_str:
            return
        fp = Path(file_path_str.strip())
        if not fp.is_file():
            console.print(f"[red]Không tìm thấy file: {fp}[/]")
            input("\nNhấn Enter để tiếp tục...")
            return
        lines = fp.read_text(encoding="utf-8").splitlines()
        urls = [
            ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#") and ln.strip().startswith("http")
        ]
        skipped = sum(
            1 for ln in lines
            if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("http")
        )
        if skipped:
            console.print(f"[yellow]⚠ Bỏ qua {skipped} dòng không hợp lệ.[/]")

    else:  # url_file
        remote_url = questionary.text(
            "Link URL tới file .txt:",
            style=_MENU_STYLE,
            validate=lambda v: True if v.strip().startswith("http") else "Cần URL hợp lệ (bắt đầu bằng http)",
        ).ask()
        if not remote_url:
            return
        console.print("[dim]Đang tải file danh sách...[/]")
        try:
            import urllib.request
            with urllib.request.urlopen(remote_url.strip(), timeout=15) as resp:
                content = resp.read().decode("utf-8")
        except Exception as e:
            console.print(f"[red]Không tải được file: {e}[/]")
            input("\nNhấn Enter để tiếp tục...")
            return
        lines = content.splitlines()
        urls = [
            ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#") and ln.strip().startswith("http")
        ]
        skipped = sum(
            1 for ln in lines
            if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("http")
        )
        if skipped:
            console.print(f"[yellow]⚠ Bỏ qua {skipped} dòng không hợp lệ.[/]")

    if not urls:
        console.print("[yellow]Không có URL nào được nhập.[/]")
        input("\nNhấn Enter để tiếp tục...")
        return

    console.print(f"\n[green]✓ {len(urls)} URL hợp lệ[/]")

    fmts = _ask_formats(cfg.get("format", ["epub"]))
    if not fmts:
        console.print("[red]Chưa chọn format nào.[/]")
        return
    output     = _ask_output(cfg.get("output", "./output"))
    split_mode = _ask_split_mode(cfg.get("split_mode", False))

    # Confirmation panel
    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Số truyện", str(len(urls)))
    t.add_row("Format",    ", ".join(f.upper() for f in fmts))
    t.add_row("Output",    output)
    t.add_row("Delay",     f"{delay}s")
    for i, u in enumerate(urls[:5], 1):
        t.add_row(f"URL {i}", f"[dim]{u}[/]")
    if len(urls) > 5:
        t.add_row("...", f"[dim]và {len(urls) - 5} URL khác[/]")
    console.print(Panel(t, title="Xác nhận batch crawl", border_style="yellow"))

    if not _confirm_or_back("▶  Bắt đầu crawl batch"):
        return

    from pathlib import Path
    Path(output).mkdir(parents=True, exist_ok=True)
    _crawler._save_config(output, delay, fmts, cfg.get("domain", "docln.sbs"),
                          cfg.get("workers"), split_mode)
    _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))

    console.print()
    result = _crawler.crawl_batch_urls(urls, fmts, output, delay)

    # Summary panel
    console.print()
    s = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    s.add_column(style="dim")
    s.add_column()
    s.add_row("Tổng",                 str(len(urls)))
    s.add_row("[green]Thành công[/]", f"[green]{len(result['ok'])}[/]")
    s.add_row("[red]Thất bại[/]",     f"[red]{len(result['fail'])}[/]")
    if result["fail"]:
        s.add_row("", "")
        for u, err in result["fail"]:
            s.add_row("[red]✗[/]", f"[dim]{u}[/]\n  {err}")
    console.print(Panel(s, title="Kết quả batch", border_style="cyan"))

    input("\nNhấn Enter để tiếp tục...")


def _action_crawl_listing() -> None:
    cfg = _crawler._load_config()

    # ── Chọn nguồn danh sách ────────────────────────────────────────────────
    src_choice = questionary.select(
        "Nguồn danh sách:",
        choices=[
            questionary.Choice("📋  Danh sách mặc định (/danh-sach)",          value="default"),
            questionary.Choice("🔗  URL tự nhập (lọc theo thể loại, tag...)", value="custom"),
            questionary.Separator(),
            questionary.Choice("←  Quay lại",                                  value="back"),
        ],
        style=_MENU_STYLE,
    ).ask()
    if not src_choice or src_choice == "back":
        return

    list_url = ""
    if src_choice == "custom":
        list_url = questionary.text(
            "Nhập URL danh sách:",
            instruction="(vd: https://docln.sbs/the-loai/mystery?truyendich=1&hoanthanh=1)",
            style=_MENU_STYLE,
            validate=lambda v: True if v.strip().startswith("http") else "Nhập URL hợp lệ (bắt đầu bằng http)",
        ).ask()
        if not list_url:
            return
        list_url = list_url.strip()

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

    fmts       = _ask_formats(cfg.get("format", ["epub"]))
    output     = _ask_output(cfg.get("output", "./output"))
    split_mode = _ask_split_mode(cfg.get("split_mode", False))
    delay      = cfg.get("delay", 1.5)

    # ── Ước tính dung lượng (chỉ khi biết số trang kết thúc) ────────────────
    est_listing = None
    if page_end != "auto":
        _est_ans = input("Ước tính dung lượng output (dựa trên mẫu trang đầu)? [Y/n]: ").strip().lower()
        if _est_ans != "n":
            try:
                console.print("[dim]Đang lấy mẫu trang đầu...[/]")
                _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))
                _base_url = list_url or f"{_fetcher.BASE_URL}/danh-sach"
                sample_soup  = _fetcher.fetch(
                    _crawler._listing_page_url(_base_url, int(page_start)), delay=delay
                )
                sample_urls  = _parser.parse_listing_page(sample_soup)
                novels_per_pg = max(len(sample_urls), 1)
                total_pages   = int(page_end) - int(page_start) + 1
                total_novels  = novels_per_pg * total_pages

                # Hằng số trung bình mỗi truyện (nhiều tập, ~30 chương, ~15 ảnh)
                _AVG_CHAPS = 30
                _AVG_IMGS  = 15
                img_bytes  = total_novels * _AVG_IMGS  * _crawler._AVG_IMG_BYTES
                txt_bytes  = total_novels * _AVG_CHAPS * _crawler._AVG_TEXT_BYTES
                per_fmt = {
                    fmt: img_bytes + txt_bytes + _crawler._FMT_OVERHEAD.get(fmt, 60 * 1024) * total_novels
                    for fmt in fmts
                }
                est_listing = {"novels": total_novels, "per_pg": novels_per_pg,
                               "pages": total_pages,   "per_fmt": per_fmt,
                               "total": sum(per_fmt.values())}

                et = Table(box=None, show_header=False, padding=(0, 1))
                et.add_column(style="dim")
                et.add_column(justify="right")
                et.add_row("Truyện ước tính",
                           f"~{total_novels}  ({novels_per_pg}/trang × {total_pages} trang)")
                et.add_row("", "")
                for fmt, sz in per_fmt.items():
                    et.add_row(fmt.upper(), f"~{_fmt_size(sz)}")
                et.add_row("[bold]Tổng cộng[/]", f"[bold green]~{_fmt_size(est_listing['total'])}[/]")
                console.print(Panel(et, title="Ước tính dung lượng (±50%)", border_style="green"))
            except Exception as e:
                console.print(f"[yellow]Không thể ước tính: {e}[/]")

    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Nguồn",  list_url if list_url else "/danh-sach (mặc định)")
    t.add_row("Trang",  f"{page_start} → {page_end}")
    if est_listing:
        t.add_row("Est.", f"~{_fmt_size(est_listing['total'])}")
    t.add_row("Format", ", ".join(f.upper() for f in fmts))
    t.add_row("Output", output)
    console.print(Panel(t, title="Xác nhận", border_style="yellow"))

    if not _confirm_or_back("▶  Bắt đầu crawl danh sách"):
        return

    from pathlib import Path
    Path(output).mkdir(parents=True, exist_ok=True)
    _crawler._save_config(output, delay, fmts, cfg.get("domain", "docln.sbs"),
                          cfg.get("workers"), split_mode)
    _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))

    page_end_val = "auto" if page_end == "auto" else int(page_end)
    console.print()
    try:
        _crawler.crawl_listing(int(page_start), page_end_val, fmts, output, delay, list_url=list_url)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏸  Đã tạm dừng![/]")
        console.print("[dim]Tiến trình đã lưu tự động. Chạy lại để tiếp tục — các truyện/chương đã tải sẽ không tải lại.[/]")
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/]")

    input("\nNhấn Enter để tiếp tục...")


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

    # ── Workers (concurrency) ────────────────────────────────────────────────
    cur_workers = cfg.get("workers", {"chapters": 3, "images": 5})
    chap_w = questionary.text(
        "Số chương fetch song song (1–10):",
        default=str(cur_workers.get("chapters", 3)),
        style=_MENU_STYLE,
        validate=lambda v: True if v.isdigit() and 1 <= int(v) <= 10 else "Nhập số từ 1 đến 10",
    ).ask() or "3"
    img_w = questionary.text(
        "Số ảnh tải song song / chương (1–20):",
        default=str(cur_workers.get("images", 5)),
        style=_MENU_STYLE,
        validate=lambda v: True if v.isdigit() and 1 <= int(v) <= 20 else "Nhập số từ 1 đến 20",
    ).ask() or "5"
    workers = {"chapters": int(chap_w), "images": int(img_w)}

    split_mode = _ask_split_mode(cfg.get("split_mode", False))

    _crawler._save_config(output, delay, fmts, domain, workers, split_mode)
    _fetcher.set_base_url(domain)
    console.print("[green]✓ Đã lưu cài đặt.[/]")
    input("\nNhấn Enter để tiếp tục...")


def _action_login() -> None:
    """Đăng nhập / đăng xuất tài khoản docln.sbs."""
    if _fetcher.is_logged_in():
        action = questionary.select(
            "Bạn đang đăng nhập. Chọn:",
            choices=[
                questionary.Choice("🔓  Đăng xuất",  value="logout"),
                questionary.Choice("←  Quay lại",    value="back"),
            ],
            style=_MENU_STYLE,
        ).ask()
        if action == "logout":
            _fetcher.logout()
            console.print("[green]✓ Đã đăng xuất.[/]")
            input("\nNhấn Enter để tiếp tục...")
        return

    console.print(Panel(
        "[dim]Đăng nhập để truy cập nội dung 18+ trên docln.sbs.\n"
        "Mật khẩu [bold]sẽ không[/bold] được lưu lại — chỉ lưu session cookie.[/]",
        title="🔑  Đăng nhập",
        border_style="cyan",
    ))

    username = questionary.text(
        "Email:",
        style=_MENU_STYLE,
        validate=lambda v: True if v.strip() else "Cần nhập email",
    ).ask()
    if not username:
        return

    password = questionary.password(
        "Mật khẩu:",
        style=_MENU_STYLE,
        validate=lambda v: True if v else "Cần nhập mật khẩu",
    ).ask()
    if not password:
        return

    console.print("[dim]Đang đăng nhập...[/]")
    success = _fetcher.login(username.strip(), password)
    if success:
        console.print("[green]✓ Đăng nhập thành công! Cookie đã được lưu.[/]")
    else:
        console.print("[red]✗ Đăng nhập thất bại. Kiểm tra lại email/mật khẩu.[/]")
    input("\nNhấn Enter để tiếp tục...")


# ─── CLI paste ───────────────────────────────────────────────────────────────

def _action_run_cli() -> None:
    """Dán một câu lệnh CLI vào để chạy trực tiếp."""
    import re, shlex

    console.print(Panel(
        "[dim]Dán câu lệnh CLI vào đây. Ví dụ:\n"
        "  [cyan]--url https://docln.sbs/truyen/123-ten-truyen --format epub docx[/]\n"
        "  [cyan]--urls https://... https://... --output D:\\\\Truyen[/]\n"
        "  [cyan]--url-file D:\\\\urls.txt --format epub[/]\n\n"
        "Phần [cyan]py crawler.py[/] ở đầu có thể bỏ hoặc giữ đều được.[/]",
        title="⌨️  Chạy từ lệnh CLI",
        border_style="cyan",
    ))

    cmd_str = questionary.text(
        "Lệnh:",
        style=_MENU_STYLE,
        validate=lambda v: True if v.strip() else "Cần nhập lệnh",
    ).ask()
    if not cmd_str:
        return
    cmd_str = cmd_str.strip()

    # Bỏ "py crawler.py", "python crawler.py", "python3 crawler.py" ở đầu
    cmd_str = re.sub(r'^(python3?|py)\s+crawler\.py\s*', '', cmd_str, flags=re.IGNORECASE).strip()
    if not cmd_str:
        console.print("[yellow]Lệnh trống sau khi xử lý.[/]")
        input("\nNhấn Enter để tiếp tục...")
        return

    try:
        extra_args = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[red]Lỗi parse lệnh: {e}[/]")
        input("\nNhấn Enter để tiếp tục...")
        return

    # Preview
    console.print(f"\n[dim]Sẽ chạy:[/] [cyan]py crawler.py {' '.join(extra_args)}[/]\n")

    confirm = questionary.select(
        "Xác nhận:",
        choices=[
            questionary.Choice("▶  Chạy ngay",  value="run"),
            questionary.Choice("←  Quay lại",   value="back"),
        ],
        style=_MENU_STYLE,
    ).ask()
    if not confirm or confirm == "back":
        return

    old_argv = sys.argv[:]
    sys.argv = ["crawler.py"] + extra_args
    try:
        _crawler.main()
    except SystemExit as e:
        if e.code and e.code != 0:
            console.print(f"[red]Lệnh kết thúc với lỗi (code {e.code})[/]")
    finally:
        sys.argv = old_argv

    input("\nNhấn Enter để tiếp tục...")


# ─── Rebuild ─────────────────────────────────────────────────────────────────

def _scan_novel_dirs(root: str) -> list:
    """Tìm tất cả thư mục có info.json trong root (depth tối đa 2).
    Xử lý cả cấu trúc split (Truyện đã hoàn thành/...) và single.
    """
    from pathlib import Path
    root_path = Path(root)
    if not root_path.is_dir():
        return []
    found = []
    for p in sorted(root_path.iterdir()):
        if not p.is_dir():
            continue
        if (p / "info.json").exists():
            found.append(p)
        else:
            for sub in sorted(p.iterdir()):
                if sub.is_dir() and (sub / "info.json").exists():
                    found.append(sub)
    return found


def _action_rebuild() -> None:
    from pathlib import Path
    cfg   = _crawler._load_config()
    delay = cfg.get("delay", 1.5)

    # 1. Chọn folder gốc
    root = _ask_output(cfg.get("output", "./output"))

    # 2. Scan tìm truyện
    console.print("[dim]Đang scan folder...[/]")
    novel_dirs = _scan_novel_dirs(root)
    if not novel_dirs:
        console.print("[yellow]Không tìm thấy truyện nào (cần có info.json).[/]")
        input("\nNhấn Enter để tiếp tục...")
        return

    # Tạo choices với tên truyện + các format hiện có
    def _existing_fmts(d: Path) -> str:
        fmts = []
        for fmt in ["epub", "docx", "pdf", "images"]:
            fmt_dir = d / fmt.upper()
            if fmt_dir.is_dir() and any(fmt_dir.iterdir()):
                fmts.append(fmt.upper())
        return ", ".join(fmts) if fmts else "chưa có"

    choices = [
        questionary.Choice(
            f"{d.name}  [dim]({_existing_fmts(d)})[/dim]",
            value=d,
        )
        for d in novel_dirs
    ]

    selected_dirs = questionary.checkbox(
        "Chọn truyện muốn build thêm format:",
        choices=choices,
        style=_MENU_STYLE,
    ).ask()
    if not selected_dirs:
        return

    # 3. Chọn format muốn build
    fmts = _ask_formats(cfg.get("format", ["epub"]))
    if not fmts:
        console.print("[red]Chưa chọn format nào.[/]")
        return

    # 4. Xác nhận
    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Số truyện", str(len(selected_dirs)))
    t.add_row("Format build", ", ".join(f.upper() for f in fmts))
    t.add_row("Delay",        f"{delay}s")
    console.print(Panel(t, title="Xác nhận rebuild", border_style="yellow"))

    if not _confirm_or_back("▶  Bắt đầu rebuild"):
        return

    # 5. Rebuild
    _fetcher.set_base_url(cfg.get("domain", "docln.sbs"))
    console.print()
    for d in selected_dirs:
        console.print(f"[cyan]▶ {d.name}[/]")
        try:
            _crawler.rebuild_novel(d, fmts, delay)
        except Exception as e:
            console.print(f"[red]  ✗ Lỗi: {e}[/]")

    input("\nNhấn Enter để tiếp tục...")


# ─── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    while True:
        console.clear()
        _print_banner()
        console.print()

        choice = questionary.select(
            "Chọn chế độ:",
            choices=[
                questionary.Choice("🔗  Crawl 1 truyện (URL)",              value="url"),
                questionary.Choice("📋  Crawl nhiều URL (danh sách)",        value="batch_urls"),
                questionary.Choice("📄  Crawl danh sách (nhiều trang)",      value="listing"),
                questionary.Choice("🔄  Build lại format từ folder có sẵn",  value="rebuild"),
                questionary.Choice("⌨️   Chạy từ lệnh CLI",                   value="run_cli"),
                questionary.Choice("⚙️   Cài đặt",                            value="settings"),
                questionary.Choice("🔑  Đăng nhập / Đăng xuất",              value="login"),
                questionary.Separator(),
                questionary.Choice("❌  Thoát",                               value="exit"),
            ],
            style=_MENU_STYLE,
        ).ask()

        if choice is None or choice == "exit":
            console.print("[dim]Tạm biệt![/]")
            break
        elif choice == "url":
            _action_crawl_url()
        elif choice == "batch_urls":
            _action_crawl_batch_urls()
        elif choice == "listing":
            _action_crawl_listing()
        elif choice == "rebuild":
            _action_rebuild()
        elif choice == "run_cli":
            _action_run_cli()
        elif choice == "settings":
            _action_settings()
        elif choice == "login":
            _action_login()


if __name__ == "__main__":
    main()
