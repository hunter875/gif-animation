"""Quan ly QMovie va nap GIF cho cua so pet.

Tach ra khoi ``pet_window`` de nhom viec "hien thi GIF" nam mot cho. Module nay
giu toan bo hieu biet ve bong ma cua QMovie:

    QMovie khong giai phong het tai nguyen C++ khi bi huy. Tao/huy lien tuc lam
    RSS phinh ~1.3 MB moi lan (doi GIF 600 lan = 1.5 GB). Vi vay cache theo
    duong dan va tai su dung.

Cach dung: moi ham nhan ``window`` (PetWindow) lam tham so dau tien. Khong ke
thua, khong vong import: ``pet_window`` import module nay, chieu nguoc lai khong.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QLabel

from gifpet.core import gif_library


# ----------------------------------------------------------------------
# Cache QMovie
# ----------------------------------------------------------------------
def movie_for(window, resolved_path):
    """Lay QMovie cua mot duong dan, tao moi chi lan dau tien."""
    movie = window._movie_cache.get(resolved_path)
    if movie is not None:
        return movie
    movie = QMovie(resolved_path)
    # GIF hong: khong cache de lan sau con thu lai duoc sau khi sua file.
    if not movie.isValid():
        return None
    window._movie_cache[resolved_path] = movie
    return movie


def prune_movie_cache(window):
    """Bo cache cua GIF da bi xoa hoac hong, giai phong bo nho."""
    dead = [p for p in window._movie_cache if not gif_library.is_valid_gif(p)]
    for path in dead:
        movie = window._movie_cache.pop(path)
        if movie is window.movie:
            # Con dang hien thi thi de QLabel nha ra truoc da.
            if window.label is not None:
                window.label.setMovie(None)
            window.movie = None
        movie.stop()
        movie.deleteLater()


def release_movies(window):
    """Dung va nha het QMovie. Goi truoc khi cua so bi huy.

    Neu de Qt huy cua so truoc roi moi huy QMovie (hoac nguoc lai), QMovie con
    dang chay se goi vao QLabel da chet -> segfault.
    """
    if window.label is not None:
        window.label.setMovie(None)
    for movie in list(window._movie_cache.values()):
        movie.stop()
        movie.deleteLater()
    window._movie_cache.clear()
    if window.movie is not None:
        window.movie.stop()
    window.movie = None


# ----------------------------------------------------------------------
# Ap movie len cua so
# ----------------------------------------------------------------------
def apply_movie(window, resolved_path):
    """Thay animation ma khong dung lai cua so hay vi tri."""
    movie = movie_for(window, resolved_path)
    if movie is None:
        return False

    old_movie = window.movie
    if old_movie is movie:
        # Cung mot GIF: chi can dam bao dang chay, khong dung toi kich thuoc.
        if not window.config.get("animation_paused") and movie.state() != QMovie.Running:
            movie.start()
        return True

    if window.label is None:
        window.label = QLabel(window)
        window.label.setAttribute(Qt.WA_TranslucentBackground)
        window.label.setStyleSheet("border: none;")

    window.movie = movie
    window._current_resolved_path = resolved_path
    window.label.setMovie(movie)

    # Giu ti le: tinh kich thuoc tu khung hinh goc doc tu file.
    refit_to_current_movie(window, resolved_path)

    # Dat lai trang thai pause cua movie moi.
    if window.config.get("animation_paused"):
        movie.setPaused(True)
    else:
        movie.start()

    # Movie cu van nam trong cache de tai su dung: chi tam dung.
    if old_movie is not None and old_movie is not movie:
        old_movie.stop()

    if window.tray is not None:
        window.tray.setIcon(window._tray_icon())
    return True


# ----------------------------------------------------------------------
# Kich thuoc
# ----------------------------------------------------------------------
def original_size(window, resolved_path=None):
    """Kich thuoc khung hinh goc cua GIF hien tai.

    Doc tu file qua QImageReader, khong qua QMovie, vi QMovie tra ve kich thuoc
    da scale sau khi setScaledSize.
    """
    if resolved_path is None:
        resolved_path = window._current_resolved_path
    dimensions = gif_library.gif_dimensions(resolved_path)
    if dimensions is not None:
        return dimensions
    if window.movie is not None:
        size = window.movie.currentPixmap().size()
        if size.width() > 0 and size.height() > 0:
            return size.width(), size.height()
    return 1, 1


def refit_to_current_movie(window, resolved_path=None):
    """Ap dung kich thuoc da luu, giu ti le cua GIF hien tai."""
    cfg = window.config
    original_width, original_height = original_size(window, resolved_path)
    lock_width = bool(cfg.get("width_locked", True))
    target = cfg.get("gif_width") if lock_width else cfg.get("gif_height")
    width, height = gif_library.scaled_size(
        original_width, original_height, target, lock_width
    )
    apply_size(window, width, height, persist=False)


def apply_size(window, width, height, persist=True):
    """Dat kich thuoc cua so va movie, giu nguyen ti le."""
    if window.movie is not None:
        window.movie.setScaledSize(QSize(width, height))
    if window.label is not None:
        window.label.resize(width, height)
        window.label.move(0, 0)
    window.resize(width, height)
    if persist:
        window.config.data["gif_width"] = width
        window.config.data["gif_height"] = height
        window.config.save()


# ----------------------------------------------------------------------
# Nap GIF
# ----------------------------------------------------------------------
def prune_gif_list(window):
    """Loai khoi thu vien nhung entry tro toi file da mat hoac hong.

    Nho vay vong doi GIF 10 giay khong bao gio chon trung file hong.
    """
    cfg = window.config
    cleaned = gif_library.existing_entries(cfg.get("gif_list"), window.base_dir)
    cfg.data["gif_list"] = cleaned
    # Giai phong QMovie cua file da bi xoa/khoi thu vien.
    if hasattr(window, "_movie_cache"):
        prune_movie_cache(window)
    return cleaned


def load_gif(window, preferred=None):
    """Nap GIF theo thu tu uu tien va luon co GIF de hien thi.

    Uu tien 1: GIF cua trang thai hien tai trong nhan vat dang dung.
    Uu tien 2: GIF da chon, neu con hop le.
    Uu tien 3: GIF hop le khac trong thu vien.
    Uu tien 4: GIF mac dinh di kem repo.
    """
    cfg = window.config
    # Luon don thu vien GIF truoc, du sau do di theo nhanh nao.
    prune_gif_list(window)

    # Uu tien 1: animation cua trang thai hien tai trong pet pack.
    if window.pack is not None and preferred is None:
        state_path = window.pack.animation_path(window.state)
        if state_path is not None:
            return apply_movie(window, state_path)

    wanted = preferred if preferred is not None else cfg.get("gif_path")

    resolved, stored = gif_library.pick_working_gif(
        wanted, cfg.get("gif_list"), window.base_dir
    )
    if resolved is None:
        # Thu cuoi: nhan vat dang dung co GIF nao khac khong.
        if window.pack is not None:
            fallback = window.pack.animation_path(window.state)
            if fallback is not None:
                return apply_movie(window, fallback)
        window._show_missing_gif_message()
        return False

    if stored != wanted:
        print(f"GIF đã chọn không dùng được, chuyển sang: {resolved}")

    stored_list = gif_library.normalize_path(resolved, window.base_dir)
    if stored_list not in cfg.data["gif_list"]:
        cfg.data["gif_list"].append(stored_list)
    cfg.data["gif_path"] = gif_library.normalize_path(resolved, window.base_dir)

    apply_movie(window, resolved)
    return True
