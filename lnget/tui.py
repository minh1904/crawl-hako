"""Menu tương tác trong terminal — chạy `lnget` không tham số.

Mỗi luồng ngắn nhất có thể: dán link → chọn tập → tải. Chọn "← Quay lại" (hoặc Ctrl+C) để lùi một bước.
"""
from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice, Separator, Style

from lnget import __version__
from lnget.config import load_settings, save_settings
from lnget.console import console, novel_header, novel_table
from lnget.http import LngetError

STYLE = Style([
    ("qmark", "fg:#22d3ee bold"), ("question", "bold"), ("answer", "fg:#22d3ee bold"),
    ("pointer", "fg:#22d3ee bold"), ("highlighted", "fg:#22d3ee bold"), ("selected", "fg:#4ade80"),
    ("separator", "fg:#555555"), ("instruction", "fg:#888888"),
])
BACK = "__back__"
FORMAT_LABELS = {"epub": "EPUB — máy đọc sách, app đọc", "docx": "DOCX — Word, sửa được",
                 "pdf": "PDF — in / đọc trên máy tính", "images": "Ảnh — thư mục ảnh minh hoạ"}


def ask(q):
    """questionary trả None khi Ctrl+C / ESC → coi như quay lại."""
    ans = q.ask()
    return BACK if ans is None else ans


def select(msg, choices, **kw):
    return ask(questionary.select(msg, choices=[*choices, Separator(), Choice("← Quay lại", BACK)],
                                  style=STYLE, **kw))


def text(msg, default="", **kw):
    return ask(questionary.text(msg, default=default, style=STYLE, **kw))


def pause():
    questionary.press_any_key_to_continue("Nhấn phím bất kỳ để tiếp tục…", style=STYLE).ask()


# ── Màn hình ──────────────────────────────────────────────────────────────────

def banner() -> None:
    from lnget.sources import all_sources, client_for

    s = load_settings()
    auth = []
    for src in all_sources(s):
        if src.supports_login:
            auth.append(f"{src.id}: " + ("[green]đã đăng nhập[/]" if client_for(src, s).has_cookies
                                         else "[yellow]chưa đăng nhập[/]"))
    console.rule(f"[bold cyan]lnget {__version__}[/]")
    console.print(f"[dim]Lưu tại[/] {s.output}   [dim]Định dạng[/] {', '.join(f.upper() for f in s.formats)}   "
                  + "   ".join(auth))


def main() -> None:
    while True:
        banner()
        choice = ask(questionary.select("Bạn muốn làm gì?", style=STYLE, choices=[
            Choice("📥  Tải truyện (dán link)", "get"),
            Choice("📋  Tải nhiều truyện (danh sách link / file)", "batch"),
            Choice("🔎  Quét trang danh sách Hako", "listing"),
            Choice("📚  Thư viện — build thêm định dạng, mở thư mục", "library"),
            Choice("👤  Tài khoản / đăng nhập", "account"),
            Choice("🌐  Mở Web UI trên trình duyệt", "ui"),
            Choice("⚙️   Cài đặt", "settings"),
            Separator(),
            Choice("Thoát", "quit"),
        ]))
        if choice in ("quit", BACK):
            return
        try:
            SCREENS[choice]()
        except LngetError as e:
            console.print(f"[red]✗ {e}[/]")
            pause()
        except KeyboardInterrupt:
            console.print("\n[yellow]Đã dừng. Chạy lại để tiếp tục — chương đã tải không tải lại.[/]")


def screen_get() -> None:
    from lnget.cli import run_jobs
    from lnget.engine import Engine

    url = text("Dán link truyện:", validate=lambda v: bool(v.strip()) or "Chưa nhập link")
    if url == BACK:
        return
    with console.status("Đang đọc thông tin truyện…"):
        info = Engine().preview(url.strip())
    console.print(novel_header(info))
    console.print(novel_table(info))
    vols = info["volumes"]
    if not vols:
        raise LngetError("Truyện chưa có chương nào")

    missing = [i for i, v in enumerate(vols, 1) if v["cached"] < len(v["chapters"])]
    mode = select("Tải tập nào?", [
        Choice(f"Tất cả ({len(vols)} tập)", "all"),
        *([Choice(f"Chỉ tập còn thiếu ({len(missing)} tập)", "missing")] if 0 < len(missing) < len(vols) else []),
        Choice("Chọn tập…", "pick"),
    ])
    if mode == BACK:
        return
    if mode == "missing":
        spec = ",".join(map(str, missing))
    elif mode == "pick":
        picked = ask(questionary.checkbox(
            "Chọn tập (Space: chọn/bỏ, a: chọn hết, Enter: xong):", style=STYLE,
            choices=[Choice(f"{v['title']}  [{len(v['chapters'])} chương]", str(i), checked=i in missing)
                     for i, v in enumerate(vols, 1)],
            validate=lambda xs: bool(xs) or "Chọn ít nhất 1 tập"))
        if picked == BACK:
            return
        spec = ",".join(picked)
    else:
        spec = None

    settings = load_settings()
    fmts = pick_formats(settings.formats)
    if fmts == BACK:
        return
    settings.formats = fmts
    results = run_jobs([url.strip()], settings.validate(), spec)
    after_job(results)


