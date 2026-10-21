# Lỗi đã gặp và cách sửa

Mọi mục ở đây là lỗi **thật đã xảy ra** trong quá trình phát triển, không phải
giả định. Ghi lại để không mắc lại, và để người sau nhận ra triệu chứng nhanh.

Sắp xếp theo lĩnh vực.

---

## Rò rỉ bộ nhớ

### RSS tăng vô hạn khi pet chạy lâu

**Triệu chứng:** để app vài giờ thì RAM vài GB, máy treo. Không có lỗi trong log.

**Đo được:** tạo/huỷ `QMovie` 600 lần → RSS tăng **1503 MB**. Sau khi sửa → 13 MB.

**Nguyên nhân:** `QMovie` của Qt **không giải phóng hết tài nguyên C++** khi bị
huỷ. `deleteLater()` và cả `gc.collect()` đều không đủ. Code cũ tạo `QMovie`
mới mỗi lần đổi animation.

**Cách phát hiện:** không nhìn code mà đo RSS:

```python
rss = int(open("/proc/self/statm").read().split()[1]) * 4096 // 1024
```

Cho pet đổi animation 600 lần, in RSS trước/sau. Nếu tăng > 200 MB là rò rỉ.

**Cách sửa:** cache `QMovie` theo đường dẫn trong `ui/gif_player.py`. Chỉ tạo
mới lần đầu. Khoá lại bằng `tests/test_stability.py`.

### Segfault khi đóng app

**Triệu chứng:** `Segmentation fault (core dumped)` khi đóng cửa sổ, hoặc khi
chạy nhiều test window liên tiếp.

**Nguyên nhân:** `QMovie` còn đang chạy, gọi vào `QLabel` đã bị huỷ. Thứ tự huỷ
sai: cửa sổ chết trước movie.

**Cách sửa:** `gif_player.release_movies(window)` phải gọi trong `closeEvent`
**trước** khi nhận event:

```python
def closeEvent(self, event):
    for timer in (...): timer.stop()
    self._release_movies()      # dừng movie + label.setMovie(None)
    event.accept()
```

Test cũng phải gọi `window.close()`, không chỉ `deleteLater()`.

---

## Qt / PyQt5

### `QMovie.currentPixmap()` trả kích thước sai

**Triệu chứng:** GIF 200×200 hiển thị thành hình vuông méo, dù đã `setScaledSize`.

**Nguyên nhân:** sau `setScaledSize()`, `currentPixmap().size()` trả kích thước
**đã scale**, không phải gốc.

**Cách sửa:** đọc file qua `QImageReader`:

```python
from PyQt5.QtGui import QImageReader
reader = QImageReader(path)
size = reader.size()   # kích thước thật
```

### `AttributeError: 'QMovie' object has no attribute 'isPaused'`

**Cách sửa:** `movie.state() == QMovie.Paused`.

### `QRegion` không import được từ `QtCore`

**Triệu chứng:** `ImportError: cannot import name 'QRegion' from 'PyQt5.QtCore'`

**Cách sửa:** `from PyQt5.QtGui import QRegion` — nó ở `QtGui`, không phải `QtCore`.

### `move()` không nhận float

**Triệu chứng:** `TypeError: move(self, ax: int, ay: int): argument 2 has unexpected type 'float'`

**Nguyên nhân:** mô phỏng rơi tính bằng float.

**Cách sửa:** `new_y = int(round(new_y))` trước khi `move()`.

### Pet ngủ ngay khi mở app

**Nguyên nhân:** `Behavior.last_interaction_ms` khởi tạo `0` → so với
`time.monotonic()` thì tưởng đã bị bỏ quên từ epoch.

**Cách sửa:** mặc định `None`, dùng `ensure_started(now_ms)` để chốt mốc lần
đầu.

### `AttributeError: property 'state' has no setter`

**Triệu chứng:** `set_state()` ném lỗi. Lỗi này **có từ bản gốc**, không test
nào chạm tới nên nằm im.

**Nguyên nhân:** `PetWindow.state` là property chỉ đọc (trả
`machine.state`), nhưng code ghi `self.state = state`.

**Cách sửa:** `self.machine.request(state, reason=...)`. Đừng ghi đè — máy
trạng thái còn phải áp quy tắc ưu tiên.

### Lỗi trong timer làm chết app

**Nguyên nhân:** timer Qt không có chỗ bắt exception. Một lỗi trong `timeout`
thoát khỏi vòng lặp sự kiện và tắt app.

**Cách sửa:** bọc qua `PetWindow._guarded()`, ghi log một lần rồi chạy tiếp.
≥ 50 lỗi trong 10 giây thì dừng vòng lặp để không đốt CPU.

