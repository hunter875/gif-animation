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

**Trợ lý AI (tuỳ chọn, mặc định tắt)**
- Hỏi pet bằng `Ctrl+Alt+A` hoặc menu khay → "Hỏi pet…".
- Hỗ trợ Groq và Google Gemini. Tự nhập API key trong Cài đặt.
- Pet chỉ được **đề xuất** hành động trong danh sách cố định:
  `say`, `react`, `set_state`, `remind`, `open_url`. Hành động khác bị bỏ.
- Mở URL hoặc hẹn nhắc giờ phải **bạn bấm đồng ý** mới chạy.
- Chỉ `https` được mở; chặn `file://`, `javascript:`, localhost, IP nội bộ.
- Giới hạn lượt/ngày (mặc định 50) và tốc độ (1.5 giây giữa hai lượt).
- Bộ nhớ chỉ chứa điều **bạn tự gõ**, xem và xoá được trong Cài đặt.
- Hết lượt hoặc mất mạng thì pet vẫn chạy bình thường.

API key lưu **tách riêng** khỏi `config.json`:

```bash
export GIFPET_API_KEY="..."   # cách 1: biến môi trường, không ghi ra đĩa
./run.sh
```

Cách 2: nhập trong Cài đặt → lưu vào `secrets.json` (quyền `0600`,
thư mục `0700`). Key **không bao giờ** nằm trong `config.json`.
Chi tiết bảo mật: `docs/SECURITY.md`.

**Thông báo từ chương trình khác (chỉ nhận, chưa có gì để gửi đi)**

Pet đọc một thư mục hộp thư và hiện thông báo do chương trình khác ghi vào,
dưới dạng **chữ thường**: không diễn giải HTML, không bấm được liên kết,
không mở đường dẫn, không chạy lệnh, không gọi model AI.

- Định dạng một thông báo là một tệp JSON. Producer ghi file tạm rồi thay thế
  (`os.replace`) nên pet không bao giờ đọc phải tệp đang ghi dở.
- Hộp thư mặc định: `<thư mục cấu hình>/notifications-inbox`
  (ví dụ Windows: `%APPDATA%\GifAnimation\notifications-inbox`).
  Đổi được trong menu khay → "Cài đặt thông báo…".
- Mặc định kiểm tra mỗi 2 giây. Mỗi vòng đọc có giới hạn và chỉ hiện một
  thông báo, nên hộp thư có nhiều việc dồn lại cũng không làm treo UI.
  Mỗi vòng chỉ xét tối đa 2000 mục trong thư mục; số mục bị bỏ qua được ghi
  vào chẩn đoán của lần quét đó.
- Mỗi thông báo có mức độ (`info`, `success`, `warning`, `error`) và thời
  gian còn hiệu lực (`ttl_seconds`, mặc định 600, tối đa 7 ngày). Thông báo
  hết hạn bị loại khỏi hàng đợi.
- "Tạm im" vẫn nhận vào lịch sử nhưng không hiện bong bóng hay thông báo khay.
  Thông báo đang chờ **không bị xoá** khi tạm im: chúng hiện lại sau khi bỏ
  tạm im, hoặc bị loại khi hết hạn.
- Lịch sử tối đa 200 mục, chỉ lưu chữ; xem ở "Thông báo đã nhận…" và xoá được.
- Pet chỉ **hiển thị**; nó không ghi gì vào hộp thư.

Gửi thử bằng công cụ có sẵn (chỉ cần Python, **không cần PyQt**):

```bash
python tools/notify_pet.py --source build --title "Xong" --message "Đã build xong"
python tools/notify_pet.py --source hermes --title "Việc chạy nền" \
    --message "Tác vụ đã xong" --severity success --ttl 3600
python tools/notify_pet.py --inbox ./inbox --source test --message "Xin chào"
```

- Không truyền `--inbox` thì dùng `notifications_inbox` trong `config.json`
  nếu đã đặt, ngược lại dùng hộp thư mặc định. `--inbox` truyền tay luôn thắng.
