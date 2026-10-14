"""Test cho bong bong thoai cua pet.

Chay: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_speech_bubble.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.ui.speech_bubble import (  # noqa: E402
    MAX_WIDTH,
    MIN_WIDTH,
    SpeechBubble,
)

_app = QApplication.instance() or QApplication([])
_AREA = _app.primaryScreen().availableGeometry()

SHORT = "Uống nước đi."
LONG = (
    "Nghỉ 5 phút: Đứng dậy vươn vai vài giây, uống một cốc nước đầy, "
    "rồi nhìn ra xa khoảng 20 giây để mắt được thư giãn hoàn toàn nhé."
)


class TestBubbleContent(unittest.TestCase):
    def test_hien_dung_noi_dung(self):
        bubble = SpeechBubble()
        bubble.say(SHORT)
        self.assertEqual(bubble.label.text(), SHORT)
        self.assertTrue(bubble.isVisible())
        bubble.hide()

    def test_noi_dung_rong_thi_khong_hien(self):
        bubble = SpeechBubble()
        bubble.say("")
        self.assertFalse(bubble.isVisible())

    def test_tu_dong_an_sau_thoi_gian(self):
        bubble = SpeechBubble()
        bubble.say(SHORT, duration_ms=1000)
        self.assertTrue(bubble.hide_timer.isActive())
        self.assertEqual(bubble.hide_timer.interval(), 1000)
        bubble.hide()

    def test_thoi_gian_an_toi_thieu_1_giay(self):
        bubble = SpeechBubble()
        # Duoi 1 giay se bi keo len 1 giay de kip doc.
        bubble.say(SHORT, duration_ms=10)
        self.assertGreaterEqual(bubble.hide_timer.interval(), 1000)
        bubble.hide()


class TestBubbleSizing(unittest.TestCase):
    """Kich thuoc phai de doc: khong qua hep, khong vuot gioi han."""

    def test_cau_ngan_khong_qua_hep(self):
        bubble = SpeechBubble()
        bubble.say(SHORT)
        self.assertGreaterEqual(bubble.width(), MIN_WIDTH)
        bubble.hide()

    def test_cau_dai_khong_vuot_gioi_han(self):
        bubble = SpeechBubble()
        bubble.say(LONG)
        self.assertLessEqual(bubble.width(), MAX_WIDTH + 4)
        self.assertGreater(bubble.width(), MIN_WIDTH)
        bubble.hide()

    def test_cau_dai_thi_xuong_dong(self):
        bubble = SpeechBubble()
        bubble.say(LONG)
        # Xuong dong nghia la cao hon mot dong.
        self.assertGreater(bubble.height(), 50)
        bubble.hide()

    def test_cau_dai_dung_gan_het_chieu_rong_cho_phep(self):
        """Khong nen de bong bong cao va hep khi con cho ngang."""
        bubble = SpeechBubble()
        bubble.say(LONG)
        self.assertGreater(
            bubble.width(),
            MAX_WIDTH * 0.8,
            "Cau dai nen dung gan het chieu rong cho phep",
        )
        bubble.hide()


class TestBubblePlacement(unittest.TestCase):
    """Bong bong phai nam trong man hinh va bam theo pet."""

    def _check(self, pet_rect):
        bubble = SpeechBubble()
        bubble.say_above(LONG, pet_rect)
        _app.processEvents()
        box = QRect(bubble.x(), bubble.y(), bubble.width(), bubble.height())
        bubble.hide()
        return box

    def test_nam_trong_man_hinh_o_moi_vi_tri(self):
        cases = [
            QRect(_AREA.x() + 300, _AREA.y() + 300, 200, 267),
            QRect(_AREA.x() + 300, _AREA.y(), 200, 267),
            QRect(_AREA.x(), _AREA.y() + 300, 200, 267),
            QRect(_AREA.right() - 200, _AREA.y() + 300, 200, 267),
            QRect(_AREA.right() - 200, _AREA.bottom() - 267, 200, 267),
        ]
        for pet_rect in cases:
            box = self._check(pet_rect)
            self.assertTrue(
                _AREA.contains(box),
                f"Bong bong {box} nam ngoai man hinh {_AREA} (pet {pet_rect})",
            )

    def test_sat_mep_tren_thi_chuyen_xuong_duoi_pet(self):
        pet_rect = QRect(_AREA.x() + 300, _AREA.y(), 200, 267)
        box = self._check(pet_rect)
        self.assertGreaterEqual(
            box.y(),
            pet_rect.y() + pet_rect.height(),
            "Pet sat mep tren thi bong bong phai nam duoi pet",
        )

    def test_binh_thuong_thi_nam_tren_pet(self):
        pet_rect = QRect(_AREA.x() + 300, _AREA.y() + 300, 200, 267)
        box = self._check(pet_rect)
        self.assertLess(
            box.y() + box.height(),
            pet_rect.y() + 20,
            "Bong bong phai nam phia tren pet",
        )

    def test_vi_tri_mac_dinh_du_cho_hien_bong_bong(self):
        """Pet moi cai dat phai o cho con du cho phia tren cho bong bong."""
        from gifpet.core import screen_utils

        x, y = screen_utils.default_position(_app, 200, 267)
        self.assertGreater(
            y,
            60,
            "Cho ngoi mac dinh phai con du cho phia tren de hien bong bong",
        )
        self.assertTrue(
            screen_utils.is_on_any_screen(
                x, y, 200, 267, screen_utils.screen_rects(_app)
            ),
            "Cho ngoi mac dinh phai nam trong man hinh",
        )

    def test_bong_bong_nam_tren_pet_o_vi_tri_mac_dinh(self):
        from gifpet.core import screen_utils

        x, y = screen_utils.default_position(_app, 200, 267)
        pet_rect = QRect(x, y, 200, 267)
        box = self._check(pet_rect)
        self.assertLess(
            box.y() + box.height(),
            pet_rect.y(),
            "O cho ngoi mac dinh, bong bong phai nam tren pet",
        )

    def test_khong_chan_chuot(self):
        """Bong bong khong duoc chan viec keo pet nam duoi no."""
        bubble = SpeechBubble()
        self.assertTrue(bubble.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertTrue(bubble.testAttribute(Qt.WA_ShowWithoutActivating))


if __name__ == "__main__":
    unittest.main(verbosity=2)
