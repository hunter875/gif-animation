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
- Ten tep khong duoc chua duong dan, dau hai cham (o dia/ADS), ky tu dieu
  khien, khong duoc la ``.``/``..`` hay ten thiet bi Windows (``CON``...).
- Gioi han tung luot: so muc thu muc duyet (``MAX_DIR_ENTRIES``), so tep liet
  ke, so tep doc, so byte moi tep, so byte tong, so thong bao tra ve. Duyet
  ``os.scandir`` kieu lazy, khong vat chat hoa ca thu muc. Luot liet ke chi
  tieu thu dung ``MAX_DIR_ENTRIES`` muc (``islice``), khong doc them muc thu
  cap+1 chi de biet "con nua hay khong"; cham tran chi tang chan doan.
- Tep hong hay qua gioi han: bo qua va tang bo dem chan doan; chi in log
  theo nhip (``diagnostic_interval``) de khong spam terminal.
- Gioi han bo dem chan doan: chi giu ``DIAGNOSTIC_SAMPLES`` mau gan nhat.
- Ack chi xoa tep JSON **hop le cau truc** va co id trung ten tep; tep khac
  (``package.json``, JSON hong, tep khong khop) duoc giu nguyen.

Module nay **khong** goi mang, khong chay lenh, khong import dong.
"""

import itertools
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

# Ten tep dai nhat chap nhan: id toi da 96 ky tu + hau to ``.json`` + du phong.
MAX_NAME_LEN = 128
# Ten thiet bi Windows (CON, NUL, COM1...) khong bao gio la ten tep hop le.
_RESERVED_NAMES = frozenset(
    ("CON", "PRN", "AUX", "NUL")
    + tuple(f"COM{i}" for i in range(1, 10))
    + tuple(f"LPT{i}" for i in range(1, 10))
)

# Gioi han co dinh cho mot luot ``names()``: so muc thu muc duoc xem xet
# (truoc khi loc). Thu muc lon khong lam luot poll cham vo han.
MAX_DIR_ENTRIES = 2000

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
    """Ten tep an toan: chi ten di dong duoc, khong duong dan/ADS/dieu khien."""
    if not isinstance(name, str) or not name:
        return False
    if len(name) > MAX_NAME_LEN:
        return False
    if any(ord(ch) < 32 or ord(ch) == 0x7F for ch in name):
        return False
    if "/" in name or "\\" in name or ":" in name or "\x00" in name:
        return False
    if name in (".", "..") or name.startswith("."):
        return False
    stem = name[: -len(INBOX_SUFFIX)] if name.endswith(INBOX_SUFFIX) else name
    if stem.upper() in _RESERVED_NAMES:
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
        self.diagnostic_count = 0
        self.skipped_count = 0
        self.bytes_read = 0
        # So muc thu muc da xem trong luot ``names()`` gan nhat: chi de chan
        # doan, khong phai du lieu nghiep vu va khong ton them I/O.
        self.last_examined = 0

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
        """Ten tep ``.json`` an toan, sap xep theo ten, toi da gioi han.

        Duyet ``os.scandir`` theo kieu lazy: chi doc den khi du
        ``MAX_FILES_LISTED`` ten hop le hoac cham tran ``MAX_DIR_ENTRIES`` muc
        (ke ca muc khong hop le), roi dong iterator. Khong bao gio vat chat
        hoa toan bo thu muc.
        """
        names = []
        examined = 0
        capped = False
        entries_seen = 0
        try:
            with os.scandir(self.directory) as entries:
                # Chi tieu thu toi da ``MAX_DIR_ENTRIES`` muc, khong hon:
                # ``islice`` cat dung tran, khong doc them mot muc de doan
                # "con nua hay khong" (muc thu cap+1 chi ton I/O vo ich).
                for entry in itertools.islice(entries, MAX_DIR_ENTRIES):
                    examined += 1
                    try:
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        continue
                    if not is_file:
                        continue
                    if not is_safe_name(entry.name):
                        continue
                    names.append(entry.name)
                    if len(names) >= MAX_FILES_LISTED:
                        capped = True
                        break
                else:
                    # Da xem het tran ma van con muc: chi bao khi that su cham
                    # tran, va khong tieu thu muc nao them.
                    if examined >= MAX_DIR_ENTRIES:
                        capped = True
                entries_seen = examined
        except FileNotFoundError:
            raise InboxProblem("missing", self.directory)
        except NotADirectoryError:
            raise InboxProblem("not_directory", self.directory)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))

        self.last_examined = entries_seen
        if capped:
            self._diagnose("<listing>", "too_many_files")
        names.sort()
        return names[:MAX_FILES_LISTED]

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

        # Mo khong theo link (O_NOFOLLOW) va doc qua descriptor da duoc xac
        # nhan la **cung** tep da lstat: thay the tep bang hardlink giua lstat
        # va open se bi bat (dev/ino/link count/type lech).
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(path, flags)
        except FileNotFoundError:
            raise InboxProblem("vanished", name)
        except OSError as exc:
            raise InboxProblem("unreadable", str(exc))
        try:
            try:
                opened = os.fstat(fd)
            except OSError as exc:
                raise InboxProblem("unreadable", str(exc))
            _verify_same_entry(info, opened, name)
            if getattr(opened, "st_size", size) > self.max_file_bytes:
                raise InboxProblem("too_large", name)
            try:
                # Doc toi da +1 byte: tep phinh ra sau khi mo van bi cat,
                # khong bao gio doc khong gioi han.
                raw = _read_bounded(fd, self.max_file_bytes + 1)
            except OSError as exc:
                raise InboxProblem("unreadable", str(exc))
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
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

        ``names_handled`` gom tep da xu ly va tep thong bao hop le nhung qua
        han (don). Tep hong/khong phai thong bao thi chi chan doan, caller
        khong the xoa chung.
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
            except InboxProblem as exc:
                handled.append(name)
                self._diagnose(name, exc.reason)
                continue
            try:
                notification = PetNotification.parse(payload, now=current)
            except NotificationError as exc:
                # Chi tep JSON **hop le ve cau truc** moi duoc coi la da xu
                # ly (de don). JSON hong hoac tep khong phai thong bao
                # (package.json, config...) duoc giu nguyen, chi chan doan.
                self._diagnose(name, exc.reason)
                continue
            if notification.expired(current):
                # Thong bao that nhung da het han: don khong hien thi.
                handled.append(name)
                self._diagnose(name, "expired")
                continue
            if not self._name_matches(payload, name):
                self._diagnose(name, "name_mismatch")
                continue
            handled.append(name)
            results.append(notification)
        return results, handled

    def _name_matches(self, payload, name):
        """Ten tep phai khop id trong payload (chan xoa nham tep cua nguoi khac)."""
        return (
            isinstance(payload, dict)
            and payload.get("id") == name[: -len(INBOX_SUFFIX)]
        )

    # ------------------------------------------------------------------
    # Don tep da xu ly (ack)
    # ------------------------------------------------------------------
    def remove(self, name):
        """Xoa mot tep da xu ly. Khong bao gio xoa ngoai thu muc inbox."""
        if not self._removable(name):
            return False
        path = os.path.join(self.directory, name)
        try:
            info = os.lstat(path)
        except OSError:
            return False
        if _is_link(info) or not _is_regular(info):
            return False
        if getattr(info, "st_nlink", 1) > 1:
            return False
        try:
            os.unlink(path)
        except OSError:
            return False
        return True

    def _removable(self, name):
        """True neu tep la thong bao cau truc hop le dung ten cua chinh no.

        Kiem tra lai o thoi diem xoa: caller khong the chi dua ten la xoa duoc
        tep khac (``package.json``, JSON hong, tep khong khop id).
        """
        if not is_safe_name(name):
            return False
        before = self.bytes_read
        try:
            payload = self.read(name)
        except InboxProblem:
            return False
        finally:
            # Kiem tra lai khong duoc tinh la byte da xu ly trong thong ke.
            self.bytes_read = before
        if not self._name_matches(payload, name):
            return False
        try:
            PetNotification.parse(payload)
        except NotificationError:
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
                 max_files=MAX_FILES_READ, now=None, inbox=None):
        # UI da dung ``InboxSource(Inbox(path))``: nhan ca thuc the ``Inbox``
        # lan duong dan thu muc (chuoi/PathLike), khong bao gio boc them lan
        # hai thanh chuoi duong dan cua doi tuong Inbox.
        if inbox is not None:
            self.inbox = inbox
        elif isinstance(directory, Inbox):
            self.inbox = directory
        else:
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


def _read_bounded(fd, limit):
    """Doc toi da ``limit`` byte tu descriptor, khong doc qua gioi han."""
    chunks = []
    total = 0
    while total < limit:
        chunk = os.read(fd, min(MAX_FILE_BYTES, limit - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def _verify_same_entry(expected, opened, name):
    """Descriptor vua mo phai la chinh tep da lstat (khong bi thay the)."""
    if _is_link(opened) or not _is_regular(opened):
        raise InboxProblem("replaced", name)
    if getattr(opened, "st_nlink", 1) > 1:
        raise InboxProblem("hardlink", name)
    try:
        expected_dev = expected.st_dev
        expected_ino = expected.st_ino
        opened_dev = opened.st_dev
        opened_ino = opened.st_ino
    except AttributeError:
        # Thieu metadata dinh danh (dev/ino): khong the chung minh cung tep
        # -> tu choi (fail closed) thay vi gia dinh ``same=True``.
        raise InboxProblem("unverifiable", name)
    if expected_dev != opened_dev or expected_ino != opened_ino:
        raise InboxProblem("replaced", name)


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