- `--source` bắt buộc: chữ thường, số, `.`, `_`, `-`; tối đa 48 ký tự.
- `--title` và `--message`: cần ít nhất một cái, tối đa 2000 ký tự.
- Mã thoát: `0` đã ghi, `2` tham số/dữ liệu sai, `3` không ghi được hộp thư.

Chương trình khác cũng ghi được trực tiếp: đặt một tệp `.json` vào hộp thư
với các khoá `id`, `source`, `title`, `message`, `severity`, `created_at`,
`expires_at` (xem `gifpet/notifications/models.py`). Tên tệp bắt đầu bằng
dấu chấm bị bỏ qua.

> Đây là **phần nhận** của MVP: pet chỉ hiển thị những gì được gửi tới.
> Phần nhận/hiển thị đã qua test; chưa cài hook tự báo hoàn thành cho Hermes.
> Kết quả và giới hạn: [`docs/NOTIFICATIONS-VALIDATION.md`](docs/NOTIFICATIONS-VALIDATION.md).

**Khay hệ thống**
Menu khay gồm: hiện/ẩn pet, tạm dừng animation, tự động đổi GIF, pet tự đi,
chế độ tập trung, cho pet ngủ ngay, nhắc tập trung/nghỉ (Pomodoro),
hỏi pet (AI), bật/tắt nhận thông báo, tạm im, thông báo đã nhận,
cài đặt thông báo, click xuyên qua pet, ẩn khi fullscreen,
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
| `Ctrl+Alt+A` | Hỏi pet (cần bật AI) |
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

## An toàn: không làm treo máy

App này chỉ vẽ một GIF nên rất nhẹ (đo thật: **~60 MB RAM, ~19% CPU một nhân
khi pet di chuyển**). Nhưng vẫn có ba lớp chặn để một lỗi không kéo cả máy xuống:

**1. Giới hạn RAM do `run.sh` đặt (mặc định 700 MB)**

```bash
./run.sh                          # trần 700 MB
GIFPET_MAX_RAM_MB=400 ./run.sh    # chặt hơn
GIFPET_MAX_RAM_MB=0 ./run.sh      # tắt giới hạn
```

Vượt trần thì chỉ tiến trình pet bị kernel dừng, hệ thống không ảnh hưởng.

**2. Lỗi trong vòng lặp không làm chết app**

Mọi timer (đổi GIF, đi lại, rơi, Pomodoro, kiểm tra fullscreen) đều chạy qua một
lớp bọc: lỗi được ghi log rồi bỏ qua, pet chạy tiếp. Nếu cùng một chỗ lỗi hơn
50 lần trong 10 giây thì vòng lặp đó tự dừng để không đốt CPU.

**3. Không rò rỉ bộ nhớ khi đổi GIF**

`QMovie` của Qt **không** giải phóng hết bộ nhớ khi bị huỷ. Tạo mới mỗi lần đổi
GIF làm RAM tăng ~1.3 MB/lần — đổi 600 lần là mất **1.5 GB**. App giữ một cache
theo đường dẫn và tái sử dụng, đo lại 600 lần đổi chỉ tốn 13 MB.
Có test hồi quy khoá lại hành vi này (`tests/test_stability.py`).

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

## Đóng gói thành binary (không cần cài Python)

```bash
./tools/build_binary.sh     # build standalone
./tools/slim_binary.sh      # dọn Qt plugin không dùng
./dist/gifpet.dist/gif-pet  # chạy
```

Kết quả đo trên Ubuntu 24.04:

| | Python trực tiếp | Binary Nuitka |
|---|---|---|
| Cần cài Python | có | **không** |
| Kích thước | 215 MB | **172 MB** |
| RAM | 58 MB | 74 MB |

