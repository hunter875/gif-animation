"""Test cho che do nhac tap trung / nghi (Pomodoro).

Chay: ./run.sh --test
Hoac: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_pomodoro.py
"""

import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core import pomodoro as pomodoro_module  # noqa: E402
from gifpet.core import state as state_module  # noqa: E402
from gifpet.core.config import Config  # noqa: E402

_app = QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def make(**overrides):
    values = {"pomodoro_focus_minutes": 25, "pomodoro_break_minutes": 5}
    values.update(overrides)
    return pomodoro_module.Pomodoro(FakeConfig(values), rng=random.Random(7))


class TestPomodoroCycle(unittest.TestCase):
    """Vong lap tap trung -> nghi."""

    def test_ban_dau_chua_bat(self):
        clock = make()
        self.assertEqual(clock.phase, pomodoro_module.IDLE)
        self.assertFalse(clock.is_active())

    def test_bat_dau_tap_trung(self):
        clock = make()
        message = clock.start(0)
        self.assertEqual(clock.phase, pomodoro_module.FOCUS)
        self.assertTrue(clock.is_focusing())
        self.assertIn("tập trung", message.lower())

    def test_het_gio_tap_trung_thi_nhic_nghi(self):
        clock = make(pomodoro_focus_minutes=25)
        clock.start(0)
        focus_ms = clock.focus_ms

        # Chua het gio: khong nhic.
        self.assertIsNone(clock.tick(focus_ms - 1))

        # Het gio: chuyen sang nghi va nhic.
        message = clock.tick(focus_ms)
        self.assertIsNotNone(message, "Het gio tap trung phai nhic")
        self.assertEqual(clock.phase, pomodoro_module.BREAK)
        self.assertIn("Nghỉ", message)

    def test_het_gio_nghi_thi_quay_lai_tap_trung(self):
        clock = make()
        clock.start(0)
        clock.tick(clock.focus_ms)
        self.assertEqual(clock.phase, pomodoro_module.BREAK)

        message = clock.tick(clock.focus_ms + clock.break_ms)
        self.assertIsNotNone(message)
        self.assertEqual(clock.phase, pomodoro_module.FOCUS)
        self.assertIn("Tập trung", message)

    def test_dem_so_hiep_hoan_thanh(self):
        clock = make()
        clock.start(0)
        self.assertEqual(clock.completed_focus, 0)
        clock.tick(clock.focus_ms)
        self.assertEqual(clock.completed_focus, 1)
        clock.tick(clock.focus_ms + clock.break_ms)
        clock.tick(clock.focus_ms * 2 + clock.break_ms)
        self.assertEqual(clock.completed_focus, 2)

    def test_tat_thi_dung_han(self):
        clock = make()
        clock.start(0)
        clock.stop()
        self.assertEqual(clock.phase, pomodoro_module.IDLE)
        self.assertIsNone(clock.tick(999_999_999), "Da tat thi khong nhic nua")


class TestPomodoroReminders(unittest.TestCase):
    """Loi nhic phai co noi dung uong nuoc / thu gian mat."""

    def test_loi_nhic_nghi_de_cap_nuoc_hoac_mat(self):
        clock = make()
        seen = set()
        for _ in range(50):
            clock.start(0)
            message = clock.tick(clock.focus_ms)
            seen.add(message)
        joined = " ".join(seen).lower()
        self.assertTrue(
            "nước" in joined or "mắt" in joined or "thư giãn" in joined,
            f"Loi nhic phai nhac uong nuoc hoac nghi mat, nhan duoc: {seen}",
        )

    def test_moi_loi_nhic_nghi_deu_hop_ly(self):
        for text in pomodoro_module.BREAK_REMINDERS:
            self.assertTrue(text.strip())
            self.assertLess(len(text), 120, "Loi nhic phai ngan gon")

    def test_lich_su_luu_lai(self):
        clock = make()
        clock.start(0)
        clock.tick(clock.focus_ms)
        self.assertGreaterEqual(len(clock.history), 2)
        self.assertEqual(clock.history[-1], clock.last_reminder)


