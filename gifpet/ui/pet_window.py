"""Cua so pet trong suot hien thi GIF.

Kien truc:
- ``Config``       : cau hinh nguoi dung, luu ngoai repo.
- ``gif_library``  : chon GIF hop le, khong bao gio ket dinh file hong.
- ``pet_pack``     : thu vien nhan vat, thieu trang thai thi dung idle.gif.
- ``screen_utils`` : giu pet trong pham vi man hinh.
- ``PetWindow``    : cua so pet, menu khay, phim tat.

Hai diem da sua so voi ban goc:
- ``mouseMoveEvent`` khong con ghi JSON moi lan di chuyen; chi luu khi tha chuot.
- ``scale_gif`` khong con ep GIF thanh hinh vuong; kich thuoc tinh theo ti le.

Trang thai hanh vi (idle/walk/drag/fall/sleep/react/talk) hien moi o muc co ban:
``set_state`` da co san va tu dong chon GIF theo trang thai. May trang thai day
du voi quy tac uu tien se nam o ``gifpet/core/state.py`` (Giai doan 3).
"""

import os
import random

from PyQt5.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QMovie, QRegion
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSystemTrayIcon,
    QVBoxLayout,
)

from gifpet.core import gif_library, paths, pet_pack
from gifpet.core import screen_utils
from gifpet.core.config import Config
from gifpet.ui.dialogs import ResizeDialog, SettingsDialog
from gifpet.ui.gif_library_dialog import GifLibraryDialog

# Goc project: noi chua GIF di kem va thu muc pets/.
BASE_DIR = paths.PROJECT_ROOT
WALK_INTERVAL_MS = 40
WALK_STEP = 2

# Trang thai hien tai cua pet. Giai doan 3 se mo rong thanh may trang thai day du.
STATE_IDLE = "idle"
STATE_WALK = "walk"
STATE_DRAG = "drag"


