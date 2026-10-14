# GIF Pet

Desktop pet hiển thị GIF nền trong suốt, viết bằng Python + PyQt5.
Chạy được trên Linux, Windows và macOS.

## Tính năng

**Hiển thị GIF**
- Tự tìm GIF khi mở app: ưu tiên GIF đã chọn → GIF hợp lệ khác trong thư viện → GIF mặc định.
  Pet không bao giờ thành cửa sổ trống.
- Bỏ qua file GIF hỏng hoặc đã bị di chuyển, không chọn trúng chúng mỗi chu kỳ đổi GIF.
- Nhân vật là một thư mục trong `pets/` gồm GIF theo trạng thái và `pet.json`.
  Thiếu trạng thái nào thì dùng `idle.gif` thay thế, nên vẫn import được bộ pet
  chưa hoàn chỉnh.
- Đổi GIF không thiết lập lại cửa sổ hay nhảy về vị trí cũ.
- Thư viện GIF: xem thumbnail, thêm, xóa, chọn một GIF cụ thể.

**Kích thước và vị trí**
- Resize luôn giữ tỉ lệ khung hình; có thể căn theo chiều rộng hoặc chiều cao.
- Tọa độ được kiểm tra khi mở app: nếu nằm ngoài mọi màn hình (rút màn hình phụ,
  đổi độ phân giải) thì pet tự về giữa màn hình chính.
- Mục “Đưa về giữa màn hình” trong menu.

**Hành vi (Giai đoạn 3)**
- Pet có 7 trạng thái: `idle`, `walk`, `drag`, `fall`, `sleep`, `react`, `talk`.
- Mở app là pet tự đi rồi nghỉ, sau một thời gian không tương tác thì ngủ.
- Kéo pet thì pet vùng vẫy; thả giữa không trung thì pet rơi và tiếp đất.
- Bấm (không kéo) thì pet phản ứng.
- Đi tới cạnh màn hình thì quay đầu, không đi mất.
- **Chế độ tập trung**: pet đứng yên hoặc ngủ, không tự đi lại.
- Tốc độ tự đi, tần suất nghỉ và thời gian ngủ chỉnh được trong Cài đặt.

**Nhắc tập trung / nghỉ (Pomodoro)**
- Bật trong menu khay hoặc Cài đặt. Mặc định 25 phút tập trung, 5 phút nghỉ.
- Hết giờ tập trung pet nhắc: uống nước, đứng dậy vận động, thư giãn mắt.
- Trong giờ tập trung pet **đứng yên**; sang giờ nghỉ thì đi lại bình thường.
- Lời nhắc hiện trong bong bóng thoại trên đầu pet và/hoặc thông báo khay.
- Có nút tạm dừng, chạy tiếp, bỏ qua pha, và "Nhắc uống nước ngay".

**Khay hệ thống**
Menu khay gồm: hiện/ẩn pet, tạm dừng animation, tự động đổi GIF, pet tự đi,
chế độ tập trung, cho pet ngủ ngay, nhắc tập trung/nghỉ (Pomodoro),
click xuyên qua pet, ẩn khi fullscreen,
luôn nổi trên cùng, thư viện GIF, chỉnh kích thước, đưa về giữa màn hình,
cài đặt và thoát.

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
./run.sh --accept     # kiểm tra từng tiêu chí nghiệm thu
./run.sh --headless   # khởi động không màn hình, để kiểm tra code
```

Thủ công:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m gifpet
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m gifpet
```

## Phát triển

Cấu trúc:

| Đường dẫn | Vai trò |
|---|---|
| `gifpet/__main__.py` | Điểm khởi động (`python -m gifpet`) |
| `gifpet/core/config.py` | Cấu hình người dùng, validate, ghi atomic |
| `gifpet/core/paths.py` | Mọi đường dẫn gốc, tập trung một chỗ |
| `gifpet/core/gif_library.py` | Chọn GIF hợp lệ, tính kích thước giữ tỉ lệ |
| `gifpet/core/pet_pack.py` | Đọc nhân vật, fallback khi thiếu trạng thái |
| `gifpet/core/screen_utils.py` | Giữ pet trong phạm vi màn hình |
| `gifpet/core/state.py` | Máy trạng thái 7 trạng thái |
| `gifpet/core/behavior.py` | Điều phối tự đi / nghỉ / ngủ |
| `gifpet/core/falling.py` | Mô phỏng rơi và tiếp đất |
| `gifpet/core/pomodoro.py` | Nhắc tập trung / nghỉ |
| `gifpet/ui/speech_bubble.py` | Bong bóng thoại của pet |
| `gifpet/ui/pet_window.py` | Cửa sổ pet, menu khay, phím tắt |
| `gifpet/ui/dialogs.py` | Dialog resize và cài đặt |
| `gifpet/ui/gif_library_dialog.py` | Dialog thư viện GIF có thumbnail |
| `pets/<tên>/pet.json` | Mô tả nhân vật: kích thước, tốc độ, tính cách |
| `tests/test_core.py` | 83 test đơn vị |
| `tests/test_pomodoro.py` | 32 test nhắc tập trung / nghỉ |
| `tests/test_acceptance.py` | 17 tiêu chí nghiệm thu |
| `tests/test_phase3_flow.py` | 16 bước vòng đời Giai đoạn 3 |
| `tools/make_state_animations.py` | Sinh animation trạng thái còn thiếu |
| `docs/ARCHITECTURE.md` | Kiến trúc và vị trí code từng giai đoạn |

Chạy test:

```bash
./run.sh --test      # tất cả test đơn vị (83 + 32)
./run.sh --accept    # 17 tiêu chí nghiệm thu
./run.sh --phase3    # 16 bước vòng đời Giai đoạn 3
# hoặc
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_core.py
```

Xem `docs/ARCHITECTURE.md` để biết cấu trúc thư mục đầy đủ và vị trí code
của từng giai đoạn.

Test dùng `QT_QPA_PLATFORM=offscreen` nên chạy được trên máy chủ không có màn hình.
Test cũng tự dùng thư mục tạm cho cấu hình, không ghi vào cấu hình thật của bạn.
