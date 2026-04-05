"""
crawler.py — Entry point chính

Sử dụng:
  python crawler.py --url https://docln.sbs/truyen/123-ten-truyen [--format epub]
  python crawler.py --url https://docln.sbs/truyen/123-ten-truyen --format epub docx pdf
  python crawler.py --page 1 --page-end 50 [--format docx]
  python crawler.py --page 1 --page-end auto [--format epub]
"""
import argparse
import io
import json
import logging
import sys
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Fix Unicode output trên Windows (tránh UnicodeEncodeError với tiếng Việt)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from tqdm import tqdm

import fetcher as _fetcher
import parser as _parser
import storage as _storage
import epub_builder
import docx_builder
import pdf_builder
import images_builder

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── Config file ─────────────────────────────────────────────────────────────

CONFIG_PATH = Path("crawl_config.json")

_CONFIG_DEFAULTS = {
    "output": "output",
    "delay": 1.5,
    "format": ["epub"],
    "workers": {"chapters": 3, "images": 5},
}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Không đọc được config: {e}")
    return {}


def _save_config(output: str, delay: float, fmts: list[str], domain: str = "",
                 workers: dict = None, split_mode: bool = False) -> None:
    data = {
        "output": output,
        "delay": delay,
        "format": fmts,
        "domain": domain or "docln.sbs",
        "workers": workers or _CONFIG_DEFAULTS["workers"],
        "split_mode": split_mode,
    }
    try:
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Không ghi được config: {e}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def parse_volumes_arg(spec: str, total: int) -> set[int]:
    """Chuyển chuỗi '1,3-5,7' thành set 1-based index {1,3,4,5,7}.
    Trả về None nếu spec là 'all' hoặc rỗng (crawl tất cả).
    """
    if not spec or spec.strip().lower() == "all":
        return None
    indices = set()
    for part in re.split(r"[,\s]+", spec.strip()):
        if "-" in part:
            a, _, b = part.partition("-")
            indices.update(range(int(a), int(b) + 1))
        else:
            indices.add(int(part))
    # Lọc ngoài khoảng hợp lệ
    return {i for i in indices if 1 <= i <= total}


# ─── Builder dispatch ─────────────────────────────────────────────────────────

BUILDERS = {
    "epub":   epub_builder.build_epub,
    "docx":   docx_builder.build_docx,
    "pdf":    pdf_builder.build_pdf,
    "images": images_builder.build_images,
}


# ─── Preview: lấy thông tin trước khi crawl ──────────────────────────────────

def fetch_novel_preview(novel_url: str, delay: float) -> tuple[dict, list[dict]]:
    """Fetch trang truyện, trả về (novel_info, volumes) để hiển thị cho user chọn.

    Returns:
        novel_info: dict với title, author, ...
        volumes: list of {volume_title, chapters: [...]}
    """
    soup = _fetcher.fetch(novel_url, delay=delay)
    novel_info = _parser.parse_novel_info(soup)
    volumes = _parser.parse_volume_list(soup)
    return novel_info, volumes


# ─── Size estimation ─────────────────────────────────────────────────────────

_AVG_IMG_BYTES  = 350 * 1024   # ~350 KB mỗi ảnh minh họa LN
_AVG_TEXT_BYTES = 15  * 1024   # ~15 KB text mỗi chương sau nén
_FMT_OVERHEAD   = {"epub": 120 * 1024, "docx": 60 * 1024, "pdf": 200 * 1024, "images": 0}


