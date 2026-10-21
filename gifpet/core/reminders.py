"""Loi nhac hen gio, luu ben qua lan tat app.

Van de cua ban cu: ``QTimer.singleShot`` chi song trong tien trinh. Hen 30 phut
roi tat app la mat loi nhac, khong bao gi. File nay thay bang mot hang doi luu
ra dia.

Thiet ke:

- Moi loi nhac la mot muc ``{"text": ..., "due": <epoch giay>}``.
- Ghi atomic, cung khuon mau voi ``config.py`` (mkstemp + os.replace).
- Doc lai moi lan kiem tra: khong giu trang thai trong bo nho, nen nhieu cua so
  pet cung khong tranh nhau.
- Loi nhac qua han qua lau (mac dinh 24 gio) bi bo qua thay vi do mot loat cung
  luc khi mo app sau nhieu ngay.

Module nay thuan tuy logic + doc/ghi file, khong phu thuoc Qt.
"""

import json
import os
import tempfile
import time

from gifpet.core.config import config_dir

REMINDERS_NAME = "reminders.json"

# Gioi han so loi nhac cho mot luc, tranh phinh vo han.
MAX_REMINDERS = 20

# Loi nhac qua han qua lau thi bo. Neu khong co gioi han nay, mo app sau mot
# tuan se do ra hang chuc thong bao cung luc.
STALE_AFTER_SECONDS = 24 * 60 * 60

# Do dai toi da cua text, cung gioi han voi actions.MAX_TEXT_CHARS.
MAX_TEXT_CHARS = 200


def reminders_path():
    return os.path.join(config_dir(), REMINDERS_NAME)


def _load_raw():
    try:
        with open(reminders_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _write_raw(items):
    directory = config_dir()
    os.makedirs(directory, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".remind-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
            json.dump(items, temp_file, indent=4, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, reminders_path())
    except BaseException:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise


def _clean(items):
    """Bo muc hong, cat text, sap xep theo gio hen."""
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text", "")).split())[:MAX_TEXT_CHARS]
        if not text:
            continue
        try:
            due = float(item.get("due", 0))
        except (TypeError, ValueError):
            continue
        if due <= 0:
            continue
        result.append({"text": text, "due": due})
    result.sort(key=lambda entry: entry["due"])
    return result[:MAX_REMINDERS]


class Reminders:
    """Hang doi loi nhac hen gio, luu o file rieng ngoai repo."""

    def __init__(self, path=None, now_func=None):
        self._path = path
        self.now_func = now_func or time.time

    def path(self):
        return self._path or reminders_path()

    def _read(self):
        if self._path:
            try:
                with open(self._path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                return []
            return _clean(data if isinstance(data, list) else [])
        return _clean(_load_raw())

    def _write(self, items):
        if self._path:
            directory = os.path.dirname(self._path) or "."
            os.makedirs(directory, exist_ok=True)
            handle, temp_path = tempfile.mkstemp(
                dir=directory, prefix=".remind-"
            )
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
                    json.dump(items, temp_file, indent=4, ensure_ascii=False)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                os.replace(temp_path, self._path)
            except BaseException:
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                raise
        else:
            _write_raw(items)

    # ------------------------------------------------------------------
    def all(self):
        return self._read()

    def add(self, text, seconds):
        """Hen nhac sau ``seconds`` giay. Tra ve True neu da luu."""
        text = " ".join((text or "").split())[:MAX_TEXT_CHARS]
        if not text:
            return False
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return False
        if seconds <= 0:
            return False

        items = self._read()
        items.append({"text": text, "due": self.now_func() + seconds})
        # Giu lai nhung loi nhac moi nhat neu vuot tran.
        items = sorted(items, key=lambda entry: entry["due"])[-MAX_REMINDERS:]
        self._write(items)
        return True

    def due(self):
        """Cac loi nhac da den gio. Khong xoa khoi file."""
        now = self.now_func()
        return [item for item in self._read() if item["due"] <= now]

    def pop_due(self):
        """Lay ra va xoa cac loi nhac da den gio. Tra ve danh sach text."""
        now = self.now_func()
        items = self._read()
        ready = [item for item in items if item["due"] <= now]
        if not ready:
            return []
        remaining = [item for item in items if item["due"] > now]
        self._write(remaining)
        return [item["text"] for item in ready]

    def drop_stale(self):
        """Bo loi nhac qua han qua lau. Goi luc khoi dong.

        Tra ve so muc da bo, de test kiem tra duoc.
        """
        now = self.now_func()
        items = self._read()
        keep = [item for item in items if now - item["due"] <= STALE_AFTER_SECONDS]
        dropped = len(items) - len(keep)
        if dropped:
            self._write(keep)
        return dropped

    def clear(self):
        try:
            os.unlink(self.path())
        except OSError:
            pass

    def count(self):
        return len(self._read())

    def next_wait_seconds(self):
        """Con bao lau nua thi toi loi nhac ke tiep. ``None`` neu khong co."""
        items = self._read()
        if not items:
            return None
        return max(0.0, items[0]["due"] - self.now_func())
