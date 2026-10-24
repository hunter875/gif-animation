# Pet trợ lý dạng module

Kế hoạch được chủ dự án duyệt ngày 24/10/2026. Đây là thiết kế và acceptance criteria; chỉ đánh dấu đã triển khai sau khi kiểm tra code và chạy test.

## Mục tiêu và luồng sử dụng

Giữ pet, animation, Pomodoro và reminders chạy local. Thêm khung chat cạnh pet có lịch sử phiên, bộ chọn module, tiến độ, nút dừng và kết quả. Lệnh do người dùng nhập trực tiếp được giao cho module đã chọn; model không được tự đổi module hoặc cấp thêm quyền. Không gọi model cho hoạt ảnh, đi/ngủ hoặc cập nhật tiến độ.

Luồng: người dùng mở chat từ khay/phím tắt → chọn Chat hiện có hoặc Hermes Docker → nhập việc → gửi → theo dõi trạng thái → dừng khi cần hoặc nhận kết quả/thông báo. Chỉ một tác vụ foreground chạy mỗi lúc trong MVP, không cho auto-retry gây tác dụng phụ lặp lại.

## Hợp đồng module

- Request gồm task id, module id, nội dung người dùng, session id thuộc module nếu có và context hội thoại có giới hạn.
- Manifest gồm id ổn định, tên hiển thị, mô tả quyền/capability, khả năng hủy và khả năng tiếp tục phiên.
- Module cung cấp chạy request, phát sự kiện tiến độ và nhận tín hiệu hủy; trả result có trạng thái, nội dung, session id và artifact nếu có. Không phụ thuộc Qt trong protocol và module nghiệp vụ.
- Registry đăng ký rõ ràng các implementation; từ chối id trùng/không tồn tại. Không import đường dẫn hoặc thực thi command do model trả về. Việc thêm module viết bằng code trusted, không phải sandbox plugin không tin cậy.
- Controller điều phối background execution và chuyển sự kiện qua signal về UI thread. Trạng thái: queued/running/cancelling/succeeded/failed/cancelled. Bỏ event muộn của task đã kết thúc, không báo thành công khi mới nhận exit code 0 hoặc khi hủy chưa được backend xác nhận.
- Conversation history giới hạn số lượt/kích thước; mặc định RAM. Kết quả model và lịch sử không tự ghi thành sở thích dài hạn.

## Module ban đầu

1. Chat local: dùng Brain/provider hiện có, giữ whitelist và xác nhận hành động trên UI thread. Request mạng chạy background. Luồng proactive cũng không được gọi mạng trực tiếp trên Qt timer. UI phải giữ thao tác được và phản hồi rõ khi provider lỗi.
2. Hermes Docker: nối runtime có sẵn qua Docker CLI, container mặc định `hermes-ui`; gọi `hermes chat --query-file - --format stream-json --oneshot` và resume theo session id thật khi backend hỗ trợ. Không đọc API key/dashboard password trên host, không dùng shell=True, không nhận executable/argv từ prompt hay model. Khi thiếu Docker/container/CLI phải báo lỗi có ích.
3. Bộ nhớ người dùng: dùng note store hiện có, cho xem/thêm/sửa/xóa rõ ràng. Transcript là dữ liệu hội thoại, không nhập vào trusted instructions và không tự biến thành user_note.

Hermes là dịch vụ agent riêng đã có quyền trong container của nó; registry không biến toàn bộ backend đó thành công cụ an toàn tuyệt đối. Hiển thị quyền của module cho người dùng khi chọn. Không tự cấu hình tài khoản cá nhân, cloud deploy, messaging hoặc lịch chạy nền trong MVP.

## Hủy và vòng đời

Hủy phải tới được tác vụ backend, không chỉ đóng cửa sổ hoặc kill Docker client. Với Hermes cần bridge có id/ack và quản lý process group trong container. Không kill container, không kill tác vụ khác, không shell ghép prompt. Hủy xong mới cho khởi chạy việc tiếp theo. Nếu backend không xác nhận, trạng thái là lỗi/không xác định; không nói đã dừng thật. Đóng panel có thể ẩn trong lúc task tiếp tục; thoát app yêu cầu dừng và cleanup có giới hạn, không để QThread bị hủy khi còn chạy.

Thông báo chỉ phát một lần khi hoàn thành/lỗi/cần người dùng; không đọc bí mật hoặc toàn bộ log vào bong bóng. Chỉ mở artifact/URL đã kiểm tra và do người dùng bấm, không tự mở đường dẫn từ output model.

## Cách triển khai và phân công

- DS-A: implementation module protocol/registry/controller, local Chat/Hermes adapters, panel và wiring, notes CRUD; sửa lỗi UI blocking, error guard và numeric config có liên quan. Cập nhật tài liệu chức năng, hướng dẫn chạy và giới hạn backend.
- DS-B: sau khi có implementation, viết test ở các file được giao, kiểm tra độc lập behavior và Windows test isolation; không sửa product code. Nêu defect kèm repro, không sửa assertion chỉ để test xanh.
- Codex: xác minh ranh giới công cụ, giao contract đúng Git SHA, đọc diff, tích hợp, chạy test độc lập và test Hermes thật nhỏ. DSH không có shell/network/cloud trong lượt sửa code; supervisor thực hiện dependency/test/runtime operations.
- Hai worker chạy lần lượt, write scope riêng, không thay đổi key/config Hermes đang dùng. Không tự push/merge/deploy.

## Acceptance bắt buộc

- Thêm module giả bằng registry mà không sửa PetWindow/controller, chạy được request và nhận đúng sự kiện/result.
- Provider giả chậm không chặn heartbeat Qt; cả chat chủ động và proactive dùng đường background. Không chạm QWidget từ worker thread.
- Một task mỗi lúc, lỗi có ích, event muộn không ghi đè task mới; hủy/thoát không rò process/thread; không báo hủy khi backend còn chạy.
- Chat có lịch sử phiên, clear history, chọn module, trạng thái, send/cancel; giữ tính năng pet/Pomodoro/reminders cũ.
- Hermes smoke thật trả session/result từ container; kiểm thử cancel thật ở bridge bằng process kiểm soát, không tác động container/tác vụ khác. Không giả live integration bằng mock.
- Notes xem/thêm/sửa/xóa; không tự lưu output model thành note. Context có giới hạn và session id thuộc đúng module.
- Test harness cách ly APPDATA và XDG theo test/process trước mọi ghi file; không đọc/xóa cấu hình thật. Chạy unit tests và acceptance/lifecycle hiện có. Ghi rõ skip/khác biệt OS.
- Kiểm tra input/argv/path và tình huống thiếu backend; Git diff không có secret hoặc thay đổi ngoài scope.

## Để sau MVP

MCP adapter có quyền theo tool, browser live-view, nhiều task song song, scheduler và task persistence/resume sau khi app bị kill, automatic preference learning, OS-global hotkey, Windows fullscreen integration. Không đánh dấu các mục này hoàn thành chỉ vì có registry. Không cần cài MCP framework hay browser engine mới cho MVP này.