def pick_formats(defaults: list[str]):
    return ask(questionary.checkbox(
        "Định dạng (Space để chọn):", style=STYLE,
        choices=[Choice(label, f, checked=f in defaults) for f, label in FORMAT_LABELS.items()],
        validate=lambda xs: bool(xs) or "Chọn ít nhất 1 định dạng"))


def after_job(results: list[dict]) -> None:
    paths = [r["path"] for r in results if r.get("path")]
    if not paths:
        pause()
        return
    if ask(questionary.confirm("Mở thư mục truyện?", default=True, style=STYLE)) is True:
        from lnget.util import open_path
        open_path(paths[-1])


def screen_batch() -> None:
    from lnget.cli import read_url_list, run_jobs

    how = select("Lấy danh sách link từ đâu?", [
        Choice("Dán link (cách nhau bằng dấu cách hoặc xuống dòng)", "paste"),
        Choice("File .txt trên máy / link file online", "file"),
    ])
    if how == BACK:
        return
    if how == "paste":
        raw = ask(questionary.text("Dán link (Esc rồi Enter để xong):", multiline=True, style=STYLE))
        if raw == BACK:
            return
        urls = [u for u in raw.split() if u.startswith("http")]
    else:
        src = ask(questionary.path("Đường dẫn file / link:", style=STYLE))
        if src == BACK:
            return
        urls = read_url_list(src.strip().strip('"'))
    if not urls:
        raise LngetError("Không có link hợp lệ")
    settings = load_settings()
    fmts = pick_formats(settings.formats)
    if fmts == BACK:
        return
    settings.formats = fmts
    console.print(f"Sẽ tải [bold]{len(urls)}[/] truyện, lần lượt từng truyện.")
    after_job(run_jobs(list(dict.fromkeys(urls)), settings.validate()))


def screen_listing() -> None:
    from types import SimpleNamespace

    from lnget.cli import cmd_list

    url = text("Link trang danh sách / thể loại (Enter = /danh-sach):")
    if url == BACK:
        return
    pages = text("Trang (vd 1, 1-5, 1- đến hết):", default="1")
    if pages == BACK:
        return
    settings = load_settings()
    fmts = pick_formats(settings.formats)
    if fmts == BACK:
        return
    cmd_list(SimpleNamespace(source="hako", url=url.strip() or None, pages=pages.strip() or "1",
                             dry_run=False, format=fmts, output=None))
    pause()


def screen_library() -> None:
    from lnget.cli import run_jobs
    from lnget.library import Library
    from lnget.util import open_path

    s = load_settings()
    items = Library(s.output, s.split_by_status).scan()
    if not items:
        console.print(f"Chưa có truyện nào trong [bold]{s.output}[/].")
        pause()
        return
    choices = []
    for nd in items:
        sm = nd.summary()
        fmts = sorted({f.upper() for v in sm["volumes"] for f in v["formats"]})
        choices.append(Choice(f"{sm['title'][:60]}  ({len(sm['volumes'])} tập · {', '.join(fmts) or 'chưa xuất'})",
                              str(nd.path)))
    path = select("Chọn truyện:", choices)
    if path == BACK:
        return
    action = select(Path(path).name, [
        Choice("Build thêm / build lại định dạng", "rebuild"),
        Choice("Tải chương mới (cập nhật)", "update"),
        Choice("Mở thư mục", "open"),
    ])
    if action == "open":
        open_path(path)
    elif action == "rebuild":
        fmts = pick_formats([])
        if fmts != BACK:
            s.formats = fmts
            run_jobs([], s.validate(), rebuild_path=path)
            pause()
    elif action == "update":
        nd = Library(s.output).load(path)
        after_job(run_jobs([nd.novel.url], s))


