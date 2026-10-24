# Kiểm chứng module thông báo — 24/10/2026

Phạm vi đã tích hợp: nhận và hiển thị thông báo. Revision code được kiểm tra:
`7b5d75ae2779272344c4ffb1b0004057986b91c7`. Không build binary hoặc push.

## Kết quả

| Kiểm tra thực tế | Kết quả |
|---|---|
| Core notification Windows | 91 đạt, 1 skip do không có quyền tạo symlink |
| Producer CLI Windows | 20/20 đạt |
| UI Qt offscreen Windows | 28/28 đạt |
| Core Linux, có symlink thật | 92/92 đạt |
| Bộ unit test cũ Windows | 265 đạt, 3 assertion failure, 1 error, 4 skip |
| Acceptance / lifecycle cũ | 17/17 và 16/16 đạt |
| Producer subprocess → inbox → Qt bubble/history | Đạt; nội dung HTML hiện nguyên văn; đóng cửa sổ dừng timer |

Các test chạy bằng Python 3.13, PyQt5 5.15.11/Qt 5.15.2 trên Windows,
với APPDATA/XDG tạm và Qt offscreen. Không dùng cấu hình/key người dùng.
Linux chỉ chạy core thuần Python trong container không mạng, user 10000,
root filesystem readonly, bỏ toàn bộ capabilities, no-new-privileges,
CPU 1, RAM 512 MB, pids 128; chỉ mount code/test readonly, không mount
credential hay Docker socket. Cấu hình thực đã được inspect trước khi chạy;
container test đã xoá sau khi lấy log. Không build image mới.

Kiểm chứng độc lập bổ sung: hardlink bị thay giữa lstat và open bị từ chối
sau khi mở descriptor; tên file drive/ADS bị chặn tại IO; JSON không liên
quan và JSON hỏng không bị ack xoá; xoá history vẫn giữ dedup sau restart;
mute giữ tin còn hạn; đổi inbox giữ nguồn custom; quét thư mục dừng đúng
2000 entry; core không import Qt. Đây là bằng chứng các tình huống đã chạy,
không phải bảo đảm chống mọi tiến trình đối địch trên máy.

## Bốn lỗi nền còn lại

Đã xuất hiện trong review trước tính năng và còn nguyên ở regression cuối:

- `TestMemory.test_them_va_doc`: fixture dựa vào XDG, chưa cách ly APPDATA
  theo từng case trên Windows nên các case dùng chung memory.
- `TestGifLibrary.test_duong_dan_windows_khong_lam_crash`: giả định một
  đường dẫn Windows không tồn tại nhưng fixture có thể tồn tại thật.
- `TestGifLibrary.test_resolve_giu_duong_dan_tuyet_doi`: giả định đường dẫn
  POSIX giữ nguyên khi chạy trên Windows.
- `TestMovieCache.test_xoa_gif_thi_giai_phong_cache`: WinError 32 khi xoá
  GIF đang được QMovie giữ file.

Không sửa bộ cũ để che lỗi. Các regression mới phát hiện trong lượt triển
khai (menu sync, độ dài PetWindow, đường dẫn cá nhân trong README) đã sửa;
`test_ui_modules.py` cuối đạt 25/25. Bộ tổng thể chưa hoàn toàn xanh.

## Phân công thực tế

- DS-A là DeepSeek Harness thật qua OpenCode Go: triển khai module core,
  UI/settings/history/tray, CLI và sửa các lỗi được giao.
- DS-B là DeepSeek Harness thật: viết ba file test riêng và sửa fixture theo
  review. Worker không chạy shell/test; Codex chạy các lệnh kiểm chứng.
- Codex: scope/roadmap/contracts, kiểm tra tool boundary, review diff,
  tích hợp, chạy regression và probe độc lập; sửa fixture test. Sau lỗi stream
  của lượt DSH cuối, Codex sửa trực tiếp hai accessor UI nhỏ theo ngoại lệ
  SIMPLE của rule; không nhận đó là code của worker.

Các lượt worker chạy tuần tự, file ownership riêng, scoped-file tools được
kiểm tra trước dispatch; không có shell/network/cloud/delegation tools.
Không có bằng chứng sandbox OS đầy đủ cho tiến trình DSH. Docker nêu trên
là môi trường chạy test của Codex, không phải sandbox của worker.
Không chấp nhận kết quả worker chỉ dựa trên exit 0 hoặc tự khai PASS;
các lần sai schema/lỗi stream được lưu nguyên và kiểm tra code độc lập.

## Cách tái chạy và bằng chứng

Trong môi trường đã cài dependencies, dùng cấu hình tạm cho cả APPDATA và
XDG_CONFIG_HOME, đặt `QT_QPA_PLATFORM=offscreen`, rồi chạy:

```text
python tests/test_notifications.py -v
python tests/test_notification_cli.py -v
python tests/test_notification_ui.py -v
```

Log và scripts kiểm chứng của lượt này nằm ngoài source checkout ở thư mục
artifact cùng cấp workspace, `artifacts/gif-notifications-20261024`:

- `integrated-final/results.json` và log từng file: regression cuối.
- `safety-results.json`, `verify_safety.py`: probe IO/state/source độc lập.
- `ui-probe.json`, `probe_ui.py`, `notification-panel.png`: CLI thật và UI render.
- `linux-results.json`, `linux-isolation.json`, `linux-tests.log`: core Linux
  và cấu hình container thực. Cấu hình ban đầu chưa đạt được giữ trong file
  `linux-isolation-initial.json`; container đó không được chạy.

Baseline trước tính năng: `artifacts/gif-review-20261024/REVIEW.md` và
`test-results.json`. Contracts/kết quả worker giữ trong artifact lượt này
và `artifacts/opencode-team`. Telemetry do adapter ghi nhận khi provider cung
cấp; không suy ra chi phí USD hoặc mức tiết kiệm token từ số liệu này.

## Giới hạn còn lại

Chưa kiểm tra thao tác tay desktop Windows, OS tray toast, chạy ngâm hay RAM
trên Windows. UI offscreen có render ảnh thực nhưng không chứng minh hành
vi của shell Windows. Chưa cài hook/mount Hermes thật nên chưa tự báo mọi
task hoàn thành. Có producer CLI và protocol/registry để các nguồn trusted
gửi tin; không có chức năng giao việc/điều khiển mới và không gọi model để
hiển thị thông báo. Các tính năng pet/AI cũ không thuộc phạm vi thay đổi.
