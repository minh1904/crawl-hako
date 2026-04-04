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
}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Không đọc được config: {e}")
    return {}


def _save_config(output: str, delay: float, fmts: list[str], domain: str = "") -> None:
    data = {
        "output": output,
        "delay": delay,
        "format": fmts,
        "domain": domain or "docln.sbs",
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
    "epub": epub_builder.build_epub,
    "docx": docx_builder.build_docx,
    "pdf": pdf_builder.build_pdf,
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
    novel_dir = _storage.get_novel_dir(output_root, title)
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

            # Kiểm tra: bỏ qua tập nếu TẤT CẢ formats đã có
            missing_fmts = [f for f in fmts if not _storage.volume_file_exists(novel_dir, vol_title, title, f)]
            if not missing_fmts:
                logger.info(f"  ✓ Đã có đủ {len(fmts)} file, bỏ qua tập này.")
                continue

            if len(missing_fmts) < len(fmts):
                logger.info(f"  ↪ Thiếu: {', '.join(missing_fmts)} — sẽ build thêm.")

            # Tải ảnh bìa tập (nếu có)
            vol_cover_bytes = cover_bytes  # fallback: dùng bìa truyện
            vol_cover_url = volume.get("volume_cover_url", "")
            if vol_cover_url:
                tmp = _fetcher.download_image(vol_cover_url, delay=delay)
                if tmp:
                    vol_cover_bytes = tmp

            # Crawl từng chương, thu thập nội dung + ảnh
            chapters_data = []
            image_cache: dict[str, bytes] = {}
            vol_img_ok = 0
            vol_img_fail = 0

            pbar = tqdm(chapters, desc=f"  {vol_title[:35]}", unit="chap",
                        dynamic_ncols=True, leave=True)
            for chap in pbar:
                chap_url = chap["url"]
                chap_title = chap["title"]
                pbar.set_postfix_str(chap_title[:45], refresh=False)

                try:
                    chap_soup = _fetcher.fetch(chap_url, delay=delay)
                    chap_data = _parser.parse_chapter_content(chap_soup)
                    if not chap_data.get("title"):
                        chap_data["title"] = chap_title

                    # Tải ảnh inline
                    img_urls = [
                        e["url"] for e in chap_data.get("elements", [])
                        if e["type"] == "image" and e["url"] not in image_cache
                    ]
                    if img_urls:
                        new_imgs = _fetcher.download_images_batch(
                            img_urls, delay=max(0.3, delay / 3), page_url=chap_url
                        )
                        image_cache.update(new_imgs)
                        failed = [u for u in img_urls if u not in new_imgs]
                        vol_img_ok   += len(new_imgs)
                        vol_img_fail += len(failed)
                        for u in failed:
                            _storage.log(novel_dir, f"  IMG_FAIL [{chap_title}]: {u}")

                    chapters_data.append(chap_data)
                    index[chap_url] = "done"
                    _storage.save_index(novel_dir, index)

                except Exception as e:
                    index[chap_url] = "error"
                    _storage.save_index(novel_dir, index)
                    tqdm.write(f"    ✗ Lỗi chương '{chap_title}': {e}")
                    _storage.log(novel_dir, f"  ERROR: {chap_title} — {e}")
                    chapters_data.append({"title": chap_title, "elements": [
                        {"type": "text", "content": f"[Lỗi tải chương này: {e}]"}
                    ]})

            if vol_img_ok + vol_img_fail > 0:
                _storage.log(novel_dir, f"  Ảnh {vol_title}: OK={vol_img_ok}, FAIL={vol_img_fail}")

            # 7. Build từng format còn thiếu
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


# ─── Crawl theo trang danh sách ──────────────────────────────────────────────

def crawl_listing(page_start: int, page_end, fmts: list[str], output_root: str, delay: float) -> None:
    """Crawl danh sách truyện từ trang /danh-sach theo range trang."""
    auto_mode = (page_end == "auto")
    page = page_start
    total_novels = 0

    while True:
        url = f"{_fetcher.BASE_URL}/danh-sach?page={page}"
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
        """,
    )
    parser.add_argument("--url", help="URL trang truyện cụ thể")
    parser.add_argument("--page", type=int, help="Trang bắt đầu trong /danh-sach")
    parser.add_argument("--page-end", default="auto",
                        help="Trang kết thúc (số hoặc 'auto' để hết). Mặc định: auto")
    parser.add_argument("--format", nargs="+", choices=["epub", "docx", "pdf"], default=["epub"],
                        help="Format output: epub docx pdf (mặc định: epub). Có thể chọn nhiều.")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay giữa các request (giây, mặc định: 1.5)")
    parser.add_argument("--output", default="output",
                        help="Thư mục output (mặc định: ./output)")
    parser.add_argument("--volumes", default=None,
                        help="Chọn tập cụ thể, vd: '1,3-5,7' hoặc 'all' (mặc định: all)")
    parser.add_argument("--domain", default=None,
                        help="Domain site (mặc định: docln.sbs), vd: --domain newsite.com")

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
        crawl_listing(args.page, page_end, fmts, args.output, args.delay)


if __name__ == "__main__":
    main()
