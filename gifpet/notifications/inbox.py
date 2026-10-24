"""Doc thong bao tu thu muc inbox chuyen dung.

Inbox la mot thu muc rieng (mac dinh nam trong thu muc cau hinh cua pet, hoac
mot thu muc chia se voi chuong trinh khac nhu Hermes). Moi thong bao la mot
tep JSON nho do producer ghi kieu atomic.

Phong thu quan trong nhat cua module nay la **chi doc trong thu muc da cau
hinh**. Cu the:

- Chi xet tep co duoi ``.json`` (ten khong bat dau bang dau cham, nen tep
  tam ``.tmp`` bi bo qua).
- Khong di theo symlink/reparse point, khong doc hardlink (so link > 1):
  do la cach pho bien de keo pet doc tep ngoai thu muc.
- Ten tep khong duoc chua duong dan, khong duoc la ``.``/``..``.
- Gioi han tung luot: so tep liet ke, so tep doc, so byte moi tep, so byte
  tong, so thong bao tra ve.
- Tep hong hay qua gioi han: bo qua va tang bo dem chan doan; chi in log
  theo nhip (``diagnostic_interval``) de khong spam terminal.
- Gioi han bo dem chan doan: chi giu ``DIAGNOSTIC_SAMPLES`` mau gan nhat.

Module nay **khong** goi mang, khong chay lenh, khong import dong.
"""

import json
import os
import time

from gifpet.notifications.models import NotificationError, PetNotification
from gifpet.notifications.protocol import NotificationSource

# Gioi han cung. Owner co the ha thap qua config nhung khong the nang cao.
MAX_FILES_LISTED = 500
MAX_FILES_READ = 40
MAX_FILE_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 512 * 1024
MAX_NOTIFICATIONS_PER_POLL = 20
DIAGNOSTIC_SAMPLES = 5
DIAGNOSTIC_INTERVAL_SECONDS = 30.0

INBOX_SUFFIX = ".json"