def estimate_novel_size(
    volumes: list[dict],
    fmts: list[str],
    delay: float,
    progress_cb=None,
) -> dict:
    """Fetch HTML từng chapter để đếm ảnh, ước tính dung lượng output.

    Không tải ảnh — chỉ parse HTML đếm số <img> tag.

    Args:
        volumes:     Danh sách tập đã lọc (từ parse_volume_list).
        fmts:        Danh sách format output cần ước tính.
        delay:       Delay giữa các request.
        progress_cb: Callback(done: int, total: int) để cập nhật progress bar.

    Returns:
        {
            "chapters": int,   tổng số chương
            "images":   int,   tổng số ảnh tìm thấy
            "per_fmt":  dict,  {fmt: bytes ước tính}
            "total":    int,   tổng tất cả formats (bytes)
        }
    """
    total_chaps = sum(len(v.get("chapters", [])) for v in volumes)
    total_imgs  = 0
    done        = 0

    for volume in volumes:
        for chap in volume.get("chapters", []):
            try:
                soup      = _fetcher.fetch(chap["url"], delay=delay)
                chap_data = _parser.parse_chapter_content(soup)
                img_count = sum(1 for e in chap_data.get("elements", []) if e["type"] == "image")
                total_imgs += img_count
            except Exception:
                pass   # bỏ qua chương lỗi, không dừng estimate
            done += 1
            if progress_cb:
                progress_cb(done, total_chaps)

    img_bytes  = total_imgs  * _AVG_IMG_BYTES
    text_bytes = total_chaps * _AVG_TEXT_BYTES

    per_fmt = {}
    for fmt in fmts:
        overhead       = _FMT_OVERHEAD.get(fmt, 60 * 1024)
        per_fmt[fmt]   = img_bytes + text_bytes + overhead

    return {
        "chapters": total_chaps,
        "images":   total_imgs,
        "per_fmt":  per_fmt,
        "total":    sum(per_fmt.values()),
    }


# ─── Per-novel file logging ───────────────────────────────────────────────────

def _setup_novel_log(novel_dir: Path) -> logging.FileHandler:
    """Gắn FileHandler vào root logger, ghi WARNING+ vào crawl.log của truyện."""
    fh = logging.FileHandler(novel_dir / "crawl.log", encoding="utf-8")
    fh.setLevel(logging.WARNING)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger().addHandler(fh)
    return fh


def _teardown_novel_log(fh: logging.FileHandler) -> None:
    logging.getLogger().removeHandler(fh)
    fh.close()


# ─── Chapter worker (chạy trong thread pool) ─────────────────────────────────

def _fetch_chapter(
    chap_idx: int,
    chap: dict,
    delay: float,
    img_workers: int,
) -> tuple:
    """Fetch + parse 1 chương + tải toàn bộ ảnh inline. Thiết kế thread-safe.

    Returns:
        (chap_idx, chap_data, new_imgs, failed_urls, error)
        error là None nếu thành công, Exception nếu thất bại.
    """
    chap_url   = chap["url"]
    chap_title = chap["title"]
    try:
        soup      = _fetcher.fetch(chap_url, delay=delay)
        chap_data = _parser.parse_chapter_content(soup)
        if not chap_data.get("title"):
            chap_data["title"] = chap_title

        img_urls = [
            e["url"] for e in chap_data.get("elements", [])
            if e["type"] == "image"
        ]
        new_imgs: dict[str, bytes] = {}
        failed:   list[str]        = []
        if img_urls:
            new_imgs = _fetcher.download_images_batch(
                img_urls,
                delay=max(0.3, delay / 3),
                page_url=chap_url,
                max_workers=img_workers,
            )
            failed = [u for u in img_urls if u not in new_imgs]

        return chap_idx, chap_data, new_imgs, failed, None
    except Exception as e:
        return chap_idx, None, {}, [], e


# ─── Core: crawl 1 truyện ────────────────────────────────────────────────────