def screen_account() -> None:
    from lnget import auth
    from lnget.sources import all_sources, client_for

    sources = [s for s in all_sources() if s.supports_login]
    src = sources[0] if len(sources) == 1 else None
    if src is None:
        sid = select("Site:", [Choice(s.name, s.id) for s in sources])
        if sid == BACK:
            return
        src = next(s for s in sources if s.id == sid)
    http = client_for(src)
    with console.status("Kiểm tra đăng nhập…"):
        who = src.whoami(http)
    console.print(f"{src.name}: " + (f"[green]đang đăng nhập — {who}[/]" if who else "[yellow]chưa đăng nhập[/]"))
    action = select("Chọn:", [
        Choice("Đăng nhập bằng trình duyệt (khuyên dùng)", "browser"),
        Choice("Đăng nhập bằng tên + mật khẩu", "password"),
        *([Choice("Đăng xuất", "logout")] if http.has_cookies else []),
    ])
    if action == "browser":
        who = auth.login_browser(src, http, on_status=lambda m: console.print(f"[cyan]{m}[/]"))
        console.print(f"[green]✓ Đã đăng nhập: {who}[/]")
    elif action == "password":
        user = text("Tên đăng nhập:")
        if user == BACK:
            return
        pw = ask(questionary.password("Mật khẩu:", style=STYLE))
        if pw == BACK:
            return
        with console.status("Đang đăng nhập…"):
            who = auth.login_password(src, http, user.strip(), pw)
        console.print(f"[green]✓ Đã đăng nhập: {who}[/]  [dim](chỉ lưu phiên đăng nhập, không lưu mật khẩu)[/]")
    elif action == "logout":
        auth.logout(http)
        console.print("Đã đăng xuất.")
    if action != BACK:
        pause()


def screen_ui() -> None:
    from lnget.web.server import serve

    console.print("Đang mở Web UI… nhấn [bold]Ctrl+C[/] để tắt và quay lại menu.")
    try:
        serve(open_browser=True)
    except KeyboardInterrupt:
        pass


def screen_settings() -> None:
    s = load_settings()
    while True:
        key = select("Cài đặt (chọn để sửa):", [
            Choice(f"Thư mục lưu:        {s.output}", "output"),
            Choice(f"Định dạng mặc định: {', '.join(f.upper() for f in s.formats)}", "formats"),
            Choice(f"Chia theo tình trạng (Đã/Chưa hoàn thành): {'Có' if s.split_by_status else 'Không'}", "split"),
            Choice(f"Giữ ảnh đã tải (build lại nhanh):          {'Có' if s.keep_image_cache else 'Không'}", "keep"),
            Choice(f"Tốc độ: chờ {s.delay}s/request · {s.chapter_workers} chương · {s.image_workers} ảnh song song", "speed"),
            Choice(f"Domain Hako: {s.domains.get('hako', 'docln.sbs (mặc định)')}", "domain"),
        ])
        if key == BACK:
            return
        if key == "output":
            v = ask(questionary.path("Thư mục lưu:", default=s.output, only_directories=True, style=STYLE))
            if v != BACK and v.strip():
                s.output = v.strip().strip('"')
        elif key == "formats":
            v = pick_formats(s.formats)
            if v != BACK:
                s.formats = v
        elif key == "split":
            s.split_by_status = not s.split_by_status
        elif key == "keep":
            s.keep_image_cache = not s.keep_image_cache
        elif key == "speed":
            for attr, label in (("delay", "Chờ giữa request (giây)"), ("chapter_workers", "Số chương song song (1-8)"),
                                ("image_workers", "Số ảnh song song (1-16)")):
                v = text(label + ":", default=str(getattr(s, attr)))
                if v == BACK:
                    break
                try:
                    setattr(s, attr, type(getattr(s, attr))(v))
                except ValueError:
                    console.print("[red]Giá trị không hợp lệ[/]")
        elif key == "domain":
            v = text("Domain Hako mới (để trống = mặc định):", default=s.domains.get("hako", ""))
            if v != BACK and v.strip():
                s.domains["hako"] = v.strip()
            elif v != BACK:
                s.domains.pop("hako", None)
        save_settings(s)
        s = load_settings()


SCREENS = {
    "get": screen_get, "batch": screen_batch, "listing": screen_listing, "library": screen_library,
    "account": screen_account, "ui": screen_ui, "settings": screen_settings,
}
