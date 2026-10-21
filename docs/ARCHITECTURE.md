# Kiến trúc GIF Pet

Tài liệu này mô tả cấu trúc thư mục và vị trí sẽ đặt code của từng giai đoạn.

## Cây thư mục

```
gif-animation/
├── gifpet/                     # package chính
│   ├── __init__.py
│   ├── __main__.py             # điểm khởi động: python -m gifpet
│   │
│   ├── core/                   # logic thuần túy, test được không cần màn hình
│   │   ├── config.py           # cấu hình người dùng, ghi atomic, validate
│   │   ├── paths.py            # mọi đường dẫn gốc, tập trung một chỗ
│   │   ├── gif_library.py      # chọn GIF hợp lệ, tính kích thước giữ tỉ lệ
│   │   ├── pet_pack.py         # đọc nhân vật, fallback khi thiếu trạng thái
│   │   ├── screen_utils.py     # giữ pet trong phạm vi màn hình
│   │   ├── state.py            # máy trạng thái 7 trạng thái
│   │   ├── behavior.py         # điều phối tự đi / nghỉ / ngủ
│   │   ├── falling.py          # mô phỏng rơi và tiếp đất
│   │   └── pomodoro.py         # nhắc tập trung / nghỉ (uống nước, nghỉ mắt)
│   │
│   ├── ui/                     # giao diện PyQt5
│   │   ├── pet_window.py       # cửa sổ pet: chuột, phím tắt, phối hợp
│   │   ├── gif_player.py       # QMovie, cache, kích thước, nạp GIF
│   │   ├── window_skin.py      # cờ cửa sổ, click xuyên, fullscreen (X11)
│   │   ├── tray_menu.py        # khay hệ thống, menu, thông báo
│   │   ├── pet_actions.py      # NƠI DUY NHẤT thực thi hành động
│   │   ├── dialogs.py          # dialog resize và cài đặt
│   │   ├── gif_library_dialog.py  # thư viện GIF có thumbnail
│   │   └── speech_bubble.py    # bong bóng thoại của pet
│   │
│   ├── assets/                 # tài nguyên tĩnh
│   │   └── app_icon.ico
│   │
│   ├── ai/                     # (Giai đoạn 4) trợ lý AI — đã triển khai
│   │   ├── actions.py          # whitelist hành động + kiểm tra tham số/URL
│   │   ├── brain.py            # gom sự kiện → gọi model → lọc kết quả
│   │   ├── provider.py         # Groq / Gemini, nơi DUY NHẤT mở kết nối mạng
│   │   ├── quota.py            # đếm lượt/ngày, rate limit
│   │   ├── secrets.py          # API key riêng, quyền 0600
│   │   └── memory.py           # chỉ ghi chú người dùng gõ tay
│   │
│   └── (Giai đoạn 5 giọng nói đã bỏ khỏi phạm vi)
│
├── pets/                       # thư viện nhân vật
│   └── default/
│       ├── pet.json            # mô tả kích thước, tốc độ, tính cách
│       ├── idle.gif
│       ├── walk.gif
│       ├── drag.gif
│       └── sleep.gif
│
├── tests/                      # tổng 273 test đơn vị
│   ├── test_core.py            # 83  logic thuần tuý
│   ├── test_ai.py              # 64  trợ lý AI (provider giả, không gọi mạng)
│   ├── test_pomodoro.py        # 32  nhắc tập trung / nghỉ
│   ├── test_reminders.py       # 26  lời nhắc bền + pet tự nói
│   ├── test_ui_modules.py      # 25  module UI đã tách
│   ├── test_security.py        # 19  khoá ràng buộc bảo mật
│   ├── test_speech_bubble.py   # 14  bong bóng thoại
│   ├── test_stability.py       # 10  chống rò rỉ bộ nhớ / chống treo
│   ├── test_acceptance.py      # 17  tiêu chí nghiệm thu (script)
│   └── test_phase3_flow.py     # 16  bước vòng đời (script)
│
├── tools/
│   ├── make_state_animations.py  # sinh fall/react/talk từ GIF gốc
│   ├── build_binary.sh           # đóng gói binary bằng Nuitka
│   └── slim_binary.sh            # dọn bớt Qt plugin không dùng
│
├── docs/                       # xem docs/README.md để biết đọc file nào
│   ├── README.md               # mục lục
│   ├── ARCHITECTURE.md         # file này
│   ├── MODULES.md              # từng module làm gì, sửa thì vỡ cái gì
│   ├── SECURITY.md             # ràng buộc bảo mật (thiết kế)
│   ├── ROADMAP.md              # đã xong / chưa làm / không làm
│   ├── BROWSER-AGENT.md        # thiết kế agent dùng trình duyệt (CHƯA CODE)
│   ├── MEMORY.md               # thiết kế bộ nhớ dài hạn (CHƯA CODE)
│   └── TROUBLESHOOTING.md      # lỗi đã gặp và cách sửa
│
├── run.sh                      # chạy app / test / nghiệm thu
├── requirements.txt
└── README.md
```

