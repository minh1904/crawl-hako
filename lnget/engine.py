"""Engine tải truyện — không in gì ra màn hình, chỉ phát event.

CLI, menu terminal và Web UI đều dùng chung engine này và tự hiển thị event theo cách riêng.
"""
from __future__ import annotations

import itertools
import logging
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from lnget.config import Settings, load_settings
from lnget.exporters import get_exporter
from lnget.http import Cancelled, HttpClient, HttpError, LngetError, LoginRequired, NotFound
from lnget.library import Library, NovelDir
from lnget.models import FORMATS, ChapterRef, Novel, Volume
from lnget.sources import client_for, find_source, get_source
from lnget.sources.base import Source

log = logging.getLogger(__name__)
Listener = Callable[[dict], None]
_ids = itertools.count(1)


def parse_volume_spec(spec: str | None, total: int) -> list[int] | None:
    """'1,3-5' → [1, 3, 4, 5] (đánh số từ 1). None/''/'all' → tất cả."""
    if not spec or spec.strip().lower() in ("all", "*"):
        return None
    out: set[int] = set()
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        a, sep, b = part.partition("-")
        try:
            lo = int(a) if a else 1
            hi = (int(b) if b else total) if sep else lo
        except ValueError:
            raise LngetError(f"Chọn tập không hợp lệ: '{part}' (ví dụ đúng: 1,3-5,8-)")
        out.update(range(lo, hi + 1))
    return sorted(i for i in out if 1 <= i <= total)


@dataclass
class JobOptions:
    url: str = ""
    formats: list[str] = field(default_factory=lambda: ["epub"])
    volume_ids: list[str] | None = None   # chọn tập theo id (Web UI)
    volume_spec: str | None = None        # hoặc theo số thứ tự "1,3-5" (CLI)
    refetch: bool = False                 # tải lại cả chương đã có trong cache
    rebuild_path: str | None = None       # chỉ build lại từ thư mục có sẵn, không tải chương mới


@dataclass
class Job:
    options: JobOptions
    id: int = field(default_factory=lambda: next(_ids))
    status: str = "queued"  # queued | running | paused | done | failed | cancelled
    title: str = ""
    source: str = ""
    path: str = ""
    error: str = ""
    hint: str = ""
    created: float = field(default_factory=time.time)
    finished: float = 0.0
    total: int = 0
    done: int = 0
    failed: int = 0
    images_ok: int = 0
    images_failed: int = 0
    volume: str = ""
    outputs: list[str] = field(default_factory=list)
    login_needed: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    run_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def __post_init__(self):
        self.run_event.set()

    def checkpoint(self) -> None:
        """Gọi giữa các bước: chờ nếu đang tạm dừng, ném Cancelled nếu đã huỷ."""
        while not self.run_event.wait(0.3):
            if self.cancel_event.is_set():
                break
        if self.cancel_event.is_set():
            raise Cancelled("Đã huỷ")

    def snapshot(self) -> dict:
        return {
            "id": self.id, "status": self.status, "title": self.title or self.options.url,
            "url": self.options.url, "source": self.source, "path": self.path,
            "formats": self.options.formats, "error": self.error, "hint": self.hint,
            "created": self.created, "finished": self.finished, "total": self.total,
            "done": self.done, "failed": self.failed, "images_ok": self.images_ok,
            "images_failed": self.images_failed, "volume": self.volume, "outputs": self.outputs,
            "login_needed": self.login_needed, "rebuild": bool(self.options.rebuild_path),
        }


