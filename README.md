# Crawl Hako

Công cụ tải truyện từ [docln.sbs](https://docln.sbs) và xuất ra file **EPUB**, **DOCX**, **PDF**, hoặc **thư mục ảnh** hỗ trợ tiếng Việt đầy đủ.

---

## Tính năng

- Tải truyện theo URL hoặc quét danh sách nhiều trang
- Xuất **EPUB** (mặc định, đọc trên Kindle, máy đọc sách, app đọc)
- Xuất **DOCX** (Word, chỉnh sửa được)
- Xuất **PDF** (font tiếng Việt Noto Serif, tự tải nếu thiếu)
- Xuất **Images** — extract toàn bộ ảnh minh họa theo tập ra thư mục
- Tải ảnh minh họa nhúng vào file (bypass Cloudflare CDN tự động)
- **Tải song song** — 3 chương + 5 ảnh/chương cùng lúc (~4–5x nhanh hơn)
- **Adaptive concurrency** — tự giảm số luồng khi bị rate-limit 429
- **Chapter-level resume** — chỉ tải lại chương thất bại, bỏ qua chương đã xong
- **Chapter content cache** — lưu nội dung chương xuống disk, re-run không cần fetch lại HTML
- **Retry loop với backoff** — tự động thử lại chương lỗi trước khi build file
- Tên folder tự động có tag `[Truyện dịch]` hoặc `[AI dịch]`
- Chia folder theo tình trạng: `Truyện đã hoàn thành` / `Truyện chưa hoàn thành`
- Ước tính dung lượng output trước khi crawl
- Chọn tập cụ thể (`--volumes 1,3-5`)
- Per-novel `crawl_log.txt` ghi lại toàn bộ lỗi
- Cấu hình domain linh hoạt (khi site đổi domain)
- Lưu cài đặt tự động vào `crawl_config.json`
- Menu UI tương tác (arrow-key) hoặc CLI truyền thống

---

## Yêu cầu

- Python **3.10+**
- Cài dependencies:

```bash
py -m pip install -r requirements.txt
playwright install chromium
```

> Windows: nếu lệnh `python` không nhận, dùng `py` thay thế.

---

## Khởi chạy

### Menu UI (khuyến nghị)

```bash
py ui.py
```

Hiện menu chọn chế độ bằng phím mũi tên:

```
╭────────── Crawl Hako ──────────╮
│  Domain  docln.sbs              │
│  Output  D:\Truyen              │
│  Format  EPUB                   │
│  Delay   1.5s                   │
│  Folder  Split HT/CHT           │
╰─────────────────────────────────╯

? Chọn chế độ:
  ❯ 🔗  Crawl 1 truyện (URL)
    📄  Crawl danh sách (nhiều trang)
    ⚙️   Cài đặt
    ────
    ❌  Thoát
```

### CLI

```bash
# Crawl 1 truyện, xuất EPUB (mặc định)
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen

# Chọn format
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --format epub docx pdf images

# Chỉ tải tập 1, 3, 4, 5
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --volumes "1,3-5"

# Chỉ định thư mục lưu
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --output "D:\Truyen"

# Crawl nhiều truyện từ trang danh sách (trang 1 đến 5)
py crawler.py --page 1 --page-end 5

# Crawl danh sách đến hết
py crawler.py --page 1 --page-end auto
```

---

## Tham số CLI

| Tham số | Mặc định | Mô tả |
|---------|---------|-------|
| `--url` | — | URL trang truyện cụ thể |
| `--page` | — | Trang bắt đầu trong `/danh-sach` |
| `--page-end` | `auto` | Trang kết thúc (số hoặc `auto`) |
| `--format` | `epub` | Format output: `epub` `docx` `pdf` `images` (chọn nhiều) |
| `--volumes` | tất cả | Chọn tập: `1,3-5,7` hoặc `all` |
| `--delay` | `1.5` | Delay giữa request (giây) |
| `--output` | `./output` | Thư mục lưu file |
| `--domain` | `docln.sbs` | Domain site (khi site đổi domain mới) |

---

## Cấu trúc thư mục output

### Chế độ Single (1 folder chung)

```
output/
└── [Truyện dịch] - Tên Truyện/
    ├── EPUB/
    │   ├── [Tập 1] Tên Truyện.epub
    │   └── [Tập 2] Tên Truyện.epub
    ├── DOCX/
    │   └── [Tập 1] Tên Truyện.docx
    ├── PDF/
    │   └── [Tập 1] Tên Truyện.pdf
    ├── IMAGES/
    │   └── [Tập 1] Tên Truyện/
    │       ├── 000_cover.jpg
    │       └── 001.jpg
    ├── chapters_cache/     ← cache nội dung chương (resume)
    │   ├── 0.json
    │   └── 1.json
    ├── cover.jpg
    ├── info.json
    ├── index.json          ← trạng thái từng chương (done/error)
    └── crawl_log.txt
```

### Chế độ Split (chia theo tình trạng)

```
output/
├── Truyện đã hoàn thành/
│   └── [Truyện dịch] - Tên Truyện/
│       └── ...
└── Truyện chưa hoàn thành/
    └── [AI dịch] - Tên Truyện 2/
        └── ...
```

**Tag tên folder:**
- `[Truyện dịch]` — bản dịch do người dịch
- `[AI dịch]` — bản dịch máy (Machine Translation)

---

## Cài đặt (`crawl_config.json`)

Sau lần chạy đầu tiên, cài đặt được lưu tự động:

```json
{
  "output": "D:\\Truyen",
  "delay": 1.5,
  "format": ["epub"],
  "domain": "docln.sbs",
  "workers": {
    "chapters": 3,
    "images": 5
  },
  "split_mode": false
}
```

| Key | Mô tả |
|-----|-------|
| `output` | Thư mục lưu file |
| `delay` | Giây chờ giữa các request |
| `format` | Danh sách format mặc định |
| `domain` | Domain site |
| `workers.chapters` | Số chương tải song song (mặc định 3, tối đa 10) |
| `workers.images` | Số ảnh tải song song mỗi chương (mặc định 5, tối đa 20) |
| `split_mode` | `true` = chia folder HT/CHT, `false` = 1 folder chung |

Chỉnh sửa file này hoặc dùng menu **Cài đặt** trong `ui.py`.

---

## Xử lý 429 / Rate Limit

- **Global throttle**: khi 1 thread nhận 429, toàn bộ thread còn lại tự chờ theo `Retry-After`
- **Adaptive workers**: nếu 429 liên tiếp ≥ 2 lần → tự giảm số luồng xuống còn một nửa
- **Retry trước build**: sau khi fetch xong, tự retry chương lỗi (60s → 120s → 240s backoff) trước khi xuất file
- **Re-run thông minh**: nếu volume có chương lỗi → tự rebuild lại file thay vì bỏ qua

---

## Xử lý Cloudflare

Ảnh CDN (`i.hako.vip`, `i2.hako.vip`) được bảo vệ bởi Cloudflare. Tool dùng 3 tầng fallback:

1. **cloudscraper** — bypass CF JS challenge tự động
2. **httpx HTTP/2** — fallback nếu cloudscraper thất bại
3. **Playwright (Chromium)** — browser thật, capture ảnh qua `page.on("response")` trong lúc navigate chapter page; inject `cf_clearance` cookie vào scraper cho các request tiếp theo

---

## Tốc độ tải

Với cấu hình mặc định (3 chương song song, 5 ảnh/chương):

| Truyện | Trước | Sau | Nhanh hơn |
|--------|-------|-----|-----------|
| 30 chương, avg 3 ảnh | ~2.5 phút | ~31s | **~5x** |
| Vol minh họa nặng (12 chương, 15 ảnh) | ~3 phút | ~20s | **~9x** |
| 50 chương, avg 4 ảnh | ~5 phút | ~53s | **~5x** |

> Thời gian thực tế phụ thuộc băng thông. Nếu bị site rate-limit, tool tự giảm workers.

---

## Đổi domain

Khi site chuyển sang domain mới:

**Qua menu:** `ui.py` → Cài đặt → nhập domain mới.

**Qua CLI:**
```bash
py crawler.py --url https://domain-moi.com/truyen/123 --domain domain-moi.com
```

---

## Cấu trúc code

| File | Vai trò |
|------|---------|
| `ui.py` | Menu UI tương tác (questionary + rich) |
| `crawler.py` | Orchestrator chính, CLI entry point, ThreadPoolExecutor |
| `fetcher.py` | HTTP client thread-safe (cloudscraper + httpx + Playwright), global 429 throttle |
| `parser.py` | HTML parser — trích xuất nội dung, translator/translation_type, XOR decrypt |
| `storage.py` | Quản lý file I/O, index resume, chapter cache, path helpers |
| `epub_builder.py` | Xuất EPUB |
| `docx_builder.py` | Xuất DOCX |
| `pdf_builder.py` | Xuất PDF (Noto Serif, tự tải font) |
| `images_builder.py` | Xuất thư mục ảnh + manifest.txt |
