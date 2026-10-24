"""Trang thai ben vung cho thong bao: dedup, history, cai dat hien thi.

Tep trang thai nam **ngoai repo**, cung thu muc cau hinh voi ``config.json``
(``notifications_state.json``). Noi dung:

- ``seen``    : id da hien thi (chi de dedup, TTL rieng).
- ``history`` : cac thong bao gan nhat (xem lai trong UI).
- ``settings``: bat/tat, am (mute), bong bong, khay, thu muc inbox.

Vi sao dedup phai ben vung: pet khoi dong lai van doc lai inbox (producer co
the chua don tep). Neu chi giu ``seen`` trong RAM thi thong bao cu se hien
lai moi lan mo app. Xoa lich su chi xoa ``history`` (``clear_history_view``),
khong dong vao ``seen``; muon phat lai tu dau thi goi ``clear_history``, nhung
thong bao **da qua han** van khong bao gio duoc phat lai; chi thong bao con han
moi co the hien lai mot lan.

Gioi han cung (owner co the ha qua config, khong the nang):

- ``MAX_HISTORY`` muc history, ``MAX_SEEN`` id dedup.
- ``SEEN_TTL_SECONDS``: id cu bi quen de tep trang thai khong phinh.

File hong: dung mac dinh, khong crash, in canh bao ngan.
"""

import json
import os
import tempfile
import threading
import time

from gifpet.notifications.models import (
    DEFAULT_SEVERITY,
    MAX_TITLE_LEN,
    SEVERITIES,
    clean_text,
    valid_notification_id,
    valid_source_id,
)

STATE_FILENAME = "notifications_state.json"
STATE_VERSION = 1

MAX_HISTORY = 200
MAX_SEEN = 500
SEEN_TTL_SECONDS = 7 * 24 * 60 * 60
HISTORY_MESSAGE_LIMIT = 500

DEFAULT_SETTINGS = {
    "enabled": True,
    "muted": False,
    "bubble": True,
    "tray": True,
    "inbox_path": "",
    "show_source": True,
}
SETTING_KEYS = tuple(DEFAULT_SETTINGS)

# Khoa ghi tep trang thai: UI (luong Qt) co the ghi cung luc voi thao tac
# khac; van de la tranh hai lan ghi chen nhau tren cung mot thu muc.
_SAVE_LOCK = threading.Lock()


def state_path(config_dir):
    return os.path.join(str(config_dir), STATE_FILENAME)