class TestPomodoroPauseResume(unittest.TestCase):
    """Tam dung va chay tiep."""

    def test_tam_dung_giu_thoi_gian_con_lai(self):
        clock = make(pomodoro_focus_minutes=10)
        clock.start(0)
        # Chay duoc 4 phut.
        now = 4 * 60 * 1000
        self.assertTrue(clock.pause(now))
        self.assertEqual(clock.phase, pomodoro_module.PAUSED)
        remaining = clock.remaining_ms(now)
        self.assertAlmostEqual(remaining, 6 * 60 * 1000, delta=1000)

    def test_tam_dung_thi_khong_nhic(self):
        clock = make(pomodoro_focus_minutes=10)
        clock.start(0)
        clock.pause(0)
        self.assertIsNone(clock.tick(999_999_999))

    def test_chay_tiep_tu_cho_da_dung(self):
        clock = make(pomodoro_focus_minutes=10)
        clock.start(0)
        clock.pause(60_000)
        remaining = clock.remaining_ms(60_000)

        self.assertTrue(clock.resume(120_000))
        self.assertEqual(clock.phase, pomodoro_module.FOCUS)
        # Sau khi chay tiep, thoi gian con lai duoc giu nguyen.
        self.assertAlmostEqual(clock.remaining_ms(120_000), remaining, delta=10)

    def test_khong_tam_dung_khi_chua_bat(self):
        clock = make()
        self.assertFalse(clock.pause(0))
        self.assertFalse(clock.resume(0))


class TestPomodoroSkip(unittest.TestCase):
    """Bo qua pha hien tai."""

    def test_bo_qua_gio_tap_trung_sang_nghi(self):
        clock = make()
        clock.start(0)
        self.assertTrue(clock.skip(1000))
        self.assertEqual(clock.phase, pomodoro_module.BREAK)

    def test_bo_qua_gio_nghi_sang_tap_trung(self):
        clock = make()
        clock.start(0)
        clock.skip(1000)
        self.assertTrue(clock.skip(2000))
        self.assertEqual(clock.phase, pomodoro_module.FOCUS)

    def test_bo_qua_khi_chua_bat_thi_khong_lam_gi(self):
        clock = make()
        self.assertFalse(clock.skip(0))


class TestPomodoroDisplay(unittest.TestCase):
    """Hien thi dem nguoc."""

    def test_dem_nguoc_dung_dinh_dang(self):
        clock = make(pomodoro_focus_minutes=25)
        clock.start(0)
        self.assertEqual(clock.remaining_text(0), "25:00")
        self.assertEqual(clock.remaining_text(60_000), "24:00")

    def test_trang_thai_tat(self):
        clock = make()
        self.assertIn("tắt", clock.status_text(0))

    def test_trang_thai_tap_trung(self):
        clock = make(pomodoro_focus_minutes=25)
        clock.start(0)
        text = clock.status_text(0)
        self.assertIn("Tập trung", text)
        self.assertIn("25:00", text)

    def test_trang_thai_nghi(self):
        clock = make()
        clock.start(0)
        clock.tick(clock.focus_ms)
        self.assertIn("Nghỉ", clock.status_text(clock.focus_ms))

    def test_trang_thai_tam_dung(self):
        clock = make()
        clock.start(0)
        clock.pause(0)
        self.assertIn("Tạm dừng", clock.status_text(0))

    def test_cau_hinh_sai_kieu_khong_lam_crash(self):
        clock = pomodoro_module.Pomodoro(
            FakeConfig({"pomodoro_focus_minutes": "khong-phai-so"})
        )
        self.assertEqual(clock.focus_ms, 25 * 60 * 1000)

        clock2 = pomodoro_module.Pomodoro(
            FakeConfig({"pomodoro_break_minutes": None})
        )
        self.assertEqual(clock2.break_ms, 5 * 60 * 1000)