class Engine:
    def __init__(self, settings_provider: Callable[[], Settings] = load_settings):
        self.settings_provider = settings_provider
        self.jobs: dict[int, Job] = {}
        self._listeners: list[Listener] = []
        self._queue: list[Job] = []
        self._cv = threading.Condition()
        self._worker: threading.Thread | None = None

    # ── Event ─────────────────────────────────────────────────────────────────

    def subscribe(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def unsubscribe(self, fn: Listener) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def emit(self, job: Job | None, type_: str, **data) -> None:
        ev = {"type": type_, "job": job.id if job else None, "ts": time.time(), **data}
        if job is not None:
            ev["snapshot"] = job.snapshot()
        for fn in list(self._listeners):
            try:
                fn(ev)
            except Exception:
                log.exception("Listener lỗi")

    # ── Xem trước ─────────────────────────────────────────────────────────────

    def preview(self, url: str) -> dict:
        settings = self.settings_provider()
        source = find_source(url, settings)
        http = client_for(source, settings)
        novel = source.fetch_novel(http, url)
        lib = Library(settings.output, settings.split_by_status)
        existing = lib.find(novel.source, novel.id)
        nd = NovelDir(existing, novel) if existing else None
        vols = []
        for v in novel.volumes:
            vols.append({
                "id": v.id, "title": v.title, "cover_url": v.cover_url,
                "chapters": [{"id": c.id, "title": c.title, "locked": c.locked} for c in v.chapters],
                "cached": sum(1 for c in v.chapters if nd and nd.has_chapter(c.id)),
                "formats": [f for f in FORMATS if nd and nd.has_output(v, f)],
            })
        d = novel.to_dict()
        d["volumes"] = vols
        d["path"] = str(existing) if existing else ""
        d["source_name"] = source.name
        d["logged_in"] = http.has_cookies
        return d

    # ── Hàng đợi (Web UI) ─────────────────────────────────────────────────────

    def submit(self, options: JobOptions) -> Job:
        job = Job(options)
        self.jobs[job.id] = job
        with self._cv:
            self._queue.append(job)
            self._cv.notify()
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._loop, name="lnget-worker", daemon=True)
                self._worker.start()
        self.emit(job, "job_queued")
        return job

    def _loop(self) -> None:
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait()
                job = self._queue.pop(0)
            if job.status == "queued":
                self.run(job)

    def pause(self, job_id: int) -> None:
        job = self.jobs[job_id]
        if job.status == "running":
            job.run_event.clear()
            job.status = "paused"
            self.emit(job, "job_paused")

    def resume(self, job_id: int) -> None:
        job = self.jobs[job_id]
        if job.status == "paused":
            job.status = "running"
            job.run_event.set()
            self.emit(job, "job_resumed")

    def cancel(self, job_id: int) -> None:
        job = self.jobs[job_id]
        if job.status in ("queued", "running", "paused"):
            job.cancel_event.set()
            job.run_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                self.emit(job, "job_finished")

    def retry(self, job_id: int) -> Job:
        return self.submit(self.jobs[job_id].options)

    def remove(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if job and job.status not in ("running", "paused"):
            if job.status == "queued":
                self.cancel(job_id)
            self.jobs.pop(job_id, None)

    # ── Chạy 1 job (đồng bộ) ──────────────────────────────────────────────────

    def run(self, job: Job) -> Job:
        job.status = "running"
        self.emit(job, "job_started")
        try:
            if job.options.rebuild_path:
                self._rebuild(job)
            else:
                self._download(job)
            job.status = "done"
        except Cancelled:
            job.status = "cancelled"
        except LoginRequired as e:
            job.status, job.error = "failed", str(e)
            job.hint = "Đăng nhập rồi chạy lại: `lnget login` hoặc mục Tài khoản trên Web UI."
        except LngetError as e:
            job.status, job.error = "failed", str(e)
        except Exception as e:  # lỗi không lường trước — vẫn báo gọn
            log.debug(traceback.format_exc())
            job.status, job.error = "failed", f"Lỗi không mong muốn: {e!r}"
        job.finished = time.time()
        if job.login_needed and not job.hint:
            job.hint = (f"{job.login_needed} chương/ảnh cần đăng nhập. "
                        "Đăng nhập (`lnget login` hoặc Web UI → Tài khoản) rồi chạy lại để tải phần còn thiếu.")
        self.emit(job, "job_finished")
        return job

    def _select(self, novel: Novel, opts: JobOptions) -> list[Volume]:
        if opts.volume_ids is not None:
            wanted = set(map(str, opts.volume_ids))
            return [v for v in novel.volumes if v.id in wanted]
        idx = parse_volume_spec(opts.volume_spec, len(novel.volumes))
        return novel.volumes if idx is None else [novel.volumes[i - 1] for i in idx]

    def _download(self, job: Job) -> None:
        settings = self.settings_provider()
        source = find_source(job.options.url, settings)
        http = client_for(source, settings)
        job.source = source.id
        self.emit(job, "log", message=f"Đang đọc thông tin truyện từ {source.name}…")
        novel = source.fetch_novel(http, job.options.url)
        job.title = novel.title
        nd = Library(settings.output, settings.split_by_status).open(novel)
        job.path = str(nd.path)
        nd.log(f"Bắt đầu tải: {novel.url} — định dạng {', '.join(job.options.formats)}")

        if novel.cover_url and nd.cover() is None:
            try:
                nd.save_cover(http.get_image(novel.cover_url, source.image_referer(novel.cover_url, novel.url)))
            except LngetError as e:
                nd.log(f"Không tải được bìa: {e}")

        volumes = self._select(novel, job.options)
        if not volumes:
            raise LngetError("Không có tập nào được chọn (hoặc truyện chưa có chương).")
        job.total = sum(len(v.chapters) for v in volumes)
        self.emit(job, "novel", novel={"title": novel.title, "volumes": len(volumes), "chapters": job.total})

        state = nd.load_state()
        with ThreadPoolExecutor(settings.image_workers, thread_name_prefix="img") as img_pool:
            for v in volumes:
                job.checkpoint()
                self._download_volume(job, source, http, nd, v, settings, img_pool, state)
        if not settings.keep_image_cache:
            nd.clear_images()
        nd.log(f"Xong: {job.done}/{job.total} chương, lỗi {job.failed}, ảnh lỗi {job.images_failed}")

    def _download_volume(self, job: Job, source: Source, http: HttpClient, nd: NovelDir, vol: Volume,
                         settings: Settings, img_pool: ThreadPoolExecutor, state: dict) -> None:
        job.volume = vol.title
        self.emit(job, "volume_started", volume=vol.title)
        errors: dict = state.setdefault("chapter_errors", {})
        img_errors: dict = state.setdefault("image_errors", {})
        fetched_any = False
        if vol.cover_url and nd.image_path(vol.cover_url) is None:
            self._fetch_image(job, source, http, nd, vol.cover_url, nd.novel.url)

        def fetch_images(ref: ChapterRef, urls: list[str]) -> None:
            # ảnh đã 404 lần trước (link chết) thì không thử lại, trừ khi tải lại toàn bộ
            todo = [u for u in urls if nd.image_path(u) is None
                    and (job.options.refetch or "404" not in img_errors.get(u, ""))]
            futs = {img_pool.submit(self._fetch_image, job, source, http, nd, u, ref.url): u for u in todo}
            for f in as_completed(futs):
                url, err = futs[f], f.result()
                if err is None:
                    job.images_ok += 1
                    img_errors.pop(url, None)
                else:
                    job.images_failed += 1
                    img_errors[url] = err
                    if ("403" in err or "401" in err) and source.is_own_image(url) and not http.has_cookies:
                        job.login_needed += 1
                    nd.log(f"Ảnh lỗi [{ref.title}] {url}: {err}")

        def work(ref: ChapterRef) -> tuple[ChapterRef, str | None, bool]:
            job.checkpoint()
            cached = None if job.options.refetch else nd.load_chapter(ref.id)
            fresh = cached is None
            try:
                chapter = cached or source.fetch_chapter(http, ref, job.cancel_event)
            except (LoginRequired, NotFound, HttpError, LngetError) as e:
                if isinstance(e, Cancelled):
                    raise
                return ref, f"{type(e).__name__}: {e}" if isinstance(e, LoginRequired) else str(e), False
            if fresh:
                nd.save_chapter(chapter)
            fetch_images(ref, chapter.image_urls)
            return ref, None, fresh

        def handle(ref: ChapterRef, err: str | None, fresh: bool) -> bool:
            nonlocal fetched_any
            if err is None:
                errors.pop(ref.id, None)
                job.done += 1
                fetched_any |= fresh
                self.emit(job, "chapter_done", chapter=ref.title, cached=not fresh)
                return True
            errors[ref.id] = err
            self.emit(job, "chapter_failed", chapter=ref.title, error=err)
            return False

        pending = list(vol.chapters)
        for attempt in range(2):  # lần 2: thử lại chương lỗi (trừ lỗi cần đăng nhập / 404)
            failed: list[ChapterRef] = []
            with ThreadPoolExecutor(settings.chapter_workers, thread_name_prefix="chap") as pool:
                futs = [pool.submit(work, ref) for ref in pending]
                for f in as_completed(futs):
                    ref, err, fresh = f.result()
                    if err and attempt == 0 and not err.startswith(("LoginRequired", "Không tìm thấy")):
                        failed.append(ref)
                        continue
                    if not handle(ref, err, fresh):
                        job.failed += 1
                        if err and err.startswith("LoginRequired"):
                            job.login_needed += 1
            nd.save_state(state)
            if not failed:
                break
            self.emit(job, "log", message=f"Thử lại {len(failed)} chương lỗi…")
            job.checkpoint()
            time.sleep(3)
            pending = failed

        missing = [f for f in job.options.formats if not nd.has_output(vol, f)]
        to_build = job.options.formats if fetched_any else missing
        self._export(job, nd, vol, to_build)

    def _fetch_image(self, job: Job, source: Source, http: HttpClient, nd: NovelDir,
                     url: str, page_url: str) -> str | None:
        try:
            job.checkpoint()
            nd.save_image(url, http.get_image(url, source.image_referer(url, page_url), job.cancel_event))
            return None
        except Cancelled:
            return "đã huỷ"
        except LngetError as e:
            return str(e)

    def _export(self, job: Job, nd: NovelDir, vol: Volume, formats: list[str]) -> None:
        if not formats:
            self.emit(job, "log", message=f"{vol.title}: đã có đủ file, bỏ qua.")
            return
        chapters = []
        for ref in vol.chapters:
            ch = nd.load_chapter(ref.id)
            if ch is not None:
                chapters.append(ch)
        if not chapters:
            self.emit(job, "log", message=f"{vol.title}: chưa có chương nào tải được, không xuất file.")
            return
        cover = nd.cover()
        if vol.cover_url:
            cover = nd.load_image(vol.cover_url) or cover
        for fmt in formats:
            job.checkpoint()
            out = nd.output_path(vol, fmt)
            self.emit(job, "export_started", format=fmt, volume=vol.title)
            try:
                get_exporter(fmt)(out, nd.novel, vol, chapters, cover, nd.load_image)
            except Exception as e:
                nd.log(f"Lỗi xuất {fmt} {out.name}: {e!r}")
                self.emit(job, "export_failed", format=fmt, volume=vol.title, error=str(e))
                continue
            job.outputs.append(str(out))
            nd.log(f"Đã xuất {out}")
            missing_count = len(vol.chapters) - len(chapters)
            self.emit(job, "export_done", format=fmt, volume=vol.title, path=str(out),
                      missing_chapters=missing_count)

    # ── Build lại từ thư mục có sẵn ───────────────────────────────────────────

    def _rebuild(self, job: Job) -> None:
        settings = self.settings_provider()
        lib = Library(settings.output, settings.split_by_status)
        nd = lib.load(job.options.rebuild_path)
        job.title, job.source, job.path = nd.novel.title, nd.novel.source, str(nd.path)
        volumes = self._select(nd.novel, job.options)
        job.total = sum(len(v.chapters) for v in volumes)
        source = get_source(nd.novel.source, settings)
        http = client_for(source, settings)
        for v in volumes:
            job.checkpoint()
            job.volume = v.title
            # ảnh còn thiếu trong cache (ví dụ đã xoá cache) → tải lại
            urls = [(ref, u) for ref in v.chapters if (ch := nd.load_chapter(ref.id)) for u in ch.image_urls
                    if nd.image_path(u) is None]
            if v.cover_url and nd.image_path(v.cover_url) is None:
                urls.append((ChapterRef("cover", "Bìa tập", nd.novel.url), v.cover_url))
            for ref, u in urls:
                err = self._fetch_image(job, source, http, nd, u, ref.url)
                job.images_ok += err is None
                job.images_failed += err is not None
            job.done += sum(1 for ref in v.chapters if nd.has_chapter(ref.id))
            self._export(job, nd, v, job.options.formats)
