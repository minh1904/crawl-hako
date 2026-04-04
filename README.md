# Crawl Hako

Công cụ tải truyện từ [docln.sbs](https://docln.sbs) và xuất ra file **EPUB**, **DOCX**, **PDF** hỗ trợ tiếng Việt đầy đủ.

---

## Tính năng

- Tải truyện theo URL hoặc quét danh sách nhiều trang
- Xuất **EPUB** (đọc trên Kindle, máy đọc sách, app đọc)
- Xuất **DOCX** (Word, chỉnh sửa được)
- Xuất **PDF** (font tiếng Việt Noto Serif, tự tải nếu thiếu)
- Tải ảnh minh họa nhúng vào file
- Resume — tự bỏ qua chương/tập đã tải, tiếp tục khi bị ngắt
- Chọn tập cụ thể (`--volumes 1,3-5`)
- Cấu hình domain linh hoạt (khi site đổi domain)
- Lưu cài đặt tự động vào `crawl_config.json`
- Menu UI tương tác (arrow-key) hoặc CLI truyền thống

---

## Yêu cầu

- Python **3.10+**
- Cài dependencies:

```bash
pip install -r requirements.txt
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
│  Format  EPUB, DOCX             │
│  Delay   1.5s                   │
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
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --format epub docx pdf

# Chỉ tải tập 1, 3, 4, 5
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --volumes "1,3-5"

# Chỉ định thư mục lưu
py crawler.py --url https://docln.sbs/truyen/123-ten-truyen --output "D:\Truyen"

# Crawl nhiều truyện từ trang danh sách (trang 1 đến 5)
py crawler.py --page 1 --page-end 5 --format epub

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
| `--format` | `epub` | Format output: `epub` `docx` `pdf` (chọn nhiều) |
| `--volumes` | tất cả | Chọn tập: `1,3-5,7` hoặc `all` |
| `--delay` | `1.5` | Delay giữa request (giây) |
| `--output` | `./output` | Thư mục lưu file |
| `--domain` | `docln.sbs` | Domain site (khi site đổi domain mới) |

---

## Cấu trúc thư mục output

```
output/
└── Tên Truyện/
    ├── EPUB/
    │   ├── [Tập 1] Tên Truyện.epub
    │   └── [Tập 2] Tên Truyện.epub
    ├── DOCX/
    │   └── [Tập 1] Tên Truyện.docx
    ├── PDF/
    │   └── [Tập 1] Tên Truyện.pdf
    ├── cover.jpg
    ├── info.json
    ├── index.json        ← resume tracking
    └── crawl_log.txt
```

---

## Cài đặt mặc định (`crawl_config.json`)

Sau lần chạy đầu tiên, cài đặt được lưu tự động vào `crawl_config.json`:

```json
{
  "output": "D:\\Truyen",
  "delay": 1.5,
  "format": ["epub", "docx"],
  "domain": "docln.sbs"
}
```

Chỉnh sửa file này hoặc dùng menu **Cài đặt** trong `ui.py` để thay đổi mặc định.

---

## Đổi domain

Khi site chuyển sang domain mới:

**Qua menu:** Mở `ui.py` → Cài đặt → nhập domain mới → Lưu.

**Qua CLI:**
```bash
py crawler.py --url https://domain-moi.com/truyen/123 --domain domain-moi.com
```

Domain mới sẽ được lưu vào `crawl_config.json` cho các lần chạy sau.

---

## Cấu trúc code

| File | Vai trò |
|------|---------|
| `ui.py` | Menu UI tương tác (questionary + rich) |
| `crawler.py` | Orchestrator chính, CLI entry point |
| `fetcher.py` | HTTP client (cloudscraper + httpx fallback) |
| `parser.py` | HTML parser — trích xuất nội dung, XOR decrypt |
| `storage.py` | Quản lý file I/O, index resume |
| `epub_builder.py` | Xuất EPUB |
| `docx_builder.py` | Xuất DOCX |
| `pdf_builder.py` | Xuất PDF (Noto Serif, tự tải font) |