Đóng gói **không làm app nhẹ đi** — Nuitka kéo theo cả Qt. Lợi ích thật là
không cần cài Python và có thư mục chạy được ngay.

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
| `gifpet/notifications/models.py` | Kiểu dữ liệu thông báo, kiểm tra và giới hạn độ dài |
| `gifpet/notifications/sender.py` | Ghi thông báo vào hộp thư kiểu atomic |
| `gifpet/notifications/inbox.py` | Đọc hộp thư có giới hạn, bỏ qua tệp hỏng |
| `gifpet/notifications/controller.py` | Vòng tick, hàng đợi, hết hạn, chống trùng |
| `gifpet/notifications/state.py` | Lịch sử và cài đặt thông báo (chỉ chữ) |
| `gifpet/ui/notification_panel.py` | Nối thông báo với pet: timer, bong bóng, khay, lịch sử, `NotificationSupportMixin` giữ các phương thức vòng đời/menu chỉ dành cho thông báo mà `PetWindow` kế thừa |
| `tools/notify_pet.py` | CLI gửi thông báo cho pet (không cần PyQt) |
| `tests/test_core.py` | 83 test đơn vị |
| `tests/test_pomodoro.py` | 32 test nhắc tập trung / nghỉ |
| `tests/test_speech_bubble.py` | 14 test bong bóng thoại |
| `tests/test_stability.py` | 10 test chống rò rỉ bộ nhớ / chống treo |
| `tests/test_ui_modules.py` | 25 test module UI đã tách |
| `tests/test_reminders.py` | 26 test lời nhắc bền + pet tự nói |
| `tests/test_security.py` | 19 test khoá ràng buộc bảo mật |
| `tests/test_ai.py` | 64 test cho trợ lý AI (không gọi mạng thật) |
| `tests/test_acceptance.py` | 17 tiêu chí nghiệm thu |
| `tests/test_phase3_flow.py` | 16 bước vòng đời Giai đoạn 3 |
| `tools/make_state_animations.py` | Sinh animation trạng thái còn thiếu |
| `tools/build_binary.sh` | Đóng gói binary bằng Nuitka |
| `tools/slim_binary.sh` | Dọn Qt plugin không dùng |
| [`docs/README.md`](docs/README.md) | **Mục lục tài liệu** — bắt đầu ở đây |
| `docs/ARCHITECTURE.md` | Code tổ chức thế nào, vì sao |
| `docs/MODULES.md` | Từng module làm gì, sửa thì ảnh hưởng gì |
| `docs/SECURITY.md` | Ràng buộc bảo mật (thiết kế) |
| `docs/ROADMAP.md` | Đã xong / chưa làm / không làm |
| `docs/TROUBLESHOOTING.md` | Lỗi đã gặp và cách sửa |
| `docs/BROWSER-AGENT.md` | Thiết kế AI agent dùng trình duyệt (chưa code) |
| `docs/MEMORY.md` | Thiết kế bộ nhớ dài hạn (chưa code) |

Chạy test:

```bash
./run.sh --test      # bộ test đơn vị
./run.sh --accept    # 17 tiêu chí nghiệm thu
./run.sh --phase3    # 16 bước vòng đời Giai đoạn 3
# hoặc
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_core.py
```

Phần thông báo có 140 test mới: Windows 139 đạt, 1 skip; core Linux 92/92 đạt.
Bộ cũ còn 4 lỗi nền trên Windows; xem
[`báo cáo kiểm chứng`](docs/NOTIFICATIONS-VALIDATION.md). Muốn thử tay thì chạy
`python tools/notify_pet.py --source thu --title "Xin chào" --message "Thử"`.

Tài liệu có mục lục riêng: [`docs/README.md`](docs/README.md).
Bảo mật (chống prompt injection, API key, quota, chi phí) ở
`docs/SECURITY.md`; tra cứu module ở `docs/MODULES.md`.

Test dùng `QT_QPA_PLATFORM=offscreen` nên chạy được trên máy chủ không có màn hình.
Test cũng tự dùng thư mục tạm cho cấu hình, không ghi vào cấu hình thật của bạn.
