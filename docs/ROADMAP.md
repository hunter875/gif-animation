# Roadmap

## Kế hoạch mới — Pet trợ lý dạng module (24/10/2026)

Chủ dự án đã duyệt triển khai. Đặc tả, cách thực thi và tiêu chí test:
[`MODULAR-ASSISTANT.md`](MODULAR-ASSISTANT.md).

| Giai đoạn | Phạm vi | Trạng thái trước triển khai |
|---|---|---|
| M0 | Sửa UI blocking, test isolation Windows, error guard/config liên quan | Chưa làm |
| M1 | Protocol + registry + background controller gắn thêm module | Chưa làm |
| M2 | Chat panel, lịch sử phiên, chọn module, progress/cancel/result | Chưa làm |
| M3 | Module Hermes Docker có session thật và hủy backend | Chưa làm |
| M4 | Notes xem/thêm/sửa/xóa, thông báo kết thúc và tài liệu sử dụng | Chưa làm |
| M5 | DS-B test độc lập, Codex tích hợp/test và nghiệm thu | Chưa làm |

Lịch sử bên dưới phản ánh các giai đoạn cũ, không thay thế kết quả review
Windows ngày 24/10/2026. Fullscreen trên Windows, hotkey toàn hệ thống và
RSS regression trên Windows chưa được kiểm chứng hoàn chỉnh. Browser agent
và long-term conversation memory cũ chưa được triển khai; transcript RAM ở
MVP mới không đồng nghĩa long-term memory.

Trạng thái tính đến commit hiện tại. Ghi rõ **đã xong / đang làm / chưa làm**,
không đánh dấu hoàn thành cho thứ chưa kiểm chứng được.

Quy ước: ✅ xong và có test · 🟡 xong một phần · ⛔ chưa làm · ❌ không làm

---

## Đã xong

### Giai đoạn 1–2 — Nền tảng ✅

| Việc | Bằng chứng |
|---|---|
| Chạy trên Linux/Windows/macOS | `run.sh`, `requirements.txt` |
| Cấu hình ngoài repo, ghi atomic | `core/config.py`, `test_core.py` |
| Giữ pet trong phạm vi màn hình | `core/screen_utils.py` |
| Resize giữ tỉ lệ khung hình | `ui/dialogs.py:ResizeDialog` |
| Lưu vị trí khi thả chuột, không lưu khi kéo | `pet_window.mouseReleaseEvent` |
| Đổi GIF không nhảy cửa sổ | `ui/gif_player.py:apply_movie` |
| Menu khay + phím tắt | `ui/tray_menu.py` |
| Click xuyên qua, ẩn khi fullscreen | `ui/window_skin.py` |
| Thư viện GIF có thumbnail, bỏ file hỏng | `ui/gif_library_dialog.py` |
| Nghiệm thu | `test_acceptance.py` 17/17 |

### Giai đoạn 3 — Pet sống ✅

| Việc | Bằng chứng |
|---|---|
| 7 trạng thái + quy tắc ưu tiên | `core/state.py` |
| Tự đi, nghỉ, ngủ | `core/behavior.py` |
| Kéo, văng, rơi, tiếp đất | `core/falling.py` |
| Click để phản ứng (phân biệt với kéo) | `pet_window.mouseReleaseEvent` |
| Bong bóng thoại | `ui/speech_bubble.py` |
| Pomodoro nhắc tập trung/nghỉ | `core/pomodoro.py` |
| Vòng đời đầy đủ | `test_phase3_flow.py` 16/16 |

### Giai đoạn 4 — Trợ lý AI ✅

| Việc | Bằng chứng |
|---|---|
| Whitelist 5 hành động + chặn URL nguy hiểm | `ai/actions.py` |
| Tách dữ liệu khỏi chỉ dẫn | `ai/brain.py:build_user_content` |
| Người dùng xác nhận hành động có tác dụng phụ | `ui/pet_actions.py` |
| API key tách riêng, quyền 0600 | `ai/secrets.py` |
| Quota theo ngày + rate limit | `ai/quota.py` |
| Bộ nhớ chỉ ghi chú người dùng gõ tay | `ai/memory.py` |
| Groq + Gemini | `ai/provider.py` |
| Không gọi model khi pet đi/rơi/ngủ | `ai/brain.py:MODEL_EVENT_KINDS` |
| Test | `test_ai.py` 64, `test_security.py` 19 |

### Độ ổn định ✅

| Việc | Bằng chứng |
|---|---|
| Chống rò rỉ QMovie (1.5 GB → 13 MB) | `ui/gif_player.py`, `test_stability.py` |
| Lỗi trong timer không giết app | `pet_window._guarded` |
| Trần RAM 700 MB | `run.sh` |
| Sửa segfault khi đóng app | `pet_window.closeEvent` |

### Cấu trúc ✅ (vừa làm)

