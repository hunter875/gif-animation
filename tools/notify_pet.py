#!/usr/bin/env python3
"""Gui mot thong bao cho GIF Pet tu bat ky chuong trinh nao.

Cong cu nay chi ghi MOT tep JSON vao hop thu cua pet. Pet tu doc hop thu
theo chu ky va hien thi thong bao duoi dang chu thuong. Cong cu:

- khong can PyQt, khong mo cua so, khong goi mang;
- khong chay lenh, khong mo duong dan, khong goi model AI;
- khong ghi gi ngoai thu muc hop thu.

Cach dung co ban (thu muc mac dinh lay tu cau hinh nguoi dung):

    python tools/notify_pet.py --source build --title "Xong" --message "Đã build"

Chon hop thu khac (duong dan tuong doi hoac bien moi truong):

    python tools/notify_pet.py --inbox ./inbox --source hermes \
        --title "Việc chạy nền" --message "Tác vụ đã xong" --severity success

Khi khong truyen ``--inbox``: dung ``notifications_inbox`` trong cau hinh neu
da dat, nguoc lai dung ``<thu muc cau hinh>/notifications-inbox``.

Ma thoat:
    0  da ghi thong bao
    2  tham so sai (argparse hoac du lieu khong hop le)
    3  khong ghi duoc hop thu (quyen, o dia, thu muc hong)
"""

import argparse
import os
import sys

# Cho phep chay truc tiep tu thu muc tools/ ma khong can cai dat goi.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gifpet.core.config import Config, default_inbox_dir  # noqa: E402
from gifpet.notifications.models import (  # noqa: E402
    DEFAULT_SEVERITY,
    DEFAULT_TTL_SECONDS,
    MAX_MESSAGE_LEN,
    MAX_SOURCE_LEN,
    MAX_TTL_SECONDS,
    SEVERITIES,
)
from gifpet.notifications.sender import SenderError, send  # noqa: E402

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_WRITE_FAILED = 3

# Loi do du lieu nhap sai (khac loi he thong tep/thu muc).
INPUT_REASONS = frozenset(
    {
        "bad_source",
        "bad_severity",
        "empty_content",
        "ttl_not_number",
        "ttl_too_long",
        "bad_expiry",
        "created_in_future",
        "bad_name",
        "bad_type",
    }
)

# Goi y sua loi theo ma loi cua sender/models. Chi la chu, khong hanh dong.
REASON_HINTS = {
    "bad_source": (
        "tên nguồn chỉ gồm chữ thường, số, dấu chấm, gạch dưới hoặc gạch nối "
        f"và tối đa {MAX_SOURCE_LEN} ký tự (ví dụ: build, hermes, backup.nightly)"
    ),
    "bad_severity": "mức độ phải là một trong: " + ", ".join(SEVERITIES),
    "empty_content": "cần ít nhất --title hoặc --message, không chỉ khoảng trắng",
    "ttl_not_number": "--ttl phải là số giây",
    "ttl_too_long": f"--ttl tối đa {MAX_TTL_SECONDS} giây (7 ngày)",
    "created_in_future": "đồng hồ máy đang lệch; kiểm tra lại thời gian hệ thống",
    "bad_expiry": "--ttl không hợp lệ",
    "too_long": "nội dung quá dài",
    "not_directory": "đường dẫn hộp thư đang là một tệp, không phải thư mục",
    "cannot_create": "không tạo được thư mục hộp thư",
    "write_failed": "không ghi được tệp vào hộp thư",
    "bad_name": "tên tệp thông báo không hợp lệ",
    "bad_type": "dữ liệu thông báo không hợp lệ",
}


def build_parser():
    """Tham so dong lenh. Mac dinh lay theo cau hinh cua nguoi dung."""
    parser = argparse.ArgumentParser(
        prog="notify_pet.py",
        description="Gửi một thông báo (chỉ chữ) cho GIF Pet qua hộp thư.",
        epilog=(
            "Pet không chạy lệnh, không mở đường dẫn và không gọi model AI. "
            "Nội dung được hiển thị nguyên văn dưới dạng chữ thường."
        ),
    )
    parser.add_argument(
        "--inbox",
        default=None,
        help=(
            "thư mục hộp thư; bỏ trống sẽ dùng notifications_inbox trong cấu "
            "hình của pet, nếu chưa đặt thì dùng thư mục mặc định"
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        help=f"tên chương trình gửi, chữ thường (tối đa {MAX_SOURCE_LEN} ký tự)",
    )
    parser.add_argument("--title", default="", help="tiêu đề ngắn (tùy chọn)")
    parser.add_argument(
        "--message",
        default="",
        help=f"nội dung thông báo (tối đa {MAX_MESSAGE_LEN} ký tự)",
    )
    parser.add_argument(
        "--severity",
        default=DEFAULT_SEVERITY,
        choices=list(SEVERITIES),
        help=f"mức độ, mặc định {DEFAULT_SEVERITY}",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help=(
            "số giây thông báo còn hiệu lực, "
            f"mặc định {DEFAULT_TTL_SECONDS}, tối đa {MAX_TTL_SECONDS}"
        ),
    )
    return parser


def configured_inbox():
    """Thu muc inbox trong cau hinh nguoi dung, hoac ``""`` neu chua dat.

    Chi doc cau hinh dang tep JSON (khong import Qt, khong mo mang). Cau hinh
    hong khong duoc lam hong cong cu: khi do tra ve chuoi rong.
    """
    try:
        value = Config().get("notifications_inbox")
    except Exception:  # cau hinh doc duoc nhung hong kieu du lieu
        return ""
    return str(value or "").strip()


def resolve_inbox(path):
    """Thu muc hop thu theo thu tu: ``--inbox``, cau hinh, mac dinh.

    ``--inbox`` luon thang cau hinh; bo trong ca hai thi dung
    ``default_inbox_dir()`` (thu muc cau hinh/notifications-inbox).
    """
    text = str(path or "").strip()
    if not text:
        text = configured_inbox()
    if text:
        return os.path.abspath(os.path.expanduser(text))
    return default_inbox_dir()


def describe_error(exc):
    """Cau bao loi de doc, khong lo chi tiet ky thuat dai dong."""
    reason = getattr(exc, "reason", "") or "unknown"
    hint = REASON_HINTS.get(reason, "")
    detail = getattr(exc, "detail", "") or str(exc)
    if hint:
        return f"{hint} [{reason}] {detail}".strip()
    return f"{reason}: {detail}".strip()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not str(args.title or "").strip() and not str(args.message or "").strip():
        parser.error("cần ít nhất --title hoặc --message")

    directory = resolve_inbox(args.inbox)
    try:
        notification, path = send(
            directory,
            source=args.source,
            title=args.title,
            message=args.message,
            severity=args.severity,
            ttl_seconds=args.ttl,
        )
    except SenderError as exc:
        print(f"Lỗi: {describe_error(exc)}", file=sys.stderr)
        print(f"     hộp thư: {directory}", file=sys.stderr)
        return EXIT_BAD_INPUT if exc.reason in INPUT_REASONS else EXIT_WRITE_FAILED

    print(f"Đã gửi thông báo [{notification.severity}] {notification.title}".strip())
    print(f"  nguồn : {notification.source}")
    print(f"  hộp thư: {directory}")
    print(f"  tệp   : {os.path.basename(path)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
