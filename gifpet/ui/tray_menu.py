"""Icon khay he thong va menu chuot phai.

Tach ra khoi ``pet_window`` vi day la phan dai nhat va thay doi thuong xuyen
nhat: moi tinh nang moi deu them mot muc menu. Nam rieng mot file thi them muc
menu chi phai sua mot cho.

Cach dung: moi ham nhan ``window`` (PetWindow) lam tham so dau tien. Cac action
duoc gan thanh thuoc tinh cua ``window`` (``window.action_visible``, ...) vi
``_sync_menu`` va cac test doc chung.
"""

import os

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon

from gifpet.core import paths

MENU_STYLE = (
    "QMenu { background-color: #333; color: white; }"
    "QMenu::item:selected { background-color: #555; }"
)


# ----------------------------------------------------------------------
# Khay he thong
# ----------------------------------------------------------------------
def setup_tray(window):
    """Tao icon khay he thong. Khong co tray thi app van chay."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Canh bao: he thong khong co khay. Dung chuot phai tren pet hoac phim tat.")
        build_menu(window)  # van tao menu de dung lai khi chuot phai
        return

    icon = tray_icon(window)
    window.tray = QSystemTrayIcon(icon, window)
    window.tray.setToolTip("GIF Pet")
    window.tray.activated.connect(window._on_tray_activated)
    build_menu(window)
    window.tray.show()


def tray_icon(window):
    """Icon khay: file .ico, neu khong co thi lay khung hinh GIF hien tai."""
    icon_path = paths.APP_ICON
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        if not icon.isNull():
            return icon
    if window.movie is not None:
        pixmap = window.movie.currentPixmap()
        if not pixmap.isNull():
            return QIcon(pixmap)
    style = window.style()
    return style.standardIcon(style.SP_ComputerIcon)


# ----------------------------------------------------------------------
# Menu
# ----------------------------------------------------------------------
def build_menu(window):
    """Dung menu mot lan va cap nhat trang thai checkbox khi mo."""
    menu = QMenu(window)
    window.menu = menu
    menu.setStyleSheet(MENU_STYLE)

    # --- Hien thi ---
    window.action_visible = QAction("Hiện pet", window, checkable=True)
    window.action_visible.triggered.connect(window.toggle_visible)

    window.action_pause = QAction("Tạm dừng animation", window, checkable=True)
    window.action_pause.triggered.connect(window.toggle_animation_pause)

    # --- Hanh vi ---
    window.action_auto_switch = QAction("Tự động đổi GIF", window, checkable=True)
    window.action_auto_switch.triggered.connect(window.toggle_auto_switch)

    window.action_walk = QAction("Pet tự đi", window, checkable=True)
    window.action_walk.triggered.connect(window.toggle_auto_walk)

    window.action_focus = QAction("Chế độ tập trung", window, checkable=True)
    window.action_focus.setToolTip("Pet đứng yên hoặc ngủ, không tự đi")
    window.action_focus.triggered.connect(window.toggle_focus_mode)

    window.action_sleep = QAction("Cho pet ngủ ngay", window)
    window.action_sleep.triggered.connect(window.send_to_sleep)

    # --- Pomodoro ---
    window.action_pomodoro = QAction(
        "Nhắc tập trung / nghỉ", window, checkable=True
    )
    window.action_pomodoro.setToolTip("Pomodoro: nhắc uống nước và thư giãn mắt")
    window.action_pomodoro.triggered.connect(window.toggle_pomodoro)

    window.pomodoro_menu = QMenu("Đồng hồ tập trung", window)
    window.action_pomodoro_status = QAction("Chưa bật", window)
    window.action_pomodoro_status.setEnabled(False)

    window.action_pomodoro_pause = QAction("Tạm dừng đồng hồ", window)
    window.action_pomodoro_pause.triggered.connect(window.pomodoro_pause)

    window.action_pomodoro_resume = QAction("Chạy tiếp", window)
    window.action_pomodoro_resume.triggered.connect(window.pomodoro_resume)

    window.action_pomodoro_skip = QAction("Bỏ qua, sang pha tiếp", window)
    window.action_pomodoro_skip.triggered.connect(window.pomodoro_skip)

    window.action_pomodoro_remind = QAction("Nhắc uống nước ngay", window)
    window.action_pomodoro_remind.triggered.connect(window.remind_now)

    window.pomodoro_menu.addAction(window.action_pomodoro_status)
    window.pomodoro_menu.addSeparator()
    window.pomodoro_menu.addAction(window.action_pomodoro_pause)
    window.pomodoro_menu.addAction(window.action_pomodoro_resume)
    window.pomodoro_menu.addAction(window.action_pomodoro_skip)
    window.pomodoro_menu.addAction(window.action_pomodoro_remind)

    # --- AI ---
    window.action_chat = QAction("Hỏi pet…", window)
    window.action_chat.triggered.connect(window.open_chat)

    # --- Cua so ---
    window.action_click_through = QAction(
        "Click xuyên qua pet", window, checkable=True
    )
    window.action_click_through.triggered.connect(window.toggle_click_through)

    window.action_pin = QAction("Luôn nổi trên cùng", window, checkable=True)
    window.action_pin.triggered.connect(
        lambda: window._apply_pin(not window.config.get("pin_to_top"))
    )

    window.action_hide_fullscreen = QAction(
        "Ẩn khi có ứng dụng toàn màn hình", window, checkable=True
    )
    window.action_hide_fullscreen.triggered.connect(window.toggle_hide_on_fullscreen)

    # --- Cong cu ---
    window.action_library = QAction("Thư viện GIF…", window)
    window.action_library.triggered.connect(window.open_library)

    window.action_resize = QAction("Chỉnh kích thước…", window)
    window.action_resize.triggered.connect(window.open_resize)

    window.action_center = QAction("Đưa về giữa màn hình", window)
    window.action_center.triggered.connect(window.center_on_screen)

    window.action_settings = QAction("Cài đặt…", window)
    window.action_settings.triggered.connect(window.open_settings)

    window.action_exit = QAction("Thoát", window)
    window.action_exit.triggered.connect(window.quit_app)

    # --- Sap xep menu, nhom theo chu de ---
    menu.addAction(window.action_visible)
    menu.addAction(window.action_pause)
    menu.addSeparator()
    menu.addAction(window.action_auto_switch)
    menu.addAction(window.action_walk)
    menu.addAction(window.action_focus)
    menu.addAction(window.action_sleep)
    menu.addSeparator()
    menu.addAction(window.action_pomodoro)
    menu.addMenu(window.pomodoro_menu)
    menu.addSeparator()
    menu.addAction(window.action_chat)
    menu.addAction(window.action_click_through)
    menu.addAction(window.action_hide_fullscreen)
    menu.addAction(window.action_pin)
    menu.addSeparator()
    menu.addAction(window.action_library)
    menu.addAction(window.action_resize)
    menu.addAction(window.action_center)
    menu.addAction(window.action_settings)
    menu.addSeparator()
    menu.addAction(window.action_exit)

    if window.tray is not None:
        window.tray.setContextMenu(menu)


def sync_menu(window):
    """Cap nhat dau checkbox va cau trang thai truoc khi hien menu."""
    cfg = window.config
    window.action_visible.setChecked(bool(cfg.get("visible")))
    window.action_visible.setText("Ẩn pet" if cfg.get("visible") else "Hiện pet")
    window.action_pause.setChecked(bool(cfg.get("animation_paused")))
    window.action_auto_switch.setChecked(bool(cfg.get("auto_switch_enabled")))
    window.action_walk.setChecked(bool(cfg.get("auto_walk")))
    window.action_focus.setChecked(bool(cfg.get("focus_mode")))
    window.action_sleep.setEnabled(window.machine.can_sleep())

    # Trang thai dong ho tap trung.
    window.action_pomodoro.setChecked(bool(cfg.get("pomodoro_enabled")))
    window.action_pomodoro_status.setText(window.pomodoro_status())
    active = cfg.get("pomodoro_enabled")
    window.pomodoro_menu.setEnabled(True)
    window.action_pomodoro_pause.setEnabled(
        active and window.pomodoro.phase in ("focus", "break")
    )
    window.action_pomodoro_resume.setEnabled(
        active and window.pomodoro.phase == "paused"
    )
    window.action_pomodoro_skip.setEnabled(active)
    window.action_click_through.setChecked(bool(cfg.get("click_through")))
    window.action_pin.setChecked(bool(cfg.get("pin_to_top")))
    window.action_hide_fullscreen.setChecked(bool(cfg.get("hide_on_fullscreen")))


def popup_menu(window, position):
    """Hien menu tai vi tri chuot, cap nhat trang thai truoc."""
    sync_menu(window)
    # Cap nhat dong ho ngay truoc khi hien, de dem nguoc dung.
    window.action_pomodoro_status.setText(window.pomodoro_status())
    window.menu.exec_(position)


def on_tray_activated(window, reason):
    """Bam trai vao icon khay: an/hien pet."""
    if reason == QSystemTrayIcon.Trigger:
        window.toggle_visible()


# ----------------------------------------------------------------------
# Thong bao khay
# ----------------------------------------------------------------------
# Dung hang cua QSystemTrayIcon qua module nay de pet_window khong phai import
# Qt widget chi de lay mot con so.
NOTIFY_INFO = QSystemTrayIcon.Information
NOTIFY_WARNING = QSystemTrayIcon.Warning
NOTIFY_SECONDS = 5000


def notify(window, message, warning=False):
    """Hien thong bao khay neu co khay. Khong co thi bo qua, khong loi."""
    if window.tray is None:
        return
    icon = NOTIFY_WARNING if warning else NOTIFY_INFO
    window.tray.showMessage("GIF Pet", message, icon, NOTIFY_SECONDS)