---

## Logic

### Vòng lặp lỗi đốt CPU

**Triệu chứng:** một nhân CPU 100% sau khi có lỗi.

**Cách sửa:** bộ đếm lỗi trong `_guarded`. Chỉ in traceback **một lần** cho mỗi
đợt lỗi, không in mỗi lần.

### Su kiện ghi mỗi 100ms làm tràn hàng đợi

**Triệu chứng:** bật `ai_proactive` thì model bị gọi liên tục.

**Nguyên nhân:** `_collect_proactive` chạy mỗi 100ms từ `_behavior_tick`, và
mỗi lần lại thêm một sự kiện `long_idle`.

**Cách sửa:** cờ `_long_idle_noted`, chỉ ghi một lần cho mỗi giai đoạn rảnh.
Đo lại: 200 tick → 0 lần gọi model.

### Quota báo sai lý do

**Triệu chứng:** hết lượt nhưng báo "chờ vài giây".

**Nguyên nhân:** kiểm `rate_limited` trước `exhausted`.

**Cách sửa:** thứ tự đúng là `disabled` → `exhausted` → `rate_limited`.

### `resume()` không thoát trạng thái pause

**Cách sửa:** lưu `_phase_before_pause` lúc `pause()`, khôi phục lúc `resume()`.

### Bong bóng thoại quá hẹp và cao

**Triệu chứng:** câu dài hiện thành `177×130` thay vì `340×76`.

**Nguyên nhân:** đo chiều rộng theo từng từ thay vì cả câu.

**Cách sửa:** `_resize_for_text()` đo một dòng, kẹp trong `[MIN_WIDTH, MAX_WIDTH]`.

### Pet mới cài đặt hiện bong bóng ở dưới

**Nguyên nhân:** vị trí mặc định `(0,0)` — góc trên-trái, không đủ chỗ phía trên.

**Cách sửa:** `screen_utils.default_position()` đặt góc dưới-trái.

---

## AI và bảo mật

### JSON thô của model thành câu nói

**Triệu chứng:** pet đọc nguyên `{"action":"delete_all","params":{}}` cho người
dùng nghe.

**Nguyên nhân:** khi hành động bị từ chối, code cũ dùng cả câu trả lời làm text.

**Cách sửa:** trả `error="rejected_action"` với `text=""`. Không bao giờ hiển
thị JSON thô.

### `in_minutes: true` lọt qua kiểm tra

**Nguyên nhân:** trong Python `isinstance(True, int)` là `True` và `True == 1`.

**Cách sửa:** `if isinstance(value, bool) or not isinstance(value, int): raise`.

### Key lộ trong config

**Nguyên nhân:** `Config` ghi mọi thứ vào một file và `save()` gọi rất thường.

**Cách sửa:** `ai/secrets.py` — env hoặc `secrets.json` với `fchmod(0600)`
tường minh, `chmod 0700` thư mục. `config.json` chỉ biết key **có hay không**.

### `NameError: QSystemTrayIcon` sau khi tách module

**Triệu chứng:** crash khi Pomodoro nhắc hoặc khi thiếu GIF. Test không phủ.

**Nguyên nhân:** đã chuyển `import QSystemTrayIcon` sang `tray_menu.py` nhưng
còn hai chỗ dùng trong `pet_window.py`.

**Cách sửa:** `tray_menu.notify(window, message, warning=False)`.

**Bài học:** sau khi tách module phải chạy `python -m pyflakes gifpet/`. Test có
thể không phủ đường hiếm gặp.

---

## Test

### Test đỏ vì dính state của test trước

**Triệu chứng:** chạy riêng thì pass, chạy cả file thì fail.

**Nguyên nhân:** `Config()` và `Reminders()` đọc từ file dùng chung.

**Cách sửa:** `XDG_CONFIG_HOME` trỏ thư mục tạm, và gọi `.clear()` trong
`setUp()`. Hoặc tạo helper `fresh_config()` đặt lại bộ đếm.

### Test bảo mật đỏ sau khi thêm tính năng

**Triệu chứng:** thêm Phase 4 (có mạng) thì `test_security.py` fail vì
"phát hiện gọi mạng".

**Sai:** nới lỏng test cho pass.

**Đúng:** sửa test để **chặt hơn** — chỉ `provider.py` được mở kết nối,
`actions.py` chỉ dùng `urlsplit` (phân tích chuỗi, không kết nối).

### Test pass nhưng không bắt được gì

**Triệu chứng:** test bảo mật xanh, nhưng thực tế có lỗ hổng.