def crawl_novel(novel_url: str, fmts: list[str], output_root: str, delay: float,
                volumes_spec: str | None = None) -> None:
    """Crawl toàn bộ 1 truyện từ URL trang truyện."""
    logger.info(f"▶ Bắt đầu crawl: {novel_url}")

    # 1. Parse thông tin truyện
    soup = _fetcher.fetch(novel_url, delay=delay)
    novel_info = _parser.parse_novel_info(soup)
    title = novel_info.get("title") or "unknown"
    logger.info(f"  Tên truyện: {title}")
    logger.info(f"  Tác giả:   {novel_info.get('author', '?')}")

    # 2. Tạo thư mục output
    split_mode = _load_config().get("split_mode", False)
    novel_dir = _storage.get_novel_dir(output_root, title, novel_info, split_mode)
    _novel_log_fh = _setup_novel_log(novel_dir)
    _storage.log(novel_dir, f"Bắt đầu crawl: {novel_url}")
    _storage.save_info(novel_dir, novel_info)

    try:
        # 3. Tải ảnh bìa
        cover_bytes = None
        cover_url = novel_info.get("cover_url", "")
        if cover_url:
            cover_bytes = _fetcher.download_image(cover_url, delay=delay)
            if cover_bytes:
                _storage.save_cover(novel_dir, cover_bytes)
                logger.info(f"  Đã tải ảnh bìa: {cover_url}")

        # 4. Parse danh sách tập
        volumes = _parser.parse_volume_list(soup)
        if not volumes:
            logger.warning("  Không tìm thấy tập nào. Kiểm tra lại URL.")
            _storage.log(novel_dir, "WARNING: Không tìm thấy tập nào")
            return

        _storage.save_volumes(novel_dir, volumes)
        logger.info(f"  Tổng số tập: {len(volumes)}")
        logger.info(f"  Formats:    {', '.join(fmts)}")

        # 5. Load index (resume)
        index = _storage.load_index(novel_dir)

        # 6. Lọc tập theo --volumes nếu có
        selected = parse_volumes_arg(volumes_spec, len(volumes))
        if selected is not None:
            volumes = [v for i, v in enumerate(volumes, 1) if i in selected]
            logger.info(f"  Crawl tập: {sorted(selected)} ({len(volumes)} tập)")

        # 7. Crawl từng tập
        for vol_num, volume in enumerate(volumes, 1):
            vol_title = volume.get("volume_title") or f"Tập {vol_num}"
            chapters = volume.get("chapters", [])
            logger.info(f"\n  [{vol_num}/{len(volumes)}] {vol_title} — {len(chapters)} chương")

            # Kiểm tra: bỏ qua tập nếu TẤT CẢ formats đã có VÀ không có chương "error"
            missing_fmts = [f for f in fmts if not _storage.volume_file_exists(novel_dir, vol_title, title, f)]
            vol_chapter_urls = {chap["url"] for chap in chapters}
            has_error_chapters = any(
                index.get(url) == "error" for url in vol_chapter_urls
            )
            if not missing_fmts and not has_error_chapters:
                logger.info(f"  ✓ Đã có đủ {len(fmts)} file, bỏ qua tập này.")
                continue
            if not missing_fmts and has_error_chapters:
                # File tồn tại nhưng có chương lỗi → rebuild để vá placeholder
                missing_fmts = fmts
                logger.info(f"  ↻ Có chương lỗi chưa vá — rebuild lại toàn bộ format.")
            elif len(missing_fmts) < len(fmts):
                logger.info(f"  ↪ Thiếu: {', '.join(missing_fmts)} — sẽ build thêm.")

            # Tải ảnh bìa tập (nếu có)
            vol_cover_bytes = cover_bytes  # fallback: dùng bìa truyện
            vol_cover_url = volume.get("volume_cover_url", "")
            if vol_cover_url:
                tmp = _fetcher.download_image(vol_cover_url, delay=delay)
                if tmp:
                    vol_cover_bytes = tmp

            # Crawl từng chương song song, thu thập nội dung + ảnh
            cfg_workers  = _load_config().get("workers", _CONFIG_DEFAULTS["workers"])
            chap_workers = int(cfg_workers.get("chapters", 3))
            img_workers  = int(cfg_workers.get("images",   5))

            # Pre-allocate theo index để giữ đúng thứ tự chương trong sách
            chapters_data: list        = [None] * len(chapters)
            image_cache: dict[str, bytes] = {}
            vol_img_ok   = 0
            vol_img_fail = 0

            _cache_lock = threading.Lock()   # bảo vệ image_cache + counters
            _index_lock = threading.Lock()   # bảo vệ index dict + save_index

            pbar = tqdm(total=len(chapters), desc=f"  {vol_title[:35]}",
                        unit="chap", dynamic_ncols=True, leave=True)

            # ── Chapter-level resume: phân loại done (từ cache) vs cần fetch ──
            to_fetch   = []   # error / chưa có / cache mất → fetch mới
            to_restore = []   # done + có cache trên disk → load lại

            for i, chap in enumerate(chapters):
                if index.get(chap["url"]) == "done":
                    cached = _storage.load_chapter_cache(novel_dir, vol_num, i)
                    if cached is not None:
                        to_restore.append((i, chap, cached))
                        continue
                to_fetch.append((i, chap))

            # Restore chapters từ cache + re-download ảnh cho builder
            if to_restore:
                logger.info(f"  ↩ {len(to_restore)} chương load từ cache, "
                            f"{len(to_fetch)} chương cần fetch.")
                for i, chap, cached_data in to_restore:
                    chapters_data[i] = cached_data
                    img_urls = [e["url"] for e in cached_data.get("elements", [])
                                if e["type"] == "image"]
                    if img_urls:
                        imgs = _fetcher.download_images_batch(
                            img_urls, delay=max(0.3, delay / 3),
                            page_url=chap["url"], max_workers=img_workers,
                        )
                        with _cache_lock:
                            image_cache.update(imgs)

            _consecutive_429 = 0   # đếm 429 liên tiếp để giảm workers động

            pbar.reset(total=len(to_fetch))

            with ThreadPoolExecutor(max_workers=chap_workers) as executor:
                futures = {
                    executor.submit(_fetch_chapter, i, chap, delay, img_workers): i
                    for i, chap in to_fetch
                }
                for fut in as_completed(futures):
                    i          = futures[fut]
                    chap       = chapters[i]
                    chap_url   = chap["url"]
                    chap_title = chap["title"]

                    idx, chap_data, new_imgs, failed, err = fut.result()

                    if err:
                        if "429" in str(err):
                            _consecutive_429 += 1
                            if _consecutive_429 >= 2 and chap_workers > 1:
                                chap_workers = max(1, chap_workers // 2)
                                logger.warning(f"  ⚡ 429 liên tiếp — giảm workers → {chap_workers}")
                        else:
                            _consecutive_429 = 0
                        with _index_lock:
                            index[chap_url] = "error"
                            _storage.save_index(novel_dir, index)
                        tqdm.write(f"    ✗ Lỗi chương '{chap_title}': {err}")
                        _storage.log(novel_dir, f"  ERROR: {chap_title} — {err}")
                        chapters_data[i] = {"title": chap_title, "elements": [
                            {"type": "text", "content": f"[Lỗi tải chương này: {err}]"}
                        ]}
                    else:
                        _consecutive_429 = 0
                        with _cache_lock:
                            for img_url, img_data in new_imgs.items():
                                if img_url not in image_cache:
                                    image_cache[img_url] = img_data
                            vol_img_ok   += len(new_imgs)
                            vol_img_fail += len(failed)
                        for u in failed:
                            _storage.log(novel_dir, f"  IMG_FAIL [{chap_title}]: {u}")
                        with _index_lock:
                            index[chap_url] = "done"
                            _storage.save_index(novel_dir, index)
                        chapters_data[i] = chap_data
                        _storage.save_chapter_cache(novel_dir, vol_num, i, chap_data)

                    pbar.update(1)

            pbar.close()

            if vol_img_ok + vol_img_fail > 0:
                _storage.log(novel_dir, f"  Ảnh {vol_title}: OK={vol_img_ok}, FAIL={vol_img_fail}")

            # 7. Retry các chương lỗi trước khi build (tuần tự + backoff)
            _MAX_CHAP_RETRIES = 3
            _RETRY_BASE_WAIT  = 60  # giây

            error_indices = [
                i for i, chap in enumerate(chapters)
                if index.get(chap["url"]) == "error"
            ]
            for retry_round in range(_MAX_CHAP_RETRIES):
                if not error_indices:
                    break
                wait = _RETRY_BASE_WAIT * (2 ** retry_round)
                logger.info(f"  ↻ Retry {len(error_indices)} chương lỗi "
                            f"(lần {retry_round + 1}/{_MAX_CHAP_RETRIES}) — chờ {wait}s...")
                time.sleep(wait)
                still_error = []
                for i in error_indices:
                    chap = chapters[i]
                    _, chap_data, new_imgs, _, err = _fetch_chapter(i, chap, delay, img_workers)
                    if err:
                        logger.warning(f"    ✗ Retry thất bại: {chap['title']} — {err}")
                        still_error.append(i)
                    else:
                        chapters_data[i] = chap_data        # gán lại vào đúng slot
                        image_cache.update(new_imgs)         # ảnh vào cache cho builder
                        index[chap["url"]] = "done"
                        _storage.save_index(novel_dir, index)
                        logger.info(f"    ✓ Retry thành công: {chap['title']}")
                error_indices = still_error
            if error_indices:
                logger.warning(f"  ⚠ Còn {len(error_indices)} chương lỗi sau {_MAX_CHAP_RETRIES} lần retry — "
                               f"sẽ build với placeholder.")

            # 8. Build từng format còn thiếu
            if not chapters_data:
                logger.warning(f"  Tập '{vol_title}' không có chương nào, bỏ qua build.")
                continue

            for fmt in missing_fmts:
                out_path = _storage.volume_output_path(novel_dir, vol_title, title, fmt)
                builder = BUILDERS[fmt]
                try:
                    builder(out_path, novel_info, vol_title, chapters_data, vol_cover_bytes, image_cache)
                    _storage.log(novel_dir, f"Xuất xong: {out_path.name}")
                    logger.info(f"  ✅ [{fmt.upper()}] {out_path.name}")
                except Exception as e:
                    logger.error(f"  ✗ Lỗi build {fmt.upper()} '{out_path.name}': {e}")
                    _storage.log(novel_dir, f"ERROR build {fmt}: {out_path.name} — {e}")

        logger.info(f"\n✅ Hoàn tất: {title}")
        logger.info(f"   Output: {novel_dir}")
        _storage.log(novel_dir, "=== Hoàn tất ===")

    finally:
        _teardown_novel_log(_novel_log_fh)


# ─── Rebuild format từ folder có sẵn ─────────────────────────────────────────

def rebuild_novel(novel_dir: Path, fmts: list[str], delay: float) -> None:
    """Build thêm format mới từ folder đã crawl, không fetch lại HTML chương.

    - Đọc info.json, cover.jpg, volumes.json từ disk
    - Nếu không có volumes.json → fetch 1 request từ novel URL
    - Với mỗi tập: load chapters_cache → re-download ảnh → build format thiếu
    """
    logger.info(f"▶ Rebuild: {novel_dir.name}")

    # 1. Load metadata
    info_file = novel_dir / "info.json"
    if not info_file.exists():
        raise RuntimeError(f"Không tìm thấy info.json trong {novel_dir}")
    novel_info = json.loads(info_file.read_text(encoding="utf-8"))
    title = novel_info.get("title", "unknown")
    cover_bytes = (novel_dir / "cover.jpg").read_bytes() if (novel_dir / "cover.jpg").exists() else None

    # 2. Load volumes structure (fetch nếu chưa có)
    volumes = _storage.load_volumes(novel_dir)
    if not volumes:
        novel_url = novel_info.get("url", "")
        if not novel_url:
            raise RuntimeError("Không có volumes.json và không có URL trong info.json")
        logger.info("  volumes.json chưa có — fetch từ network...")
        soup = _fetcher.fetch(novel_url, delay=delay)
        volumes = _parser.parse_volume_list(soup)
        _storage.save_volumes(novel_dir, volumes)

    # 3. Build từng tập
    for vol_num, volume in enumerate(volumes, 1):
        vol_title = volume.get("volume_title") or f"Tập {vol_num}"
        chapters  = volume.get("chapters", [])

        missing_fmts = [f for f in fmts
                        if not _storage.volume_file_exists(novel_dir, vol_title, title, f)]
        if not missing_fmts:
            logger.info(f"  ✓ {vol_title} đã có đủ format, bỏ qua.")
            continue

        logger.info(f"  [{vol_num}/{len(volumes)}] {vol_title} — build {', '.join(missing_fmts)}")

        chapters_data: list[dict] = []
        image_cache: dict[str, bytes] = {}

        for i, chap in enumerate(chapters):
            cached = _storage.load_chapter_cache(novel_dir, vol_num, i)
            if cached is None:
                logger.warning(f"    ⚠ Thiếu cache chương {i+1}/{len(chapters)} — dùng placeholder.")
                chapters_data.append({
                    "title": chap.get("title", f"Chương {i+1}"),
                    "elements": [{"type": "text",
                                  "content": "[Chưa có cache — chạy crawl lại để lấy nội dung]"}],
                })
                continue
            chapters_data.append(cached)
            img_urls = [e["url"] for e in cached.get("elements", []) if e["type"] == "image"]
            if img_urls:
                imgs = _fetcher.download_images_batch(
                    img_urls, delay=max(0.3, delay / 3),
                    page_url=chap.get("url", ""), max_workers=5,
                )
                image_cache.update(imgs)

        # Volume cover
        vol_cover_bytes = cover_bytes
        vol_cover_url = volume.get("volume_cover_url", "")
        if vol_cover_url:
            tmp = _fetcher.download_image(vol_cover_url, delay=delay)
            if tmp:
                vol_cover_bytes = tmp

        for fmt in missing_fmts:
            out_path = _storage.volume_output_path(novel_dir, vol_title, title, fmt)
            try:
                BUILDERS[fmt](out_path, novel_info, vol_title, chapters_data,
                              vol_cover_bytes, image_cache)
                logger.info(f"  ✅ [{fmt.upper()}] {out_path.name}")
            except Exception as e:
                logger.error(f"  ✗ Lỗi build {fmt.upper()} '{out_path.name}': {e}")

    logger.info(f"✅ Rebuild xong: {title}")


# ─── Crawl theo trang danh sách ──────────────────────────────────────────────

def _listing_page_url(base: str, page: int) -> str:
    """Ghép ?page=N hoặc &page=N tùy URL base đã có query string chưa."""
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}page={page}"


