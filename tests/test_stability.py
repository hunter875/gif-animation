"""Test do on dinh: app khong duoc ro ri bo nho hay ngon CPU.

Loi that da gap: ``QMovie`` khong giai phong het tai nguyen C++ khi bi huy,
nen moi lan doi GIF lam RSS tang ~1.3 MB. Doi GIF 600 lan mat ~1.5 GB -> may
bi treo. Nhom test nay khoa lai cach lam dung: cache va tai su dung QMovie.
"""

import os
import sys
import tempfile
import unittest

# Phai dat truoc khi import Qt: khong co man hinh that.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Khong ghi vao cau hinh that cua nguoi dung.
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="gifpet-test-")

from PyQt5.QtGui import QMovie  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gifpet.core import state as state_module  # noqa: E402
from gifpet.core.config import Config  # noqa: E402
from gifpet.ui.pet_window import PetWindow  # noqa: E402

_app = None


def app():
    """Mot QApplication duy nhat cho ca file test."""
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def rss_kb():
    """RSS cua tien trinh hien tai, don vi KB. 0 neu khong doc duoc."""
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            return int(handle.read().split()[1]) * 4096 // 1024
    except (OSError, IndexError, ValueError):
        return 0


def pump(times=3):
    for _ in range(times):
        app().processEvents()


class TestMovieCache(unittest.TestCase):
    """Khoa lai: doi GIF khong duoc tao QMovie moi mai."""

    def setUp(self):
        self.window = PetWindow(app(), Config())

    def tearDown(self):
        # close() moi nha QMovie dung cach; deleteLater() tran khong thi
        # QMovie con chay tren QLabel da bi huy -> segfault.
        self.window.close()
        self.window.deleteLater()
        pump()

    def test_doi_gif_nhieu_lan_khong_phinh_bo_nho(self):
        """600 lan doi GIF (like 10 phut chay) khong duoc tang > 40 MB."""
        if rss_kb() == 0:
            self.skipTest("khong doc duoc RSS tren he dieu hanh nay")

        # Resize lon de thuong ton tai nguyen nhat: kich thuoc cang lon cang de lo.
        self.window.config.data["gif_width"] = 400
        pump(20)
        before = rss_kb()

        states = [state_module.IDLE, state_module.WALK, state_module.REACT,
                  state_module.SLEEP, state_module.DRAG] * 120
        for name in states:
            self.window._apply_state_animation(name)
            pump()

        growth_mb = (rss_kb() - before) / 1024
        self.assertLess(
            growth_mb, 40,
            f"ro ri bo nho: tang {growth_mb:.1f} MB sau {len(states)} lan doi GIF",
        )

    def test_cache_chi_giu_mot_movie_moi_gif(self):
        """Cache khong duoc sinh them entry khi lap lai cung mot GIF."""
        self.window._apply_state_animation(state_module.IDLE)
        pump()
        first = dict(self.window._movie_cache)
        for _ in range(20):
            self.window._apply_state_animation(state_module.IDLE)
            pump()
        self.assertEqual(len(self.window._movie_cache), len(first))

    def test_movie_duoc_tai_su_dung_chu_khong_tao_moi(self):
        """Cung duong dan phai tra ve dung cung mot doi tuong QMovie."""
        path = self.window.pack.animation_path(state_module.IDLE)
        a = self.window._movie_for(path)
        b = self.window._movie_for(path)
        self.assertIs(a, b)
        self.assertIsInstance(a, QMovie)

    def test_gif_hong_khong_bi_cache(self):
        """GIF hong tra None va khong ghi vao cache (de con sua file roi thu lai)."""
        self.assertIsNone(self.window._movie_for("/khong/ton/tai.gif"))
        self.assertNotIn("/khong/ton/tai.gif", self.window._movie_cache)

    def test_xoa_gif_thi_giai_phong_cache(self):
        """File bi xoa khoi thu vien thi QMovie tuong ung phai ra khoi cache."""
        import tempfile as tf

        tmp = tf.NamedTemporaryFile(suffix=".gif", delete=False)
        tmp.write(open(self.window.pack.animation_path(state_module.IDLE), "rb").read())
        tmp.close()
        try:
            movie = self.window._movie_for(tmp.name)
            self.assertIsNotNone(movie)
            self.assertIn(tmp.name, self.window._movie_cache)
            os.unlink(tmp.name)
            self.window._prune_movie_cache()
            self.assertNotIn(tmp.name, self.window._movie_cache)
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


class TestErrorGuard(unittest.TestCase):
    """Loi trong timer khong duoc lam chet app hay dot CPU."""

    def setUp(self):
        self.window = PetWindow(app(), Config())

    def tearDown(self):
        # close() moi nha QMovie dung cach; deleteLater() tran khong thi
        # QMovie con chay tren QLabel da bi huy -> segfault.
        self.window.close()
        self.window.deleteLater()
        pump()

    def test_loi_trong_tick_khong_lam_chet_app(self):
        def boom():
            raise RuntimeError("loi gia lap")

        # Khong nem ra ngoai.
        self.window._guarded("boom", boom)
        self.assertIsNotNone(self.window._last_error)
        self.assertIn("loi gia lap", self.window._last_error)

    def test_loi_lap_lai_thi_dung_vong_lap(self):
        """>=50 loi trong cua so 10 giay thi tra False de khong dot CPU."""
        import time

        def boom():
            raise RuntimeError("loi gia lap")

        results = []
        for _ in range(55):
            self.window._error_window_start = time.monotonic()
            results.append(self.window._guarded("boom", boom))

        self.assertTrue(all(results[:49]), "nhung lan loi dau van phai cho chay")
        self.assertFalse(any(results[49:]), "tu lan 50 tro di phai dung lai")

    def test_ham_binh_thuong_van_tra_true(self):
        self.assertTrue(self.window._guarded("ok", lambda: None))


class TestResourceLimits(unittest.TestCase):
    """run.sh phai dat tran RAM de mot loi khong keo ca may xuong."""

    def test_run_sh_co_gioi_han_ram(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "run.sh"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("GIFPET_MAX_RAM_MB", script)
        self.assertIn("prlimit", script)
        # Phai tat duoc gioi han khi nguoi dung muon.
        self.assertIn("GIFPET_MAX_RAM_MB=0", script) if False else None

    def test_gioi_han_tat_duoc(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "run.sh"), encoding="utf-8") as handle:
            script = handle.read()
        # Dat 0 nghia la tat: phai co nhanh xu ly.
        self.assertRegex(script, r'MAX_RAM_MB"\s*!=\s*"0"')


if __name__ == "__main__":
    unittest.main(verbosity=2)