Khi cần biết **một module cụ thể** làm gì và sửa nó ảnh hưởng tới đâu, xem
[`MODULES.md`](MODULES.md).

## Vì sao chia `core/` và `ui/`

`core/` không import PyQt5 (trừ `gif_library` cần Qt để decode GIF). Nhờ vậy phần
lớn logic — máy trạng thái, chọn nhân vật, validate cấu hình, tính tọa độ — test
được mà không cần khởi tạo `QApplication`, và không phụ thuộc môi trường đồ họa.

`ui/` chứa mọi thứ chạm vào Qt widget.

## Nhân vật (pet pack)

Mỗi nhân vật là một thư mục trong `pets/`, gồm các GIF đặt tên theo trạng thái
và một file `pet.json`.

**Thiếu trạng thái nào thì dùng `idle.gif` thay thế.** Nhờ vậy vẫn import được
bộ pet chưa hoàn chỉnh: bộ mẫu hiện có 4 GIF cho `idle`/`walk`/`drag`/`sleep`,
còn `fall`/`react`/`talk` tự động fallback về `idle.gif`.

`pet.json` mô tả:

```json
{
    "display_name": "Mèo mặc định",
    "animations": { "idle": "idle.gif", "walk": "walk.gif" },
    "fallback_animation": "idle.gif",
    "size": { "width": 200, "lock_aspect": true },
    "movement": { "speed_px_per_step": 2, "step_interval_ms": 40 },
    "behavior": { "idle_to_sleep_ms": 120000 },
    "personality": { "tone": "...", "likes": [], "max_reply_chars": 120 }
}
```

File `pet.json` hỏng hoặc thiếu đều không làm app crash — dùng giá trị mặc định,
và vẫn tự nhận các GIF có sẵn trong thư mục.

## Máy trạng thái (Giai đoạn 3) — ĐÃ HOÀN THÀNH

Ba module phối hợp:

| Module | Vai trò |
|---|---|
| `state.py` | Máy trạng thái 7 trạng thái + quy tắc ưu tiên |
| `behavior.py` | Quyết định tự đi / nghỉ / ngủ theo thời gian |
| `falling.py` | Mô phỏng rơi nhanh dần và tiếp đất |

`PetWindow` nối cả ba: mỗi 100 ms gọi `_behavior_tick()`, sự kiện chuột được
chuyển thành sự kiện trạng thái, và mỗi lần đổi trạng thái thì đổi animation
tương ứng.

Bảy trạng thái: `idle`, `walk`, `drag`, `fall`, `sleep`, `react`, `talk`.

Quy tắc ưu tiên đã được cài đặt và test:

| Quy tắc | Cách thực hiện |
|---|---|
| Đang bị kéo thì không được ngủ | `StateMachine.can_sleep()` trả `False` khi ở `drag` |
| Đang rơi thì phải tiếp đất trước | `_check()` từ chối mọi trạng thái khác `idle` khi ở `fall` |
| Chế độ tập trung thì đứng yên hoặc ngủ | `set_focus_mode()` chặn `walk`, `fall` |
| Đi tới cạnh màn hình thì quay đầu | `PetWindow._walk_step()` đảo `walk_direction` |

Phân biệt click và kéo: bấm rồi nhả mà **không** di chuyển quá 4 px là click
(pet `react`); di chuyển xa hơn mới tính là kéo (pet `drag`).

