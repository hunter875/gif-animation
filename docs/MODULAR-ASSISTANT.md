# Pet nhận thông báo dạng module

Phạm vi mới do chủ dự án chốt ngày 24/10/2026: chỉ nhận và hiển thị thông báo. Thay thế kế hoạch chat/giao việc/điều khiển trước đó; chưa có code cho kế hoạch cũ.

## Trải nghiệm

Hermes hoặc chương trình khác gửi notification → pet hiện bong bóng và tùy chọn thông báo khay → lịch sử ghi nguồn, thời gian, tiêu đề/nội dung. Người dùng bật/tắt, tạm im lặng, xem/xóa lịch sử và chọn thư mục nhận. Không có ô giao việc, nút chạy task, tool execution, URL tự mở hay API điều khiển backend. Animation/Pomodoro/reminders hiện tại giữ nguyên; không gọi model để hiển thị thông báo.

## Kiến trúc mở rộng

- Model thuần Python: version, id, source, title, message, severity, created_at, expires_at. Validate kiểu, độ dài và thời gian hữu hạn; severity chỉ info/success/warning/error. Nội dung plain text, không HTML/shell/URL action/lệnh.
- NotificationSource protocol: id, display name, poll(limit) -> notifications. Registry đăng ký implementation trusted bằng code, từ chối id trùng. Thêm source mới không sửa PetWindow. Không phải sandbox plugin không tin cậy.
- Inbox source nhận từng file JSON trong thư mục chuyên dụng. Producer ghi temp rồi replace atomic. Consumer chỉ đọc file thường, không theo symlink/reparse/hardlink đáng ngờ; giới hạn byte/file/số lượng và không đọc ngoài thư mục cấu hình. File hỏng/quá hạn được bỏ qua có chẩn đoán, không crash/spam log. Không xóa file ngoài inbox, không mở URL/artifact từ nội dung. Implementation chốt rõ ack/retention: pet **không xoá** tệp trong hộp thư và tự bỏ qua tệp đã hiển thị (dedup theo id); tệp quá hạn theo `expires_at` bị bỏ qua.
- Dispatcher/controller dùng Qt timer và queue bounded, rate limit và dedup theo id. Seen/history bounded riêng ở config user để hạn chế replay sau restart. Poll có lượng việc giới hạn, không network/subprocess/model trên GUI thread. Bật lại sau mute không đổ tin đã hết hạn.
- UI nhận signal, hiển thị plain text, lịch sử giới hạn, tùy chọn bubble/tray, pause/mute và chỉ báo nguồn. Không tự gọi AI hay thực thi từ notification.

## Producer CLI và Hermes

Helper tools/notify_pet.py nhận title/message/source/severity/TTL và optional inbox, tạo id/timestamp và ghi atomic. Không cần Qt, không mạng, không đọc credential. Dùng từ bất kỳ chương trình/worker nào có cùng inbox.

Mặc định inbox dưới config user (Windows APPDATA/GifAnimation); UI cho chọn inbox riêng. Nếu Hermes chạy trong container, xuất ra một thư mục được mount (ví dụ `/workspace/pet-notifications`), rồi chọn đúng thư mục host tương ứng của mount đó ở pet — đường dẫn tuyệt đối phụ thuộc máy, nên cấu hình qua `notifications_inbox` hoặc `--inbox` thay vì ghi cứng trong tài liệu. Tài liệu hướng dẫn JSON/producer, không sửa profile/mount/key/scheduler/command runner Hermes. Không tuyên bố mọi task Hermes tự phát tin khi chưa có auto-hook.

## Trạng thái triển khai (24/10/2026)

Đã có code, **chưa có test tự động nào được chạy trong lần sửa này** (chờ lượt chạy cuối của người phụ trách):

- `gifpet/notifications/`: `models.py`, `sender.py`, `inbox.py`, `controller.py`,
  `dispatcher.py`, `registry.py`, `state.py`.
- `gifpet/ui/notification_panel.py`: timer polling, bong bóng thoại, thông báo
  khay, cua so lịch sử, hộp thoại cài đặt, bật/tắt và tạm im.
