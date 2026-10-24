# Pet nhận thông báo dạng module

Phạm vi mới do chủ dự án chốt ngày 24/10/2026: chỉ nhận và hiển thị thông báo. Thay thế kế hoạch chat/giao việc/điều khiển trước đó; chưa có code cho kế hoạch cũ.

## Trải nghiệm

Hermes hoặc chương trình khác gửi notification → pet hiện bong bóng và tùy chọn thông báo khay → lịch sử ghi nguồn, thời gian, tiêu đề/nội dung. Người dùng bật/tắt, tạm im lặng, xem/xóa lịch sử và chọn thư mục nhận. Không có ô giao việc, nút chạy task, tool execution, URL tự mở hay API điều khiển backend. Animation/Pomodoro/reminders hiện tại giữ nguyên; không gọi model để hiển thị thông báo.

## Kiến trúc mở rộng

- Model thuần Python: version, id, source, title, message, severity, created_at, expires_at. Validate kiểu, độ dài và thời gian hữu hạn; severity chỉ info/success/warning/error. Nội dung plain text, không HTML/shell/URL action/lệnh.
- NotificationSource protocol: id, display name, poll(limit) -> notifications. Registry đăng ký implementation trusted bằng code, từ chối id trùng. Thêm source mới không sửa PetWindow. Không phải sandbox plugin không tin cậy.
- Inbox source nhận từng file JSON trong thư mục chuyên dụng. Producer ghi temp rồi replace atomic. Consumer chỉ đọc file thường, không theo symlink/reparse/hardlink đáng ngờ; giới hạn byte/file/số lượng và không đọc ngoài thư mục cấu hình. File hỏng/quá hạn được bỏ qua có chẩn đoán, không crash/spam log. Không xóa file ngoài inbox, không mở URL/artifact từ nội dung. Implementation chốt rõ ack/retention.
- Dispatcher/controller dùng Qt timer và queue bounded, rate limit và dedup theo id. Seen/history bounded riêng ở config user để hạn chế replay sau restart. Poll có lượng việc giới hạn, không network/subprocess/model trên GUI thread. Bật lại sau mute không đổ tin đã hết hạn.
- UI nhận signal, hiển thị plain text, lịch sử giới hạn, tùy chọn bubble/tray, pause/mute và chỉ báo nguồn. Không tự gọi AI hay thực thi từ notification.

## Producer CLI và Hermes

Helper tools/notify_pet.py nhận title/message/source/severity/TTL và optional inbox, tạo id/timestamp và ghi atomic. Không cần Qt, không mạng, không đọc credential. Dùng từ bất kỳ chương trình/worker nào có cùng inbox.

Mặc định inbox dưới config user (Windows APPDATA/GifAnimation); UI cho chọn inbox riêng. Hermes Docker có thể xuất vào /workspace/pet-notifications, tương ứng D:\hermes-local\workspace\pet-notifications trên host; chọn đúng thư mục đó ở pet. Tài liệu hướng dẫn JSON/producer, không sửa profile/mount/key/scheduler/command runner Hermes. Không tuyên bố mọi task Hermes tự phát tin khi chưa có auto-hook.

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
