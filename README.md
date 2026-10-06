# lnget (crawl-hako v2) — bản beta

> [!WARNING]
> **Đây là bản beta (2.0.0-beta) nằm ở nhánh `rewrite-v2`.** Code được viết lại hoàn toàn so với bản cũ trên `main`.
>
> **Đã chạy thử:** tải truyện Hako ra EPUB / DOCX / PDF / ảnh, tiếp tục tải sau khi dừng, giao diện web, menu, CLI, `setup.bat`.
> **Chưa kiểm chứng:** đăng nhập Hako (bằng trình duyệt và bằng mật khẩu) với tài khoản thật, và truyện/chương bị khoá vì chưa đăng nhập.
>
> **Lấy bản beta:** trên GitHub chọn nhánh **`rewrite-v2`** (nút chọn branch phía trên danh sách file) → **`<> Code` → Download ZIP**, rồi làm theo phần [Cài đặt](#cài-đặt-windows-không-cần-biết-lập-trình). Hoặc: `git clone -b rewrite-v2 https://github.com/minh1904/crawl-hako.git`.
>
> **Báo lỗi:** mở [Issue](https://github.com/minh1904/crawl-hako/issues), gửi kèm link truyện và file `lnget.log` trong thư mục truyện. Đặc biệt cần: link truyện/chương **phải đăng nhập mới xem được**, và đăng nhập có hiện đúng tên tài khoản không.
>
> Muốn dùng bản cũ ổn định: dùng nhánh `main`.

Tải light novel từ **Hako / Cổng Light Novel** ([docln.sbs](https://docln.sbs)) ra **EPUB**, **DOCX**, **PDF** hoặc **thư mục ảnh minh hoạ**, kèm ảnh bìa và ảnh trong chương.

Có 3 cách dùng, cùng một bộ máy bên dưới:

| Cách dùng | Hợp với | Mở bằng |
|---|---|---|
| **Giao diện web** (khuyên dùng) | Mọi người | bấm đúp `lnget-ui.bat`, hoặc `lnget ui` |
| **Menu trong cửa sổ lệnh** | Thích dùng phím mũi tên | bấm đúp `lnget.bat`, hoặc `lnget` |
| **Dòng lệnh (CLI)** | Tải hàng loạt, chạy tự động | `lnget get <link>` … |

> **Hako đổi chính sách (2026):** một số truyện và ảnh chỉ xem được khi đã đăng nhập. lnget hỗ trợ đăng nhập (bằng trình duyệt hoặc tài khoản/mật khẩu) và chỉ lưu *phiên đăng nhập* trên máy bạn, không lưu mật khẩu. Truyện mở công khai vẫn tải được mà không cần đăng nhập.

---

## Cài đặt (Windows, không cần biết lập trình)

Chỉ làm 1 lần.

1. **Cài Python 3.10 trở lên** từ <https://www.python.org/downloads/>.
   Khi cài, **tick ô "Add Python to PATH"** ở dưới cùng rồi bấm *Install Now*.
2. **Tải lnget:** trên trang GitHub này bấm **`<> Code` → Download ZIP**, chuột phải file ZIP → **Extract All…** (ví dụ vào `D:\lnget`).
3. Mở thư mục vừa giải nén, **bấm đúp `setup.bat`**. Chờ đến khi hiện `Xong!` (lần đầu mất 1–3 phút).

Xong. Từ giờ:

- Bấm đúp **`lnget-ui.bat`** → trình duyệt tự mở giao diện lnget.
- Hoặc bấm đúp **`lnget.bat`** → menu trong cửa sổ lệnh.

Để nguyên cửa sổ đen của `lnget-ui.bat` trong lúc dùng; đóng nó là tắt lnget.

<details>
<summary>macOS / Linux / người đã quen Python</summary>

```bash
git clone https://github.com/<bạn>/crawl-hako.git && cd crawl-hako
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[browser]"
lnget ui
```

`[browser]` cài Playwright để đăng nhập bằng trình duyệt. Không cần thì `pip install -e .`.
</details>

---

## Dùng giao diện web

1. **Tải truyện** — dán link truyện (vd `https://docln.sbs/truyen/123-ten-truyen`). Dán xong là tự mở.
2. Hiện ra thông tin truyện và **kệ sách các tập**. Bấm vào bìa để chọn/bỏ tập.
   Mặc định đã chọn sẵn những tập chưa tải đủ; có nút *Chọn tất cả*, *Chỉ tập còn thiếu*, *Bỏ chọn*.
3. Chọn định dạng ở thanh dưới cùng (EPUB / DOCX / PDF / Ảnh) → bấm **Tải N tập**.
4. Theo dõi ở **Hàng đợi**: tạm dừng, tiếp tục, huỷ, thử lại; xong thì bấm biểu tượng thư mục để mở file.
5. **Thư viện** liệt kê truyện đã tải. Bấm vào một truyện để *build thêm định dạng* (không tải lại chương), *tải chương mới* khi truyện ra thêm, hoặc *mở thư mục*.
6. **Tài khoản** — đăng nhập Hako. **Cài đặt** — thư mục lưu, định dạng mặc định, tốc độ, domain.

Trang web chỉ chạy trên máy bạn (`http://127.0.0.1:8765`), máy khác không truy cập được.

---

## Đăng nhập Hako

Cần khi gặp thông báo *"cần đăng nhập"* hoặc ảnh/chương bị thiếu.

**Cách 1 — bằng trình duyệt (khuyên dùng):** *Tài khoản → Đăng nhập bằng trình duyệt* (hoặc `lnget login --browser`).
lnget mở Edge/Chrome ở trang đăng nhập Hako; bạn đăng nhập như bình thường (nên tick *Ghi nhớ*), cửa sổ tự đóng khi xong. Mật khẩu không đi qua lnget.

**Cách 2 — tài khoản + mật khẩu:** nhập trên trang *Tài khoản* (hoặc `lnget login`). lnget gửi một lần tới Hako để lấy phiên đăng nhập, không lưu mật khẩu.

Phiên đăng nhập lưu ở `%APPDATA%\lnget\sessions\` (Windows) hoặc `~/.config/lnget/sessions/`. **Đăng xuất** sẽ xoá file này. Không chia sẻ thư mục đó cho người khác.

---

## Menu trong cửa sổ lệnh

Chạy `lnget` (hoặc bấm đúp `lnget.bat`):

```
📥  Tải truyện (dán link)
📋  Tải nhiều truyện (danh sách link / file)
🔎  Quét trang danh sách Hako
📚  Thư viện — build thêm định dạng, mở thư mục
👤  Tài khoản / đăng nhập
🌐  Mở Web UI trên trình duyệt
⚙️   Cài đặt
```

`↑ ↓` di chuyển, `Enter` chọn, `Space` tick ô, **`← Quay lại`** hoặc `Ctrl+C` để lùi.

---

## Dòng lệnh (CLI)

```bash
lnget get https://docln.sbs/truyen/123-ten-truyen            # tải tất cả tập, định dạng mặc định
lnget get URL -f epub pdf                                     # chọn định dạng
lnget get URL -v 1,3-5                                        # chỉ tập 1, 3, 4, 5  (4- = từ tập 4 đến hết)
lnget get URL1 URL2 --file ds.txt                             # nhiều truyện; file: mỗi dòng 1 link, # để ghi chú
lnget get URL --refetch                                       # tải lại cả chương đã có
lnget info URL                                                # xem danh sách tập, tập nào đã tải
lnget list --pages 1-3                                        # quét /danh-sach trang 1–3 và tải hết
lnget list --url "https://docln.sbs/the-loai/mystery?hoanthanh=1" --pages 1- --dry-run
lnget login --browser | lnget login | lnget logout | lnget whoami
lnget library                                                 # truyện đã tải
lnget rebuild "D:\Truyen\[Truyện dịch] Tên truyện" -f docx    # xuất thêm định dạng, không cần mạng
lnget config                                                  # xem cài đặt
lnget config output="D:\Truyen" formats=epub,pdf delay=1.5
lnget ui --port 9000 --no-browser
```

Link domain cũ (`ln.hako.vn`, `docln.net`) vẫn dùng được — lnget tự đổi sang domain hiện tại.

**Tạm dừng / tiếp tục:** `Ctrl+C` để dừng. Chạy lại đúng lệnh đó, các chương đã tải được bỏ qua.

---

## Thư mục kết quả

```
<thư mục lưu>/
└── [Truyện dịch] Tên truyện/
    ├── EPUB/   Tên truyện - Vol 1.epub
    ├── DOCX/   Tên truyện - Vol 1.docx
    ├── PDF/    Tên truyện - Vol 1.pdf
    ├── IMAGES/ Tên truyện - Vol 1/   000_cover.jpg, 001.jpg, …, manifest.txt
    ├── cover.jpg
    ├── novel.json      thông tin truyện + danh sách tập/chương
    ├── lnget.log       nhật ký: chương lỗi, ảnh lỗi, file đã xuất
    └── .cache/         nội dung chương + ảnh đã tải (để tiếp tục và build lại)
```

- Tag tên thư mục: `[Truyện dịch]`, `[AI dịch]`, `[Sáng tác]`.
- Bật *Chia thư mục theo tình trạng* để tách `Đã hoàn thành/` và `Chưa hoàn thành/`. Khi truyện đổi tên hoặc hoàn thành, lnget tự chuyển thư mục cũ sang chỗ mới.
- Xoá `.cache/` để giải phóng dung lượng; lần sau tải tiếp hoặc build lại sẽ phải tải lại.

---

## Cài đặt

Lưu ở `%APPDATA%\lnget\config.json` (đổi qua trang *Cài đặt*, menu, hoặc `lnget config key=value`).

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `output` | `~/Downloads/lnget` | Thư mục lưu truyện |
| `formats` | `["epub"]` | Định dạng mặc định: `epub` `docx` `pdf` `images` |
| `delay` | `1.0` | Giây chờ giữa 2 request tới trang của site (ảnh trên CDN ngoài tải nhanh hơn) |
| `chapter_workers` | `3` | Số chương tải song song (1–8) |
| `image_workers` | `4` | Số ảnh tải song song (1–16) |
| `split_by_status` | `false` | Chia thư mục Đã/Chưa hoàn thành |
| `keep_image_cache` | `true` | Giữ ảnh đã tải để build lại nhanh |
| `domains` | `{}` | Domain mới khi site đổi, vd `lnget config domain.hako=docln.moi` |

Đặt biến môi trường `LNGET_HOME` để đổi nơi lưu config/session (ví dụ chạy portable từ USB).

---

## Lỗi thường gặp

| Hiện ra | Nguyên nhân / cách sửa |
|---|---|
| `'py' is not recognized` | Python chưa vào PATH → cài lại Python, tick **Add Python to PATH** |
| `Chưa cài đặt. Hãy chạy setup.bat trước.` | Chạy `setup.bat` một lần |
| `Chưa hỗ trợ trang này` | Link không phải Hako, hoặc Hako đổi domain → *Cài đặt → Domain* |
| `… cần đăng nhập Hako` / gợi ý đăng nhập sau khi tải | Đăng nhập rồi tải lại; chỉ phần còn thiếu được tải |
| `Site giới hạn tốc độ (429)` | lnget tự chờ rồi tải tiếp. Hay gặp thì tăng `delay` hoặc giảm số luồng |
| Nhiều ảnh lỗi `404` | Ảnh gốc (thường là link Discord/imgur cũ) đã bị xoá phía nguồn — không tải được; file vẫn xuất với dòng *[Ảnh không tải được]* |
| Không mở được trình duyệt khi đăng nhập | Cài Edge hoặc Chrome, hoặc chạy `.venv\Scripts\playwright install chromium`; hoặc dùng cách đăng nhập bằng mật khẩu |
| PDF lỗi dấu tiếng Việt | Lần đầu xuất PDF cần mạng để tải font Noto Serif vào `%APPDATA%\lnget\fonts` |

Chi tiết lỗi của từng truyện nằm trong `lnget.log` ở thư mục truyện. Chạy CLI với `--debug` để xem log đầy đủ.

---

## Nâng cấp từ bản cũ (crawl-hako v1)

- `py ui.py` → `lnget` (menu) hoặc `lnget ui` (web). `py crawler.py --url X` → `lnget get X`.
- Thư mục truyện tải bằng bản cũ **không dùng tiếp được** (cấu trúc cache khác). Tải lại bằng lnget, hoặc giữ file EPUB/PDF cũ như bình thường.
- `cookies.json` và `crawl_config.json` cũ không còn dùng; hãy xoá `cookies.json` nếu còn.

---

## Dành cho người phát triển

```
lnget/
  sources/        mỗi site 1 file: base.py (interface Source), hako.py
  http.py         HttpClient (curl_cffi giả lập Chrome), throttle theo host, 429, cookie dùng chung
  engine.py       chạy job, phát event; không in gì — CLI / menu / web tự hiển thị
  library.py      thư mục truyện, cache chương theo ID, cache ảnh
  exporters/      epub, docx, pdf, images — cùng chữ ký export(...)
  cli.py tui.py console.py auth.py
  web/server.py   FastAPI + SSE (chỉ 127.0.0.1, yêu cầu header X-Lnget cho request ghi)
  web/static/     giao diện đã build (được commit để người dùng không cần Node)
webui/            mã nguồn giao diện: React + Vite + Tailwind v4 + shadcn/ui
tests/            pytest + HTML mẫu thật của từng site
```

**Chạy test:** `pip install -e ".[dev]"` rồi `pytest`.

**Sửa giao diện web** (cần Node 20+):

```bash
cd webui && npm install
lnget ui --no-browser          # terminal 1: API ở :8765
npm run dev                    # terminal 2: http://localhost:5173 (proxy /api)
npm run build                  # build ra lnget/web/static — nhớ commit thư mục này
```

**Thêm site mới:** tạo `lnget/sources/<site>.py` kế thừa `Source`, cài `fetch_novel()` và `fetch_chapter()` (dùng `_html.extract_elements` để lấy đoạn văn + ảnh), thêm class vào `SOURCE_CLASSES` trong `lnget/sources/__init__.py`, và lưu vài trang HTML thật vào `tests/fixtures/<site>/` để viết test. Site cần đăng nhập thì cài thêm `login()`, `whoami()`, `is_login_cookie()`.

### Lộ trình

- [x] Lõi mới đa site + Hako (đăng nhập, giải mã nội dung, ảnh CDN), CLI, menu, Web UI
- [ ] Valvrare Team (valvrareteam.net)
- [ ] Bản `lnget.exe` portable (không cần cài Python)
- [ ] Extension trình duyệt (gửi phiên đăng nhập sang lnget, tải nhanh từ trang đang đọc)

Dùng cho mục đích đọc cá nhân. Hãy ủng hộ nhóm dịch và tác giả.
