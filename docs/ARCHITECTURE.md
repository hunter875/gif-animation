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
│   │   ├── pet_window.py       # cửa sổ pet, menu khay, phím tắt
│   │   ├── dialogs.py          # dialog resize và cài đặt
│   │   ├── gif_library_dialog.py  # thư viện GIF có thumbnail
│   │   └── speech_bubble.py    # bong bóng thoại của pet
│   │
│   ├── assets/                 # tài nguyên tĩnh
│   │   └── app_icon.ico
│   │
│   ├── ai/                     # (Giai đoạn 4) — CHƯA TRIỂN KHAI
│   │   └── __init__.py         # mô tả thiết kế dự kiến
│   │
│   └── voice/                  # (Giai đoạn 5) — CHƯA TRIỂN KHAI
│       └── __init__.py         # mô tả thiết kế dự kiến
│
├── pets/                       # thư viện nhân vật
│   └── default/
│       ├── pet.json            # mô tả kích thước, tốc độ, tính cách
│       ├── idle.gif
│       ├── walk.gif
│       ├── drag.gif
│       └── sleep.gif
│
├── tests/
│   ├── test_core.py            # 83 test đơn vị
│   ├── test_pomodoro.py        # 32 test nhắc tập trung / nghỉ
│   ├── test_acceptance.py      # 17 tiêu chí nghiệm thu
│   └── test_phase3_flow.py     # 16 bước vòng đời Giai đoạn 3
│
├── tools/
│   └── make_state_animations.py  # sinh fall/react/talk từ GIF gốc
│
├── docs/
│   └── ARCHITECTURE.md         # file này
│
├── run.sh                      # chạy app / test / nghiệm thu
├── requirements.txt
└── README.md
```

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

## Giai đoạn 4 — AI (chưa triển khai)

Dự kiến trong `gifpet/ai/`:

| Module | Vai trò |
|---|---|
| `provider.py` | giao diện chung cho các nhà cung cấp (Groq, Gemini, ...) |
| `actions.py` | danh sách hành động được phép + kiểm tra tên/tham số/tần suất |
| `memory.py` | bộ nhớ xem và xóa được; chỉ lưu điều người dùng cho phép |
| `quota.py` | đếm lượt dùng trong ngày, trần lượt/ngày |
| `brain.py` | gom sự kiện → gọi model → trả về (câu nói, hành động) |

Nguyên tắc bắt buộc:

- Model **chỉ được đề xuất hành động có trong danh sách cho phép**. App kiểm tra
  tên hành động, tham số và tần suất trước khi thực hiện.
- Không nhận lệnh tùy ý như chạy shell hay mở file.
- Không gửi lại toàn bộ lịch sử mỗi lần; chỉ gửi sự kiện đã chọn.
- Hết quota hoặc mất mạng thì pet vẫn hoạt động local bình thường.
- Click liên tục được gom thành một sự kiện; pet tự đi, rơi, ngủ **không** gọi model.

## Giai đoạn 5 — Giọng nói (chưa triển khai)

Dự kiến trong `gifpet/voice/`:

| Module | Vai trò |
|---|---|
| `stt.py` | bấm để nói → chuyển thành chữ |
| `tts.py` | đọc câu trả lời, có nút tắt tiếng |
| `talk.py` | điều phối: bấm phím → nói → STT → AI → TTS → animation `talk` |

Bắt đầu bằng "bấm để nói", **không** nghe mic liên tục — vì khó quản lý tiếng ồn,
độ trễ và số lượt sử dụng.

## Chạy

```bash
./run.sh              # chạy app
./run.sh --test       # chạy tất cả test đơn vị
./run.sh --accept     # 17 tiêu chí nghiệm thu
./run.sh --phase3     # 16 bước vòng đời Giai đoạn 3
./run.sh --headless   # khởi động không màn hình
```