**Cách kiểm chứng:** cố tình vi phạm rồi xem test có đỏ không.

```bash
# thêm vi phạm
echo 'import subprocess; subprocess.run("ls", shell=True)' >> gifpet/core/paths.py
python tests/test_security.py     # PHẢI có FAIL
git checkout gifpet/core/paths.py
```

Đã làm 3 lần với 3 nhóm test khác nhau. Test an toàn mà không bao giờ fail là
test vô dụng.

### Test yếu lọt qua review

**Ví dụ đã gặp:** `self.assertTrue(True)` — luôn pass, không kiểm tra gì.

**Cách sửa:** thay bằng assert có nghĩa (đọc file, kiểm giá trị cụ thể).

---

## Môi trường phát triển

### Sandbox chặn ghi `~/.config`, `~/.cache`, `~/.ssh`

**Cách xử lý:** dùng `XDG_CONFIG_HOME`, `--cache-dir /tmp/...`,
`NUITKA_CACHE_DIR=/tmp/nuitka-cache`.

### Không có màn hình

**Cách chạy test:** `QT_QPA_PLATFORM=offscreen`.

**Hạn chế:** không kiểm chứng được độ mượt, độ trong suốt, click xuyên thật.
Phải nhờ người dùng xác nhận.

### Chrome không chạy được (chặn hướng B/C của browser agent)

Đã **thử thật** và fail ở nhiều mức:

```bash
# 1. dump-dom cơ bản
google-chrome --headless --disable-gpu --no-sandbox \
  --dump-dom "data:text/html,<h1>Xin chao</h1>"
# -> Touch: cannot touch '~/.local/share/applications/mimeapps.list': Permission denied
# -> Failed to create headless user data directory container.
# -> exit 0 nhưng KHÔNG có output

# 2. thêm --user-data-dir riêng
google-chrome --headless --user-data-dir=/tmp/cprof --dump-dom "..."
# -> exit 0, output rỗng

# 3. thêm --headless=new --virtual-time-budget
# -> chrome_crashpad_handler: --database is required
# -> timeout: the monitored command dumped core
```

**Nguyên nhân:** sandbox chặn ghi `~/.local/share/applications` và thư mục
crashpad. `/tmp` thì ghi được nhưng Chrome vẫn không render.

**Hệ quả với dự án:** mọi hướng cần điều khiển trình duyệt (Playwright, CDP)
**không kiểm chứng được** trên máy này. Xem `BROWSER-AGENT.md` mục "Kiểm chứng".

**Cách xử lý nếu vẫn phải làm:** thiết kế để phần lớn logic nằm ở module
thuần tuý (`policy.py`) test được không cần Chrome; phần mở trang thật để
người dùng kiểm chứng.

**Còn Firefox? Đã thử, cũng fail.**

```bash
firefox --headless --profile /tmp/ff --screenshot /tmp/ff.png "data:text/html,<h1>x</h1>"
# -> internal error: cannot create XDG_RUNTIME_DIR folder
#    "/run/user/1003/snap.firefox": mkdir: permission denied

XDG_RUNTIME_DIR=/tmp/xdgr firefox --headless ...
# -> cùng lỗi: bản snap vẫn cố ghi vào /run/user/1003
```

Firefox trên máy này là **bản snap**, và nó cứng nhắc dùng
`/run/user/<uid>/snap.firefox` — không tôn trọng `XDG_RUNTIME_DIR`. Không có
quyền tạo thư mục đó nên không chạy được.

**Kết luận:** cả Chrome và Firefox đều không chạy được trong môi trường phát
triển này. Không phải lỗi cấu hình — là giới hạn sandbox.

### Nuitka

| Lỗi | Cách sửa |
|---|---|
| `failed to create cache directory` | `export NUITKA_CACHE_DIR=/tmp/nuitka-cache` |
| `standalone mode requires 'patchelf'` | `pip install patchelf`, thêm `.venv/bin` vào PATH |
| `data file conflicts with executable 'gifpet'` | `--output-filename=gif-pet` |

---

## Quy trình rút ra

1. **Đo trước khi tin.** Rò rỉ QMovie chỉ lộ khi đo RSS. "Trông ổn" không phải
   bằng chứng.
2. **Chạy test sau mỗi bước tách module.** Đã bắt được `set_state` hỏng ngay.
3. **Pyflakes sau khi tách.** Bắt được `QSystemTrayIcon` mà test không phủ.
4. **Test an toàn phải được kiểm chứng bằng vi phạm cố ý.**
5. **Ghi lại lỗi vào đây ngay khi sửa xong.** Trí nhớ sẽ mất, tài liệu thì không.