class NotificationState:
    """Trang thai dedup/history/cai dat, tu quan ly file JSON rieng.

    ``clock`` la ham tra epoch giay; test truyen dong ho gia de tat dinh.
    """

    def __init__(self, path, clock=None):
        self.path = str(path)
        self._clock = clock or time.time
        self.seen = {}        # id -> epoch giay luc ghi nhan
        self.history = []     # list[dict], moi nhat o dau
        self.settings = dict(DEFAULT_SETTINGS)
        self.load()

    # ------------------------------------------------------------------
    # Doc/ghi
    # ------------------------------------------------------------------
    def load(self):
        """Doc tep trang thai; hong thi dung mac dinh (khong ném exception)."""
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            return False
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            print(f"[thông báo] không đọc được trạng thái ({exc}), dùng mặc định.")
            return False

        if not isinstance(raw, dict):
            print("[thông báo] trạng thái không phải object JSON, dùng mặc định.")
            return False

        version = raw.get("version", STATE_VERSION)
        if version != STATE_VERSION:
            print(f"[thông báo] trạng thái phiên bản lạ ({version}), bỏ qua.")
            return False

        seen = raw.get("seen")
        if isinstance(seen, dict):
            for ident, stamp in seen.items():
                if valid_notification_id(ident) and _is_number(stamp):
                    self.seen[ident] = float(stamp)
        elif isinstance(seen, list):
            # Ban cu chi luu danh sach id: gan moc hien tai.
            now = self._clock()
            for ident in seen:
                if valid_notification_id(ident):
                    self.seen[ident] = now

        history = raw.get("history")
        if isinstance(history, list):
            for entry in history:
                item = _clean_history_entry(entry)
                if item is not None:
                    self.history.append(item)
            self.history = self.history[:MAX_HISTORY]

        settings = raw.get("settings")
        if isinstance(settings, dict):
            for key in SETTING_KEYS:
                if key in settings:
                    self.settings[key] = _coerce_setting(
                        key, settings[key], DEFAULT_SETTINGS[key]
                    )
        self._prune_seen()
        return True

    def save(self):
        """Ghi atomic, co khoa: UI va tep trang thai khong ghi chong nhau.

        Loi ghi khong duoc lam hong trai nghiem pet: in canh bao ngan va tra
        False, khong ném exception ra timer Qt.
        """
        directory = os.path.dirname(self.path) or "."
        payload = {
            "version": STATE_VERSION,
            "seen": self.seen,
            "history": self.history[:MAX_HISTORY],
            "settings": self.settings,
        }
        temp_path = None
        try:
            with _SAVE_LOCK:
                os.makedirs(directory, exist_ok=True)
                handle, temp_path = tempfile.mkstemp(
                    prefix=".notify-state-", suffix=".tmp", dir=directory
                )
                with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
                    json.dump(payload, temp_file, ensure_ascii=False, indent=2)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                os.replace(temp_path, self.path)
                temp_path = None
            return True
        except OSError as exc:
            print(f"[thông báo] không ghi được trạng thái ({exc}).")
            return False
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass


    # ------------------------------------------------------------------
    # Cai dat
    # ------------------------------------------------------------------
    def get_setting(self, key, default=None):
        """Gia tri cai dat; thieu key thi dung ``default`` (hoac mac dinh goc).

        Tang UI/controller goi ``get_setting(key, False)`` tu truoc, nen tham
        so thu hai la tuy chon va giu tuong thich nguoc.
        """
        if key in self.settings:
            return self.settings[key]
        if default is not None:
            return default
        return DEFAULT_SETTINGS.get(key)

    def set_setting(self, key, value, save=True):
        if key not in DEFAULT_SETTINGS:
            raise KeyError(key)
        self.settings[key] = _coerce_setting(key, value, DEFAULT_SETTINGS[key])
        if save:
            self.save()
        return self.settings[key]

    def update_settings(self, values, save=True):
        changed = {}
        for key, value in values.items():
            if key in DEFAULT_SETTINGS:
                current = self.settings.get(key)
                new_value = _coerce_setting(key, value, DEFAULT_SETTINGS[key])
                if new_value != current:
                    changed[key] = new_value
                self.settings[key] = new_value
        if changed and save:
            self.save()
        return changed

    def enabled(self):
        """Feature bat/tat (khong tinh am mute). Xem ``active``."""
        return bool(self.get_setting("enabled"))

    def active(self):
        """Con duong thong bao co dang hoat dong khong (bat va khong am)."""
        return bool(self.get_setting("enabled")) and not bool(
            self.get_setting("muted")
        )

    # ------------------------------------------------------------------
    # Dedup
    # ------------------------------------------------------------------
    def is_seen(self, notification_id):
        return notification_id in self.seen

    def mark_seen(self, notification_id, save=True):
        if not valid_notification_id(notification_id):
            return False
        if notification_id in self.seen:
            return False
        self.seen[notification_id] = self._clock()
        self._prune_seen()
        if save:
            self.save()
        return True

    def _prune_seen(self):
        """Bo id qua cu va cat bot khi vuot ``MAX_SEEN`` (giu id moi nhat)."""
        now = self._clock()
        cutoff = now - SEEN_TTL_SECONDS
        for ident in [k for k, v in self.seen.items() if v < cutoff]:
            del self.seen[ident]
        if len(self.seen) > MAX_SEEN:
            ordered = sorted(self.seen.items(), key=lambda item: item[1])
            for ident, _ in ordered[: len(self.seen) - MAX_SEEN]:
                del self.seen[ident]

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def add_history(self, notification, save=True):
        """Ghi mot thong bao vao history (moi nhat o dau), cat theo gioi han."""
        entry = {
            "id": notification.id,
            "source": notification.source,
            "title": notification.title[:MAX_TITLE_LEN],
            "message": notification.message[:HISTORY_MESSAGE_LIMIT],
            "severity": notification.severity,
            "created_at": float(notification.created_at),
            "received_at": float(self._clock()),
        }
        self.history = [item for item in self.history if item.get("id") != entry["id"]]
        self.history.insert(0, entry)
        if len(self.history) > MAX_HISTORY:
            del self.history[MAX_HISTORY:]
        if save:
            self.save()
        return entry

    def clear_history(self, save=True):
        """Xoa history *va* danh dau dedup (xem duoc lai tu dau).

        Nho xoa ``seen``, thong bao con han trong inbox co the hien lai mot
        lan; thong bao da qua han van bi bo qua vi ``expired``.
        """
        count = len(self.history)
        self.history = []
        self.seen = {}
        if save:
            self.save()
        return count

    def clear_history_view(self, save=True):
        """Chi xoa history hien thi; giu ``seen`` de khong replay tin cu.

        Dung khi nguoi dung xoa lich su nhung khong muon inbox da xu ly bi
        phat lai sau restart.
        """
        count = len(self.history)
        self.history = []
        if save:
            self.save()
        return count

    def recent(self, limit=50):
        limit = max(1, min(MAX_HISTORY, int(limit)))
        return self.history[:limit]


def _clean_history_entry(entry):
    """Chuan hoa mot muc history doc tu dia; tra None neu khong dung duoc."""
    if not isinstance(entry, dict):
        return None
    ident = entry.get("id")
    source = entry.get("source")
    if not valid_notification_id(ident) or not valid_source_id(source):
        return None
    severity = entry.get("severity")
    if severity not in SEVERITIES:
        severity = DEFAULT_SEVERITY
    created_at = entry.get("created_at")
    received_at = entry.get("received_at")
    return {
        "id": ident,
        "source": source,
        "title": clean_text(entry.get("title", ""), MAX_TITLE_LEN),
        "message": clean_text(entry.get("message", ""), HISTORY_MESSAGE_LIMIT),
        "severity": severity,
        "created_at": float(created_at) if _is_number(created_at) else 0.0,
        "received_at": float(received_at) if _is_number(received_at) else 0.0,
    }


def _coerce_setting(key, value, default):
    if isinstance(default, bool):
        return bool(value) if isinstance(value, bool) else default
    if isinstance(default, str):
        if not isinstance(value, str):
            return default
        text = value.strip()
        # Duong dan inbox la chuoi nguoi dung go; khong chua ky tu dieu khien.
        if any(ord(ch) < 32 for ch in text):
            return default
        return text[:260]
    return value


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
