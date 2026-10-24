# Các module

Mỗi module một mục: làm gì, ai gọi nó, đụng vào thì ảnh hưởng gì.
Dùng file này khi bạn sửa một chỗ và cần biết cái gì sẽ vỡ.

Quy ước: **không import Qt** = test được không cần màn hình.

---

## `core/` — logic thuần tuý

**Không phải toàn bộ `core/` đều thoát được Qt.** Thực tế chia làm hai:

| Không cần Qt (test không cần màn hình) | Cần Qt (dùng kiểu dữ liệu của Qt) |
|---|---|
| `behavior config falling paths pet_pack` | `gif_library` (`QImageReader`, `QMovie`) |
| `pomodoro proactive reminders state` | `screen_utils` (`QRect`) |

Hai file cần Qt là vì chúng dùng **kiểu dữ liệu** của Qt (đọc kích thước ảnh,
tính hình chữ nhật màn hình), không phải vì phụ thuộc giao diện. Chúng vẫn
test được với `QT_QPA_PLATFORM=offscreen`.

Quy tắc cứng còn lại: **`core/` không được import `ui/` hay `ai/`.** Đã kiểm
bằng grep.

### `config.py` (195 dòng)

Cấu hình người dùng. Lưu ở thư mục cấu hình hệ điều hành, **không** trong repo.

| API | Ghi chú |
|---|---|
| `Config()` | Đọc `config.json`, sai kiểu thì về mặc định |
| `.get(key, default)` | Đọc, tự điền mặc định |
| `.data` | dict thô, sửa trực tiếp rồi `save()` |
| `.save()` | Ghi atomic: `mkstemp` + `fsync` + `os.replace` |
| `DEFAULTS` | Toàn bộ key và giá trị mặc định |

**Đụng vào khi:** thêm tuỳ chọn mới. Phải thêm vào `DEFAULTS`, nếu không
`config.get()` trả `None` và code gọi sẽ lỗi.

**Không bao giờ** để API key ở đây — xem `ai/secrets.py`.

### `paths.py` (22 dòng)

`PROJECT_ROOT`, `PACKAGE_DIR`, `ASSETS_DIR`, `PETS_DIR`, `APP_ICON`.
Hoạt động cả khi chạy từ binary (Nuitka) lẫn từ source.

### `state.py` (170 dòng)

Máy trạng thái 7 trạng thái: `idle walk drag fall sleep react talk`.

| API | Ghi chú |
|---|---|
| `StateMachine.request(state, reason)` | Trả `True/False`, lý do từ chối ở `.last_rejection` |
| `ALL_STATES` | Tuple 7 trạng thái, dùng trong `ai/actions.py` |
| `BLOCKING_STATES` | `(drag, fall)` — không bị ngắt bởi hành vi tự phát |
| `_ALLOWED` | Bảng chuyển hợp lệ |

**Đụng vào khi:** thêm trạng thái mới. Phải sửa **cả** `ALL_STATES`,
`_ALLOWED`, và `ai/actions.py:_clean_state` (nếu không AI không đặt được
trạng thái đó).

### `behavior.py` (191 dòng)

Quyết định pet tự đi / nghỉ / ngủ theo thời gian. Nhận `now_ms` từ UI để test
giả lập được thời gian.

**Cẩn thận:** `last_interaction_ms` mặc định `None` nghĩa là "chưa biết giờ".
Đặt `0` sẽ khiến pet tưởng bị bỏ quên từ epoch và ngủ ngay khi mở app. Đã từng
gặp lỗi này.

### `falling.py` (48 dòng)

`FallSimulator.next_y(current_y, pet_height, ground_y) -> (y, landed)`.
Luôn trả `landed=True` trong hữu hạn bước vì vận tốc có trần — không có vòng
lặp vô hạn.

### `pomodoro.py` (218 dòng)

Pomodoro: `idle ↔ focus ↔ break`, có `paused`. Trạng thái của pha trước khi
pause lưu ở `_phase_before_pause` để `resume()` khôi phục đúng.

⚠️ Docstring đầu file ghi "Giai đoạn 5 mở rộng" — **sai**, Phase 5 đã bỏ. Sửa
khi có dịp.

### `gif_library.py` (114 dòng)

