"""Test cac module UI da tach ra khoi pet_window.

Loi ich cua viec tach: nhung phan nay test duoc ma khong can dung ca cua so
pet. Truoc day chung nam trong pet_window.py 1467 dong nen phai khoi tao ca
app moi kiem tra duoc.

Khong goi mang, khong mo trinh duyet that.
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="gifpet-ui-test-")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core import state as state_module  # noqa: E402
from gifpet.core.config import Config  # noqa: E402
from gifpet.ui import pet_actions  # noqa: E402
from gifpet.ui import tray_menu, window_skin  # noqa: E402
from gifpet.ui.pet_window import PetWindow  # noqa: E402

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def pump(times=3):
    for _ in range(times):
        app().processEvents()


class WindowCase(unittest.TestCase):
    """Tao mot PetWindow that de test cac module phu."""

    def setUp(self):
        self.window = PetWindow(app(), Config())
        # Loi nhac luu o file dung chung: xoa truoc moi test de khong dinh
        # trang thai cua test truoc.
        self.window.reminders.clear()
        pump()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        pump()


# ----------------------------------------------------------------------
# pet_actions
# ----------------------------------------------------------------------
class TestPetActions(WindowCase):

    def test_cau_bao_loi_co_ban(self):
        for code in ("disabled", "no_key", "exhausted", "network", "auth"):
            message = pet_actions.error_message(code)
            self.assertTrue(message, f"{code} phai co cau bao")
            self.assertNotEqual(message, "Có lỗi khi gọi AI.", code)

    def test_ma_la_khong_lam_crash(self):
        self.assertEqual(
            pet_actions.error_message("ma-khong-ton-tai"), "Có lỗi khi gọi AI."
        )

    def test_su_kien_bi_bo_qua_khong_bao_gi(self):
        """ignored_event khong phai loi: khong nen hien bong bong."""
        self.assertEqual(pet_actions.error_message("ignored_event"), "")

    def test_say_hien_bong_bong(self):
        pet_actions.run_action(self.window, "say", {"text": "nghỉ mắt đi"})
        pump()
        self.assertIsNotNone(self.window.bubble)

    def test_react_doi_trang_thai(self):
        pet_actions.run_action(self.window, "react", {})
        pump()
        self.assertEqual(self.window.state, state_module.REACT)

    def test_set_state_doi_trang_thai(self):
        pet_actions.run_action(self.window, "set_state", {"state": "talk"})
        pump()
        self.assertEqual(self.window.state, state_module.TALK)

    def test_open_url_doc_hai_bi_chan(self):
        """Kiem tra lai lan cuoi: khong tin rang da duoc loc o tren."""
        opened = []
        # Gia lap QDesktopServices de khong mo trinh duyet that.
        original = pet_actions.QDesktopServices.openUrl
        pet_actions.QDesktopServices.openUrl = staticmethod(
            lambda url: opened.append(url.toString())
        )
        try:
            for url in (
                "file:///etc/passwd",
                "javascript:alert(1)",
                "http://example.com",
                "https://127.0.0.1/a",
                "https://169.254.169.254/",
            ):
                pet_actions.open_url(self.window, url)
            self.assertEqual(opened, [], f"bi mo nham: {opened}")
        finally:
            pet_actions.QDesktopServices.openUrl = original

    def test_open_url_hop_le_duoc_mo(self):
        opened = []
        original = pet_actions.QDesktopServices.openUrl
        pet_actions.QDesktopServices.openUrl = staticmethod(
            lambda url: opened.append(url.toString())
        )
        try:
            pet_actions.open_url(self.window, "https://example.com/a")
            self.assertEqual(opened, ["https://example.com/a"])
        finally:
            pet_actions.QDesktopServices.openUrl = original

    def test_remind_luu_ra_file_khong_dung_timer(self):
        """Loi nhac phai luu ben: hen 30 phut roi tat app van con."""
        from gifpet.core.reminders import Reminders

        pet_actions.run_action(
            self.window, "remind", {"text": "uống nước", "in_minutes": 30}
        )
        pump()
        # Doc lai bang object moi: khong dung trang thai trong bo nho.
        saved = Reminders().all()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["text"], "uống nước")

    def test_remind_co_bao_cho_nguoi_dung(self):
        pet_actions.run_action(
            self.window, "remind", {"text": "uống nước", "in_minutes": 5}
        )
        pump()
        self.assertIsNotNone(self.window.bubble)
        self.assertEqual(self.window.pending_reminders(), 1)

    def test_check_reminders_noi_khi_den_gio(self):
        """Timer quet phai lay ra va noi loi nhac den gio."""
        self.window.reminders.add("đến giờ rồi", 0.01)
        import time

        time.sleep(0.05)
        self.window._check_reminders()
        pump()
        # Da lay ra khoi hang doi.
        self.assertEqual(self.window.pending_reminders(), 0)

    def test_drop_stale_khi_khoi_dong(self):
        """Loi nhac cu qua 24h bi bo, khong do ra mot loat thong bao."""
        self.window.reminders.add("cũ", 0.01)
        # Gia lap loi nhac tu 3 ngay truoc.
        items = self.window.reminders.all()
        items[0]["due"] -= 3 * 24 * 3600
        self.window.reminders._write(items)
        self.window._drop_stale_reminders()
        self.assertEqual(self.window.pending_reminders(), 0)

    def test_proactive_tat_mac_dinh(self):
        """ai_proactive mac dinh tat: khong goi model khi pet ranh."""
        self.assertFalse(self.window.proactive.enabled())


# ----------------------------------------------------------------------
# window_skin
# ----------------------------------------------------------------------
class TestWindowSkin(WindowCase):

    def test_cua_so_trong_suot_khong_vien(self):
        from PyQt5.QtCore import Qt

        flags = self.window.windowFlags()
        self.assertTrue(flags & Qt.FramelessWindowHint)
        self.assertTrue(flags & Qt.Tool)
        self.assertTrue(
            self.window.testAttribute(Qt.WA_TranslucentBackground)
        )

    def test_click_through_bat_tat(self):
        from PyQt5.QtCore import Qt

        self.assertFalse(bool(self.window.config.get("click_through")))
        window_skin.apply_click_through(self.window, True, persist=False)
        self.assertTrue(
            self.window.testAttribute(Qt.WA_TransparentForMouseEvents)
        )
        window_skin.apply_click_through(self.window, False, persist=False)
        self.assertFalse(
            self.window.testAttribute(Qt.WA_TransparentForMouseEvents)
        )

    def test_click_through_luu_vao_config(self):
        window_skin.apply_click_through(self.window, True, persist=True)
        self.assertTrue(bool(self.window.config.get("click_through")))

    def test_fullscreen_tren_may_khong_display_tra_false(self):
        """Khong co DISPLAY: khong duoc cho la fullscreen (tranh an pet nham)."""
        old = os.environ.pop("DISPLAY", None)
        try:
            self.assertFalse(window_skin.another_window_is_fullscreen(self.window))
        finally:
            if old is not None:
                os.environ["DISPLAY"] = old

    def test_pin_bat_tat(self):
        window_skin.apply_pin(self.window, True, persist=False)
        self.assertTrue(bool(self.window.config.get("pin_to_top")))
        window_skin.apply_pin(self.window, False, persist=False)
        self.assertFalse(bool(self.window.config.get("pin_to_top")))


# ----------------------------------------------------------------------
# tray_menu
# ----------------------------------------------------------------------
class TestTrayMenu(WindowCase):

    def test_menu_duoc_dung(self):
        self.assertIsNotNone(self.window.menu)
        self.assertGreater(len(self.window.menu.actions()), 15)

    def test_co_du_muc_quan_trong(self):
        for name in (
            "action_visible", "action_pause", "action_auto_switch",
            "action_walk", "action_focus", "action_sleep", "action_pomodoro",
            "action_chat", "action_click_through", "action_pin",
            "action_hide_fullscreen", "action_library", "action_resize",
            "action_center", "action_settings", "action_exit",
        ):
            self.assertTrue(hasattr(self.window, name), f"thieu {name}")

    def test_sync_menu_khop_voi_config(self):
        self.window.config.data["visible"] = False
        self.window.config.data["auto_walk"] = False
        tray_menu.sync_menu(self.window)
        self.assertFalse(self.window.action_visible.isChecked())
        self.assertEqual(self.window.action_visible.text(), "Hiện pet")
        self.assertFalse(self.window.action_walk.isChecked())

    def test_sync_menu_visible_text(self):
        self.window.config.data["visible"] = True
        tray_menu.sync_menu(self.window)
        self.assertEqual(self.window.action_visible.text(), "Ẩn pet")

    def test_notify_khong_co_tray_khong_loi(self):
        """Khong co khay: goi notify khong duoc nem exception."""
        self.window.tray = None
        tray_menu.notify(self.window, "thu")
        tray_menu.notify(self.window, "thu", warning=True)


# ----------------------------------------------------------------------
# Tuong tac giua cac module
# ----------------------------------------------------------------------
class TestModuleIntegration(WindowCase):

    def test_window_uy_thac_cho_module_moi(self):
        """Cac method tren window phai la lop moong, khong chua logic."""
        import inspect

        for name in (
            "_load_gif", "_apply_movie", "_movie_for", "_apply_size",
            "_build_menu", "_sync_menu", "_run_action", "_handle_brain_result",
            "_apply_click_through", "_check_fullscreen", "_apply_pin",
        ):
            source = inspect.getsource(getattr(self.window, name))
            self.assertLess(
                len(source.splitlines()), 12,
                f"{name} van con logic, nen chuyen vao module phu",
            )

    def test_pet_window_khong_con_qua_dai(self):
        """Giu pet_window o muc doc duoc: moi lan phinh la phai tach."""
        import gifpet.ui.pet_window as module

        path = module.__file__
        with open(path, encoding="utf-8") as handle:
            lines = len(handle.read().splitlines())
        self.assertLess(
            lines, 1050,
            f"pet_window.py dang {lines} dong; nen tach bot trach nhiem",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
