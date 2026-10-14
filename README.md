# GIF Pet

Desktop pet hiển thị GIF nền trong suốt, viết bằng Python + PyQt5.
Chạy được trên Linux, Windows và macOS.

## Tính năng

**Hiển thị GIF**
- Tự tìm GIF khi mở app: ưu tiên GIF đã chọn → GIF hợp lệ khác trong thư viện → GIF mặc định.
  Pet không bao giờ thành cửa sổ trống.
- Bỏ qua file GIF hỏng hoặc đã bị di chuyển, không chọn trúng chúng mỗi chu kỳ đổi GIF.
- Đổi GIF không thiết lập lại cửa sổ hay nhảy về vị trí cũ.
- Thư viện GIF: xem thumbnail, thêm, xóa, chọn một GIF cụ thể.

**Kích thước và vị trí**
- Resize luôn giữ tỉ lệ khung hình; có thể căn theo chiều rộng hoặc chiều cao.
- Tọa độ được kiểm tra khi mở app: nếu nằm ngoài mọi màn hình (rút màn hình phụ,
  đổi độ phân giải) thì pet tự về giữa màn hình chính.
- Mục “Đưa về giữa màn hình” trong menu.

**Khay hệ thống**
Menu khay gồm: hiện/ẩn pet, tạm dừng animation, tự động đổi GIF, pet tự đi,
click xuyên qua pet, ẩn khi fullscreen, luôn nổi trên cùng, thư viện GIF,
chỉnh kích thước, đưa về giữa màn hình, cài đặt và thoát.

**Lưu cấu hình**
- Cấu hình nằm ở thư mục cấu hình của hệ điều hành, **không** trong repo:
  - Linux: `$XDG_CONFIG_HOME/GifAnimation/config.json` (mặc định `~/.config/GifAnimation/`)
  - Windows: `%APPDATA%\GifAnimation\config.json`
  - macOS: `~/Library/Application Support/GifAnimation/config.json`
- Chỉ ghi file khi thả chuột, không ghi trong lúc kéo.
- Ghi kiểu atomic (file tạm rồi thay thế), cấu hình hỏng không làm app crash.

## Phím tắt

Phím tắt luôn hoạt động, kể cả khi đã bật click xuyên qua pet:

| Phím | Tác dụng |
|---|---|
| `Ctrl+Alt+H` | Hiện/ẩn pet |
| `Ctrl+Alt+P` | Tạm dừng / tiếp tục animation |
| `Ctrl+Alt+C` | Đưa pet về giữa màn hình |
| `Ctrl+Alt+Q` | Thoát ứng dụng |

> **Lưu ý về click xuyên:** khi bật, chuột sẽ không bấm được vào pet.
> Đây là lý do menu khay và các phím tắt ở trên luôn được giữ hoạt động.
> Nếu hệ thống không có khay, hãy dùng `Ctrl+Alt+Q` để thoát.

## Yêu cầu

- Python 3.8+
- PyQt5
- Môi trường đồ họa (X11 hoặc Wayland). Đây là app GUI.

Trên Linux, nếu Qt báo thiếu thư viện hệ thống, cài thêm gói runtime:

```bash
sudo apt install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
```

## Chạy

```bash
./run.sh              # tự tạo virtualenv và cài dependency
./run.sh --test       # chạy test (không cần màn hình)
./run.sh --headless   # khởi động không màn hình, để kiểm tra code
```

Thủ công:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Phát triển

Cấu trúc:

| File | Vai trò |
|---|---|
| `main.py` | Điểm khởi động |
| `transparent_window.py` | Cửa sổ pet, menu khay, phím tắt |
| `config.py` | Cấu hình người dùng, validate, ghi atomic |
| `gif_library.py` | Chọn GIF hợp lệ, tính kích thước giữ tỉ lệ |
| `screen_utils.py` | Giữ pet trong phạm vi màn hình |
| `dialogs.py` | Dialog resize và cài đặt |
| `gif_library_dialog.py` | Dialog thư viện GIF có thumbnail |
| `tests/test_pet.py` | Test tự động |

Chạy test:

```bash
./run.sh --test
# hoặc
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_pet.py
```

Test dùng `QT_QPA_PLATFORM=offscreen` nên chạy được trên máy chủ không có màn hình.
Test cũng tự dùng thư mục tạm cho cấu hình, không ghi vào cấu hình thật của bạn.