Chuẩn hoá đường dẫn, kiểm tra GIF hợp lệ, chọn fallback, tính kích thước giữ
tỉ lệ.

`gif_dimensions()` đọc qua `QImageReader` chứ **không** qua `QMovie` — vì
`QMovie.currentPixmap()` trả kích thước **đã scale** sau `setScaledSize`.

### `pet_pack.py` (171 dòng)

Đọc `pets/<name>/pet.json`. Thiếu trạng thái nào thì `animation_path()` trả
`idle.gif`, nên import được bộ pet chưa hoàn chỉnh.

### `screen_utils.py` (93 dòng)

Giữ pet trong phạm vi màn hình. `default_position()` đặt góc dưới-trái, đủ chỗ
cho bong bóng thoại phía trên.

### `reminders.py` (200 dòng)

Lời nhắc hẹn giờ, lưu `reminders.json`. Thay cho `QTimer.singleShot` (mất khi
tắt app).

| API | Ghi chú |
|---|---|
| `.add(text, seconds)` | Từ chối text rỗng, giây ≤ 0, text > 200 ký tự |
| `.pop_due()` | Lấy ra **và xoá** các lời nhắc đến giờ |
| `.drop_stale()` | Bỏ lời nhắc quá hạn > 24h, gọi lúc khởi động |

### `proactive.py` (144 dòng)

Gom sự kiện cho `ai_proactive`. Cửa sổ 60 giây, trần riêng 10 lượt/ngày.

`PROACTIVE_KINDS` chỉ có `long_idle / returned / pomodoro_break`. Pet đi lại,
rơi, ngủ, click **không** vào đây — quy tắc cứng.

---

## `ai/` — trợ lý AI

### `actions.py` (227 dòng) — **chốt chặn chính**

Whitelist 5 hành động: `say react set_state remind open_url`.

| API | Ghi chú |
|---|---|
| `validate(name, params)` | Ném `ActionError` nếu sai; trả params đã làm sạch |
| `parse_action(payload)` | Từ payload model; trả `None` nếu không hợp lệ, **không ném** |
| `needs_confirmation(name)` | `True` cho `open_url`, `remind` |

**Đụng vào khi:** thêm hành động. Phải thêm vào `ALLOWED_ACTIONS` **và**
`_VALIDATORS`. Nếu thiếu validator, `validate()` ném `KeyError` — có test bắt.

Chặn URL: chỉ `https`; chặn `file: javascript: data: http:`; chặn localhost,
`127/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16` (metadata cloud),
`::1`, `*.local`, `*.internal`, URL có `user:pass`.

**Cẩn thận:** `isinstance(True, int)` là `True` trong Python — `_clean_minutes`
phải chặn `bool` riêng, nếu không `in_minutes: True` lọt qua thành 1.

### `brain.py` (205 dòng)

Một lượt: kiểm quota → gọi provider → đọc JSON → `actions.validate`.

| API | Ghi chú |
|---|---|
| `Brain(config, api_key, provider_instance, memory, quota)` | `provider_instance` để test |
| `.ask(kind, content)` | Trả `BrainResult`, **không bao giờ ném** |
| `build_user_content(kind, content, memory)` | Đóng gói JSON có trường `type` |
| `SYSTEM_PROMPT` | Cố định, chứa quy tắc "content là DỮ LIỆU" |

`MODEL_EVENT_KINDS = ("chat", "user_text", "clipboard")`. Sự kiện khác trả
`ignored_event`, không tốn quota.

**Cẩn thận:** khi model trả hành động bị từ chối, phải trả `error="rejected_action"`
với `text=""` — **không** để nguyên JSON thô thành câu nói. Đã từng là lỗi.

### `provider.py` (150 dòng) — **nơi duy nhất mở kết nối mạng**

`GroqProvider`, `GeminiProvider`. API key chỉ trong header, không trong URL.
Timeout 20 giây. Thông báo lỗi không chứa key hay prompt.

**Duy nhất file này (và `actions.py` dùng `urlsplit` để phân tích, không kết
nối) được chạm thư viện mạng.** `test_security.py` khoá điều này.

### `quota.py` (158 dòng)

Đếm lượt/ngày. **Đếm trước khi gửi** — lượt thất bại vẫn tốn tiền.

