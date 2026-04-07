# Crawl Hako

Công cụ tải truyện từ [docln.sbs](https://docln.sbs) và xuất ra file **EPUB**, **DOCX**, **PDF**, hoặc **thư mục ảnh** hỗ trợ tiếng Việt đầy đủ.

---

## Hướng dẫn cài đặt từ đầu (dành cho người chưa quen lập trình)

> Làm theo đúng thứ tự. Mỗi bước chỉ cần làm **1 lần duy nhất**.

---

### Bước 1 — Tải và cài Python

1. Mở trình duyệt, vào địa chỉ: **https://www.python.org/downloads/**
2. Bấm nút vàng lớn **"Download Python 3.x.x"** (bản mới nhất).
3. Mở file `.exe` vừa tải về (thường nằm ở thư mục `Downloads`).
4. **⚠️ Rất quan trọng:** Trước khi bấm Install, nhìn xuống dưới cùng của cửa sổ cài đặt, tích vào ô:
   > ☑ **Add Python to PATH**

   Nếu không tick ô này, các bước sau sẽ báo lỗi.

5. Bấm **"Install Now"** và chờ cài xong.
6. Mỗi khi terminal mở lên, đọc và gõ "y" để đồng ý cài từng phần đến khi nào xong là được
7. Bấm **Close** khi xong.

**Kiểm tra Python đã cài thành công chưa:**

- Bấm phím `Windows` → gõ `cmd` → bấm Enter để mở **Command Prompt** (cửa sổ đen).
- Gõ lệnh sau rồi bấm Enter:

  ```
  py --version
  ```

- Nếu hiện ra ví dụ `Python 3.12.4` → **thành công**, tiếp tục bước 2.
- Nếu hiện lỗi `'py' is not recognized` → cài lại Python và nhớ tick ô **Add Python to PATH**.

---

### Bước 2 — Tải công cụ về máy

1. Quay lại trang GitHub này, bấm nút **`<> Code`** (màu xanh lá) ở góc trên phải.
2. Chọn **"Download ZIP"**.
3. File `crawl-hako-main.zip` sẽ được tải về thư mục `Downloads`.
4. Chuột phải vào file ZIP → chọn **"Extract All..."** → chọn nơi muốn lưu, ví dụ `D:\` → bấm **Extract**.
5. Sau khi giải nén sẽ có thư mục `crawl-hako` (hoặc tên tương tự) chứa các file của tool.

---

### Bước 3 — Mở Command Prompt đúng vị trí

Cần mở cửa sổ lệnh **trỏ vào đúng thư mục** vừa giải nén.

**Cách nhanh nhất:**
1. Mở thư mục `crawl-hako` trong File Explorer.
2. Bấm vào **thanh địa chỉ** (chỗ hiện đường dẫn ở trên cùng) để nó được bôi đen.
3. Gõ `cmd` rồi bấm **Enter**.
4. Cửa sổ đen (Command Prompt) sẽ mở và đã trỏ sẵn vào đúng thư mục.

---

### Bước 4 — Cài các thư viện cần thiết

Trong cửa sổ cmd vừa mở, gõ lệnh sau rồi bấm **Enter**:

```
py -m pip install -r requirements.txt
```

Chờ cho đến khi hiện `Successfully installed ...` — có thể mất **2–5 phút** tùy tốc độ mạng. Trong lúc chờ không cần làm gì cả.

---

### Bước 5 — Cài thêm trình duyệt tự động (Playwright)

Tiếp tục gõ lệnh sau trong cùng cửa sổ cmd, bấm **Enter**:

```
playwright install chromium
```

Tool sẽ tự tải về một bản Chrome riêng (~150 MB) để dùng khi cần. Chờ cho đến khi hiện `Chromium ... downloaded` là xong. **Chỉ cần làm 1 lần.**

---

### Bước 6 — Chạy tool

Gõ lệnh sau rồi bấm **Enter**:

```
py ui.py
```

Một menu sẽ hiện lên trong cửa sổ cmd:

```
? Chọn chế độ:
  ❯ 🔗  Crawl 1 truyện (URL)
    📋  Crawl nhiều URL (danh sách)
    ...
```

Dùng phím **↑ ↓** để di chuyển, **Enter** để chọn.

---

### Lỗi thường gặp

| Hiện ra gì | Nguyên nhân | Cách sửa |
|-----------|------------|---------|
| `'py' is not recognized` | Python chưa vào PATH | Gỡ cài đặt Python, cài lại, nhớ tick **Add Python to PATH** |
| `No module named 'xxx'` | Chưa cài thư viện | Chạy lại `py -m pip install -r requirements.txt` |
| `playwright: command not found` | Playwright chưa cài | Chạy `py -m pip install playwright` rồi `playwright install chromium` |
| Cài rất chậm hoặc bị treo | Mạng chậm hoặc tường lửa | Thử dùng mạng khác hoặc tắt VPN |
| `Permission denied` | Không có quyền ghi file | Chuột phải vào `cmd` → **Run as administrator** |

---

## Bắt đầu nhanh (dành cho người mới)

**Bước 1 — Cài đặt:**
```bash
py -m pip install -r requirements.txt
playwright install chromium
```

**Bước 2 — Chạy menu:**
```bash
py ui.py
```

**Bước 3 — Tải truyện:**
- Chọn `🔗 Crawl 1 truyện (URL)` → dán link truyện → chọn tập → Enter
- File EPUB sẽ xuất ra thư mục `./output/`

> **Không biết dùng CLI?** Dùng menu `ui.py` — điều hướng bằng phím mũi tên, **ESC** hoặc chọn `← Quay lại` để về menu trước.

---

## Tính năng

- Tải truyện theo URL hoặc quét danh sách nhiều trang
- **Tải nhiều truyện** từ danh sách URL (nhập tay, file `.txt`, hoặc link file online)
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
- **Rebuild format từ folder có sẵn** — scan folder, chọn truyện, build thêm format mới không cần crawl lại
- **Dán lệnh CLI vào menu** — chạy lệnh CLI trực tiếp từ giao diện menu
- Tên folder tự động có tag `[Truyện dịch]` hoặc `[AI dịch]`
- Chia folder theo tình trạng: `Truyện đã hoàn thành` / `Truyện chưa hoàn thành`
- Ước tính dung lượng output trước khi crawl
- Chọn tập cụ thể (`--volumes 1,3-5`)
- Per-novel `crawl_log.txt` ghi lại toàn bộ lỗi
- Cấu hình domain linh hoạt (khi site đổi domain)
- Lưu cài đặt tự động vào `crawl_config.json`
- Menu UI tương tác (arrow-key) với nút **← Quay lại** và thông báo **tạm dừng**

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
│  Folder  Single                 │
╰─────────────────────────────────╯

? Chọn chế độ:
  ❯ 🔗  Crawl 1 truyện (URL)
    📋  Crawl nhiều URL (danh sách)
    📄  Crawl danh sách (nhiều trang)
    🔄  Build lại format từ folder có sẵn
    ⌨️   Chạy từ lệnh CLI
    ⚙️   Cài đặt
    ────
    ❌  Thoát
```

**Điều hướng:**
- `↑ ↓` — di chuyển
- `Enter` — chọn
- `ESC` hoặc chọn `← Quay lại` — về menu trước
- `Ctrl+C` trong lúc crawl — tạm dừng (tiến trình tự lưu, chạy lại để tiếp tục)

#### Tải 1 truyện

1. Chọn `🔗 Crawl 1 truyện (URL)`
2. Dán link truyện (vd: `https://docln.sbs/truyen/123-ten-truyen`)
3. Chọn tập muốn tải (Space bỏ chọn, Enter xác nhận)
4. Chọn format, thư mục lưu
5. Chọn `▶ Bắt đầu crawl`

#### Tải nhiều truyện (danh sách URL)

1. Chọn `📋 Crawl nhiều URL (danh sách)`
2. Chọn cách nhập:
   - **Nhập tay** — gõ/dán từng URL, Enter sau mỗi URL, dòng trống để kết thúc
   - **File local** — nhập đường dẫn file `.txt` (mỗi dòng 1 URL, `#` để comment)
   - **Link online** — dán link tới file `.txt` trên mạng (GitHub raw, Pastebin...)
3. Chọn format, xác nhận → crawl tuần tự từng truyện

Ví dụ file `urls.txt`:
```
# Truyện yêu thích
https://docln.sbs/truyen/123-truyen-a
https://docln.sbs/truyen/456-truyen-b

# Đang theo dõi
https://docln.sbs/truyen/789-truyen-c
```

#### Dán lệnh CLI vào menu

1. Chọn `⌨️ Chạy từ lệnh CLI`
2. Dán lệnh vào (phần `py crawler.py` có thể bỏ hoặc giữ)
3. Xác nhận → chạy

---

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

# Crawl nhiều URL cùng lúc (space-separated)
py crawler.py --urls https://docln.sbs/truyen/123 https://docln.sbs/truyen/456

# Crawl từ file danh sách URL (local)
py crawler.py --url-file urls.txt

# Crawl từ file danh sách URL (link online)
py crawler.py --url-file "https://raw.githubusercontent.com/user/repo/main/urls.txt"

# Crawl danh sách trang 1–5
py crawler.py --page 1 --page-end 5

# Crawl danh sách đến hết
py crawler.py --page 1 --page-end auto

# Crawl theo thể loại/lọc
py crawler.py --page 1 --page-end auto --list-url "https://docln.sbs/the-loai/mystery?hoanthanh=1"
```

---

## Tham số CLI

| Tham số | Mặc định | Mô tả |
|---------|---------|-------|
| `--url` | — | URL trang truyện cụ thể |
| `--urls` | — | Nhiều URL truyện cách nhau bằng dấu cách |
| `--url-file` | — | File `.txt` local hoặc link online chứa danh sách URL (mỗi dòng 1 URL, `#` để comment) |
| `--page` | — | Trang bắt đầu trong `/danh-sach` |
| `--page-end` | `auto` | Trang kết thúc (số hoặc `auto`) |
| `--format` | `epub` | Format output: `epub` `docx` `pdf` `images` (chọn nhiều) |
| `--volumes` | tất cả | Chọn tập: `1,3-5,7` hoặc `all` |
| `--delay` | `1.5` | Delay giữa request (giây) |
| `--output` | `./output` | Thư mục lưu file |
| `--domain` | `docln.sbs` | Domain site (khi site đổi domain mới) |
| `--list-url` | `/danh-sach` | URL danh sách tùy chỉnh (lọc thể loại, tag...) |

---

## Tạm dừng và tiếp tục

Nhấn **Ctrl+C** bất kỳ lúc nào để tạm dừng. Tool sẽ hiện:

```
⏸ Đã tạm dừng!
Tiến trình đã lưu tự động. Chạy lại cùng URL để tiếp tục — các chương đã tải sẽ không tải lại.
```

Chạy lại cùng lệnh/URL là tool sẽ tự bỏ qua chương đã có và tiếp tục từ chỗ dừng.

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
    │   ├── 1_0.json        ← tập 1, chương 0
    │   ├── 1_1.json
    │   └── 2_0.json        ← tập 2, chương 0
    ├── cover.jpg
    ├── info.json
    ├── volumes.json        ← cấu trúc tập/chương (dùng cho rebuild)
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

## Rebuild format từ folder có sẵn

Nếu đã crawl trước đó (có `chapters_cache/`) và muốn build thêm format mới mà không crawl lại:

```
ui.py → 🔄 Build lại format từ folder có sẵn
  → Chọn folder gốc → scan tự động tìm truyện
  → Checkbox chọn truyện (hiển thị format đã có)
  → Chọn format muốn build thêm → Rebuild
```

- Không fetch lại HTML chương — đọc thẳng từ `chapters_cache/`
- Chỉ re-download ảnh (cần nhúng vào file)
- Nếu chưa có `volumes.json`: tự fetch 1 request từ URL trong `info.json` để lấy cấu trúc tập
- Truyện crawl bằng phiên bản cũ (chưa có cache): hiển thị placeholder và nhắc crawl lại

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