- `NotificationSupportMixin` trong `gifpet/ui/notification_panel.py` giữ các
  phương thức vòng đời/menu chỉ dành cho thông báo
  (`_init_notification_fields`, `_setup_notifications`,
  `_apply_notification_settings`, `open_notification_history`,
  `open_notification_settings`, `toggle_notifications`,
  `toggle_notification_mute`, `_shutdown_notifications`).
  `PetWindow(QLabel, NotificationSupportMixin)` kế thừa chúng, nên
  `pet_window.py` không còn phình to và `window_skin` vẫn thấy `QLabel` là lớp
  cơ sở đầu tiên (`type(window).__mro__[1]`).
- `build_state(config)` dùng chính thư mục của `config.path` được truyền vào,
  nên hồ sơ cấu hình cách ly đúng thay vì luôn đọc `config.json` toàn cục.
- Nối vào pet: mixin gọi một lần lúc khởi động, áp dụng lại sau khi đóng Cài
  đặt, bốn mục menu khay, và dọn timer/dialog trong `quit_app`/`closeEvent`.
- `gifpet/ui/speech_bubble.py` có thêm cờ `plain` để nội dung ngoài luôn được
  hiển thị dạng chữ thường, không diễn giải HTML.
- `tools/notify_pet.py`: CLI độc lập (không cần PyQt). Không truyền `--inbox`
  thì dùng `notifications_inbox` trong cấu hình nếu có, ngược lại dùng hộp thư
  mặc định; `--inbox` truyền tay luôn được ưu tiên.

Giới hạn đã chốt: mỗi vòng quét chỉ xét tối đa 2000 mục thư mục (dùng
`islice`, không đọc thêm mục thứ 2001), tối đa 500 tệp được liệt kê, 40 tệp
được đọc, 64 KB/tệp, 512 KB tổng, 20 thông báo mỗi vòng, hàng đợi dispatcher
32 mục, chẩn đoán 10 mục, lịch sử 200 mục. Khi tạm im, thông báo đang chờ
**không** bị xoá: chúng hiện lại sau khi bỏ tạm im hoặc bị loại khi hết hạn.
Không có chat, không điều khiển tác vụ, không tự mở URL, không chạy lệnh.

Chưa làm / chưa kiểm chứng: test của DS-B chưa chạy, chạy thử tay trên Windows,
và đường dẫn inbox thật của Hermes. Không có auto-hook nào được cài trong
Hermes, nên **không** khẳng định mọi task Hermes tự gửi tin.

## Phân công

1. DS-A implementation model/protocol/registry/inbox/sender/controller, UI history/settings, wiring pet/tray, CLI và tài liệu. Chỉ thêm config notification; không xây chat/agent controller/browser/MCP hay đổi quyền AI hiện tại.
2. DS-B viết test độc lập sau implementation: payload hostile, expiry, file hỏng/quá lớn, dedup/restart, bounds/rate/mute, source extension, UI plain text, producer subprocess và regression. Chỉ sửa test được giao, cách ly APPDATA/XDG trước mọi ghi file.
3. Codex kiểm tra tool boundary, diff, tích hợp, chạy test độc lập và thử producer thật → consumer → presenter. Hai worker chạy lần lượt, không ghi chung file. Không push/deploy.

## Acceptance

- CLI thật gửi tin; pet nhận đúng nguồn/title/message/severity và hiển thị, consumer không gọi AI/subprocess/network.
- Source giả đăng ký qua registry chạy được không sửa PetWindow/controller.
- File malformed/sai kiểu/quá lớn/quá hạn, HTML/control text, path escape/symlink không crash/chạy lệnh/mở URL/đọc ngoài inbox.
- Dedup trong phiên và sau restart theo chính sách ghi rõ; history/queue/workload bounded. Một source lỗi không khóa source khác.
- Enable/mute/bubble/tray rõ ràng; clear history không vô tình replay tin cũ. Không tự ghi notification thành user memory/secret.
- Chạy test mới và regression cũ trong config tạm, tách lỗi/skip nền khỏi lỗi mới. Không sửa assertion để che defect.
- Roadmap ghi đúng implemented/verified/pending. Không đánh dấu auto-hook Hermes hay desktop thật/OS chưa test là hoàn tất từ offscreen.

## Ngoài phạm vi

Giao việc/điều khiển Hermes/module khác, chat/history hội thoại, hủy task backend, browser live view, MCP tools, cloud, Facebook, scheduler và tự học sở thích. Lỗi cũ ngoài notification (AI network blocking, Gemini mặc định, global hotkey, Windows fullscreen) xử lý riêng.