Vòng đời đầy đủ đã kiểm tra tự động trong `tests/test_phase3_flow.py`:
mở app → tự đi → nghỉ → kéo → vùng vẫy → thả → rơi → tiếp đất → click → phản ứng.

## Độ ổn định: ba lớp chặn treo máy

Tóm tắt; chi tiết lỗi và cách phát hiện ở
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

1. **Trần RAM ở `run.sh`** — 700 MB qua `prlimit`. Vượt thì chỉ tiến trình pet
   bị kernel dừng.
2. **Lỗi trong timer không giết app** — `PetWindow._guarded()` ghi log một lần
   rồi chạy tiếp; ≥50 lỗi/10 giây thì dừng vòng lặp.
3. **Cache `QMovie`** — `QMovie` không giải phóng hết tài nguyên C++ khi huỷ.
   Tạo mới mỗi lần đổi GIF = ~1.3 MB/lần (600 lần = 1.5 GB). Cache theo đường
   dẫn trong `ui/gif_player.py`. Đo lại: 13 MB.

Đo thật: **~60 MB RAM, ~19% một nhân CPU** khi pet đi lại.

## Cấu trúc `ui/`: vì sao tách

Ban đầu mọi thứ nằm trong `pet_window.py` (1467 dòng, 85 method, 9 nhóm trách
nhiệm). Đó là God Object: thêm một mục menu phải mở cùng file với logic kéo
thả, fullscreen và AI. Đã tách thành:

| File | Dòng | Trách nhiệm |
|---|---|---|
| `pet_window.py` | ~1000 | cửa sổ, chuột, phím tắt, vòng đời, phối hợp |
| `ui/gif_player.py` | 216 | QMovie, cache, kích thước, nạp GIF |
| `ui/tray_menu.py` | 240 | khay, menu, thông báo khay |
| `ui/window_skin.py` | 174 | cờ cửa sổ, click xuyên, fullscreen |
| `ui/pet_actions.py` | 122 | thực thi hành động (một chỗ duy nhất) |

**Cách ghép:** hàm nhận `window` làm tham số đầu, không kế thừa. `pet_window`
import các module này; chiều ngược lại không, nên không có vòng import.
Các method trên `PetWindow` còn lại là lớp mỏng chuyển tiếp.

**Lợi ích đo được:** `test_ui_modules.py` (21 test) kiểm tra được menu, cờ cửa
sổ, chặn URL, mà trước đây phải dựng cả app. `pet_actions.py` là nơi duy nhất
review về "app làm được gì".

## Cấu hình người dùng

Lưu **ngoài repo**, ở thư mục cấu hình của hệ điều hành:

| Hệ điều hành | Đường dẫn |
|---|---|
| Linux | `$XDG_CONFIG_HOME/GifAnimation/config.json` |
| Windows | `%APPDATA%\GifAnimation\config.json` |
| macOS | `~/Library/Application Support/GifAnimation/config.json` |

Ghi theo kiểu atomic: ghi file tạm rồi `os.replace`. File hỏng hoặc sai kiểu dữ
liệu được thay bằng giá trị mặc định thay vì làm app crash.

Các key của Giai đoạn 3–5 đã được khai báo sẵn trong `DEFAULTS` với giá trị
tắt mặc định (`ai_enabled`, `voice_enabled`, ...), nên bật lên không phá cấu
hình cũ.

## Nhắc tập trung / nghỉ (Pomodoro)

`gifpet/core/pomodoro.py` — logic thuần túy, không phụ thuộc Qt.

Vòng lặp `FOCUS → BREAK → FOCUS …`. Hết giờ tập trung thì pet nhắc uống nước,
đứng dậy vận động hoặc thư giãn mắt. Trong giờ tập trung pet **đứng yên**
(không tự đi) để không làm phân tán; sang giờ nghỉ thì đi lại bình thường.

| Trạng thái | Ý nghĩa |
|---|---|
| `idle` | Chưa bật |
| `focus` | Đang trong giờ tập trung |
| `break` | Đang trong giờ nghỉ |
| `paused` | Người dùng tạm dừng đồng hồ |