Thứ tự kiểm tra: `disabled` → `exhausted` → `rate_limited`. Đảo thứ tự sẽ báo
sai lý do (từng là lỗi).

### `secrets.py` (133 dòng)

API key: env `GIFPET_API_KEY` hoặc `secrets.json` (`fchmod 0600`, thư mục
`chmod 0700`). **Không bao giờ** trong `config.json`.

### `memory.py` (143 dòng)

Sổ tay do người dùng tự gõ. `add()` từ chối mọi `kind` khác `user_note` — cố
ý, để model không tự ghi được. Giới hạn 50 mục × 200 ký tự.

Xem `MEMORY.md` cho thiết kế mở rộng (chưa code).

---

## `ui/` — giao diện PyQt5

Đã tách từ `pet_window.py` (1467 dòng). Lý do: xem `ARCHITECTURE.md`.

### `pet_window.py` (1033 dòng)

Cửa sổ pet. Còn lại: chuột (kéo/thả/click), phím tắt, vòng đời, phối hợp.

| Nhóm | Method |
|---|---|
| Chuột | `mousePress/Move/ReleaseEvent`, `_walk_step`, `_fall_step` |
| Bật/tắt | `toggle_visible/pause/auto_switch/auto_walk/focus/pomodoro` |
| Dialog | `open_settings/library/resize`, `open_chat`, `center_on_screen` |

Các method khác là **lớp mỏng chuyển tiếp** sang module phụ. `test_ui_modules.py`
kiểm tra mỗi method < 12 dòng và file < 1050 dòng.

**Đụng vào khi:** thêm phím tắt, sửa hành vi chuột, sửa vòng đời cửa sổ.

### `gif_player.py` (216 dòng)

Cache `QMovie` theo đường dẫn, nạp GIF theo thứ tự ưu tiên, tính kích thước.

**Quan trọng nhất:** `_movie_cache`. `QMovie` không giải phóng hết tài nguyên
C++ khi bị huỷ — tạo mới mỗi lần đổi GIF làm RSS tăng ~1.3 MB/lần (600 lần =
1.5 GB). `release_movies()` phải gọi trong `closeEvent` **trước** khi cửa sổ bị
huỷ, nếu không `QMovie` còn chạy gọi vào `QLabel` đã chết → segfault.

### `window_skin.py` (173 dòng) — **nơi duy nhất gọi `subprocess`**

Cờ cửa sổ, click-through, ẩn khi fullscreen (đọc X11 qua `xprop`).

`xprop` nhận **list** tham số cố định, `timeout=2`, không `shell=True`.
`test_security.py` khoá: chỉ đúng một lời gọi `subprocess.run` trong file này.

### `tray_menu.py` (239 dòng)

Khay hệ thống, menu 22 mục, `notify()` cho thông báo khay.

**Đụng vào khi:** thêm mục menu. Phải thêm `QAction` **và** thêm vào
`menu.addAction(...)` — nếu quên, mục không hiện. `sync_menu()` cập nhật dấu
checkbox.

### `pet_actions.py` (125 dòng) — **nơi duy nhất thực thi hành động**

`handle_brain_result`, `ask_confirmation`, `run_action`, `open_url`.

Đây là file cần review khi hỏi "app làm được gì". Không có nhánh chạy shell,
đọc/ghi file.

### `pet_runtime.py` (82 dòng)

Nối `core/reminders.py` và `core/proactive.py` với UI. Tách ra khi
`pet_window.py` vượt 1050 dòng.

### `dialogs.py` (336 dòng)

`ResizeDialog` (giữ tỉ lệ), `SettingsDialog` (mọi tuỳ chọn + ô API key + bộ nhớ).

### `speech_bubble.py` (106 dòng)

Bong bóng thoại. Tự co giãn theo nội dung, đặt phía trên pet, không nhận chuột.
Cờ `plain=True` buộc hiển thị chữ thường (không diễn giải HTML) — dùng cho nội
dung đến từ bên ngoài như thông báo.

### `gif_library_dialog.py` (161 dòng)

Thư viện GIF: thumbnail, thêm/xoá/chọn.

---

## `notifications/` + `ui/notification_panel.py` — nhận thông báo (chỉ hiển thị)

