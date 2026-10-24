"""Model thong bao: du lieu da validate, chi la chu plain text.

Nguyen tac:

- Nhan vao la du lieu khong dang tin (file JSON cua chuong trinh khac).
  ``parse`` kiem tra kieu, do dai, thoi gian huu han; sai thi tra ve loi
  thay vi ném exception xuyen qua.
- Khong co truong nao mang y nghia hanh dong: khong ``url``, khong
  ``command``, khong ``action``. Them truong nghia la them be mat tan cong,
  nen chi owner moi duoc mo rong.
- Chuoi dieu khien duoc loai bo; HTML duoc giu nguyen nhu **van ban** va
  tang UI dat ``PlainText``, nen the <b> khong duoc dien giai.

Thoi gian dung epoch giay (``time.time()``) de producer va consumer khong
phu thuoc dong ho chung; logic UI dung ``int(time.monotonic()*1000)``.
"""

import os
import re
import time

# Chi bon muc do, dung chung cho bong bong/khay/history.
SEVERITIES = ("info", "success", "warning", "error")
DEFAULT_SEVERITY = "info"

# Gioi han do dai. Tieu de ngan de doc tren khay; noi dung du mot doan van.
MAX_ID_LEN = 96
MAX_SOURCE_LEN = 48
MAX_TITLE_LEN = 160
MAX_MESSAGE_LEN = 2000

# Thoi gian tao khong duoc lech qua xa so voi dong ho may: file rac co
# timestamp nam 1970 hoac nam 3000 deu bi tu choi thay vi giu trong queue.
MAX_CLOCK_SKEW_SECONDS = 24 * 60 * 60
# TTL hop ly: tu vai giay den mot tuan. 0/khong co nghia la dung mac dinh.
MAX_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_TTL_SECONDS = 10 * 60

# Ky tu dieu khien C0/C1 (tru tab va xuong dong) bi loai: chung co the pha
# hien thi hoac gia mao giao dien trong terminal/history.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_KEYS = frozenset(
    ("version", "id", "source", "title", "message", "severity", "created_at",
     "expires_at")
)
_OS_RANDOM = os.urandom
REQUIRED_KEYS = ("id", "source", "created_at", "expires_at")
PAYLOAD_VERSION = 1


class NotificationError(ValueError):
    """Payload khong hop le. ``reason`` la ma ngan de ghi chan doan."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def clean_text(value, limit):
    """Chuan hoa chuoi hien thi: bo ky tu dieu khien, gop khoang trang, cat do dai.

    Khong strip HTML: the ``<b>`` chi duoc hien thi nhu chu thuong, nhung viec
    xoa tag lai co the lam mat noi dung that cua nguoi gui. Tang UI moi la
    noi quyet dinh khong dien giai markup.
    """
    if not isinstance(value, str):
        return ""
    text = _CONTROL.sub(" ", value)
    text = _WHITESPACE.sub(" ", text.replace("\r\n", "\n"))
    text = text.strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "\u2026"
    return text


def valid_source_id(value):
    """Id nguon: chu thuong, so, dau cham/gach, toi da ``MAX_SOURCE_LEN``."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_SOURCE_LEN
        and bool(_SOURCE_PATTERN.match(value))
    )


