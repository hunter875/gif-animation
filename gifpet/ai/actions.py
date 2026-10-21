"""Danh sach hanh dong duoc phep va kiem tra truoc khi thuc hien.

Day la **chot chan chinh** cua Giai doan 4. Xem ``docs/SECURITY.md`` muc 2.3.

Nguyen tac: model khong bao gio duoc thuc thi truc tiep. No chi duoc de xuat
mot hanh dong; app kiem tra bon buoc, tat ca phai qua:

    1. Ten hanh dong co trong ``ALLOWED_ACTIONS``?
    2. Tham so dung kieu?
    3. Tham so dung mien gia tri?
    4. Tan suat hop le?

Neu buoc 1 truot thi hanh dong **khong ton tai**, model noi gi cung vay. Khong
co nhanh nao chay shell, doc file tuy y, hay goi mang ngoai danh sach.

Module nay thuan tuy logic, khong phu thuoc Qt nen test duoc de dang.
"""

import re
from urllib.parse import urlsplit

from gifpet.core import state as state_module

# --- Gioi han ---
MAX_TEXT_CHARS = 200
MAX_URL_CHARS = 500
MIN_REMIND_MINUTES = 1
MAX_REMIND_MINUTES = 24 * 60

# Mien URL duoc phep: chi https, va khong tro vao may cua nguoi dung.
ALLOWED_URL_SCHEMES = ("https",)
# Ky tu dieu khien (ngoai xuong dong) khong duoc co trong text hien ra.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ActionError(Exception):
    """Hanh dong bi tu choi. Message ghi ly do de log, khong hien cho nguoi dung."""


# ----------------------------------------------------------------------
# Dinh nghia hanh dong
# ----------------------------------------------------------------------
# risk:
#   "display"  chi hien thi, khong can hoi nguoi dung
#   "side_effect" co tac dung phu that, phai hoi nguoi dung truoc
#
# Moi hanh dong co mot ham validate rieng. Khong dung kieu chung chung: kiem
# tra tan suat va mien gia tri phai viet tuong minh theo tung hanh dong.

ALLOWED_ACTIONS = {
    "say": {"risk": "display", "params": ("text",)},
    "react": {"risk": "display", "params": ()},
    "set_state": {"risk": "display", "params": ("state",)},
    "remind": {"risk": "side_effect", "params": ("text", "in_minutes")},
    "open_url": {"risk": "side_effect", "params": ("url",)},
}

# Hanh dong co tac dung phu phai duoc nguoi dung xac nhan.
SIDE_EFFECT_ACTIONS = tuple(
    name for name, spec in ALLOWED_ACTIONS.items() if spec["risk"] == "side_effect"
)


def is_allowed(name):
    return name in ALLOWED_ACTIONS


# ----------------------------------------------------------------------
# Kiem tra tung hanh dong
# ----------------------------------------------------------------------
def _clean_text(value):
    if not isinstance(value, str):
        raise ActionError("text phai la chuoi")
    text = value.strip()
    if not text:
        raise ActionError("text rong")
    if len(text) > MAX_TEXT_CHARS:
        raise ActionError(f"text dai qua {MAX_TEXT_CHARS} ky tu")
    if _CONTROL_CHARS.search(text):
        raise ActionError("text chua ky tu dieu khien")
    return text


def _is_private_host(host):
    """True neu host tro vao may cuc bo hoac mang noi bo.

    Chan tan cong kieu prompt injection dung pet de quet dich vu noi bo.
    """
    if not host:
        return True
    host = host.strip("[]").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    # Ten mien noi bo pho bien.
    if host.endswith((".local", ".internal", ".localhost", ".home.arpa")):
        return True

    # IPv4: chan 10/8, 127/8, 169.254/16, 172.16/12, 192.168/16.
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            return True
        if a in (10, 127, 0):
            return True
        if a == 169 and b == 254:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
        if a == 192 and b == 168:
            return True

    # IPv6: chan loopback va link-local.
    if ":" in host and (host.startswith("fe80") or host.startswith("fd") or host == "::1"):
        return True
    return False


