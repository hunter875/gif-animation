"""Co che cua so: trong suot, click xuyen, fullscreen, luon noi tren cung.

Tach ra khoi ``pet_window`` vi day la nhom viec cham vao window manager cua he
dieu hanh - cho de loi nhat va cung la cho kho test nhat. Nam rieng mot file
thi viec sua logic X11 khong phai doc ca cua so pet.

Cach dung: moi ham nhan ``window`` (PetWindow) lam tham so dau tien.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QRegion



def setup_window_flags(window):
    """Cua so khong vien, trong suot, khong chiem taskbar."""
    window.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
    window.setAttribute(Qt.WA_TranslucentBackground)
    apply_pin(window, window.config.get("pin_to_top"), persist=False)


def apply_pin(window, pinned, persist=True):
    """Bat/tat luon noi tren cung.

    Doi window flags se an cua so, nen phai goi show() lai va giu vi tri.
    """
    pinned = bool(pinned)
    window.config.data["pin_to_top"] = pinned
    geometry = window.geometry()
    was_visible = window.isVisible()
    window.setWindowFlag(Qt.WindowStaysOnTopHint, pinned)
    window.setGeometry(geometry)
    if was_visible:
        window.show()
    if persist:
        window.config.save()


# ----------------------------------------------------------------------
# Click xuyen qua
# ----------------------------------------------------------------------
def toggle_click_through(window):
    enabled = not bool(window.config.get("click_through"))
    apply_click_through(window, enabled)


def apply_click_through(window, enabled, persist=True):
    """Bat/tat click xuyen qua pet.

    WA_TransparentForMouseEvents giu cho Qt khong nhan su kien chuot, va mask
    rong lam cho cua so khong nhan input o tang cua so (X11/Wayland). Khi bat,
    menu khay va phim tat van hoat dong binh thuong.
    """
    enabled = bool(enabled)
    window.config.data["click_through"] = enabled
    window.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
    if enabled:
        window.setMask(QRegion())
    else:
        window.clearMask()
    if persist:
        window.config.save()
    if enabled:
        print(
            "Đã bật click xuyên. Dùng khay hệ thống hoặc Ctrl+Alt+H để hiện/ẩn, "
            "Ctrl+Alt+Q để thoát."
        )


# ----------------------------------------------------------------------
# An khi co ung dung toan man hinh
# ----------------------------------------------------------------------
def toggle_hide_on_fullscreen(window):
    toggle_fullscreen_watch(
        window, not bool(window.config.get("hide_on_fullscreen"))
    )


def toggle_fullscreen_watch(window, enabled):
    enabled = bool(enabled)
    window.config.data["hide_on_fullscreen"] = enabled
    if enabled:
        window.fullscreen_timer.start(1000)
        check_fullscreen(window)
    else:
        window.fullscreen_timer.stop()
        restore_after_fullscreen(window)
    window.config.save()


def restore_after_fullscreen(window):
    """Hien lai pet sau khi ung dung toan man hinh dong."""
    if not window._hidden_for_fullscreen:
        return
    window._hidden_for_fullscreen = False
    if window.config.get("visible"):
        window.show()
        if not window.config.get("animation_paused") and window.movie is not None:
            window.movie.setPaused(False)


def check_fullscreen(window):
    """An pet khi co ung dung khac dang chiem toan man hinh.

    Uu tien tin hieu tu window manager qua X11; neu khong lay duoc thi so sanh
    vung lam viec voi toan bo man hinh lam uoc luong.
    """
    if not window.config.get("hide_on_fullscreen"):
        return
    fullscreen = another_window_is_fullscreen(window)
    if fullscreen and not window._hidden_for_fullscreen:
        window._hidden_for_fullscreen = True
        # super().hide(): bo qua override hide cua PetWindow neu co.
        type(window).__mro__[1].hide(window)
        if window.movie is not None:
            window.movie.setPaused(True)
        print("Có ứng dụng toàn màn hình: tạm ẩn pet.")
    elif not fullscreen:
        restore_after_fullscreen(window)


def another_window_is_fullscreen(window):
    """True neu man hinh chinh dang bi cua so khac phu kin.

    Tren X11 doc thuoc tinh _NET_ACTIVE_WINDOW roi kiem tra _NET_WM_STATE co
    _NET_WM_STATE_FULLSCREEN. Neu khong ho tro, tra ve False de tranh an pet
    nham.
    """
    if os.name == "nt" or not os.environ.get("DISPLAY"):
        return False
    try:
        return x11_fullscreen_active(window)
    except Exception:
        return False


def x11_fullscreen_active(window):
    """Doc trang thai fullscreen tu X11 bang xprop.

    Chi doc, khong dieu khien: ``xprop`` nhan danh sach tham so co dinh, khong
    qua shell. Xem docs/SECURITY.md.
    """
    import subprocess

    def xprop(args):
        result = subprocess.run(
            ["xprop"] + args,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout if result.returncode == 0 else ""

    root = xprop(["-root", "_NET_ACTIVE_WINDOW"])
    if "window id" not in root:
        return False
    window_id = root.split("window id")[-1].strip().split()[0]
    if not window_id or window_id == "0x0":
        return False

    # Cua so cua chinh pet khong tinh la fullscreen.
    handle = window.windowHandle()
    if handle is not None:
        try:
            if hex(int(handle.winId())) == hex(int(window_id, 16)):
                return False
        except (ValueError, TypeError):
            pass

    state = xprop(["-id", window_id, "_NET_WM_STATE"])
    return "_NET_WM_STATE_FULLSCREEN" in state