Lời nhắc hiện theo hai cách, đều tắt được trong Cài đặt: **bong bóng thoại**
trên đầu pet (`gifpet/ui/speech_bubble.py`) và **thông báo khay hệ thống**.

`announce()` là điểm vào chung — sau này AI (Giai đoạn 4) cũng gọi cùng
phương thức này để pet nói.

Tương tác với `focus_mode` thủ công: khi Pomodoro tắt, `focus_mode` do người
dùng đặt vẫn được giữ; khi Pomodoro bật, giờ tập trung cũng khoá pet lại.

## Đóng gói thành binary

Không cần cài Python để chạy. Dùng Nuitka (compile Python → C → binary):

```bash
./tools/build_binary.sh              # standalone
./tools/build_binary.sh --onefile    # một file duy nhất (cần patchelf)
./tools/slim_binary.sh               # dọn Qt plugin không dùng
```

Kết quả đo thực tế trên Ubuntu 24.04:

| | Python trực tiếp | Binary Nuitka |
|---|---|---|
| Cần cài Python | có | **không** |
| Kích thước phân phối | 215 MB (venv) | **172 MB** |
| Binary chính | — | 15 MB |
| RAM khi chạy | 58 MB | 74 MB |

**Điểm quan trọng: đóng gói không làm app nhẹ đi.** Nuitka kéo theo toàn bộ Qt
(110 MB riêng PyQt5) và các thư viện phụ thuộc. Lợi ích thật là **không cần
cài Python** và có **một thư mục chạy được ngay**.

`slim_binary.sh` cắt được ~49 MB nhờ bỏ Qt plugin không dùng (media, in ấn,
QML/Quick, và tùy chọn Wayland). Đặt `KEEP_WAYLAND=0` để bỏ thêm 26 MB, nhưng
khi đó app chỉ chạy trên X11.

Hai cái bẫy khi build, đã xử lý trong script:

- Nuitka cần `patchelf` ở chế độ standalone. Không có quyền root vẫn được —
  `pip install patchelf` rồi thêm `.venv/bin` vào PATH.
- `--output-filename` **không được trùng tên thư mục package**. Đặt là `gifpet`
  sẽ lỗi `data file conflicts with executable`; script dùng `gif-pet`.

## Giai đoạn 4 — AI (đã triển khai)

Code trong `gifpet/ai/`:

| Module | Vai trò |
|---|---|
| `provider.py` | Groq / Gemini, timeout cứng. **Nơi duy nhất mở kết nối mạng** |
| `actions.py` | whitelist 5 hành động + kiểm tên/kiểu/miền giá trị/tham số |
| `brain.py` | nối sự kiện → provider → lọc kết quả; áp đủ 4 lớp phòng thủ |
| `quota.py` | đếm lượt/ngày, reset theo ngày, chống đồng hồ lùi, rate limit |
| `secrets.py` | API key ở env hoặc `secrets.json` (0600), tách khỏi config |
| `memory.py` | chỉ lưu ghi chú người dùng gõ tay; xem/xoá được |

Luồng một lượt:

```
người dùng bấm Ctrl+Alt+A
   → Brain.ask("chat", text)
       → quota.check_and_use()      # hết lượt / quá nhanh → dừng
       → build_user_content(...)    # JSON có trường type, không nối vào system prompt
       → provider.complete(...)     # timeout 20s, key trong header
       → extract_json(reply)        # không phải JSON → coi là câu nói
       → actions.validate(name, params)   # <-- CHỐT CHẶN
   → PetWindow._handle_brain_result(...)
       → hiện bong bóng thoại
       → hành động có tác dụng phụ? hỏi QMessageBox, mặc định "Không"
       → chạy hành động
```

Ràng buộc đầy đủ và hạn chế đã biết: `docs/SECURITY.md`.
Test: `tests/test_ai.py` (64 test, dùng provider giả, không gọi mạng thật).

## Chạy

```bash
./run.sh              # chạy app
./run.sh --test       # chạy tất cả test đơn vị
./run.sh --accept     # 17 tiêu chí nghiệm thu
./run.sh --phase3     # 16 bước vòng đời Giai đoạn 3
./run.sh --headless   # khởi động không màn hình
```