def _clean_url(value):
    if not isinstance(value, str):
        raise ActionError("url phai la chuoi")
    url = value.strip()
    if not url:
        raise ActionError("url rong")
    if len(url) > MAX_URL_CHARS:
        raise ActionError(f"url dai qua {MAX_URL_CHARS} ky tu")
    if _CONTROL_CHARS.search(url):
        raise ActionError("url chua ky tu dieu khien")

    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_URL_SCHEMES:
        # Chan file://, javascript:, data:, ftp:, http: ...
        raise ActionError(f"scheme khong duoc phep: {parts.scheme or '(khong co)'}")
    if parts.username or parts.password:
        # Chan kieu https://user:pass@host - de gia mao.
        raise ActionError("url khong duoc chua thong tin dang nhap")
    if _is_private_host(parts.hostname):
        raise ActionError(f"url tro vao mang noi bo: {parts.hostname}")
    return url


def _clean_state(value):
    if not isinstance(value, str):
        raise ActionError("state phai la chuoi")
    if value not in state_module.ALL_STATES:
        raise ActionError(f"trang thai khong hop le: {value}")
    return value


def _clean_minutes(value):
    # Chan bool: trong Python, True la int (== 1) nen lot qua kiem tra kieu.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActionError("in_minutes phai la so nguyen")
    if not MIN_REMIND_MINUTES <= value <= MAX_REMIND_MINUTES:
        raise ActionError(
            f"in_minutes ngoai khoang {MIN_REMIND_MINUTES}..{MAX_REMIND_MINUTES}"
        )
    return value


_VALIDATORS = {
    "say": {"text": _clean_text},
    "react": {},
    "set_state": {"state": _clean_state},
    "remind": {"text": _clean_text, "in_minutes": _clean_minutes},
    "open_url": {"url": _clean_url},
}


def validate(name, params):
    """Kiem tra mot hanh dong. Tra ve dict tham so da lam sach.

    Nem ``ActionError`` neu bi tu choi. Caller **khong duoc** thuc hien hanh
    dong nao neu ham nay nem loi.
    """
    if not isinstance(name, str) or name not in ALLOWED_ACTIONS:
        raise ActionError(f"hanh dong khong duoc phep: {name!r}")
    if not isinstance(params, dict):
        raise ActionError("tham so phai la dict")

    expected = set(ALLOWED_ACTIONS[name]["params"])
    got = set(params)
    if got != expected:
        raise ActionError(
            f"tham so khong khop cho {name}: can {sorted(expected)}, nhan {sorted(got)}"
        )

    validators = _VALIDATORS[name]
    return {key: validators[key](value) for key, value in params.items()}


def parse_action(payload):
    """Doc mot de xuat hanh dong tu model.

    Dang mong doi::

        {"action": "say", "params": {"text": "Nghi mat chut di"}}

    Chap nhan them ``say`` dang chuoi ngan gon khong can hanh dong.

    Tra ve ``(ten, tham so)`` hoac ``None`` neu payload khong phai de xuat hop
    le. **Khong nem exception** vi day la du lieu tu model.
    """
    if not isinstance(payload, dict):
        return None
    name = payload.get("action")
    params = payload.get("params", {})
    try:
        return name, validate(name, params)
    except ActionError:
        return None


def needs_confirmation(name):
    """Hanh dong co tac dung phu thi phai hoi nguoi dung."""
    return name in SIDE_EFFECT_ACTIONS


def describe(name, params):
    """Cau mo ta ngan de hien trong hop xac nhan."""
    if name == "open_url":
        return f"Mở trang web: {params.get('url', '')}"
    if name == "remind":
        minutes = params.get("in_minutes", 0)
        return f"Nhắc sau {minutes} phút: {params.get('text', '')}"
    return f"{name} {params}"
