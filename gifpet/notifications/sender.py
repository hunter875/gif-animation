"""Ghi thong bao ra inbox theo kieu atomic.

Producer co the la bat ky chuong trinh nao (script Python, hook, container
Hermes) mien la ghi duoc mot tep JSON vao thu muc inbox. Module nay la ban
tham chieu dung chung cho ``tools/notify_pet.py`` va cho test.

Vi sao atomic:

- Pet doc inbox lien tuc. Neu producer ghi truc tiep, pet co the doc phai tep
  ghi do va bao "bad_json" lien tuc.
- Cach lam: ghi tep tam ``.tmp`` cung thu muc (cung o dia nen ``os.replace``
  la thao tac nguyen tu), ``flush`` + ``fsync``, roi ``os.replace`` sang ten
  ``.json``. Ten bat dau bang dau cham nen ``Inbox.names`` bo qua.
- Khong ghi ra ngoai thu muc inbox; khong tu tao thu muc ngoai y muon
  (caller phai tao bang ``ensure_inbox``).
"""

import json
import os
import re
import tempfile

from gifpet.notifications.models import (
    DEFAULT_SEVERITY,
    DEFAULT_TTL_SECONDS,
    NotificationError,
    PetNotification,
)

TEMP_PREFIX = ".notify-"
TEMP_SUFFIX = ".tmp"

# Ten di dong duoc: khong dau hai cham (o dia ``Z:``, ADS ``a:b``), khong
# khoang trang, khong ky tu dieu khien, khong dau cham o dau, khong ``.``/``..``.
_PORTABLE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_RESERVED_WINDOWS = frozenset(
    ("CON", "PRN", "AUX", "NUL")
    + tuple(f"COM{i}" for i in range(1, 10))
    + tuple(f"LPT{i}" for i in range(1, 10))
)


def portable_json_name(ident):
    """Ten tep ``<id>.json`` an toan da nen tang, hoac ``None`` neu id xau."""
    if not isinstance(ident, str) or not _PORTABLE_NAME.match(ident):
        return None
    if ident in (".", ".."):
        return None
    if ident.split(".", 1)[0].upper() in _RESERVED_WINDOWS:
        return None
    return f"{ident}.json"


class SenderError(RuntimeError):
    """Khong ghi duoc thong bao. ``reason`` la ma ngan."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def ensure_inbox(directory):
    """Tao thu muc inbox neu chua co. Tra ve duong dan da chuan hoa."""
    path = os.path.abspath(str(directory))
    if os.path.exists(path) and not os.path.isdir(path):
        raise SenderError("not_directory", path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise SenderError("cannot_create", str(exc))
    return path


def write_notification(directory, notification):
    """Ghi ``notification`` thanh mot tep JSON trong ``directory``.

    Tra ve duong dan tep vua tao. Tep khong bao gio ton tai o trang thai
    nua voi: hoac chua co, hoac day du.
    """
    if not isinstance(notification, PetNotification):
        raise SenderError("bad_type", type(notification).__name__)
    # Ten tep duoc suy ra tu id, nen id phai la ten di dong duoc: chan tien to
    # o dia (``Z:``), ADS, dau hai cham, duong dan va ky tu dieu khien truoc
    # khi noi vao thu muc inbox.
    name = portable_json_name(notification.id)
    if name is None:
        raise SenderError("bad_name", str(notification.id)[:64])
    path = ensure_inbox(directory)
    target = os.path.join(path, name)
    payload = notification.to_dict()

    handle = None
    temp_path = None
    try:
        handle, temp_path = tempfile.mkstemp(
            prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX, dir=path
        )
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        handle = None
        os.replace(temp_path, target)
        temp_path = None
    except OSError as exc:
        raise SenderError("write_failed", str(exc))
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return target


def send(directory, source, title, message, severity=DEFAULT_SEVERITY,
         ttl_seconds=DEFAULT_TTL_SECONDS, id=None, now=None):
    """Tao va ghi mot thong bao. Tra ve ``(notification, path)``."""
    try:
        notification = PetNotification.build(
            source=source,
            title=title,
            message=message,
            severity=severity,
            ttl_seconds=ttl_seconds,
            id=id,
            now=now,
        )
    except NotificationError as exc:
        raise SenderError(exc.reason, exc.detail)
    return notification, write_notification(directory, notification)