# Windows: FILE_ATTRIBUTE_REPARSE_POINT. os.lstat bao cao co nay cho junction
# va symlink, nen chan duoc ca truong hop `islink` khong bat.
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class InboxProblem(Exception):
    """Thu muc inbox khong dung duoc. ``reason`` la ma ngan."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def is_safe_name(name):
    """Ten tep an toan: khong duong dan, khong dau cham, khong cham tron."""
    if not isinstance(name, str) or not name:
        return False
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    if name in (".", "..") or name.startswith("."):
        return False
    return name.endswith(INBOX_SUFFIX)


class Inbox:
    """Thu muc inbox: liet ke, doc an toan va don tep da xu ly.

    ``reject_hardlinks``/``follow_symlinks`` de ``True`` va khong nen doi:
    chi de test mo phong truong hop nen tang khong bao cao duoc link count.
    """

    def __init__(self, directory, max_file_bytes=MAX_FILE_BYTES,
                 max_files=MAX_FILES_READ, now=None):
        self.directory = str(directory)
        self.max_file_bytes = min(MAX_FILE_BYTES, max(256, int(max_file_bytes)))
        self.max_files = max(1, min(MAX_FILES_READ, int(max_files)))
        self._now = now or time.time
        self._last_diagnostic = 0.0
        self.diagnostics = []      # (thoi diem, ten tep, ly do) - toi da 5
        self.bytes_read = 0

    # ------------------------------------------------------------------
    # Kiem tra thu muc
    # ------------------------------------------------------------------
    def check(self):
        """Xac nhan thu muc ton tai, la thu muc that, khong phai symlink."""
        path = self.directory
        if not path:
            raise InboxProblem("empty_path")
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise InboxProblem("missing", path)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))
        if _is_link(info):
            raise InboxProblem("symlink", path)
        if not os.path.isdir(path):
            raise InboxProblem("not_directory", path)
        return True

    # ------------------------------------------------------------------
    # Liet ke
    # ------------------------------------------------------------------
    def names(self):
        """Ten tep ``.json`` an toan, sap xep theo ten, toi da gioi han."""
        try:
            entries = list(os.scandir(self.directory))
        except FileNotFoundError:
            raise InboxProblem("missing", self.directory)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))

        names = []
        for entry in entries:
            if len(names) >= MAX_FILES_LISTED:
                self._diagnose("<listing>", "too_many_files")
                break
            try:
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                continue
            if not is_file:
                continue
            if not is_safe_name(entry.name):
                continue
            names.append(entry.name)
        names.sort()
        return names

    # ------------------------------------------------------------------
    # Doc
    # ------------------------------------------------------------------
    def read(self, name):
        """Doc mot tep va tra dict JSON. Ném ``InboxProblem`` neu khong an toan."""
        if not is_safe_name(name):
            raise InboxProblem("unsafe_name", repr(name)[:64])
        path = os.path.join(self.directory, name)

        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise InboxProblem("vanished", name)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))

        # Symlink/reparse: lstat bao cao link, con islink bat ca Windows.
        if _is_link(info) or os.path.islink(path):
            raise InboxProblem("symlink", name)
        if not _is_regular(info):
            raise InboxProblem("not_regular_file", name)
        if getattr(info, "st_nlink", 1) > 1:
            raise InboxProblem("hardlink", name)
        size = getattr(info, "st_size", 0)
        if size > self.max_file_bytes:
            raise InboxProblem("too_large", f"{name} ({size} bytes)")
        if size <= 0:
            raise InboxProblem("empty_file", name)

        try:
            with open(path, "rb") as handle:
                # Doc toi da +1 byte: tep phinh ra giua lstat va read van
                # bi cat, khong bao gio doc khong gioi han.
                raw = handle.read(self.max_file_bytes + 1)
        except FileNotFoundError:
            raise InboxProblem("vanished", name)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))
        if len(raw) > self.max_file_bytes:
            raise InboxProblem("too_large", name)
        self.bytes_read += len(raw)

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise InboxProblem("not_utf8", name)
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, RecursionError):
            raise InboxProblem("bad_json", name)
        if not isinstance(payload, dict):
            raise InboxProblem("not_object", name)
        return payload

    # ------------------------------------------------------------------
    # Kich thuoc
    # ------------------------------------------------------------------
    def _size_of(self, name):
        """Kich thuoc tep da qua cung kiem tra an toan (khong doc noi dung)."""
        if not is_safe_name(name):
            raise InboxProblem("unsafe_name", repr(name)[:64])
        path = os.path.join(self.directory, name)
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise InboxProblem("vanished", name)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))
        if _is_link(info) or os.path.islink(path):
            raise InboxProblem("symlink", name)
        if not _is_regular(info):
            raise InboxProblem("not_regular_file", name)
        if getattr(info, "st_nlink", 1) > 1:
            raise InboxProblem("hardlink", name)
        return max(0, int(getattr(info, "st_size", 0)))

    # ------------------------------------------------------------------
    # Mot luot doc
    # ------------------------------------------------------------------
    def poll(self, limit=MAX_NOTIFICATIONS_PER_POLL, now=None):
        """Doc cac tep moi nhat, tra ``(notifications, names_handled)``.

        ``names_handled`` gom ca tep hong de caller don chung di (tranh doc
        lai mai mai). Caller chi nen xoa khi da "ack" (xem ``controller``).
        """
        current = self._now() if now is None else float(now)
        limit = max(1, min(MAX_NOTIFICATIONS_PER_POLL, int(limit)))
        budget = MAX_TOTAL_BYTES
        results = []
        names_total = []
        handled = []

        try:
            names = self.names()
        except InboxProblem as exc:
            self._diagnose("<inbox>", exc.reason)
            return results, handled

        for name in names:
            if len(names_total) >= self.max_files:
                self._diagnose(name, "max_files_exceeded")
                break
            if len(results) >= limit:
                # Het cho trong queue cua luot nay: tep van nam tren dia va
                # se duoc doc o luot sau, khong bi coi la da xu ly.
                break
            names_total.append(name)
            try:
                before = self._size_of(name)
            except InboxProblem as exc:
                handled.append(name)
                self._diagnose(name, exc.reason)
                continue
            if before > budget:
                # Qua ngan sach byte cua luot nay: don cac tep da xu ly roi
                # dung. Tep qua lon (hoac cac tep dung sau no) duoc xet lai o
                # luot sau, khong bao gio lam nghen ca hang doi.
                self._diagnose(name, "total_bytes_exceeded")
                break
            budget -= before
            try:
                payload = self.read(name)
                notification = PetNotification.parse(payload, now=current)
            except InboxProblem as exc:
                handled.append(name)
                self._diagnose(name, exc.reason)
                continue
            except NotificationError as exc:
                handled.append(name)
                self._diagnose(name, exc.reason)
                continue
            handled.append(name)
            if notification.expired(current):
                self._diagnose(name, "expired")
                continue
            results.append(notification)
        return results, handled

    # ------------------------------------------------------------------
    # Don tep da xu ly (ack)
    # ------------------------------------------------------------------
    def remove(self, name):
        """Xoa mot tep da xu ly. Khong bao gio xoa ngoai thu muc inbox."""
        if not is_safe_name(name):
            return False
        path = os.path.join(self.directory, name)
        try:
            info = os.lstat(path)
        except OSError:
            return False
        if _is_link(info) or not _is_regular(info):
            return False
        try:
            os.unlink(path)
        except OSError:
            return False
        return True

    def acknowledge(self, names):
        removed = 0
        for name in names:
            if self.remove(name):
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Chan doan
    # ------------------------------------------------------------------
    def _diagnose(self, name, reason):
        """Ghi mot mau chan doan, in log theo nhip de khong spam terminal."""
        self.diagnostic_count += 1
        self.skipped_count += 1
        self.diagnostics.append((self._now(), name, reason))
        if len(self.diagnostics) > DIAGNOSTIC_SAMPLES:
            del self.diagnostics[: len(self.diagnostics) - DIAGNOSTIC_SAMPLES]
        now = self._now()
        if now - self._last_diagnostic >= DIAGNOSTIC_INTERVAL_SECONDS:
            self._last_diagnostic = now
            print(
                f"[thông báo] bỏ qua dữ liệu không hợp lệ trong inbox: "
                f"{reason} ({name}) - tổng {self.diagnostic_count} lần"
            )

    def reset_diagnostics(self):
        self.diagnostics = []
        self.diagnostic_count = 0
        self.skipped_count = 0
        self.bytes_read = 0
        self._last_diagnostic = 0.0


class InboxSource(NotificationSource):
    """Nguon thong bao doc tu thu muc inbox.

    ``poll`` tra ve danh sach ``PetNotification``; tep da xu ly duoc ghi nho
    trong ``pending_ack`` de controller xoa sau khi hien thi xong.
    """

    source_id = "inbox"
    display_name = "Hộp thư JSON"

    def __init__(self, directory, max_file_bytes=MAX_FILE_BYTES,
                 max_files=MAX_FILES_READ, now=None):
        self.inbox = Inbox(directory, max_file_bytes=max_file_bytes,
                           max_files=max_files, now=now)
        self.pending_ack = []

    def poll(self, limit):
        notifications, handled = self.inbox.poll(limit)
        self.pending_ack.extend(handled)
        return notifications

    def take_ack(self):
        """Tra ve va xoa danh sach ten tep can don."""
        names = self.pending_ack
        self.pending_ack = []
        return names


def _is_link(info):
    """True neu stat tra ve symlink hay reparse point (Windows junction)."""
    if os.path.islink is not None:
        try:
            mode = info.st_mode
        except AttributeError:
            mode = 0
        if mode and (mode & 0o170000) == 0o120000:
            return True
    attrs = getattr(info, "st_file_attributes", 0)
    if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return False


def _is_regular(info):
    try:
        mode = info.st_mode
    except AttributeError:
        return True
    return (mode & 0o170000) == 0o100000
