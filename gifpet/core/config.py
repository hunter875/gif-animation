"""Quan ly cau hinh nguoi dung.

Cau hinh duoc luu o thu muc cau hinh cua he dieu hanh (XDG tren Linux,
AppData tren Windows, Application Support tren macOS) thay vi trong repo,
de clone repo sang may khac khong keo theo duong dan ca nhan.

Ghi file theo kieu atomic: ghi ra file tam roi thay the file cu, tranh
truong hop file bi hong khi app tat giua luc ghi.
"""

import json
import os
import tempfile

APP_NAME = "GifAnimation"

# Cac key cau hinh va kieu du lieu mong doi, dung de validate khi doc.
#
# Nhom theo giai doan de de mo rong:
#   - Hien thi / vi tri   : Giai doan 1-2 (da xong)
#   - Nhan vat va hanh vi : Giai doan 3 (trang thai, tu di, nem tha)
#   - AI                  : Giai doan 4 (chat, tinh cach, bo nho, quota)
#   - Giong noi           : Giai doan 5 (STT, TTS)
DEFAULTS = {
    # --- Hien thi va vi tri ---
    "x": 0,
    "y": 0,
    "pin_to_top": True,
    "visible": True,
    "animation_paused": False,
    "auto_switch_enabled": True,
    "auto_switch_seconds": 10,
    "auto_walk": False,
    "click_through": False,
    "hide_on_fullscreen": True,
    "width_locked": True,
    # --- Nhan vat ---
    "pet_pack": "default",
    "gif_path": "idle.gif",
    "gif_width": 200,
    "gif_height": 200,
    "gif_list": [],
    # --- Giai doan 3: hanh vi ---
    "focus_mode": False,
    "walk_speed": 2,
    "walk_pause_chance": 0.3,
    "sleep_after_seconds": 120,
    "gravity_enabled": True,
    # --- Giai doan 4: AI (tat mac dinh, chua trien khai) ---
    "ai_enabled": False,
    "ai_provider": "groq",
    "ai_model": "",
    "ai_daily_limit": 50,
    "ai_used_today": 0,
    "ai_used_date": "",
    "ai_proactive": False,
    # --- Giai doan 5: giong noi (tat mac dinh, chua trien khai) ---
    "voice_enabled": False,
    "voice_muted": True,
}


def config_dir():
    """Thu muc cau hinh theo he dieu hanh."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    if os.uname().sysname == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    # Linux / BSD: theo XDG Base Directory Specification.
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_NAME)


def config_path():
    return os.path.join(config_dir(), "config.json")


def _coerce(value, default):
    """Ep kieu gia tri doc tu file ve kieu cua gia tri mac dinh.

    File cau hinh co the bi sua tay hoac hong; tra ve gia tri mac dinh
    neu khong the ep kieu thay vi de app crash.
    """
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return default
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return default
        return default
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, str):
        return value if isinstance(value, str) else default
    if isinstance(default, list):
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        return list(default)
    return value


class Config:
    """Cau hinh nguoi dung, luu ngoai repo."""

    def __init__(self, path=None):
        self.path = path or config_path()
        self.data = {}
        self.load()

    def load(self):
        """Doc cau hinh, bo qua file hong va luon dien du key mac dinh."""
        raw = {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                raw = loaded
            else:
                print(f"Canh bao: {self.path} khong phai object JSON, dung mac dinh.")
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            print(f"Canh bao: khong doc duoc {self.path} ({exc}), dung mac dinh.")

        self.data = {}
        for key, default in DEFAULTS.items():
            if key in raw:
                self.data[key] = _coerce(raw[key], default)
            else:
                self.data[key] = default if not isinstance(default, list) else list(default)
        return self.data

    def save(self):
        """Ghi cau hinh theo kieu atomic de khong lam hong file cu."""
        directory = os.path.dirname(self.path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            # File tam cung thu muc de os.replace la thao tac atomic.
            handle, temp_path = tempfile.mkstemp(
                prefix=".config-", suffix=".tmp", dir=directory
            )
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
                    json.dump(self.data, temp_file, indent=4, ensure_ascii=False)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                os.replace(temp_path, self.path)
            except BaseException:
                # Don file tam neu ghi that bai giua chung.
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                raise
        except OSError as exc:
            print(f"Canh bao: khong ghi duoc cau hinh ({exc}).")

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        if key in DEFAULTS:
            return DEFAULTS[key]
        return default

    def set(self, key, value):
        self.data[key] = value
