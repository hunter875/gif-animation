"""Luu API key tach rieng khoi config.json.

Xem ``docs/SECURITY.md`` muc 3. Ly do phai tach:

- ``config.json`` duoc ghi lai rat thuong (moi lan keo pet, moi lan roi xong),
  nen key se nam trong nhieu ban ghi de va de lot ra khi nguoi dung chia se
  file cau hinh de nho ho tro.
- Quyen file cua config phu thuoc ``umask``. File bi mat phai tu dat quyen
  tuong minh.

Thu tu uu tien khi doc:

    1. bien moi truong ``GIFPET_API_KEY`` - khong ghi ra dia
    2. file ``secrets.json`` trong thu muc cau hinh, quyen 0600

Khong co thu ba. Key khong bao gio nam trong ``config.json``.
"""

import json
import os
import tempfile

from gifpet.core.config import config_dir

# Ten bien moi truong, dat ten co tien to de khong dam vao bien khac.
ENV_VAR = "GIFPET_API_KEY"
SECRETS_NAME = "secrets.json"


def secrets_path():
    return os.path.join(config_dir(), SECRETS_NAME)


def _load_all():
    """Doc toan bo file secrets. Hong thi coi nhu rong, khong crash."""
    try:
        with open(secrets_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data):
    """Ghi file secrets theo kieu atomic, quyen 0600 tuong minh."""
    directory = config_dir()
    os.makedirs(directory, exist_ok=True)
    # Thu muc cung phai han che: mac dinh 0755 cho phep nguoi khac liet ke ten
    # file, du khong doc duoc noi dung. 0700 la muc dung cho thu muc co bi mat.
    if os.name != "nt":
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
    handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".secret-")
    try:
        # fchmod tren fd: khong co khoang ho giua tao file va dat quyen.
        # Dung os.chmod(temp_path) sau khi fdopen la sai: file da ton tai voi
        # quyen do umask quyet dinh trong khoang thoi gian do.
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
            handle = None  # fdopen da nhan quyen so huu fd
            json.dump(data, temp_file, indent=4, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, secrets_path())
    except BaseException:
        if handle is not None:
            try:
                os.close(handle)
            except OSError:
                pass
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise


def get_api_key():
    """Tra ve API key dang dung, hoac ``None`` neu chua cau hinh."""
    from_env = os.environ.get(ENV_VAR, "").strip()
    if from_env:
        return from_env
    value = _load_all().get("api_key", "")
    return value.strip() if isinstance(value, str) and value.strip() else None


def source():
    """Cho biet key dang lay tu dau, de hien trong Cai dat."""
    if os.environ.get(ENV_VAR, "").strip():
        return "env"
    if get_api_key():
        return "file"
    return None


def set_api_key(value):
    """Luu key vao file rieng quyen 0600. Chuoi rong = xoa key."""
    value = (value or "").strip()
    data = _load_all()
    if value:
        data["api_key"] = value
    else:
        data.pop("api_key", None)

    if not data:
        # Khong con bi mat nao: xoa han file thay vi de file rong.
        try:
            os.unlink(secrets_path())
        except OSError:
            pass
        return
    _write_all(data)


def clear_api_key():
    set_api_key("")


def masked(value):
    """Dang hien an toan: chi 4 ky tu cuoi."""
    if not value:
        return "(chưa có)"
    if len(value) <= 4:
        return "•" * len(value)
    return "…" + value[-4:]


def env_override_active():
    """True neu bien moi truong dang de len file (de canh bao trong UI)."""
    return bool(os.environ.get(ENV_VAR, "").strip())
