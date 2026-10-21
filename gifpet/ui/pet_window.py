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
import sys
import time

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

from gifpet.core import behavior as behavior_module
from gifpet.core import falling
from gifpet.core import gif_library, paths, pet_pack
from gifpet.core import pomodoro as pomodoro_module
from gifpet.core import screen_utils
from gifpet.core import state as state_module
from gifpet.core.config import Config
from gifpet.ui.dialogs import ResizeDialog, SettingsDialog
from gifpet.ui.gif_library_dialog import GifLibraryDialog
from gifpet.ui.speech_bubble import SpeechBubble

# Goc project: noi chua GIF di kem va thu muc pets/.
BASE_DIR = paths.PROJECT_ROOT
WALK_INTERVAL_MS = 40
WALK_STEP = 2

# Nhip chay cua vong lap hanh vi (ms).
BEHAVIOR_TICK_MS = 100
# Nhip roi (ms) - nhanh hon de chuyen dong muot.
FALL_TICK_MS = 30
# Nhip kiem tra dong ho Pomodoro (ms).
POMODORO_TICK_MS = 1000


class PetWindow(QLabel):
    def __init__(self, app, config=None):
        super().__init__()
        self.app = app
        self.config = config or Config()
        self.dragging = False
        self.offset = QPoint()
        self._press_pos = QPoint()
        self._moved = False
        self.label = None
        self.movie = None
        # Cache QMovie theo duong dan: QMovie khong giai phong het tai nguyen
        # khi bi huy, nen phai tai su dung thay vi tao moi moi lan doi GIF.
        self._movie_cache = {}
        # Dem loi trong timer de chan vong lap loi dot CPU.
        self._error_count = 0
        self._error_window_start = 0.0
        self._error_paused = False
        self._last_error = None
        self.tray = None
        self.walk_direction = 1
        self._hidden_for_fullscreen = False
        self._current_resolved_path = None
        self.pack = None
        self.packs = []

        # May trang thai va bo dieu phoi hanh vi (Giai doan 3).
        self.machine = state_module.StateMachine(
            initial=state_module.IDLE,
            focus_mode=bool(self.config.get("focus_mode")),
        )
        self.machine.listeners.append(self._on_state_changed)
        self.behavior = behavior_module.Behavior(self.config)
        self.fall_sim = falling.FallSimulator()
        self._state_until_ms = 0
        self._fall_ground_y = 0

        # Nhac tap trung / nghi.
        self.pomodoro = pomodoro_module.Pomodoro(self.config)
        self.bubble = None
        self._last_checkin_ms = 0

        self._restore_state()
        self._load_pack()
        self._configure_from_pack()
        self._setup_window_flags()
        self._load_gif()
        self._setup_timers()
        self._setup_tray()
        self._setup_shortcuts()
        self._restore_geometry()

    @property
    def state(self):
        """Trang thai hien tai, lay tu may trang thai."""
        return self.machine.state

    def pack_behavior(self, key, default):
        """Gia tri hanh vi tu pet.json, uu tien hon mac dinh."""
        if self.pack is not None:
            value = self.pack.behavior.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
        return default

    def pack_movement(self, key, default):
        """Gia tri di chuyen tu pet.json."""
        if self.pack is not None:
            value = self.pack.movement.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
        return default

    def _configure_from_pack(self):
        """Ap dung thong so cua nhan vat vao bo mo phong roi."""
        self.fall_sim = falling.FallSimulator(
            gravity=self.pack_behavior("fall_gravity", 2.2),
            max_speed=self.pack_behavior("fall_max_speed", 28.0),
        )

    def now_ms(self):
        """Dong ho don dieu, dung cho logic hanh vi."""
        return int(time.monotonic() * 1000)

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
        self.switch_timer.timeout.connect(
            lambda: self._guarded("auto_switch_gif", self.auto_switch_gif)
        )
        self._apply_switch_timer()

        # Vong lap hanh vi: quyet dinh di / nghi / ngu.
        self.behavior_timer = QTimer(self)
        self.behavior_timer.timeout.connect(
            lambda: self._guarded("_behavior_tick", self._behavior_tick)
        )
        self.behavior_timer.start(BEHAVIOR_TICK_MS)

        # Di chuyen: tach rieng de toc do muot theo pet.json.
        self.walk_timer = QTimer(self)
        self.walk_timer.timeout.connect(
            lambda: self._guarded("_walk_step", self._walk_step)
        )

        # Roi: nhip nhanh hon.
        self.fall_timer = QTimer(self)
        self.fall_timer.timeout.connect(
            lambda: self._guarded("_fall_step", self._fall_step)
        )

        # Het thoi gian phan ung / noi thi quay ve idle.
        self.state_timer = QTimer(self)
        self.state_timer.setSingleShot(True)
        self.state_timer.timeout.connect(
            lambda: self._guarded("_on_state_timeout", self._on_state_timeout)
        )

        # Dong ho tap trung / nghi.
        self.pomodoro_timer = QTimer(self)
        self.pomodoro_timer.timeout.connect(
            lambda: self._guarded("_pomodoro_tick", self._pomodoro_tick)
        )
        if self.config.get("pomodoro_enabled"):
            self.pomodoro.start(self.now_ms())
            self.pomodoro_timer.start(POMODORO_TICK_MS)
            # Bat dau giua gio tap trung: pet phai dung yen ngay.
            self._sync_focus_with_pomodoro()

        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.timeout.connect(
            lambda: self._guarded("_check_fullscreen", self._check_fullscreen)
        )
        if self.config.get("hide_on_fullscreen"):
            self.fullscreen_timer.start(1000)

    # ------------------------------------------------------------------
    # Vong lap hanh vi (Giai doan 3)
    # ------------------------------------------------------------------
    def _guarded(self, name, func, *args):
        """Chay mot ham trong timer, nuot loi de app khong chet.

        Timer cua Qt khong co cho bat loi: mot exception trong ``timeout`` se
        thoat khoi vong lap su kien va tat app. Voi pet trang tri thi dung han
        la qua dat, nen ghi lai loi roi tiep tuc chay.

        Chan vong lap loi lien tuc: qua nhieu loi trong 10 giay thi dung timer
        de khong dot CPU.
        """
        now = time.monotonic()
        try:
            func(*args)
        except Exception:
            import traceback

            # Cua so 10 giay: dem lai tu dau khi da qua lau.
            if now - self._error_window_start > 10.0:
                self._error_window_start = now
                self._error_count = 0

            self._error_count += 1
            self._last_error = f"{name}: {traceback.format_exc(limit=2)}"

            # Chi in lan dau cua moi dot loi de log khong bi don rac.
            if self._error_count == 1:
                print(
                    f"[lỗi] {name} gặp sự cố, pet vẫn tiếp tục chạy:",
                    file=sys.stderr,
                )
                traceback.print_exc()

            # Loi lap lai qua nhieu: dung timer nay de khong dot CPU.
            if self._error_count >= 50 and not self._error_paused:
                self._error_paused = True
                print(
                    f"[cảnh báo] {name} lỗi liên tục {self._error_count} lần, "
                    "tạm dừng vòng lặp để không ngốn CPU.",
                    file=sys.stderr,
                )
            if self._error_count >= 50:
                return False
        return True

    def _behavior_tick(self):
        """Goi moi 100ms: quyet dinh pet tu lam gi."""
        if self.config.get("animation_paused") or not self.config.get("visible"):
            return
        if self._hidden_for_fullscreen or not self.config.get("auto_walk"):
            # Van cho ngu du khong bat tu di.
            if self.machine.state == state_module.IDLE and not self.config.get("auto_walk"):
                self.behavior.idle_tick(self.machine, self.now_ms())
            return

        now = self.now_ms()
        if self.machine.state == state_module.WALK:
            self.behavior.walk_tick(self.machine, now)
        else:
            self.behavior.idle_tick(self.machine, now)

    def _on_state_changed(self, previous, current):
        """Phan ung khi trang thai doi: doi animation va bat/tat timer."""
        if not self._guarded("_apply_state_animation", self._apply_state_animation, current):
            # GIF loi lien tuc: quay ve idle, dung cao hon.
            return
        self._guarded("_sync_state_timers", self._sync_state_timers, previous, current)
        print(f"[state] {previous} -> {current} ({self.machine.reason})")

    def _apply_state_animation(self, state_name):
        if self.pack is None:
            return
        path = self.pack.animation_path(state_name)
        if path is None:
            return
        self._apply_movie(path)

    def _sync_state_timers(self, previous, current):
        """Bat/tat timer theo trang thai moi."""
        # Di chuyen.
        if current == state_module.WALK:
            interval = int(self.pack_movement("step_interval_ms", 40))
            self.walk_timer.start(max(10, interval))
        else:
            self.walk_timer.stop()

        # Roi.
        if current == state_module.FALL:
            self.fall_sim.reset()
            self._fall_ground_y = falling.ground_y_for_screen(self.app)
            self.fall_timer.start(FALL_TICK_MS)
        else:
            self.fall_timer.stop()

        # Trang thai co thoi han.
        self.state_timer.stop()
        if current == state_module.REACT:
            self.state_timer.start(int(self.pack_behavior("react_duration_ms", 1500)))
        elif current == state_module.TALK:
            self.state_timer.start(int(self.pack_behavior("talk_duration_ms", 3000)))

        # Ngu thi dung moi chuyen dong.
        if current == state_module.SLEEP:
            self.walk_timer.stop()

    def _on_state_timeout(self):
        """Het thoi gian phan ung hoac noi: quay ve idle."""
        if self.machine.state in (state_module.REACT, state_module.TALK):
            self.machine.request(state_module.IDLE, reason="hết thời gian hiệu ứng")

    def _fall_step(self):
        """Mot buoc roi. Tiep dat thi chuyen sang idle."""
        ground = self._fall_ground_y
        new_y, landed = self.fall_sim.next_y(self.y(), self.height(), ground)
        # FallSimulator tra ve float; Qt move() can int.
        new_y = int(round(new_y))
        self.move(int(self.x()), new_y)
        if landed:
            self.fall_timer.stop()
            self.config.data["y"] = new_y
            self.config.save()
            self.behavior.on_landed(self.machine, self.now_ms())

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

        self.action_focus = QAction("Chế độ tập trung", self, checkable=True)
        self.action_focus.setToolTip("Pet đứng yên hoặc ngủ, không tự đi")
        self.action_focus.triggered.connect(self.toggle_focus_mode)

        self.action_sleep = QAction("Cho pet ngủ ngay", self)
        self.action_sleep.triggered.connect(self.send_to_sleep)

        # --- Nhac tap trung / nghi ---
        self.action_pomodoro = QAction("Nhắc tập trung / nghỉ", self, checkable=True)
        self.action_pomodoro.setToolTip("Pomodoro: nhắc uống nước và thư giãn mắt")
        self.action_pomodoro.triggered.connect(self.toggle_pomodoro)

        self.pomodoro_menu = QMenu("Đồng hồ tập trung", self)
        self.action_pomodoro_status = QAction("Chưa bật", self)
        self.action_pomodoro_status.setEnabled(False)

        self.action_pomodoro_pause = QAction("Tạm dừng đồng hồ", self)
        self.action_pomodoro_pause.triggered.connect(self.pomodoro_pause)

        self.action_pomodoro_resume = QAction("Chạy tiếp", self)
        self.action_pomodoro_resume.triggered.connect(self.pomodoro_resume)

        self.action_pomodoro_skip = QAction("Bỏ qua, sang pha tiếp", self)
        self.action_pomodoro_skip.triggered.connect(self.pomodoro_skip)

        self.action_pomodoro_remind = QAction("Nhắc uống nước ngay", self)
        self.action_pomodoro_remind.triggered.connect(self.remind_now)

        self.pomodoro_menu.addAction(self.action_pomodoro_status)
        self.pomodoro_menu.addSeparator()
        self.pomodoro_menu.addAction(self.action_pomodoro_pause)
        self.pomodoro_menu.addAction(self.action_pomodoro_resume)
        self.pomodoro_menu.addAction(self.action_pomodoro_skip)
        self.pomodoro_menu.addAction(self.action_pomodoro_remind)

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
        self.menu.addAction(self.action_focus)
        self.menu.addAction(self.action_sleep)
        self.menu.addSeparator()
        self.menu.addAction(self.action_pomodoro)
        self.menu.addMenu(self.pomodoro_menu)
        self.menu.addSeparator()
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
        self.action_focus.setChecked(bool(self.config.get("focus_mode")))
        self.action_sleep.setEnabled(self.machine.can_sleep())

        # Trang thai dong ho tap trung.
        self.action_pomodoro.setChecked(bool(self.config.get("pomodoro_enabled")))
        self.action_pomodoro_status.setText(self.pomodoro_status())
        active = self.config.get("pomodoro_enabled")
        self.pomodoro_menu.setEnabled(True)
        self.action_pomodoro_pause.setEnabled(
            active and self.pomodoro.phase in ("focus", "break")
        )
        self.action_pomodoro_resume.setEnabled(
            active and self.pomodoro.phase == "paused"
        )
        self.action_pomodoro_skip.setEnabled(active)
        self.action_click_through.setChecked(bool(self.config.get("click_through")))
        self.action_pin.setChecked(bool(self.config.get("pin_to_top")))
        self.action_hide_fullscreen.setChecked(bool(self.config.get("hide_on_fullscreen")))

    def _popup_menu(self, position):
        self._sync_menu()
        # Cap nhat dong ho ngay truoc khi hien, de dem nguoc dung.
        self.action_pomodoro_status.setText(self.pomodoro_status())
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
        # Giai phong QMovie cua file da bi xoa/khoi thu vien.
        if hasattr(self, "_movie_cache"):
            self._prune_movie_cache()
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

    def _movie_for(self, resolved_path):
        """Lay QMovie cua mot duong dan, tao moi chi lan dau tien.

        QMovie khong giai phong het tai nguyen C++ khi bi huy, nen tao/huy lien
        tuc lam RSS phinh khoang 1.3 MB moi lan: doi GIF 600 lan la mat ~1.5 GB.
        Vi vay giu cache theo duong dan va tai su dung lai.
        """
        movie = self._movie_cache.get(resolved_path)
        if movie is not None:
            return movie
        movie = QMovie(resolved_path)
        # GIF hong: khong cache de lan sau con thu lai duoc sau khi sua file.
        if not movie.isValid():
            return None
        self._movie_cache[resolved_path] = movie
        return movie

    def _prune_movie_cache(self):
        """Bo cache cua GIF da bi xoa hoac hong, giai phong bo nho."""
        dead = [p for p in self._movie_cache if not gif_library.is_valid_gif(p)]
        for path in dead:
            movie = self._movie_cache.pop(path)
            if movie is self.movie:
                # Con dang hien thi thi de QLabel nha ra truoc da.
                if self.label is not None:
                    self.label.setMovie(None)
                self.movie = None
            movie.stop()
            movie.deleteLater()

    def _apply_movie(self, resolved_path):
        """Thay animation ma khong dung lai cua so hay vi tri."""
        movie = self._movie_for(resolved_path)
        if movie is None:
            return False

        old_movie = self.movie
        if old_movie is movie:
            # Cung mot GIF: chi can dam bao dang chay, khong dung toi kich thuoc.
            if not self.config.get("animation_paused") and movie.state() != QMovie.Running:
                movie.start()
            return True

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

        # Movie cu van nam trong cache de tai su dung: chi tam dung.
        if old_movie is not None and old_movie is not movie:
            old_movie.stop()

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
        x = int(self.config.get("x", -1))
        y = int(self.config.get("y", -1))

        # Chua tung dat cho: chon vi tri ban dau hop ly.
        if x < 0 or y < 0:
            safe_x, safe_y = screen_utils.default_position(self.app, width, height)
            self.config.data["x"] = safe_x
            self.config.data["y"] = safe_y
            self.config.save()
        else:
            safe_x, safe_y = screen_utils.ensure_visible(self.app, x, y, width, height)
            if (safe_x, safe_y) != (x, y):
                print(
                    f"Tọa độ đã lưu ({x}, {y}) nằm ngoài màn hình, "
                    f"đưa về ({safe_x}, {safe_y})."
                )
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
    # Khoang di chuyen toi thieu (px) de coi la keo chu thay vi click.
    DRAG_THRESHOLD = 4

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.globalPos() - self.pos()
            self._press_pos = event.globalPos()
            self._moved = False
            # Chua vao trang thai drag ngay: phai doi xem nguoi dung co keo
            # that khong. Neu chi bam roi nha thi do la click, khong phai keo.
        elif event.button() == Qt.RightButton:
            self._popup_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        """Chi di chuyen cua so; KHONG ghi file o day."""
        if not (self.dragging and event.buttons() == Qt.LeftButton):
            return

        if not self._moved:
            moved_enough = (
                event.globalPos() - self._press_pos
            ).manhattanLength() > self.DRAG_THRESHOLD
            if moved_enough:
                self._moved = True
                # Keo that su: luc nay moi vao trang thai drag (vung vay).
                self.behavior.on_drag_start(self.machine, self.now_ms())

        if self._moved:
            self.move(event.globalPos() - self.offset)
            # Bong bong thoai di theo pet.
            if self.bubble is not None and self.bubble.isVisible():
                self.bubble._place_above(self.frameGeometry())

    def mouseReleaseEvent(self, event):
        """Tha chuot: luu vi tri, va quyet dinh roi hay dung yen."""
        if event.button() != Qt.LeftButton or not self.dragging:
            return
        self.dragging = False

        now = self.now_ms()

        # Bam roi nha ma khong keo: day la click, pet phan ung.
        if not self._moved:
            self.behavior.on_click(self.machine, now)
            return

        self.config.data["x"] = self.x()
        self.config.data["y"] = self.y()
        self.config.save()

        # Tha giua khong trung thi roi xuong.
        ground = falling.ground_y_for_screen(self.app)
        tolerance = self.pack_behavior("near_ground_px", 60)
        near = falling.near_ground(self.y(), self.height(), ground, tolerance)
        self.behavior.on_drag_release(self.machine, now, near_ground=near)

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
        """Bat/tat pet tu di. Vong lap hanh vi se lo phan con lai."""
        enabled = not bool(self.config.get("auto_walk"))
        self.config.data["auto_walk"] = enabled
        if not enabled and self.machine.state == state_module.WALK:
            self.behavior.stop_walking(self.machine, self.now_ms())
        self.config.save()

    def _apply_walk_timer(self):
        """Giu lai de tuong thich; vong lap hanh vi quan ly walk_timer."""
        if not self.config.get("auto_walk") and self.machine.state == state_module.WALK:
            self.behavior.stop_walking(self.machine, self.now_ms())

    def _walk_step(self):
        """Pet tu di ngang. Cham bien man hinh thi quay dau, khong di mat."""
        screen = self.app.primaryScreen()
        if screen is None:
            return
        if self.machine.state != state_module.WALK:
            self.walk_timer.stop()
            return

        # Toc do uu tien lay tu config, roi den pet.json.
        speed = int(self.config.get("walk_speed") or 0)
        if speed <= 0:
            speed = int(self.pack_movement("speed_px_per_step", WALK_STEP))
        speed = max(1, speed)

        area = QRect(screen.availableGeometry())
        x = self.x() + speed * self.walk_direction
        # Cham bien thi quay dau va kep lai trong man hinh.
        if x <= area.left():
            x = area.left()
            self.walk_direction = 1
        elif x + self.width() >= area.right():
            x = area.right() - self.width()
            self.walk_direction = -1
        self.move(x, self.y())
        self.config.data["x"] = x

    def send_to_sleep(self):
        """Cho pet ngu ngay, bo qua thoi gian cho."""
        if not self.machine.can_sleep():
            print("Không thể cho ngủ lúc này (đang bị kéo hoặc đang rơi).")
            return False
        return self.machine.request(state_module.SLEEP, reason="người dùng cho ngủ")

    def wake_up(self):
        """Danh thuc pet."""
        return self.behavior.note_interaction(self.now_ms()) or self.machine.on_interaction()

    def toggle_focus_mode(self):
        """Che do tap trung: pet dung yen hoac ngu, khong tu di."""
        enabled = not bool(self.config.get("focus_mode"))
        self.config.data["focus_mode"] = enabled
        self.machine.set_focus_mode(enabled)
        self.behavior.note_interaction(self.now_ms())
        self.config.save()
        print(
            "Chế độ tập trung: BẬT - pet đứng yên."
            if enabled
            else "Chế độ tập trung: TẮT - pet tự đi lại."
        )

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
    # Nhac tap trung / nghi (Pomodoro)
    # ------------------------------------------------------------------
    def _pomodoro_tick(self):
        """Kiem tra dong ho moi giay, nhic khi chuyen pha."""
        if not self.config.get("pomodoro_enabled"):
            return
        message = self.pomodoro.tick(self.now_ms())
        if message:
            # Chuyen pha: cap nhat lai trang thai dung yen / di lai.
            self._sync_focus_with_pomodoro()
            self.announce(message, duration_ms=9000)

    def announce(self, message, duration_ms=6000):
        """Cho pet noi mot cau: hien bong bong thoai va thong bao khay.

        Sau nay AI co the goi cung phuong thuc nay.
        """
        if not message:
            return
        if self.config.get("pomodoro_bubble", True):
            self._show_bubble(message, duration_ms)
        if self.config.get("pomodoro_notify", True) and self.tray is not None:
            self.tray.showMessage("GIF Pet", message, QSystemTrayIcon.Information, 5000)
        print(f"[nói] {message}")

    def _show_bubble(self, message, duration_ms):
        """Hien bong bong thoai tren dau pet."""
        if self.bubble is None:
            self.bubble = SpeechBubble()
        # Dung chinh kich thuoc cua so pet lam moc.
        self.bubble.say_above(message, self.frameGeometry(), duration_ms)

    def toggle_pomodoro(self):
        """Bat/tat che do nhac tap trung / nghi."""
        enabled = not bool(self.config.get("pomodoro_enabled"))
        self.config.data["pomodoro_enabled"] = enabled
        if enabled:
            message = self.pomodoro.start(self.now_ms())
            self.pomodoro_timer.start(POMODORO_TICK_MS)
            self.announce(message, duration_ms=6000)
        else:
            message = self.pomodoro.stop()
            self.pomodoro_timer.stop()
            self.announce(message, duration_ms=4000)
        # Tap trung thi pet dung yen.
        self._sync_focus_with_pomodoro()
        self.config.save()

    def _sync_focus_with_pomodoro(self):
        """Trong gio tap trung thi pet dung yen, gio nghi thi di lai.

        Khi Pomodoro tat, tra quyen kiem soat lai cho che do tap trung thu cong:
        nguoi dung van co the tu bat ``focus_mode`` trong Cai dat hoac menu.
        """
        if not self.config.get("pomodoro_enabled"):
            # Nha chan cua Pomodoro, nhung giu che do tap trung thu cong.
            manual_focus = bool(self.config.get("focus_mode"))
            self.machine.set_focus_mode(manual_focus)
            return

        # Trong gio tap trung, hoac nguoi dung tu bat focus_mode.
        focusing = self.pomodoro.is_focusing() or bool(self.config.get("focus_mode"))
        self.machine.set_focus_mode(focusing)
        if focusing and self.machine.state == state_module.WALK:
            self.behavior.stop_walking(self.machine, self.now_ms())
        elif not focusing and self.machine.state == state_module.IDLE:
            # Vua het gio tap trung: cho pet nghi mot chut roi di lai.
            self.behavior.note_interaction(self.now_ms())

    def pomodoro_pause(self):
        if self.pomodoro.pause(self.now_ms()):
            self.announce("Đã tạm dừng đồng hồ.", duration_ms=3000)
            self.config.save()
            return True
        return False

    def pomodoro_resume(self):
        if self.pomodoro.resume(self.now_ms()):
            self._sync_focus_with_pomodoro()
            self.announce(
                f"Chạy tiếp: {self.pomodoro.status_text(self.now_ms())}",
                duration_ms=3000,
            )
            return True
        return False

    def pomodoro_skip(self):
        """Bo qua pha hien tai."""
        if self.pomodoro.skip(self.now_ms()):
            self._sync_focus_with_pomodoro()
            self.announce(self.pomodoro.last_reminder, duration_ms=6000)
            return True
        return False

    def remind_now(self):
        """Nhac uong nuoc / thu gian mat ngay lap tuc."""
        message = self.pomodoro.random_break_reminder()
        self.announce(message, duration_ms=7000)
        return message

    def pomodoro_status(self):
        """Chuoi trang thai de hien trong menu."""
        return self.pomodoro.status_text(self.now_ms())

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
        focus_changed = values["focus_mode"] != bool(self.config.get("focus_mode"))

        self.config.data.update(values)
        self.config.save()

        if click_through_changed:
            self._apply_click_through(values["click_through"], persist=False)
        if hide_fullscreen_changed:
            self.toggle_fullscreen_watch(values["hide_on_fullscreen"])
        if pin_changed:
            self._apply_pin(values["pin_to_top"], persist=False)
        if focus_changed:
            # Ap dung che do tap trung qua may trang thai.
            self.machine.set_focus_mode(values["focus_mode"])
        self._apply_pomodoro_settings()
        self._apply_switch_timer()
        self._apply_walk_timer()

    def _apply_pomodoro_settings(self):
        """Bat/tat dong ho theo cai dat moi."""
        enabled = bool(self.config.get("pomodoro_enabled"))
        if enabled and not self.pomodoro_timer.isActive():
            self.pomodoro.start(self.now_ms())
            self.pomodoro_timer.start(POMODORO_TICK_MS)
            self.announce(self.pomodoro.last_reminder or "Bắt đầu tập trung.", 6000)
        elif not enabled and self.pomodoro_timer.isActive():
            self.pomodoro_timer.stop()
            self.pomodoro.stop()
        self._sync_focus_with_pomodoro()

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
        if self.bubble is not None:
            self.bubble.hide()
        if self.tray is not None:
            self.tray.hide()
        self.app.quit()

    def _release_movies(self):
        """Dung va nha het QMovie. Goi truoc khi cua so bi huy.

        Neu de Qt huy cua so truoc roi moi huy QMovie (hoac nguoc lai), QMovie
        con dang chay se goi vao QLabel da chet -> segfault. Phai dung han va
        go tham chieu tu QLabel truoc.
        """
        if self.label is not None:
            self.label.setMovie(None)
        for movie in list(self._movie_cache.values()):
            movie.stop()
            movie.deleteLater()
        self._movie_cache.clear()
        if self.movie is not None:
            self.movie.stop()
        self.movie = None

    def closeEvent(self, event):
        # Tat het timer truoc khi nha tai nguyen: tranh tick vao luc dang don.
        for timer in (self.switch_timer, self.behavior_timer, self.walk_timer,
                      self.fall_timer, self.state_timer, self.pomodoro_timer,
                      self.fullscreen_timer):
            timer.stop()
        self._release_movies()
        self.config.save()
        if self.tray is not None:
            self.tray.hide()
        event.accept()