class TestPomodoroWithPetWindow(unittest.TestCase):
    """Tich hop voi cua so pet."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(os.path.join(self.temp_dir, "config.json"))

    def test_bat_pomodoro_thi_pet_dung_yen(self):
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update(
            {"pomodoro_enabled": False, "pomodoro_focus_minutes": 1}
        )
        window = PetWindow(_app, self.config)

        window.toggle_pomodoro()
        self.assertTrue(self.config.get("pomodoro_enabled"))
        self.assertTrue(window.pomodoro.is_focusing())
        self.assertFalse(
            window.machine.can_walk(),
            "Trong gio tap trung pet phai dung yen",
        )
        window.quit_app()

    def test_tat_pomodoro_thi_pet_di_lai_duoc(self):
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update({"pomodoro_enabled": True, "pomodoro_focus_minutes": 1})
        window = PetWindow(_app, self.config)
        self.assertTrue(window.pomodoro.is_focusing())

        window.toggle_pomodoro()
        self.assertFalse(self.config.get("pomodoro_enabled"))
        self.assertTrue(
            window.machine.can_walk(),
            "Tat Pomodoro thi pet phai tu di lai duoc",
        )
        window.quit_app()

    def test_nhac_ngay_tao_loi_nhic(self):
        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        message = window.remind_now()
        self.assertTrue(message)
        self.assertEqual(message, window.pomodoro.last_reminder)
        window.quit_app()

    def test_khoi_dong_voi_tap_trung_bat_san_thi_pet_dung_yen(self):
        """Bug da sua: mo app voi pomodoro_enabled=True thi pet phai dung yen ngay."""
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update(
            {"pomodoro_enabled": True, "pomodoro_focus_minutes": 25, "auto_walk": True}
        )
        window = PetWindow(_app, self.config)
        self.assertTrue(window.pomodoro.is_focusing())
        self.assertFalse(
            window.machine.can_walk(),
            "Mo app giua gio tap trung ma pet van di duoc -> sai",
        )
        window.quit_app()

    def test_chuyen_sang_gio_nghi_thi_pet_di_lai_duoc(self):
        """Bug da sua: het gio tap trung thi phai bo chan di lai."""
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update(
            {"pomodoro_enabled": True, "pomodoro_focus_minutes": 25, "auto_walk": True}
        )
        window = PetWindow(_app, self.config)
        self.assertFalse(window.machine.can_walk())

        # Gia lap dong ho da het gio tap trung.
        window.pomodoro.phase_end_ms = window.now_ms() - 1
        window._pomodoro_tick()

        self.assertEqual(window.pomodoro.phase, "break")
        self.assertTrue(
            window.machine.can_walk(),
            "Sang gio nghi ma pet van bi chan di -> sai",
        )
        window.quit_app()

    def test_menu_co_muc_pomodoro(self):
        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        labels = [a.text() for a in window.menu.actions() if a.text()]
        self.assertIn("Nhắc tập trung / nghỉ", labels)

        submenu_labels = [a.text() for a in window.pomodoro_menu.actions()]
        self.assertIn("Nhắc uống nước ngay", submenu_labels)
        self.assertIn("Bỏ qua, sang pha tiếp", submenu_labels)
        window.quit_app()

    def test_bong_bong_thoai_hien_loi_nhic(self):
        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        window.announce("Uống nước đi nhé.", duration_ms=500)
        self.assertIsNotNone(window.bubble)
        self.assertEqual(window.bubble.label.text(), "Uống nước đi nhé.")
        window.quit_app()

    def test_tat_bong_bong_thi_khong_hien(self):
        from gifpet.ui.pet_window import PetWindow

        self.config.data["pomodoro_bubble"] = False
        window = PetWindow(_app, self.config)
        window.bubble = None
        window.announce("Không nên hiện.", duration_ms=500)
        self.assertIsNone(window.bubble, "Da tat bong bong thi khong duoc tao")
        window.quit_app()

    def test_het_gio_tap_trung_pet_nhic_nghi(self):
        """Chay nhanh: 1 phut tap trung, kiem tra co nhic khi het gio."""
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update(
            {"pomodoro_enabled": True, "pomodoro_focus_minutes": 1}
        )
        window = PetWindow(_app, self.config)

        # Gia lap dong ho da qua gio tap trung.
        now = window.now_ms()
        window.pomodoro.phase_end_ms = now - 1
        window._pomodoro_tick()

        self.assertEqual(window.pomodoro.phase, "break")
        self.assertTrue(window.pomodoro.last_reminder)
        window.quit_app()

    def test_trong_gio_nghi_pet_di_lai_duoc(self):
        from gifpet.ui.pet_window import PetWindow

        self.config.data.update(
            {"pomodoro_enabled": True, "pomodoro_focus_minutes": 1}
        )
        window = PetWindow(_app, self.config)
        now = window.now_ms()
        window.pomodoro.phase_end_ms = now - 1
        window._pomodoro_tick()

        self.assertEqual(window.pomodoro.phase, "break")
        self.assertTrue(
            window.machine.can_walk(),
            "Trong gio nghi pet phai di lai duoc",
        )
        window.quit_app()


if __name__ == "__main__":
    unittest.main(verbosity=2)