| Việc | Kết quả |
|---|---|
| Tách `pet_window.py` | 1467 → 1009 dòng |
| `ui/gif_player.py` | quản lý QMovie, cache, kích thước |
| `ui/window_skin.py` | cờ cửa sổ, click-through, fullscreen |
| `ui/tray_menu.py` | khay, menu, thông báo |
| `ui/pet_actions.py` | **một** chỗ thực thi hành động |
| Test module phụ | `test_ui_modules.py` 21 |
| Pyflakes sạch | `python -m pyflakes gifpet/` |

---

### Lời nhắc bền qua lần tắt app ✅

Trước: `QTimer.singleShot` chỉ sống trong tiến trình — hẹn 30 phút rồi tắt app
là mất, không báo gì.

Nay: `core/reminders.py` lưu ra `reminders.json`, ghi atomic. `PetWindow` có
`reminder_timer` quét mỗi 5 giây. Lời nhắc quá hạn quá 24 giờ bị bỏ (mở app sau
nhiều ngày không đổ ra một loạt thông báo).
Bằng chứng: `test_reminders.py` (26 test) + `test_ui_modules.py` 5 test tích hợp.

### Pet tự nói (`ai_proactive`) có tác dụng ✅

Trước: cờ có trong config, Cài đặt có checkbox, nhưng **không có gì đọc nó**.

Nay: `core/proactive.py:ProactiveBatcher` gom sự kiện trong cửa sổ 60 giây,
trần riêng 10 lượt/ngày (thấp hơn `ai_daily_limit`), không chạy trong giờ tập
trung. Chỉ nhận `long_idle`; pet đi/rơi/ngủ/click không bao giờ vào hàng đợi.
Đo được: 200 tick liên tiếp khi rảnh → **0 lần** gọi model (chỉ 1 lần sau khi
qua cửa sổ).

---

## Hạn chế đã biết của Giai đoạn 4

Ghi rõ để không hiểu nhầm là đã hoàn hảo. (Trước đây mục này nằm trong
`SECURITY.md`; đã chuyển về đây vì nó là **trạng thái**, không phải thiết kế.)

1. **Chưa kiểm tra chéo response của provider.** Tin vào cấu trúc JSON của
   Groq/Gemini; nếu họ đổi schema, `ProviderError("bad_response")` và pet báo
   lỗi (không crash) — nhưng không tự phát hiện được.

2. **Chưa có xác thực chứng chỉ tuỳ chỉnh.** Dùng CA mặc định của hệ thống.
   Môi trường có proxy chèn chứng chỉ sẽ không kết nối được.

3. **`open_url` mở bằng trình duyệt mặc định** qua `QDesktopServices`. Nếu
   máy đặt mặc định là ứng dụng lạ, ứng dụng đó nhận URL. Ngoài phạm vi kiểm
   soát của app.

4. **`open_url` không kiểm tra giá trị trả về.** Nếu không có trình duyệt,
   `openUrl()` trả `False` nhưng người dùng không thấy phản hồi gì. (~5 dòng
   để sửa.)

5. **Chưa có giới hạn theo chi phí tiền tệ**, chỉ theo số lượt và độ dài.

6. **Chưa kiểm thử trên máy có màn hình thật** — xem mục dưới.

---

## Đang có vấn đề, nên làm sớm

### 🟡 Chưa kiểm thử trên máy có màn hình thật

Toàn bộ test chạy `QT_QPA_PLATFORM=offscreen`. **Chưa ai nhìn thấy pet chuyển
động thật**: độ mượt, trong suốt, click xuyên, bong bóng thoại.

**Cần:** chạy `./run.sh` trên máy có X11/Wayland và xác nhận bằng mắt.

---

## Chưa làm — theo thứ tự tôi đề nghị

### 1. Đa nhân vật ⛔

Hạ tầng đã sẵn (`pets/<name>/`), chỉ thiếu UI chọn.

- [ ] Dropdown chọn nhân vật trong Cài đặt
- [ ] Nút "Mở thư mục pets" để người dùng tự thêm
- [ ] Kiểm tra `pet.json` hợp lệ khi chọn, báo lỗi rõ
- [ ] ~120 dòng + 8 test

### 2. Tự cập nhật ⛔

Hiện muốn cập nhật phải `git pull`. Với người dùng thường đây là rào cản.

- [ ] Kiểm tra phiên bản qua GitHub Releases API (chỉ **đọc**, không tự tải)
- [ ] Hỏi người dùng trước khi tải
- [ ] Kiểm tra checksum trước khi thay file
- [ ] ⚠️ Rủi ro: tự cập nhật là bề mặt tấn công mới. Nếu làm, phải ký gói và
      xác thực chữ ký.
- [ ] ~150 dòng + 10 test

### 3. Thông báo hệ điều hành ⛔

Hiện chỉ có `QSystemTrayIcon.showMessage` (không phải mọi DE đều hỗ trợ).

- [ ] `notify-send` trên Linux, `winrt` trên Windows, `osascript` trên macOS
- [ ] Người dùng chọn bật/tắt từng loại
- [ ] ~100 dòng + 8 test

### 4. Hành động AI mở rộng ⛔

Thêm hành động vào `ai/actions.py` là đủ hạ tầng. Ứng viên:

| Hành động | Rủi ro | Cần xác nhận |
|---|---|---|
| `play_sound` | thấp | không |
| `open_app` | cao | có — và phải giới hạn danh sách app |
| `set_volume` | trung bình | có |
| `take_screenshot` | cao (riêng tư) | có |

⚠️ Mỗi hành động mới là một bề mặt tấn công mới. Không thêm `open_app` mà
không có whitelist đường dẫn tuyệt đối.

### 5. Chủ đề / giao diện ⛔

- [ ] Sáng/tối cho menu và bong bóng thoại
- [ ] Cỡ chữ bong bóng
- [ ] ~80 dòng

### 6. Pet điều khiển trình duyệt 🟡 **chưa quyết định**

**Có yêu cầu, chưa chọn hướng, chưa code.** Ba hướng và so sánh đầy đủ:
[`BROWSER-AGENT.md`](BROWSER-AGENT.md).

| Hướng | Làm được gì | Đánh đổi |
|---|---|---|
| A — mở rộng `open_url` | Mở trang, tìm kiếm | Không đọc/bấm được; **không đụng bảo mật** |
| B — Chromium riêng (Playwright) | Đọc, bấm, gõ | +~490 MB; phải sửa `SECURITY.md` mục 7 |
| C — điều khiển trình duyệt của bạn | Đọc, bấm, gõ, dùng phiên đăng nhập | Rủi ro dữ liệu **cao**; sửa nhiều |

Ràng buộc đang cấm B và C: `SECURITY.md` mục 7 ghi ⛔ điều khiển trình duyệt,
và `test_security.py` khoá chỉ `window_skin.py` được `subprocess`. Làm B/C
**bắt buộc** sửa cả hai, có chủ đích.

Chưa quyết vì cần trả lời 7 câu hỏi trong `BROWSER-AGENT.md`, trong đó quan
trọng nhất là: **chấp nhận +490 MB và mất khả năng kiểm chứng tự động không?**

### 7. Bộ nhớ dài hạn ⛔

Thiết kế đầy đủ: [`MEMORY.md`](MEMORY.md). Chưa code.

Hiện chỉ có sổ tay do người dùng tự gõ. Thiếu: lịch sử hội thoại (hiểu "cái
kia"), memory do pet đề xuất, hạn dùng.

Đề nghị làm **lịch sử hội thoại trong RAM** trước — rủi ro gần 0 (mất khi tắt
app), giá trị cao nhất.

### 8. Nhiều pet cùng lúc ⛔

Kiến trúc hiện tại một `PetWindow` = một pet. Muốn nhiều pet phải đổi
`__main__` thành vòng lặp tạo nhiều cửa sổ. Không khó nhưng ảnh hưởng config
(mỗi pet một bộ vị trí). Chưa cần.

---

## Không làm

| Việc | Lý do |
|---|---|
| ❌ Giọng nói (Giai đoạn 5) | Đã bỏ theo yêu cầu; mic liên tục là rủi ro riêng tư |
| ❌ Điều khiển **Chrome bạn đang dùng** (CDP trên profile cá nhân, extension `<all_urls>`) | Đọc được toàn bộ việc duyệt web, cookie, mật khẩu |
| 🟡 Điều khiển **trình duyệt riêng, profile tạm** | **Chưa quyết.** Về nguyên tắc an toàn hơn dòng trên, nhưng vẫn đụng `SECURITY.md` mục 7. Xem [`BROWSER-AGENT.md`](BROWSER-AGENT.md) |
| ❌ Chạy shell từ kết quả model | Không bao giờ. Xem `docs/SECURITY.md` mục 7 |
| ❌ Đọc/ghi file tuỳ ý theo yêu cầu model | Như trên |
| ❌ Tự tải và chạy mã từ mạng | Như trên |

---

## Nguyên tắc khi thêm tính năng

Đúc kết từ những gì đã hỏng trong dự án này:

1. **Đo trước khi tin.** Rò rỉ QMovie chỉ lộ ra khi đo RSS thật. "Trông ổn"
   không phải bằng chứng.
2. **Test phải bắt được vi phạm.** Một test an toàn mà không bao giờ fail là
   test vô dụng. Đã 3 lần tôi cố tình vi phạm để kiểm chứng.
3. **Một chỗ làm một việc.** `pet_actions.py` tồn tại để chỉ có một nơi thực
   thi hành động, dễ review.
4. **Không nới lỏng test bảo mật mà không có chủ đích.** Khi Phase 4 thêm
   network, `test_security.py` được sửa để chặt hơn (chỉ `provider.py` được mở
   kết nối), không phải để pass.
5. **Ghi hạn chế vào tài liệu.** `docs/SECURITY.md` mục 8 liệt kê 7 điều chưa
   làm được. Không giấu.

---

## Lệnh thường dùng

```bash
./run.sh                  # chạy app
./run.sh --test           # toàn bộ test (273 test)
./run.sh --accept         # 17 tiêu chí nghiệm thu
./run.sh --phase3         # 16 bước vòng đời pet
.venv/bin/python -m pyflakes gifpet/    # kiểm tra import thừa
./tools/build_binary.sh   # đóng gói binary
```