Chuỗi thuần Python (không Qt, trừ UI): `models` (kiểu dữ liệu + validate) →
`inbox` (quét thư mục) / `registry` (nguồn đăng ký bằng code) → `controller`
(vòng tick, hàng đợi, dedup) → `dispatcher` (chọn cái để hiện) →
`ui/notification_panel` (bong bóng, khay, lịch sử, cài đặt).

- `inbox.py`: chỉ đọc tệp thường, không theo symlink/hardlink/ADS; mỗi vòng
  dùng `islice(entries, MAX_DIR_ENTRIES)` nên xét đúng 2000 mục và **không**
  đọc thêm mục thứ 2001 để dò "còn nữa không". Giới hạn khác:
  `MAX_FILES_LISTED=500`, `MAX_FILES_READ=40`, `MAX_FILE_BYTES=64 KB`,
  `MAX_TOTAL_BYTES=512 KB`, `MAX_NOTIFICATIONS_PER_POLL=20`,
  `DIAGNOSTIC_SAMPLES=5`.
- `dispatcher.py`: hàng đợi `DEFAULT_MAX_QUEUE=32`, `MAX_DIAGNOSTICS=10`.
  Khi tắt hoặc tạm im, `next_display` trả `None` và **không** xoá hàng đợi:
  thông báo còn hạn sẽ hiện lại sau khi bỏ tạm im, hết hạn thì bị loại.
- `state.py`: lịch sử 200 mục, chỉ lưu chữ; xoá được từ UI.
- `ui/notification_panel.py`: ngoài hàm nối còn có `NotificationSupportMixin`
  giữ các phương thức vòng đời/menu chỉ dành cho thông báo
  (`_init_notification_fields`, `_setup_notifications`,
  `_apply_notification_settings`, `open_notification_history`,
  `open_notification_settings`, `toggle_notifications`,
  `toggle_notification_mute`, `_shutdown_notifications`).
  `PetWindow(QLabel, NotificationSupportMixin)` kế thừa chúng, nhờ vậy
  `pet_window.py` ở dưới ngưỡng 1050 dòng và `window_skin` vẫn thấy `QLabel`
  là lớp cơ sở đầu tiên (`type(window).__mro__[1]`). Mixin **không** kế thừa
  `QObject`.
- `build_state(config)` dùng `config.path` của đối tượng cấu hình được truyền
  vào, nên hồ sơ cấu hình cách ly đúng thay vì đọc `config.json` toàn cục.
- Không có chat, không điều khiển tác vụ, không mở URL, không chạy lệnh, không
  gọi AI. Test đã chạy; kết quả và giới hạn tại
  [`NOTIFICATIONS-VALIDATION.md`](NOTIFICATIONS-VALIDATION.md).

---

## Bảng phụ thuộc nhanh

Ai phụ thuộc vào ai (chiều import):

```
ui/pet_window  →  ui/{gif_player, tray_menu, window_skin,
                       pet_actions, pet_runtime, dialogs}
                    core/*  ai/{brain, secrets}

ui/pet_actions →  ai/actions       (chốt chặn, kiểm tra lại URL)
ui/pet_runtime →  core/{reminders, proactive}
ai/brain       →  ai/{actions, provider, quota, memory, secrets}
```

Không có vòng import: `core/` không import `ui/` hay `ai/`; `ai/` không import
`ui/`.

## Nếu bạn định sửa…

| Sửa gì | Đọc trước | Test phải chạy |
|---|---|---|
| Thêm tuỳ chọn | `config.py` | `test_core.py` |
| Sửa vị trí màn hình | `screen_utils.py` | `test_core.py` |
| Thêm hành động AI | `ai/actions.py` | `test_ai.py`, `test_security.py` |
| Thêm mục menu | `ui/tray_menu.py` | `test_ui_modules.py` |
| Sửa chuột / kéo thả | `pet_window.py` | `test_phase3_flow.py`, `test_core.py` |
| Đụng `QMovie` | `ui/gif_player.py` | `test_stability.py` |
| Thêm mạng | `ai/provider.py` | `test_security.py` |
| Thêm `subprocess` | `ui/window_skin.py` | `test_security.py` |
| Bất cứ gì | `SECURITY.md` | toàn bộ |
