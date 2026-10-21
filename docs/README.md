# Tài liệu

Bộ tài liệu của GIF Pet. Mỗi file có **một mục đích rõ ràng** — nếu bạn đang
tìm thứ gì, bảng dưới nói nên đọc file nào.

## Bắt đầu đọc ở đâu

| Bạn muốn… | Đọc |
|---|---|
| Chạy thử app | [`../README.md`](../README.md) |
| Hiểu code tổ chức ra sao | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Biết cái gì đã xong, cái gì chưa | [`ROADMAP.md`](ROADMAP.md) |
| Thêm tính năng mà không phá bảo mật | [`SECURITY.md`](SECURITY.md) |
| Sửa một module cụ thể | [`MODULES.md`](MODULES.md) |
| Thiết kế AI agent dùng trình duyệt | [`BROWSER-AGENT.md`](BROWSER-AGENT.md) |
| Thiết kế bộ nhớ dài hạn | [`MEMORY.md`](MEMORY.md) |
| Tra lỗi đã gặp và cách sửa | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |

## Nguyên tắc của bộ tài liệu này

1. **Tách thiết kế khỏi trạng thái.** `SECURITY.md` mô tả *phải làm gì*;
   `ROADMAP.md` nói *đã làm được đến đâu*. Trước đây hai thứ trộn trong một
   file, dẫn đến chỗ đọc xong tưởng đã có tính năng chưa hề code.

2. **Mọi khẳng định phải kiểm chứng được.** Khi doc nói "đã sửa", phải chỉ ra
   được test hoặc lệnh chứng minh. Khi doc nói "chưa có", không được giấu.

3. **Ghi rõ điều không làm, kèm lý do.** Danh sách "không làm" quan trọng
   ngang danh sách tính năng — nó ngăn người sau tự ý thêm thứ nguy hiểm.

4. **Số liệu phải đo, không phỏng đoán.** Ví dụ "rò rỉ 1.5 GB" là số đo thật,
   không phải ước lượng.

## Cấu trúc

```
docs/
├── README.md            file này — mục lục
├── ARCHITECTURE.md      code tổ chức thế nào, vì sao
├── MODULES.md           từng module làm gì, đụng vào thì ảnh hưởng gì
├── SECURITY.md          ràng buộc bảo mật (thiết kế, không phải trạng thái)
├── ROADMAP.md           đã xong / đang làm / chưa làm / không làm
├── BROWSER-AGENT.md     thiết kế AI agent dùng trình duyệt (CHƯA CODE)
├── MEMORY.md            thiết kế bộ nhớ dài hạn (CHƯA CODE)
└── TROUBLESHOOTING.md   lỗi đã gặp, nguyên nhân, cách sửa
```

## Quy ước khi viết thêm doc

- Ghi rõ **ngày hoặc commit** khi mô tả trạng thái, vì trạng thái sẽ cũ.
- Việc chưa làm thì đánh dấu ⛔ hoặc ghi "(chưa code)" **ngay trong tiêu đề**.
- Đừng mô tả tính năng trong tài liệu kiến trúc; kiến trúc chỉ mô tả cái đang có.
