# lnget (crawl-hako v2) — beta

Tải light novel từ **Hako** ([docln.sbs](https://docln.sbs)) ra **EPUB / DOCX / PDF / ảnh**. Có giao diện web, menu trong cửa sổ lệnh và CLI.

> [!WARNING]
> Bản beta, viết lại hoàn toàn. **Đăng nhập Hako chưa được kiểm chứng với tài khoản thật.** Bản cũ ổn định ở nhánh `main`.
> Gặp lỗi? Mở [Issue](https://github.com/minh1904/crawl-hako/issues) kèm link truyện và file `lnget.log` trong thư mục truyện.

## Cài đặt (Windows)

1. Cài [Python 3.10+](https://www.python.org/downloads/), **tick "Add Python to PATH"**.
2. Chọn nhánh **`rewrite-v2`** trên GitHub → **`<> Code` → Download ZIP** → giải nén.
3. Bấm đúp **`setup.bat`**, chờ hiện `Xong!`.

## Sử dụng

- **`lnget-ui.bat`** — mở giao diện web: dán link → bấm bìa chọn tập → chọn định dạng → **Tải**. Giữ cửa sổ đen mở trong lúc dùng.
- **`lnget.bat`** — menu điều khiển bằng phím mũi tên.
- **CLI:**

```bash
lnget get <link> [-f epub pdf] [-v 1,3-5]   # tải truyện, chọn định dạng / tập
lnget get --file ds.txt                       # nhiều truyện, mỗi dòng 1 link
lnget info <link>                             # xem tập nào đã tải
lnget login --browser                         # đăng nhập Hako
lnget rebuild "<thư mục truyện>" -f docx      # xuất thêm định dạng, không tải lại
lnget config output="D:\Truyen"               # đổi thư mục lưu
```

Dừng bằng `Ctrl+C`, chạy lại là tải tiếp — chương đã có được bỏ qua.

## Đăng nhập Hako

Một số truyện/ảnh chỉ tải được khi đã đăng nhập. Vào **Tài khoản → Đăng nhập bằng trình duyệt** (Edge/Chrome mở trang Hako, bạn tự đăng nhập), hoặc nhập tài khoản + mật khẩu. lnget chỉ lưu phiên đăng nhập trên máy, không lưu mật khẩu.

## Lỗi thường gặp

| Lỗi | Cách sửa |
|---|---|
| `'py' is not recognized` | Cài lại Python, tick **Add Python to PATH** |
| `Chưa cài đặt` | Chạy `setup.bat` |
| `Chưa hỗ trợ trang này` | Hako đổi domain → *Cài đặt → Domain* |
| Gợi ý "cần đăng nhập" | Đăng nhập rồi tải lại |
| Ảnh lỗi `404` | Ảnh gốc đã bị xoá phía nguồn, không tải được |

## Phát triển

```bash
pip install -e ".[dev]" && pytest        # Python
cd webui && npm install && npm run build  # giao diện web → lnget/web/static
```

Thêm site mới: tạo `lnget/sources/<site>.py` kế thừa `Source`, đăng ký trong `lnget/sources/__init__.py`.

**Sắp tới:** Valvrare Team · bản `.exe` portable · extension trình duyệt.