def crawl_listing(page_start: int, page_end, fmts: list[str], output_root: str, delay: float,
                  list_url: str = "") -> None:
    """Crawl danh sách truyện theo range trang.

    Args:
        list_url: URL base tùy chỉnh (vd: https://docln.sbs/the-loai/mystery?truyendich=1).
                  Nếu để trống sẽ dùng /danh-sach mặc định.
    """
    auto_mode = (page_end == "auto")
    page = page_start
    total_novels = 0
    base = list_url.strip() or f"{_fetcher.BASE_URL}/danh-sach"

    while True:
        url = _listing_page_url(base, page)
        logger.info(f"\n📄 Trang danh sách {page}: {url}")

        try:
            soup = _fetcher.fetch(url, delay=delay)
        except Exception as e:
            logger.error(f"Lỗi fetch trang {page}: {e}")
            break

        novel_urls = _parser.parse_listing_page(soup)
        if not novel_urls:
            logger.info(f"Trang {page} không có truyện → đã hết danh sách.")
            break

        logger.info(f"  Tìm thấy {len(novel_urls)} truyện trên trang {page}")
        total_novels += len(novel_urls)

        for i, nurl in enumerate(novel_urls, 1):
            logger.info(f"\n  [{i}/{len(novel_urls)}] {nurl}")
            try:
                crawl_novel(nurl, fmts, output_root, delay)
            except Exception as e:
                logger.error(f"  ✗ Lỗi crawl truyện {nurl}: {e}")

        if not auto_mode and page >= int(page_end):
            break
        page += 1

    logger.info(f"\n✅ Đã crawl {total_novels} truyện từ {page_start} đến {page - 1}.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Crawler truyện docln.sbs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python crawler.py --url https://docln.sbs/truyen/123-ten-truyen
  python crawler.py --url https://docln.sbs/truyen/123-ten-truyen --format docx
  python crawler.py --url https://docln.sbs/truyen/123-ten-truyen --format epub docx pdf
  python crawler.py --page 1 --page-end 5 --format epub
  python crawler.py --page 1 --page-end auto
  python crawler.py --page 1 --page-end auto --list-url "https://docln.sbs/the-loai/mystery?hoanthanh=1"
        """,
    )
    parser.add_argument("--url", help="URL trang truyện cụ thể")
    parser.add_argument("--page", type=int, help="Trang bắt đầu trong /danh-sach")
    parser.add_argument("--page-end", default="auto",
                        help="Trang kết thúc (số hoặc 'auto' để hết). Mặc định: auto")
    parser.add_argument("--format", nargs="+", choices=["epub", "docx", "pdf", "images"], default=["epub"],
                        help="Format output: epub docx pdf images (mặc định: epub). Có thể chọn nhiều.")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay giữa các request (giây, mặc định: 1.5)")
    parser.add_argument("--output", default="output",
                        help="Thư mục output (mặc định: ./output)")
    parser.add_argument("--volumes", default=None,
                        help="Chọn tập cụ thể, vd: '1,3-5,7' hoặc 'all' (mặc định: all)")
    parser.add_argument("--domain", default=None,
                        help="Domain site (mặc định: docln.sbs), vd: --domain newsite.com")
    parser.add_argument("--list-url", default="",
                        help="URL danh sách tùy chỉnh, vd: https://docln.sbs/the-loai/mystery?hoanthanh=1. "
                             "Phân trang tự thêm &page=N. Mặc định: /danh-sach")

    args = parser.parse_args()

    if not args.url and not args.page:
        parser.print_help()
        sys.exit(1)

    # Load config — CLI args ghi đè lên config
    cfg = _load_config()
    if args.output == "output":
        args.output = cfg.get("output", "output")
    if args.delay == 1.5 and "delay" in cfg:
        args.delay = cfg["delay"]
    if args.format == ["epub"] and "format" in cfg:
        args.format = cfg["format"]
    if args.domain is None:
        args.domain = cfg.get("domain", "docln.sbs")

    # Áp dụng domain
    _fetcher.set_base_url(args.domain)

    # Hỏi địa điểm lưu nếu chưa được chỉ định (cả CLI lẫn config)
    if args.output == "output":
        print("Nhập đường dẫn thư mục lưu file (Enter để dùng mặc định './output'): ", end="", flush=True)
        user_input = input().strip()
        if user_input:
            args.output = user_input

    Path(args.output).mkdir(parents=True, exist_ok=True)
    print(f"Thư mục lưu: {Path(args.output).resolve()}")

    fmts = list(dict.fromkeys(args.format))  # dedup, giữ thứ tự

    # Lưu config hiện tại để dùng lần sau
    _save_config(args.output, args.delay, fmts, args.domain)

    if args.url:
        crawl_novel(args.url, fmts, args.output, args.delay, args.volumes)
    elif args.page:
        page_end = args.page_end
        if page_end != "auto":
            try:
                page_end = int(page_end)
            except ValueError:
                logger.error("--page-end phải là số hoặc 'auto'")
                sys.exit(1)
        crawl_listing(args.page, page_end, fmts, args.output, args.delay, list_url=args.list_url)


if __name__ == "__main__":
    main()
