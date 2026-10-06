"""Dòng lệnh `lnget`. Chạy `lnget` không tham số để mở menu tương tác."""
from __future__ import annotations

import argparse
import getpass
import logging
import sys
import urllib.request
from pathlib import Path

from lnget import __version__
from lnget.config import Settings, config_path, load_settings, save_settings
from lnget.http import LngetError

EPILOG = """
ví dụ:
  lnget                                   mở menu tương tác
  lnget ui                                mở Web UI trên trình duyệt
  lnget get https://docln.sbs/truyen/123-ten-truyen
  lnget get URL -f epub pdf -v 1,3-5      chọn định dạng và tập
  lnget get --file ds.txt                 tải nhiều truyện (mỗi dòng 1 link, # để ghi chú)
  lnget info URL                          xem danh sách tập
  lnget list --pages 1-3                  quét trang danh sách Hako và tải hết
  lnget login --browser                   đăng nhập Hako bằng trình duyệt
  lnget rebuild "D:/Truyen/[Truyện dịch] Abc" -f docx
  lnget config output="D:/Truyen" delay=1.5
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lnget", description="Tải light novel ra EPUB / DOCX / PDF / ảnh.",
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"lnget {__version__}")
    p.add_argument("--debug", action="store_true", help="in log chi tiết")
    sub = p.add_subparsers(dest="cmd", metavar="<lệnh>")

    def fmt_opts(sp):
        sp.add_argument("-f", "--format", nargs="+", choices=["epub", "docx", "pdf", "images"],
                        help="định dạng (mặc định theo cài đặt)")
        sp.add_argument("-o", "--output", help="thư mục lưu (mặc định theo cài đặt)")

    g = sub.add_parser("get", help="tải truyện theo link")
    g.add_argument("urls", nargs="*", metavar="URL")
    g.add_argument("--file", help="file .txt (hoặc link) chứa danh sách URL")
    g.add_argument("-v", "--volumes", help="chọn tập: 1,3-5 hoặc 4- (mặc định: tất cả)")
    g.add_argument("--refetch", action="store_true", help="tải lại cả chương đã có")
    fmt_opts(g)

    i = sub.add_parser("info", help="xem thông tin + danh sách tập")
    i.add_argument("url")

    ls = sub.add_parser("list", help="quét trang danh sách và tải từng truyện")
    ls.add_argument("--source", default="hako")
    ls.add_argument("--url", help="link trang danh sách / thể loại (mặc định /danh-sach)")
    ls.add_argument("--pages", default="1", help="trang: 3, 1-5 hoặc 1- (đến hết). Mặc định: 1")
    ls.add_argument("--dry-run", action="store_true", help="chỉ in danh sách link, không tải")
    fmt_opts(ls)

    lg = sub.add_parser("login", help="đăng nhập (lưu session, không lưu mật khẩu)")
    lg.add_argument("source", nargs="?", default="hako")
    lg.add_argument("--browser", action="store_true", help="mở trình duyệt để tự đăng nhập")
    lg.add_argument("-u", "--username")

    lo = sub.add_parser("logout", help="xoá session đăng nhập")
    lo.add_argument("source", nargs="?", default="hako")

    sub.add_parser("whoami", help="xem trạng thái đăng nhập các site")
    sub.add_parser("sources", help="các site được hỗ trợ")
    sub.add_parser("library", help="liệt kê truyện đã tải")

    rb = sub.add_parser("rebuild", help="xuất lại định dạng từ thư mục đã tải (không cần mạng)")
    rb.add_argument("path")
    rb.add_argument("-v", "--volumes")
    rb.add_argument("-f", "--format", nargs="+", choices=["epub", "docx", "pdf", "images"], required=True)

    c = sub.add_parser("config", help="xem / đổi cài đặt: lnget config key=value")
    c.add_argument("pairs", nargs="*", metavar="key=value")

    u = sub.add_parser("ui", help="mở Web UI")
    u.add_argument("--port", type=int, default=8765)
    u.add_argument("--no-browser", action="store_true", help="không tự mở trình duyệt")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if args.cmd is None:
        from lnget.tui import main as tui_main
        return tui_main()
    from lnget.console import console
    try:
        COMMANDS[args.cmd](args)
    except LngetError as e:
        console.print(f"[red]✗ {e}[/]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã dừng. Chạy lại cùng lệnh để tiếp tục — chương đã tải không tải lại.[/]")
        sys.exit(130)


# ── Lệnh ──────────────────────────────────────────────────────────────────────

def _settings(args) -> Settings:
    s = load_settings()
    if getattr(args, "output", None):
        s.output = args.output
    if getattr(args, "format", None):
        s.formats = args.format
    return s.validate()


def run_jobs(urls: list[str], settings: Settings, volumes: str | None = None,
             refetch: bool = False, rebuild_path: str | None = None) -> list[dict]:
    from lnget.console import ProgressView, console, print_summary
    from lnget.engine import Engine, Job, JobOptions

    engine = Engine(lambda: settings)
    results = []
    targets = [rebuild_path] if rebuild_path else urls
    with ProgressView() as view:
        engine.subscribe(view)
        for n, url in enumerate(targets, 1):
            if len(targets) > 1:
                view.progress.console.print(f"[bold cyan]({n}/{len(targets)})[/] {url}")
            job = Job(JobOptions(url="" if rebuild_path else url, formats=settings.formats,
                                 volume_spec=volumes, refetch=refetch, rebuild_path=rebuild_path))
            try:
                engine.run(job)
            except KeyboardInterrupt:
                job.cancel_event.set()
                raise
            results.append(job.snapshot())
    for snap in results:
        print_summary(snap)
    if len(results) > 1:
        ok = sum(r["status"] == "done" for r in results)
        console.print(f"[bold]Tổng: {ok}/{len(results)} truyện thành công[/]")
    return results


def read_url_list(src: str) -> list[str]:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=20) as r:
            text = r.read().decode("utf-8", "replace")
    else:
        p = Path(src)
        if not p.is_file():
            raise LngetError(f"Không thấy file: {src}")
        text = p.read_text(encoding="utf-8")
    urls = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not urls:
        raise LngetError("File không có link nào")
    return urls


def cmd_get(args) -> None:
    urls = list(args.urls)
    if args.file:
        urls += read_url_list(args.file)
    if not urls:
        raise LngetError("Cần ít nhất 1 link truyện (hoặc --file)")
    results = run_jobs(list(dict.fromkeys(urls)), _settings(args), args.volumes, args.refetch)
    if any(r["status"] != "done" for r in results):
        sys.exit(1)


def cmd_info(args) -> None:
    from lnget.console import console, novel_header, novel_table
    from lnget.engine import Engine

    with console.status("Đang đọc thông tin truyện…"):
        info = Engine().preview(args.url)
    console.print(novel_header(info))
    console.print(novel_table(info))


def cmd_list(args) -> None:
    from lnget.console import console
    from lnget.http import NotFound
    from lnget.sources import client_for, get_source

    settings = _settings(args)
    source = get_source(args.source, settings)
    a, sep, b = args.pages.partition("-")
    start, end = int(a or 1), (int(b) if b else None) if sep else int(a or 1)
    http = client_for(source, settings)
    urls: list[str] = []
    page = start
    while end is None or page <= end:
        try:
            with console.status(f"Đang quét trang {page}…"):
                found = source.list_novels(http, page, args.url)
        except NotFound:
            break
        new = [u for u in found if u not in urls]
        if not new:
            break
        console.print(f"Trang {page}: {len(new)} truyện")
        urls += new
        page += 1
    if args.dry_run:
        console.print("\n".join(urls))
        return
    if urls:
        run_jobs(urls, settings)


def cmd_login(args) -> None:
    from lnget import auth
    from lnget.console import console
    from lnget.sources import client_for, get_source

    source = get_source(args.source)
    http = client_for(source)
    if args.browser:
        who = auth.login_browser(source, http, on_status=lambda m: console.print(f"[cyan]{m}[/]"))
    else:
        username = args.username or input(f"Tên đăng nhập {source.name}: ").strip()
        password = getpass.getpass("Mật khẩu (không hiện khi gõ): ")
        with console.status("Đang đăng nhập…"):
            who = auth.login_password(source, http, username, password)
    console.print(f"[green]✓ Đã đăng nhập {source.name}: {who}[/]")


def cmd_logout(args) -> None:
    from lnget.console import console
    from lnget.sources import client_for, get_source

    source = get_source(args.source)
    client_for(source).clear_cookies()
    console.print(f"Đã đăng xuất {source.name}.")


def cmd_whoami(args) -> None:
    from lnget.console import console
    from lnget.sources import all_sources, client_for

    for s in all_sources():
        if not s.supports_login:
            console.print(f"{s.name}: [dim]không cần đăng nhập[/]")
            continue
        with console.status(f"Kiểm tra {s.name}…"):
            who = s.whoami(client_for(s))
        console.print(f"{s.name}: " + (f"[green]{who}[/]" if who else "[yellow]chưa đăng nhập[/]"))


def cmd_sources(args) -> None:
    from lnget.console import console
    from lnget.sources import all_sources

    for s in all_sources():
        feats = [x for x, ok in (("đăng nhập", s.supports_login), ("quét danh sách", s.supports_listing)) if ok]
        console.print(f"[bold]{s.id}[/]  {s.name}  [cyan]{s.domain}[/]  [dim]{', '.join(feats)}[/]")


def cmd_library(args) -> None:
    from rich.table import Table

    from lnget.console import console
    from lnget.library import Library

    s = load_settings()
    items = Library(s.output, s.split_by_status).scan()
    if not items:
        console.print(f"Chưa có truyện nào trong {s.output}")
        return
    t = Table(header_style="bold")
    for col in ("Truyện", "Tập", "Chương đã có", "Định dạng", "Thư mục"):
        t.add_column(col)
    for nd in items:
        sm = nd.summary()
        fmts = sorted({f for v in sm["volumes"] for f in v["formats"]})
        t.add_row(sm["title"][:50], str(len(sm["volumes"])),
                  f"{sum(v['cached'] for v in sm['volumes'])}/{sum(v['chapters'] for v in sm['volumes'])}",
                  ", ".join(f.upper() for f in fmts) or "-", Path(sm["path"]).name[:40])
    console.print(t)


def cmd_rebuild(args) -> None:
    s = load_settings()
    s.formats = args.format
    run_jobs([], s.validate(), args.volumes, rebuild_path=args.path)


def cmd_config(args) -> None:
    from lnget.console import console

    s = load_settings()
    for pair in args.pairs:
        key, _, value = pair.partition("=")
        key = key.strip().replace("-", "_")
        if not hasattr(s, key) or key == "domains":
            if key.startswith("domain."):
                s.domains[key.split(".", 1)[1]] = value
                continue
            raise LngetError(f"Không có cài đặt '{key}'")
        cur = getattr(s, key)
        if isinstance(cur, bool):
            setattr(s, key, value.lower() in ("1", "true", "yes", "on", "co", "có"))
        elif isinstance(cur, (int, float)):
            setattr(s, key, type(cur)(value))
        elif isinstance(cur, list):
            setattr(s, key, [x for x in value.replace(",", " ").split() if x])
        else:
            setattr(s, key, value)
    if args.pairs:
        save_settings(s)
    console.print(f"[dim]{config_path()}[/]")
    for k, v in s.to_dict().items():
        console.print(f"  [bold]{k}[/] = {v}")


def cmd_ui(args) -> None:
    from lnget.web.server import serve

    serve(port=args.port, open_browser=not args.no_browser)


COMMANDS = {
    "get": cmd_get, "info": cmd_info, "list": cmd_list, "login": cmd_login, "logout": cmd_logout,
    "whoami": cmd_whoami, "sources": cmd_sources, "library": cmd_library, "rebuild": cmd_rebuild,
    "config": cmd_config, "ui": cmd_ui,
}