class PetWindow(QLabel):
    def __init__(self, app, config=None):
        super().__init__()
        self.app = app
        self.config = config or Config()
        self.dragging = False
        self.offset = QPoint()
        self.label = None
        self.movie = None
        self.tray = None
        self.walk_direction = 1
        self._hidden_for_fullscreen = False
        self._current_resolved_path = None
        self.state = STATE_IDLE
        self.pack = None
        self.packs = []

        self._restore_state()
        self._load_pack()
        self._setup_window_flags()
        self._load_gif()
        self._setup_timers()
        self._setup_tray()
        self._setup_shortcuts()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # Khoi tao
    # ------------------------------------------------------------------
    def _restore_state(self):
        cfg = self.config
        cfg.data["gif_list"] = self._clean_list(cfg.get("gif_list"))

    def _load_pack(self):
        """Tim cac nhan vat trong pets/ va chon nhan vat dang dung."""
        self.packs = pet_pack.discover_packs(paths.PETS_DIR)
        if not self.packs:
            print(
                f"Canh bao: khong tim thay nhan vat nao trong {paths.PETS_DIR}. "
                "Se dung danh sach GIF rieng le trong cau hinh."
            )
            return

        wanted = self.config.get("pet_pack")
        chosen = None
        for pack in self.packs:
            if pack.name == wanted:
                chosen = pack
                break
        if chosen is None:
            chosen = pet_pack.load_default_pack(paths.PETS_DIR)

        self.pack = chosen
        if chosen is not None:
            missing = chosen.missing_states()
            if missing:
                print(
                    f"Nhan vat '{chosen.name}' thieu animation cho: "
                    f"{', '.join(missing)} -> dung {chosen.fallback_animation} thay the."
                )
            self.config.data["pet_pack"] = chosen.name

    def available_packs(self):
        return list(self.packs)


    def _clean_list(self, entries):
        """Loai entry trung lap va entry rong khoi thu vien."""
        cleaned = []
        for entry in entries or []:
            if isinstance(entry, str) and entry.strip() and entry not in cleaned:
                cleaned.append(entry)
        return cleaned

    def _setup_window_flags(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._apply_pin(self.config.get("pin_to_top"), persist=False)

    def _setup_shortcuts(self):
        """Phim tat luon dung duoc, ke ca khi bat click xuyen."""
        self.shortcut_pause = QShortcut(QKeySequence("Ctrl+Alt+P"), self)
        self.shortcut_pause.activated.connect(self.toggle_animation_pause)

        self.shortcut_center = QShortcut(QKeySequence("Ctrl+Alt+C"), self)
        self.shortcut_center.activated.connect(self.center_on_screen)

        self.shortcut_visible = QShortcut(QKeySequence("Ctrl+Alt+H"), self)
        self.shortcut_visible.activated.connect(self.toggle_visible)

        # Thoat phai luon dung duoc: neu bat click xuyen, chuot khong bam duoc pet.
        self.shortcut_quit = QShortcut(QKeySequence("Ctrl+Alt+Q"), self)
        self.shortcut_quit.activated.connect(self.quit_app)

    def _setup_timers(self):
        self.switch_timer = QTimer(self)
        self.switch_timer.timeout.connect(self.auto_switch_gif)
        self._apply_switch_timer()

        self.walk_timer = QTimer(self)
        self.walk_timer.timeout.connect(self._walk_step)

        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.timeout.connect(self._check_fullscreen)
        if self.config.get("hide_on_fullscreen"):
            self.fullscreen_timer.start(1000)

    def _setup_tray(self):
        """Tao icon khay he thong. Khong co tray thi app van chay."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Canh bao: he thong khong co khay. Dung chuot phai tren pet hoac phim tat.")
            self._build_menu()  # van tao menu de dung lai khi chuot phai
            return

        icon = self._tray_icon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("GIF Pet")
        self.tray.activated.connect(self._on_tray_activated)
        self._build_menu()
        self.tray.show()

    def _tray_icon(self):
        icon_path = paths.APP_ICON
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                return icon
        if self.movie is not None:
            pixmap = self.movie.currentPixmap()
            if not pixmap.isNull():
                return QIcon(pixmap)
        return self.style().standardIcon(self.style().SP_ComputerIcon)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _build_menu(self):
        """Dung menu mot lan va cap nhat trang thai checkbox khi mo."""
        self.menu = QMenu(self)
        self.menu.setStyleSheet(
            "QMenu { background-color: #333; color: white; }"
            "QMenu::item:selected { background-color: #555; }"
        )

        self.action_visible = QAction("Hiện pet", self, checkable=True)
        self.action_visible.triggered.connect(self.toggle_visible)

        self.action_pause = QAction("Tạm dừng animation", self, checkable=True)
        self.action_pause.triggered.connect(self.toggle_animation_pause)

        self.action_auto_switch = QAction("Tự động đổi GIF", self, checkable=True)
        self.action_auto_switch.triggered.connect(self.toggle_auto_switch)

        self.action_walk = QAction("Pet tự đi", self, checkable=True)
        self.action_walk.triggered.connect(self.toggle_auto_walk)

        self.action_click_through = QAction("Click xuyên qua pet", self, checkable=True)
        self.action_click_through.triggered.connect(self.toggle_click_through)

        self.action_pin = QAction("Luôn nổi trên cùng", self, checkable=True)
        self.action_pin.triggered.connect(lambda: self._apply_pin(not self.config.get("pin_to_top")))

        self.action_hide_fullscreen = QAction(
            "Ẩn khi có ứng dụng toàn màn hình", self, checkable=True
        )
        self.action_hide_fullscreen.triggered.connect(self.toggle_hide_on_fullscreen)

        self.action_library = QAction("Thư viện GIF…", self)
        self.action_library.triggered.connect(self.open_library)

        self.action_resize = QAction("Chỉnh kích thước…", self)
        self.action_resize.triggered.connect(self.open_resize)

        self.action_center = QAction("Đưa về giữa màn hình", self)
        self.action_center.triggered.connect(self.center_on_screen)

        self.action_settings = QAction("Cài đặt…", self)
        self.action_settings.triggered.connect(self.open_settings)

        self.action_exit = QAction("Thoát", self)
        self.action_exit.triggered.connect(self.quit_app)

        self.menu.addAction(self.action_visible)
        self.menu.addAction(self.action_pause)
        self.menu.addSeparator()
        self.menu.addAction(self.action_auto_switch)
        self.menu.addAction(self.action_walk)
        self.menu.addAction(self.action_click_through)
        self.menu.addAction(self.action_hide_fullscreen)
        self.menu.addAction(self.action_pin)
        self.menu.addSeparator()
        self.menu.addAction(self.action_library)
        self.menu.addAction(self.action_resize)
        self.menu.addAction(self.action_center)
        self.menu.addAction(self.action_settings)
        self.menu.addSeparator()
        self.menu.addAction(self.action_exit)

        if self.tray is not None:
            self.tray.setContextMenu(self.menu)

    def _sync_menu(self):
        self.action_visible.setChecked(bool(self.config.get("visible")))
        self.action_visible.setText(
            "Ẩn pet" if self.config.get("visible") else "Hiện pet"
        )
        self.action_pause.setChecked(bool(self.config.get("animation_paused")))
        self.action_auto_switch.setChecked(bool(self.config.get("auto_switch_enabled")))
        self.action_walk.setChecked(bool(self.config.get("auto_walk")))
        self.action_click_through.setChecked(bool(self.config.get("click_through")))
        self.action_pin.setChecked(bool(self.config.get("pin_to_top")))
        self.action_hide_fullscreen.setChecked(bool(self.config.get("hide_on_fullscreen")))

    def _popup_menu(self, position):
        self._sync_menu()
        self.menu.exec_(position)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_visible()

    # ------------------------------------------------------------------
    # GIF
    # ------------------------------------------------------------------
    def _load_gif(self, preferred=None):
        """Nap GIF theo thu tu uu tien va luon co GIF de hien thi.

        Uu tien 1: GIF cua trang thai hien tai trong nhan vat dang dung.
        Uu tien 2: GIF da chon, neu con hop le.
        Uu tien 3: GIF hop le khac trong thu vien.
        Uu tien 4: GIF mac dinh di kem repo.
        """
        cfg = self.config
        # Luon don thu vien GIF truoc, du sau do di theo nhanh nao.
        self._prune_gif_list()

        # Uu tien 1: animation cua trang thai hien tai trong pet pack.
        if self.pack is not None and preferred is None:
            state_path = self.pack.animation_path(self.state)
            if state_path is not None:
                return self._apply_movie(state_path)

        wanted = preferred if preferred is not None else cfg.get("gif_path")

        resolved, stored = gif_library.pick_working_gif(
            wanted, cfg.get("gif_list"), BASE_DIR
        )
        if resolved is None:
            # Thu cuoi: nhan vat dang dung co GIF nao khac khong.
            if self.pack is not None:
                fallback = self.pack.animation_path(self.state)
                if fallback is not None:
                    return self._apply_movie(fallback)
            self._show_missing_gif_message()
            return False

        if stored != wanted:
            print(f"GIF đã chọn không dùng được, chuyển sang: {resolved}")

        stored_list = gif_library.normalize_path(resolved, BASE_DIR)
        if stored_list not in cfg.data["gif_list"]:
            cfg.data["gif_list"].append(stored_list)
        cfg.data["gif_path"] = gif_library.normalize_path(resolved, BASE_DIR)

        self._apply_movie(resolved)
        return True

    def _prune_gif_list(self):
        """Loai khoi thu vien nhung entry tro toi file da mat hoac hong.

        Nho vay vong doi GIF 10 giay khong bao gio chon trung file hong.
        """
        cfg = self.config
        cleaned = gif_library.existing_entries(cfg.get("gif_list"), BASE_DIR)
        cfg.data["gif_list"] = cleaned
        return cleaned

    def set_state(self, state):
        """Chuyen trang thai va doi animation tuong ung.

        Neu nhan vat khong co GIF cho trang thai nay, ``animation_path`` tu
        dong tra ve fallback (mac dinh idle.gif), nen khong can xu ly rieng.
        """
        if state == self.state:
            return False
        previous = self.state
        self.state = state

        if self.pack is None:
            return False

        path = self.pack.animation_path(state)
        if path is None:
            self.state = previous
            return False
        # Khong dung lai cua so hay vi tri: chi thay movie.
        self._apply_movie(path)
        return True

    def _apply_movie(self, resolved_path):
        """Thay animation ma khong dung lai cua so hay vi tri."""
        old_movie = self.movie
        movie = QMovie(resolved_path)
        if not movie.isValid():
            return False

        if self.label is None:
            self.label = QLabel(self)
            self.label.setAttribute(Qt.WA_TranslucentBackground)
            self.label.setStyleSheet("border: none;")

        self.movie = movie
        self._current_resolved_path = resolved_path
        self.label.setMovie(movie)

        # Giu ti le: tinh kich thuoc tu khung hinh goc doc tu file.
        self._refit_to_current_movie(resolved_path)

        # Dat lai trang thai pause cua movie moi.
        if self.config.get("animation_paused"):
            movie.setPaused(True)
        else:
            movie.start()

        if old_movie is not None and old_movie is not movie:
            old_movie.stop()
            old_movie.deleteLater()

        if self.tray is not None:
            self.tray.setIcon(self._tray_icon())
        return True

    def original_size(self, resolved_path=None):
        """Kich thuoc khung hinh goc cua GIF hien tai.

        Doc tu file qua QImageReader, khong qua QMovie, vi QMovie tra ve kich
        thuoc da scale sau khi setScaledSize.
        """
        if resolved_path is None:
            resolved_path = self._current_resolved_path
        dimensions = gif_library.gif_dimensions(resolved_path)
        if dimensions is not None:
            return dimensions
        if self.movie is not None:
            size = self.movie.currentPixmap().size()
            if size.width() > 0 and size.height() > 0:
                return size.width(), size.height()
        return 1, 1

    def _refit_to_current_movie(self, resolved_path=None):
        """Ap dung kich thuoc da luu, giu ti le cua GIF hien tai."""
        cfg = self.config
        original_width, original_height = self.original_size(resolved_path)
        lock_width = bool(cfg.get("width_locked", True))
        target = cfg.get("gif_width") if lock_width else cfg.get("gif_height")
        width, height = gif_library.scaled_size(
            original_width, original_height, target, lock_width
        )
        self._apply_size(width, height, persist=False)

    def _apply_size(self, width, height, persist=True):
        if self.movie is not None:
            self.movie.setScaledSize(QSize(width, height))
        if self.label is not None:
            self.label.resize(width, height)
            self.label.move(0, 0)
        self.resize(width, height)
        if persist:
            self.config.data["gif_width"] = width
            self.config.data["gif_height"] = height
            self.config.save()

    # ------------------------------------------------------------------
    # Vi tri
    # ------------------------------------------------------------------
    def _restore_geometry(self):
        """Dat pet dung cho, keo ve man hinh chinh neu toa do da luu bi lac."""
        width = max(1, self.width())
        height = max(1, self.height())
        x = int(self.config.get("x", 0))
        y = int(self.config.get("y", 0))

        safe_x, safe_y = screen_utils.ensure_visible(self.app, x, y, width, height)
        if (safe_x, safe_y) != (x, y):
            print(f"Tọa độ đã lưu ({x}, {y}) nằm ngoài màn hình, đưa về ({safe_x}, {safe_y}).")
            self.config.data["x"] = safe_x
            self.config.data["y"] = safe_y
            self.config.save()
        self.move(safe_x, safe_y)

        if self.config.get("click_through"):
            self._apply_click_through(True, persist=False)

        if not self.config.get("visible"):
            super().hide()
        else:
            self.show()

    def center_on_screen(self):
        width = max(1, self.width())
        height = max(1, self.height())
        x, y = screen_utils.center_on_primary(self.app, width, height)
        self.move(x, y)
        self.config.data["x"] = x
        self.config.data["y"] = y
        self.config.save()
        if not self.config.get("visible"):
            self.toggle_visible()
        print(f"Đã đưa pet về giữa màn hình: ({x}, {y})")

    # ------------------------------------------------------------------
    # Chuot
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.globalPos() - self.pos()
        elif event.button() == Qt.RightButton:
            self._popup_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        """Chi di chuyen cua so; KHONG ghi file o day."""
        if self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        """Luu vi tri mot lan duy nhat khi tha chuot."""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.config.data["x"] = self.x()
            self.config.data["y"] = self.y()
            self.config.save()

    # ------------------------------------------------------------------
    # Hanh dong menu
    # ------------------------------------------------------------------
    def toggle_visible(self):
        visible = not bool(self.config.get("visible"))
        self.config.data["visible"] = visible
        if visible:
            self.show()
            self.raise_()
        else:
            super().hide()
            # Khong chay animation khi pet bi an.
            if self.movie is not None:
                self.movie.setPaused(True)
        if visible and not self.config.get("animation_paused") and self.movie is not None:
            self.movie.setPaused(False)
        self.config.save()

    def toggle_animation_pause(self):
        """Tach rieng voi viec doi GIF: pause GIF that su dung hinh."""
        paused = not bool(self.config.get("animation_paused"))
        self.config.data["animation_paused"] = paused
        if self.movie is not None:
            self.movie.setPaused(paused)
        self.config.save()
        print("Animation tạm dừng." if paused else "Animation tiếp tục.")

    def toggle_auto_switch(self):
        enabled = not bool(self.config.get("auto_switch_enabled"))
        self.config.data["auto_switch_enabled"] = enabled
        self._apply_switch_timer()
        self.config.save()

    def _apply_switch_timer(self):
        if self.config.get("auto_switch_enabled") and not self.config.get("animation_paused"):
            seconds = max(2, int(self.config.get("auto_switch_seconds", 10)))
            self.switch_timer.start(seconds * 1000)
        else:
            self.switch_timer.stop()

    def toggle_auto_walk(self):
        enabled = not bool(self.config.get("auto_walk"))
        self.config.data["auto_walk"] = enabled
        self._apply_walk_timer()
        self.config.save()

    def _apply_walk_timer(self):
        if self.config.get("auto_walk") and self.config.get("visible"):
            self.walk_timer.start(WALK_INTERVAL_MS)
        else:
            self.walk_timer.stop()

    def _walk_step(self):
        """Pet tu đi ngang trong pham vi man hinh chinh."""
        screen = self.app.primaryScreen()
        if screen is None:
            return
        area = QRect(screen.availableGeometry())
        x = self.x() + WALK_STEP * self.walk_direction
        if x <= area.left():
            x = area.left()
            self.walk_direction = 1
        elif x + self.width() >= area.right():
            x = area.right() - self.width()
            self.walk_direction = -1
        self.move(x, self.y())
        self.config.data["x"] = x

    def toggle_click_through(self):
        enabled = not bool(self.config.get("click_through"))
        self._apply_click_through(enabled)

    def _apply_click_through(self, enabled, persist=True):
        """Bat/tat click xuyen qua pet.

        WA_TransparentForMouseEvents giu cho Qt khong nhan su kien chuot, va
        mask rong lam cho cua so khong nhan input o tang cua so (X11/Wayland).
        Khi bat, menu khay va phim tat van hoat dong binh thuong.
        """
        enabled = bool(enabled)
        self.config.data["click_through"] = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        if enabled:
            self.setMask(QRegion())
        else:
            self.clearMask()
        if persist:
            self.config.save()
        if enabled:
            print(
                "Đã bật click xuyên. Dùng khay hệ thống hoặc Ctrl+Alt+H để hiện/ẩn, "
                "Ctrl+Alt+Q để thoát."
            )

    def toggle_hide_on_fullscreen(self):
        self.toggle_fullscreen_watch(not bool(self.config.get("hide_on_fullscreen")))

    def toggle_fullscreen_watch(self, enabled):
        enabled = bool(enabled)
        self.config.data["hide_on_fullscreen"] = enabled
        if enabled:
            self.fullscreen_timer.start(1000)
            self._check_fullscreen()
        else:
            self.fullscreen_timer.stop()
            self._restore_after_fullscreen()
        self.config.save()

    def _restore_after_fullscreen(self):
        if not self._hidden_for_fullscreen:
            return
        self._hidden_for_fullscreen = False
        if self.config.get("visible"):
            self.show()
            if not self.config.get("animation_paused") and self.movie is not None:
                self.movie.setPaused(False)

    def _check_fullscreen(self):
        """An pet khi co ung dung khac dang chiem toan man hinh.

        Uu tien tin hieu tu window manager qua X11; neu khong lay duoc thi
        so sanh vung lam viec voi toan bo man hinh lam uoc luong.
        """
        if not self.config.get("hide_on_fullscreen"):
            return
        fullscreen = self._another_window_is_fullscreen()
        if fullscreen and not self._hidden_for_fullscreen:
            self._hidden_for_fullscreen = True
            super().hide()
            if self.movie is not None:
                self.movie.setPaused(True)
            print("Có ứng dụng toàn màn hình: tạm ẩn pet.")
        elif not fullscreen:
            self._restore_after_fullscreen()

    def _another_window_is_fullscreen(self):
        """Tra ve True neu man hinh chinh dang bi cua so khac phu kin.

        Tren X11 doc thuoc tinh _NET_ACTIVE_WINDOW roi kiem tra _NET_WM_STATE
        co _NET_WM_STATE_FULLSCREEN. Neu khong ho tro, tra ve False de tranh
        an pet nham.
        """
        if os.name == "nt" or not os.environ.get("DISPLAY"):
            return False
        try:
            return self._x11_fullscreen_active()
        except Exception:
            return False

    def _x11_fullscreen_active(self):
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
        handle = self.windowHandle()
        if handle is not None:
            try:
                if hex(int(handle.winId())) == hex(int(window_id, 16)):
                    return False
            except (ValueError, TypeError):
                pass

        state = xprop(["-id", window_id, "_NET_WM_STATE"])
        return "_NET_WM_STATE_FULLSCREEN" in state

    # ------------------------------------------------------------------
    # Dialog
    # ------------------------------------------------------------------
    def open_library(self):
        dialog = GifLibraryDialog(
            self.config.get("gif_list"), self.config.get("gif_path"), BASE_DIR, self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.config.data["gif_list"] = self._clean_list(dialog.result_entries())
            chosen = dialog.selected
            self.config.save()
            if chosen:
                self._load_gif(preferred=chosen)
            else:
                # Danh sach co the da bi don het; dam bao van con GIF.
                self._load_gif()

    def open_resize(self):
        original_width, original_height = self.original_size()
        dialog = ResizeDialog(
            original_width,
            original_height,
            self.config.get("gif_width", original_width),
            bool(self.config.get("width_locked", True)),
            self,
        )
        if dialog.exec_() == QDialog.Accepted:
            width, height, lock_width = dialog.values()
            self.config.data["width_locked"] = lock_width
            self._apply_size(width, height, persist=True)

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        click_through_changed = values["click_through"] != bool(
            self.config.get("click_through")
        )
        hide_fullscreen_changed = values["hide_on_fullscreen"] != bool(
            self.config.get("hide_on_fullscreen")
        )
        pin_changed = values["pin_to_top"] != bool(self.config.get("pin_to_top"))

        self.config.data.update(values)
        self.config.save()

        if click_through_changed:
            self._apply_click_through(values["click_through"], persist=False)
        if hide_fullscreen_changed:
            self.toggle_fullscreen_watch(values["hide_on_fullscreen"])
        if pin_changed:
            self._apply_pin(values["pin_to_top"], persist=False)
        self._apply_switch_timer()
        self._apply_walk_timer()

    def _apply_pin(self, pinned, persist=True):
        flags = self.windowFlags()
        if pinned:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.config.data["pin_to_top"] = bool(pinned)
        if persist:
            self.config.save()
        if self.config.get("visible"):
            self.show()

    # ------------------------------------------------------------------
    # GIF switching
    # ------------------------------------------------------------------
    def auto_switch_gif(self):
        """Doi sang GIF hop le khac trong thu vien."""
        if self.config.get("animation_paused"):
            return
        current = self.config.get("gif_path")
        candidates = [
            entry
            for entry in self.config.get("gif_list")
            if entry != current
            and gif_library.is_valid_gif(gif_library.resolve_path(entry, BASE_DIR))
        ]
        if not candidates:
            return
        new_gif = random.choice(candidates)
        self._load_gif(preferred=new_gif)
        self.config.save()

    def _show_missing_gif_message(self):
        text = (
            "Không tìm thấy GIF nào dùng được.\n\n"
            "Hãy thêm GIF qua “Thư viện GIF…” hoặc đặt lại file abc.gif "
            "vào thư mục ứng dụng."
        )
        print(text)
        if self.tray is not None:
            self.tray.showMessage("GIF Pet", text, QSystemTrayIcon.Warning, 5000)

    # ------------------------------------------------------------------
    # Thoat
    # ------------------------------------------------------------------
    def quit_app(self):
        self.config.save()
        if self.tray is not None:
            self.tray.hide()
        self.app.quit()

    def closeEvent(self, event):
        self.config.save()
        if self.tray is not None:
            self.tray.hide()
        event.accept()
