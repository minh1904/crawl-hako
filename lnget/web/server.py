"""Web UI local: FastAPI + Server-Sent Events. Chỉ nghe trên 127.0.0.1.

Bảo vệ:
- Chỉ chấp nhận Host là localhost/127.0.0.1 (chống DNS rebinding).
- Mọi request thay đổi dữ liệu phải có header `X-Lnget: 1` — trang web lạ không gửi được
  header tuỳ chỉnh mà không qua CORS preflight (server không cho phép) → chống CSRF.
- Chỉ mở / build lại thư mục nằm trong thư mục lưu truyện.
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import webbrowser
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lnget import __version__, auth
from lnget.config import Settings, load_settings, save_settings
from lnget.engine import Engine, JobOptions
from lnget.http import LngetError
from lnget.library import Library
from lnget.models import FORMATS
from lnget.sources import all_sources, client_for, find_source, get_source
from lnget.util import open_path

STATIC = Path(__file__).parent / "static"


class PreviewIn(BaseModel):
    url: str


class JobIn(BaseModel):
    url: str
    formats: list[str]
    volume_ids: list[str] | None = None
    refetch: bool = False


class RebuildIn(BaseModel):
    path: str
    formats: list[str]
    volume_ids: list[str] | None = None


class PathIn(BaseModel):
    path: str


class LoginIn(BaseModel):
    username: str
    password: str


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or Engine()
    app = FastAPI(title="lnget", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    image_cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "[::1]"):
            return JSONResponse({"detail": "Host không hợp lệ"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-lnget") != "1":
            return JSONResponse({"detail": "Thiếu header X-Lnget"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(LngetError)
    async def lnget_error(_req: Request, exc: LngetError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def inside_output(path: str) -> Path:
        s = load_settings()
        p = Path(path).resolve()
        root = Path(s.output).expanduser().resolve()
        if p != root and root not in p.parents:
            raise HTTPException(400, "Đường dẫn nằm ngoài thư mục lưu truyện")
        return p

    # ── Trạng thái / cài đặt ──────────────────────────────────────────────────

    @app.get("/api/status")
    def status():
        s = load_settings()
        return {
            "version": __version__,
            "settings": s.to_dict(),
            "formats": list(FORMATS),
            "sources": [{
                "id": src.id, "name": src.name, "domain": src.domain,
                "supports_login": src.supports_login, "supports_listing": src.supports_listing,
                "has_session": client_for(src, s).has_cookies,
            } for src in all_sources(s)],
        }

    @app.put("/api/settings")
    def put_settings(body: dict):
        s = load_settings()
        merged = {**s.to_dict(), **{k: v for k, v in body.items() if k in s.to_dict()}}
        try:
            s = Settings(**merged).validate()
        except (TypeError, ValueError) as e:
            raise HTTPException(400, f"Cài đặt không hợp lệ: {e}")
        save_settings(s)
        return s.to_dict()

    # ── Tài khoản ─────────────────────────────────────────────────────────────

    @app.get("/api/accounts/{sid}")
    def whoami(sid: str):
        src = get_source(sid)
        return {"source": sid, "user": src.whoami(client_for(src))}

    @app.post("/api/accounts/{sid}/login")
    def login(sid: str, body: LoginIn):
        src = get_source(sid)
        return {"source": sid, "user": auth.login_password(src, client_for(src), body.username, body.password)}

    @app.post("/api/accounts/{sid}/browser-login")
    def browser_login(sid: str):
        src = get_source(sid)
        return {"source": sid, "user": auth.login_browser(src, client_for(src))}

    @app.post("/api/accounts/{sid}/logout")
    def logout(sid: str):
        auth.logout(client_for(get_source(sid)))
        return {"source": sid, "user": None}

    # ── Truyện / job ──────────────────────────────────────────────────────────

    @app.post("/api/preview")
    def preview(body: PreviewIn):
        return engine.preview(body.url.strip())

    @app.get("/api/jobs")
    def jobs():
        return [j.snapshot() for j in sorted(engine.jobs.values(), key=lambda j: -j.id)]

    @app.post("/api/jobs")
    def create_job(body: JobIn):
        find_source(body.url)  # báo lỗi sớm nếu link không hỗ trợ
        fmts = [f for f in body.formats if f in FORMATS]
        if not fmts:
            raise HTTPException(400, "Chọn ít nhất 1 định dạng")
        job = engine.submit(JobOptions(url=body.url.strip(), formats=fmts,
                                       volume_ids=body.volume_ids, refetch=body.refetch))
        return job.snapshot()

    @app.post("/api/jobs/{job_id}/{action}")
    def job_action(job_id: int, action: str):
        if job_id not in engine.jobs:
            raise HTTPException(404, "Không có job này")
        if action == "retry":
            return engine.retry(job_id).snapshot()
        fn = {"pause": engine.pause, "resume": engine.resume, "cancel": engine.cancel}.get(action)
        if fn is None:
            raise HTTPException(400, "Thao tác không hợp lệ")
        fn(job_id)
        return engine.jobs[job_id].snapshot()

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: int):
        engine.remove(job_id)
        return {"ok": True}

    @app.post("/api/jobs/clear")
    def clear_jobs():
        for jid in [j.id for j in engine.jobs.values() if j.status in ("done", "failed", "cancelled")]:
            engine.remove(jid)
        return {"ok": True}

    @app.get("/api/events")
    async def events(request: Request):
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)

        def listener(ev: dict) -> None:
            loop.call_soon_threadsafe(_put_nowait, q, ev)

        engine.subscribe(listener)

        async def stream():
            try:
                yield "retry: 2000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
                        continue
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            finally:
                engine.unsubscribe(listener)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── Thư viện ──────────────────────────────────────────────────────────────

    @app.get("/api/library")
    def library():
        s = load_settings()
        return {"root": s.output, "items": [nd.summary() for nd in Library(s.output, s.split_by_status).scan()]}

    @app.get("/api/library/cover")
    def library_cover(path: str):
        p = inside_output(path)
        for f in p.glob("cover.*"):
            return FileResponse(f, headers={"Cache-Control": "max-age=3600"})
        raise HTTPException(404)

    @app.post("/api/library/rebuild")
    def rebuild(body: RebuildIn):
        p = inside_output(body.path)
        fmts = [f for f in body.formats if f in FORMATS]
        if not fmts:
            raise HTTPException(400, "Chọn ít nhất 1 định dạng")
        job = engine.submit(JobOptions(formats=fmts, volume_ids=body.volume_ids, rebuild_path=str(p)))
        return job.snapshot()

    @app.post("/api/open")
    def open_folder(body: PathIn):
        p = inside_output(body.path)
        if not p.exists():
            raise HTTPException(404, "Không tìm thấy")
        open_path(p)
        return {"ok": True}

    # ── Proxy ảnh bìa (CDN chặn hotlink) ──────────────────────────────────────

    @app.get("/api/image")
    def image(url: str, source: str):
        if url in image_cache:
            data, ctype = image_cache[url]
        else:
            src = get_source(source)
            if not url.startswith(("http://", "https://")):
                raise HTTPException(400)
            try:
                data = client_for(src).get_image(url, src.image_referer(url, src.base_url + "/"))
            except LngetError as e:
                raise HTTPException(502, str(e))
            ctype = "image/png" if data[:2] == b"\x89P" else "image/webp" if data[:2] == b"RI" else "image/jpeg"
            image_cache[url] = (data, ctype)
            while len(image_cache) > 200:
                image_cache.popitem(last=False)
        return Response(data, media_type=ctype, headers={"Cache-Control": "max-age=86400"})

    # ── Giao diện ─────────────────────────────────────────────────────────────

    if (STATIC / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets", check_dir=False), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            f = (STATIC / full_path).resolve()
            if full_path and f.is_file() and STATIC.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def no_ui():
            return HTMLResponse("<h1>lnget</h1><p>Chưa build giao diện web. Trong thư mục webui/: "
                                "<code>npm install && npm run build</code>. API vẫn chạy tại /api.</p>")

    return app


def _put_nowait(q: asyncio.Queue, ev: dict) -> None:
    try:
        q.put_nowait(ev)
    except asyncio.QueueFull:
        pass


def _free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise LngetError("Không tìm được cổng trống để chạy Web UI")


def serve(port: int = 8765, open_browser: bool = True) -> None:
    import uvicorn

    from lnget.console import console

    port = _free_port(port)
    url = f"http://127.0.0.1:{port}"
    console.print(f"[bold green]Web UI:[/] {url}   [dim](Ctrl+C để tắt)[/]")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
