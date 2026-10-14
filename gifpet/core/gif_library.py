"""Quan ly thu vien GIF: chuan hoa duong dan, kiem tra hop le, tim fallback.

Muc dich chinh: khong bao gio de app chon trung mot GIF hong hoac da bi di
chuyen, va luon co GIF de hien thi.
"""

import os

from PyQt5.QtGui import QImageReader, QMovie

DEFAULT_GIF = "abc.gif"


def gif_dimensions(path):
    """Kich thuoc THAT cua GIF, doc tu header.

    Khong dung QMovie.currentPixmap() vi sau khi goi setScaledSize, QMovie
    tra ve kich thuoc da scale, lam mat kich thuoc goc va hong ti le khi
    resize nhieu lan. QImageReader doc thang tu file nen luon chinh xac.
    """
    if not path or not os.path.isfile(path):
        return None
    reader = QImageReader(path)
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        return None
    return size.width(), size.height()


def normalize_path(path, base_dir):
    """Doi duong dan tuyet doi thanh tuong doi theo project neu nam trong project."""
    if not path:
        return path
    try:
        if os.path.isabs(path) and os.path.abspath(path).startswith(os.path.abspath(base_dir) + os.sep):
            return os.path.relpath(path, base_dir)
    except (OSError, ValueError):
        pass
    return path


def resolve_path(path, base_dir):
    """Chuan hoa duong dan GIF cho moi he dieu hanh.

    - Duong dan tuyet doi kieu POSIX duoc giu nguyen.
    - Duong dan tuyet doi kieu Windows (vd 'D:/x/y.gif') duoc giu nguyen vi
      tren Linux chung se khong ton tai va duoc xu ly boi buoc fallback.
    - Duong dan tuong doi resolve theo thu muc project, khong theo CWD.
    """
    if not path:
        return path
    if os.path.isabs(path):
        return path
    if len(path) > 2 and path[1] == ":" and path[2] in ("/", "\\"):
        return path
    return os.path.join(base_dir, path)


def is_valid_gif(path):
    """True neu file ton tai va QMovie doc duoc no nhu mot GIF hop le."""
    if not path or not os.path.isfile(path):
        return False
    movie = QMovie(path)
    return bool(movie.isValid())


def pick_working_gif(preferred, gif_list, base_dir, default=DEFAULT_GIF):
    """Chon GIF de hien thi theo thu tu uu tien.

    1. GIF da chon, neu con hop le.
    2. GIF hop le dau tien trong thu vien.
    3. GIF mac dinh di kem repo.

    Tra ve (path_da_resolve, entry_luu_config) hoac (None, None) neu khong con
    GIF nao dung duoc.
    """
    candidates = []
    if preferred:
        candidates.append(preferred)
    for item in gif_list or []:
        if item not in candidates:
            candidates.append(item)
    if default not in candidates:
        candidates.append(default)

    for candidate in candidates:
        resolved = resolve_path(candidate, base_dir)
        if is_valid_gif(resolved):
            return resolved, candidate
    return None, None


def existing_entries(gif_list, base_dir):
    """Loc thu vien, chi giu entry tro toi file GIF hop le."""
    return [item for item in (gif_list or []) if is_valid_gif(resolve_path(item, base_dir))]


def scaled_size(original_width, original_height, target, lock_width):
    """Tinh kich thuoc moi giu nguyen ti le khung hinh.

    ``lock_width`` True nghia la ``target`` la chieu rong mong muon, nguoc lai
    la chieu cao mong muon. Tra ve (width, height) toi thieu 1px.
    """
    original_width = max(1, int(original_width or 1))
    original_height = max(1, int(original_height or 1))
    target = max(1, int(target or 1))

    if lock_width:
        width = target
        height = round(original_height * target / original_width)
    else:
        height = target
        width = round(original_width * target / original_height)
    return max(1, width), max(1, height)
