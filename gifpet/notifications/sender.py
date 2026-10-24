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
import tempfile

from gifpet.notifications.models import (
    DEFAULT_SEVERITY,
    DEFAULT_TTL_SECONDS,
    NotificationError,
    PetNotification,
)

TEMP_PREFIX = ".notify-"
TEMP_SUFFIX = ".tmp"


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
    path = ensure_inbox(directory)
    name = f"{notification.id}{'.json'}"
    if os.sep in name or "/" in name or name.startswith("."):
        raise SenderError("bad_name", notification.id)
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
