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
import logging
import sys

# Fix Unicode output trên Windows (tránh UnicodeEncodeError với tiếng Việt)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

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


# ─── Builder dispatch ─────────────────────────────────────────────────────────

BUILDERS = {
    "epub": epub_builder.build_epub,
    "docx": docx_builder.build_docx,
    "pdf": pdf_builder.build_pdf,
}


# ─── Core: crawl 1 truyện ────────────────────────────────────────────────────

def crawl_novel(novel_url: str, fmts: list[str], output_root: str, delay: float) -> None:
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
    _storage.log(novel_dir, f"Bắt đầu crawl: {novel_url}")
    _storage.save_info(novel_dir, novel_info)

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

    # 6. Crawl từng tập
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

        for chap_idx, chap in enumerate(chapters, 1):
            chap_url = chap["url"]
            chap_title = chap["title"]

            try:
                chap_soup = _fetcher.fetch(chap_url, delay=delay)
                chap_data = _parser.parse_chapter_content(chap_soup)
                if not chap_data.get("title"):
                    chap_data["title"] = chap_title

                # Tải ảnh inline
                for elem in chap_data.get("elements", []):
                    if elem["type"] == "image":
                        img_url = elem["url"]
                        if img_url not in image_cache:
                            img_bytes = _fetcher.download_image(img_url, delay=max(0.3, delay / 3))
                            if img_bytes:
                                image_cache[img_url] = img_bytes

                chapters_data.append(chap_data)
                index[chap_url] = "done"
                _storage.save_index(novel_dir, index)
                logger.info(f"    ✓ [{chap_idx}/{len(chapters)}] {chap_title}")

            except Exception as e:
                index[chap_url] = "error"
                _storage.save_index(novel_dir, index)
                logger.error(f"    ✗ Lỗi chương '{chap_title}': {e}")
                _storage.log(novel_dir, f"  ERROR: {chap_title} — {e}")
                chapters_data.append({"title": chap_title, "elements": [
                    {"type": "text", "content": f"[Lỗi tải chương này: {e}]"}
                ]})

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


# ─── Crawl theo trang danh sách ──────────────────────────────────────────────

def crawl_listing(page_start: int, page_end, fmts: list[str], output_root: str, delay: float) -> None:
    """Crawl danh sách truyện từ trang /danh-sach theo range trang."""
    auto_mode = (page_end == "auto")
    page = page_start
    total_novels = 0

    while True:
        url = f"https://docln.sbs/danh-sach?page={page}"
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

    args = parser.parse_args()

    if not args.url and not args.page:
        parser.print_help()
        sys.exit(1)

    # Hỏi địa điểm lưu nếu chưa được chỉ định qua --output
    if args.output == "output":
        print("Nhập đường dẫn thư mục lưu file (Enter để dùng mặc định './output'): ", end="", flush=True)
        user_input = input().strip()
        if user_input:
            args.output = user_input

    Path(args.output).mkdir(parents=True, exist_ok=True)
    print(f"Thư mục lưu: {Path(args.output).resolve()}")

    fmts = list(dict.fromkeys(args.format))  # dedup, giữ thứ tự

    if args.url:
        crawl_novel(args.url, fmts, args.output, args.delay)
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