def valid_notification_id(value):
    """Id thong bao: duoc phep chu hoa vi UUID/sha1 tu producer khac nhau."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_ID_LEN
        and bool(_ID_PATTERN.match(value))
    )


class PetNotification:
    """Mot thong bao da validate, bat bien. Chi de hien thi."""

    __slots__ = ("id", "source", "title", "message", "severity",
                 "created_at", "expires_at")

    def __init__(self, id, source, title, message, severity, created_at,
                 expires_at):
        self.id = id
        self.source = source
        self.title = title
        self.message = message
        self.severity = severity
        self.created_at = created_at
        self.expires_at = expires_at

    def __eq__(self, other):
        if not isinstance(other, PetNotification):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self):
        return hash((self.id, self.source, self.created_at))

    def __repr__(self):
        # Repr khong bao gio chua toan bo noi dung: tranh doan van la vao log.
        return (
            f"PetNotification(id={self.id!r}, source={self.source!r}, "
            f"severity={self.severity!r}, title={self.title[:40]!r})"
        )

    # ------------------------------------------------------------------
    # Truy van
    # ------------------------------------------------------------------
    def expired(self, now=None):
        now = time.time() if now is None else now
        return now >= self.expires_at

    def remaining_seconds(self, now=None):
        now = time.time() if now is None else now
        return max(0.0, self.expires_at - now)

    def display_text(self):
        """Chuoi mot dong de dua vao bong bong/khay.

        Bong bong thoai cua pet lon hon mot dong duoc; o day chi ghep tieu de
        va noi dung, khong cat menh lenh hay the HTML.
        """
        if self.title and self.message:
            return f"{self.title}\n{self.message}"
        return self.title or self.message

    def history_entry(self):
        """Ban ghi lich su. Khong chua id day du? Co, de debug, nhung cat ngan."""
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "created_at": float(self.created_at),
            "expires_at": float(self.expires_at),
        }

    def to_dict(self):
        """Ban ghi JSON (producer dung), day du truong trong payload."""
        return {
            "version": PAYLOAD_VERSION,
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "created_at": float(self.created_at),
            "expires_at": float(self.expires_at),
        }

    # ------------------------------------------------------------------
    # Tao va parse
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, source, title, message, severity=DEFAULT_SEVERITY, id=None,
              ttl_seconds=DEFAULT_TTL_SECONDS, created_at=None, now=None):
        """Tao thong bao moi cho producer. Ném ``NotificationError`` neu sai.

        ``now`` chi dung de test dong ho; producer that khong can truyen.
        """
        current = time.time() if now is None else float(now)
        if created_at is None:
            created_at = current
        try:
            created_at = float(created_at)
        except (TypeError, ValueError):
            raise NotificationError("created_at_not_number", repr(created_at))
        try:
            ttl = float(ttl_seconds)
        except (TypeError, ValueError):
            raise NotificationError("ttl_not_number", repr(ttl_seconds))
        if ttl != ttl or ttl in (float("inf"), float("-inf")):
            raise NotificationError("ttl_not_finite", repr(ttl_seconds))
        ttl = max(1.0, min(MAX_TTL_SECONDS, ttl))
        expires_at = created_at + ttl
        if id is None:
            id = new_id()
        return cls.parse({
            "version": PAYLOAD_VERSION,
            "id": id,
            "source": source,
            "title": title,
            "message": message,
            "severity": severity,
            "created_at": created_at,
            "expires_at": expires_at,
        }, now=current)

    @classmethod
    def parse(cls, payload, now=None):
        """Validate mot dict tu nguon khong dang tin.

        Khong bao gio doc file hay mo ket noi: chi kiem tra du lieu trong dict.
        Truong la bi tu choi (whitelist) de moi truong moi sau nay phai duoc
        them co chu dich.
        """
        current = time.time() if now is None else float(now)
        if not isinstance(payload, dict):
            raise NotificationError("not_object", type(payload).__name__)

        extra = set(payload) - _ALLOWED_KEYS
        if extra:
            raise NotificationError("unknown_fields", ",".join(sorted(extra)))
        missing = [key for key in REQUIRED_KEYS if key not in payload]
        if missing:
            raise NotificationError("missing_fields", ",".join(missing))

        version = payload.get("version", PAYLOAD_VERSION)
        if version != PAYLOAD_VERSION or isinstance(version, bool):
            raise NotificationError("bad_version", repr(version))

        ident = payload.get("id")
        if not valid_notification_id(ident):
            raise NotificationError("bad_id", repr(ident)[:64])

        source = payload.get("source")
        if not valid_source_id(source):
            raise NotificationError("bad_source", repr(source)[:64])

        severity = payload.get("severity", DEFAULT_SEVERITY)
        if severity not in SEVERITIES:
            raise NotificationError("bad_severity", repr(severity)[:32])

        title = clean_text(payload.get("title", ""), MAX_TITLE_LEN)
        message = clean_text(payload.get("message", ""), MAX_MESSAGE_LEN)
        if not title and not message:
            raise NotificationError("empty_content")

        created_at = _finite_number(payload.get("created_at"), "created_at")
        expires_at = _finite_number(payload.get("expires_at"), "expires_at")
        if expires_at <= created_at:
            raise NotificationError("bad_expiry", "expires_at <= created_at")
        if created_at - current > MAX_CLOCK_SKEW_SECONDS:
            raise NotificationError("created_in_future", str(created_at))
        if expires_at - created_at > MAX_TTL_SECONDS:
            raise NotificationError("ttl_too_long", str(expires_at - created_at))

        return cls(
            id=ident,
            source=source,
            title=title,
            message=message,
            severity=severity,
            created_at=created_at,
            expires_at=expires_at,
        )

    def from_payload_safe(self, payload, now=None):
        """Bien the khong ném exception: tra (notification, None) hoac (None, loi)."""
        try:
            return PetNotification.parse(payload, now=now), None
        except NotificationError as exc:
            return None, exc


def _finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NotificationError("not_number", field)
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise NotificationError("not_finite", field)
    return number


def new_id(now=None):
    """Id duy nhat cho producer: thoi gian + ngau nhien, an toan da tien trinh."""
    stamp = int((time.time() if now is None else float(now)) * 1000)
    return f"n{stamp:x}-{_OS_RANDOM(6).hex()}"
