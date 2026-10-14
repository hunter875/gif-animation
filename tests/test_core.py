"""Test cho cac module logic cua GIF Pet.

Chay: ./run.sh --test
Hoac: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_core.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core import gif_library  # noqa: E402
from gifpet.core import pet_pack  # noqa: E402
from gifpet.core import screen_utils  # noqa: E402
from gifpet.core import state as state_module  # noqa: E402
from gifpet.core.config import DEFAULTS, Config  # noqa: E402
from gifpet.core.paths import PETS_DIR, PROJECT_ROOT  # noqa: E402

BASE_DIR = PROJECT_ROOT
_app = QApplication.instance() or QApplication([])

DEFAULT_PACK_DIR = os.path.join(PETS_DIR, "default")
VALID_GIF = os.path.join(DEFAULT_PACK_DIR, "idle.gif")
# Cac GIF nam trong thu muc nhan vat, khong phai goc project.
GIF_BASE = DEFAULT_PACK_DIR


class TestScaledSize(unittest.TestCase):
    """Resize phai giu ti le, khong ep vuong."""

    def test_giu_ti_le_khi_co_chieu_rong(self):
        # GIF 500x667, thu nho con rong 250 -> cao 334 (khong phai 250).
        width, height = gif_library.scaled_size(500, 667, 250, lock_width=True)
        self.assertEqual(width, 250)
        self.assertEqual(height, 334)
        self.assertNotEqual(width, height, "Khong duoc ep GIF thanh hinh vuong")

    def test_giu_ti_le_khi_co_chieu_cao(self):
        width, height = gif_library.scaled_size(500, 667, 667, lock_width=False)
        self.assertEqual(height, 667)
        self.assertEqual(width, 500)

    def test_ti_le_duoc_bao_toan(self):
        width, height = gif_library.scaled_size(864, 648, 432, lock_width=True)
        self.assertAlmostEqual(width / height, 864 / 648, places=2)

    def test_gif_rong_ngang(self):
        width, height = gif_library.scaled_size(864, 648, 200, lock_width=True)
        self.assertEqual(width, 200)
        self.assertEqual(height, 150)

    def test_gif_doc(self):
        width, height = gif_library.scaled_size(646, 862, 100, lock_width=False)
        self.assertEqual(height, 100)
        self.assertEqual(width, 75)

    def test_khong_tra_ve_zero(self):
        width, height = gif_library.scaled_size(0, 0, 0, lock_width=True)
        self.assertGreaterEqual(width, 1)
        self.assertGreaterEqual(height, 1)


class TestGifLibrary(unittest.TestCase):
    """Chon GIF khong bao gio ket dinh file hong."""

    def test_gif_hop_le_duoc_nhan(self):
        self.assertTrue(gif_library.is_valid_gif(VALID_GIF))

    def test_file_khong_ton_tai_bi_tu_choi(self):
        self.assertFalse(gif_library.is_valid_gif("/khong/ton/tai.gif"))

    def test_file_rac_bi_tu_choi(self):
        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as handle:
            handle.write(b"day khong phai GIF")
            bad_path = handle.name
        try:
            self.assertFalse(
                gif_library.is_valid_gif(bad_path),
                "File .gif hong phai bi tu choi",
            )
        finally:
            os.unlink(bad_path)

    def test_uu_tien_gif_da_chon(self):
        resolved, stored = gif_library.pick_working_gif(
            "idle.gif", ["idle.gif", "drag.gif"], GIF_BASE
        )
        self.assertTrue(resolved.endswith("idle.gif"))

    def test_file_mat_thi_chon_gif_khac(self):
        """Xoa file dang chon -> van phai tim duoc GIF hop le khac."""
        resolved, stored = gif_library.pick_working_gif(
            "da-bi-xoa.gif", ["da-bi-xoa.gif", "drag.gif"], GIF_BASE
        )
        self.assertIsNotNone(resolved, "Phai fallback sang GIF con dung duoc")
        self.assertTrue(resolved.endswith("drag.gif"))

    def test_duong_dan_windows_khong_lam_crash(self):
        resolved, stored = gif_library.pick_working_gif(
            "D:/pythonone/nice one/gg/abc.gif", ["idle.gif"], GIF_BASE
        )
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.endswith("idle.gif"))

    def test_khong_con_gif_nao_thi_tra_ve_none(self):
        resolved, stored = gif_library.pick_working_gif(
            "hong.gif", ["hong.gif"], GIF_BASE, default="cung-hong.gif"
        )
        self.assertIsNone(resolved)

    def test_existing_entries_loc_file_hong(self):
        entries = ["idle.gif", "khong-ton-tai.gif", "drag.gif"]
        result = gif_library.existing_entries(entries, GIF_BASE)
        self.assertEqual(result, ["idle.gif", "drag.gif"])

    def test_resolve_duong_dan_tuong_doi_theo_project(self):
        resolved = gif_library.resolve_path("idle.gif", GIF_BASE)
        self.assertEqual(resolved, os.path.join(GIF_BASE, "idle.gif"))

    def test_resolve_giu_duong_dan_tuyet_doi(self):
        self.assertEqual(
            gif_library.resolve_path("/tmp/x.gif", GIF_BASE), "/tmp/x.gif"
        )

    def test_normalize_dua_ve_tuong_doi(self):
        absolute = os.path.join(GIF_BASE, "idle.gif")
        self.assertEqual(gif_library.normalize_path(absolute, GIF_BASE), "idle.gif")


class TestConfig(unittest.TestCase):
    """Cau hinh: validate, atomic write, khong crash khi file hong."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.path = os.path.join(self.temp_dir, "config.json")

    def test_tao_mac_dinh_khi_chua_co_file(self):
        config = Config(self.path)
        for key, value in DEFAULTS.items():
            self.assertIn(key, config.data)
        self.assertEqual(config.get("gif_path"), DEFAULTS["gif_path"])

    def test_luu_va_doc_lai(self):
        config = Config(self.path)
        config.set("x", 123)
        config.set("gif_width", 250)
        config.save()

        reloaded = Config(self.path)
        self.assertEqual(reloaded.get("x"), 123)
        self.assertEqual(reloaded.get("gif_width"), 250)

    def test_file_json_hong_khong_lam_crash(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ day khong phai json hop le ")
        config = Config(self.path)
        self.assertEqual(config.get("x"), DEFAULTS["x"])

    def test_json_khong_phai_object_khong_lam_crash(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump([1, 2, 3], handle)
        config = Config(self.path)
        self.assertEqual(config.get("x"), DEFAULTS["x"])

    def test_gia_tri_sai_kieu_duoc_ep_ve_mac_dinh(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"x": "khong-phai-so", "pin_to_top": "true", "gif_width": "300"}, handle)
        config = Config(self.path)
        self.assertEqual(config.get("x"), DEFAULTS["x"], "Gia tri sai kieu -> mac dinh")
        self.assertIs(config.get("pin_to_top"), True, "Chuoi 'true' -> bool True")
        self.assertEqual(config.get("gif_width"), 300, "Chuoi so -> int")

    def test_khong_de_lai_file_tam(self):
        config = Config(self.path)
        config.save()
        leftovers = [f for f in os.listdir(self.temp_dir) if f.startswith(".config-")]
        self.assertEqual(leftovers, [], "Khong duoc de lai file tam sau khi ghi")

    def test_ghi_de_len_file_cu(self):
        config = Config(self.path)
        config.set("x", 1)
        config.save()
        config.set("x", 2)
        config.save()
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["x"], 2)


class TestScreenUtils(unittest.TestCase):
    """Pet khong duoc lac khoi man hinh."""

    def setUp(self):
        self.screen = _app.primaryScreen()
        self.area = self.screen.availableGeometry()
        self.rects = screen_utils.screen_rects(_app)

    def test_toa_do_trong_man_hinh_duoc_giu(self):
        x, y = screen_utils.ensure_visible(_app, 10, 10, 100, 100)
        self.assertEqual((x, y), (10, 10))

    def test_toa_do_ngoai_man_hinh_duoc_keo_ve(self):
        x, y = screen_utils.ensure_visible(_app, 99999, 99999, 100, 100)
        self.assertTrue(
            screen_utils.is_on_any_screen(x, y, 100, 100, self.rects),
            "Sau khi sua, pet phai nam trong man hinh",
        )

    def test_toa_do_am_duoc_keo_ve(self):
        x, y = screen_utils.ensure_visible(_app, -5000, -5000, 100, 100)
        self.assertTrue(screen_utils.is_on_any_screen(x, y, 100, 100, self.rects))

    def test_man_hinh_phu_bi_rut(self):
        """Toa do tung nam tren man hinh phu gio khong con ton tai."""
        x, y = screen_utils.ensure_visible(_app, 5000, 200, 200, 200)
        self.assertTrue(screen_utils.is_on_any_screen(x, y, 200, 200, self.rects))

    def test_center_nam_trong_man_hinh(self):
        x, y = screen_utils.center_on_primary(_app, 200, 260)
        self.assertTrue(screen_utils.is_on_any_screen(x, y, 200, 260, self.rects))

    def test_center_dung_giua(self):
        x, y = screen_utils.center_on_primary(_app, 100, 100)
        expected_x = self.area.x() + (self.area.width() - 100) // 2
        self.assertEqual(x, expected_x)

    def test_pet_nho_o_goc_duoc_giu_nguyen(self):
        """Pet 5x5 hop le o goc khong duoc coi la lac."""
        self.assertTrue(
            screen_utils.is_on_any_screen(10, 10, 5, 5, self.rects),
            "Pet nho trong man hinh khong duoc keo ve giua",
        )

    def test_pet_thoa_ra_ngoai_mot_phan_du_lon_duoc_giu(self):
        """Con thay >= 40px thi nguoi dung van keo lai duoc."""
        x = self.area.width() - 60
        y = self.area.height() - 60
        self.assertTrue(screen_utils.is_on_any_screen(x, y, 200, 200, self.rects))

    def test_pet_chi_con_vai_pixel_thi_keo_ve(self):
        """Chi thay 5x5 px thi khong the bam vao -> phai keo ve."""
        x = self.area.width() - 5
        y = self.area.height() - 5
        self.assertFalse(screen_utils.is_on_any_screen(x, y, 200, 200, self.rects))


class TestOriginalSizeNotPolluted(unittest.TestCase):
    """QMovie tra ve kich thuoc da scale sau setScaledSize -> phai doc tu file."""

    def test_gif_dimensions_doc_dung_kich_thuoc_goc(self):
        self.assertEqual(gif_library.gif_dimensions(VALID_GIF), (500, 667))

    def test_kich_thuoc_goc_khong_doi_sau_resize(self):
        from gifpet.ui.pet_window import PetWindow

        temp_dir = tempfile.mkdtemp()
        config = Config(os.path.join(temp_dir, "config.json"))
        idle = os.path.join(DEFAULT_PACK_DIR, "idle.gif")
        config.data.update(
            {"gif_path": idle, "gif_list": [idle], "gif_width": 250}
        )
        window = PetWindow(_app, config)
        self.assertEqual(window.original_size(), (500, 667))

        # Sau khi scale, kich thuoc goc van phai la 500x667.
        window._apply_size(100, 133, persist=False)
        self.assertEqual(
            window.original_size(),
            (500, 667),
            "Resize khong duoc lam sai kich thuoc goc",
        )
        window.quit_app()

    def test_ti_le_on_dinh_qua_nhieu_lan_resize(self):
        """Nhieu lan resize lien tiep van giu dung ti le cua GIF dang hien."""
        from gifpet.ui.pet_window import PetWindow

        temp_dir = tempfile.mkdtemp()
        config = Config(os.path.join(temp_dir, "config.json"))
        config.data.update({"gif_width": 200, "width_locked": True})
        window = PetWindow(_app, config)

        # Kich thuoc goc lay tu GIF that dang hien thi (qua pet pack).
        original_width, original_height = window.original_size()
        self.assertGreater(original_width, 1)
        original_ratio = original_width / original_height

        for target in [200, 400, 150, 600, 100]:
            config.data["gif_width"] = target
            window._refit_to_current_movie()
            expected_height = round(original_height * target / original_width)
            self.assertEqual(window.width(), target)
            # Lam tron sang pixel nguyen nen dung sai toi da 1px.
            self.assertLessEqual(
                abs(window.height() - expected_height),
                1,
                msg=f"Chieu cao sai qua 1px o lan resize rong={target}",
            )
            ratio = window.width() / window.height()
            self.assertLess(
                abs(ratio - original_ratio),
                0.02,
                msg=f"Ti le lech qua nhieu o lan resize rong={target}",
            )
        window.quit_app()


class TestMouseMoveDoesNotWrite(unittest.TestCase):
    """Loi chinh cua ban goc: mouseMoveEvent ghi JSON moi lan di chuyen."""

    def test_keo_pet_khong_ghi_file_lien_tuc(self):
        from gifpet.ui.pet_window import PetWindow

        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "config.json")
        config = Config(config_path)
        window = PetWindow(_app, config)

        save_calls = []
        original_save = config.save

        def counting_save():
            save_calls.append(1)
            original_save()

        config.save = counting_save

        from PyQt5.QtCore import QPoint, QEvent, Qt
        from PyQt5.QtGui import QMouseEvent

        start = window.pos()
        window.dragging = True
        window.offset = QPoint(0, 0)

        # Mo phong 50 lan di chuyen chuot.
        for step in range(50):
            event = QMouseEvent(
                QEvent.MouseMove,
                QPoint(step, step),
                QPoint(start.x() + step, start.y() + step),
                Qt.LeftButton,
                Qt.LeftButton,
                Qt.NoModifier,
            )
            window.mouseMoveEvent(event)

        self.assertEqual(
            save_calls, [], "mouseMoveEvent khong duoc ghi file"
        )

        # Chi khi tha chuot moi ghi, va chi mot lan.
        release = QMouseEvent(
            QEvent.MouseButtonRelease,
            QPoint(0, 0),
            QPoint(0, 0),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        window.mouseReleaseEvent(release)
        self.assertEqual(len(save_calls), 1, "Chi ghi mot lan khi tha chuot")
        window.quit_app()


class TestAnimationPauseSeparate(unittest.TestCase):
    """Pause animation phai tach roi voi dung viec doi GIF."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(os.path.join(self.temp_dir, "config.json"))

    def test_pause_khong_tat_auto_switch_setting(self):
        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        self.config.data["auto_switch_enabled"] = True
        window.toggle_animation_pause()

        self.assertTrue(self.config.get("animation_paused"))
        self.assertTrue(
            self.config.get("auto_switch_enabled"),
            "Pause animation khong duoc tat tuy chon doi GIF",
        )
        window.quit_app()

    def test_pause_dung_animation_that_su(self):
        from PyQt5.QtGui import QMovie

        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        window.toggle_animation_pause()
        self.assertEqual(
            window.movie.state(), QMovie.Paused, "GIF phai dung chay khi pause"
        )
        window.toggle_animation_pause()
        self.assertNotEqual(
            window.movie.state(), QMovie.Paused, "GIF phai chay lai khi bo pause"
        )
        window.quit_app()

    def test_tat_doi_gif_khong_lam_dung_animation(self):
        from PyQt5.QtGui import QMovie

        from gifpet.ui.pet_window import PetWindow

        window = PetWindow(_app, self.config)
        window.toggle_auto_switch()
        self.assertFalse(self.config.get("auto_switch_enabled"))
        self.assertNotEqual(
            window.movie.state(),
            QMovie.Paused,
            "Tat doi GIF khong duoc lam animation dung",
        )
        window.quit_app()


class TestGifSwitchingSkipsBroken(unittest.TestCase):
    """Khong duoc chon trung file hong moi 10 giay."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(os.path.join(self.temp_dir, "config.json"))

    def test_khong_chon_file_hong(self):
        """Thu vien GIF rieng chi duoc chua file dung duoc."""
        from gifpet.ui.pet_window import PetWindow

        # Duong dan tuyet doi toi GIF that, de khong phu thuoc CWD.
        good = os.path.join(DEFAULT_PACK_DIR, "idle.gif")
        good2 = os.path.join(DEFAULT_PACK_DIR, "drag.gif")
        self.config.data["gif_list"] = [good, "da-bi-xoa.gif", good2]
        self.config.data["gif_path"] = good
        window = PetWindow(_app, self.config)

        self.assertNotIn(
            "da-bi-xoa.gif",
            window.config.get("gif_list"),
            "Entry hong phai bi loai khoi danh sach",
        )

        chosen = set()
        for _ in range(30):
            window.auto_switch_gif()
            chosen.add(window.config.get("gif_path"))

        for entry in chosen:
            resolved = gif_library.resolve_path(entry, BASE_DIR)
            self.assertTrue(
                gif_library.is_valid_gif(resolved),
                f"Da chon trung GIF hong: {entry}",
            )
        window.quit_app()

    def test_danh_sach_duoc_don_sau_khi_nap(self):
        """Entry tro toi file khong ton tai bi loai khi nap cau hinh."""
        from gifpet.ui.pet_window import PetWindow

        good = os.path.join(DEFAULT_PACK_DIR, "idle.gif")
        self.config.data["gif_list"] = [good, "da-bi-xoa.gif"]
        window = PetWindow(_app, self.config)
        self.assertNotIn(
            "da-bi-xoa.gif",
            window.config.get("gif_list"),
            "Entry hong phai bi loai khoi danh sach",
        )
        window.quit_app()


class TestNoPersonalPathsInRepo(unittest.TestCase):
    """Repo khong duoc commit duong dan may ca nhan."""

    def test_repo_khong_co_duong_dan_ca_nhan(self):
        """Quet file du lieu, khong duoc dinh duong dan tuyet doi ca nhan.

        Bo qua comment va docstring trong file .py vi chung chi la vi du
        minh hoa (vd cach nhan dien duong dan kieu Windows), khong phai
        duong dan cua may nguoi dung.
        """
        import io
        import tokenize

        markers = ("D:/", "C:/", "C:\\", "/home/", "/Users/")
        offenders = []

        for name in sorted(os.listdir(BASE_DIR)):
            path = os.path.join(BASE_DIR, name)
            if not os.path.isfile(path):
                continue

            if name.endswith(".py"):
                # Loai bo comment va string literal (docstring).
                try:
                    with open(path, "rb") as handle:
                        tokens = list(tokenize.tokenize(handle.readline))
                except (OSError, tokenize.TokenError, SyntaxError):
                    continue
                pieces = []
                for token in tokens:
                    if token.type in (tokenize.COMMENT, tokenize.STRING):
                        continue
                    pieces.append(token.string)
                content = "\n".join(pieces)
            elif name.endswith((".json", ".md", ".sh", ".txt")):
                try:
                    with open(path, encoding="utf-8") as handle:
                        content = handle.read()
                except (OSError, UnicodeDecodeError):
                    continue
            else:
                continue

            for marker in markers:
                if marker in content:
                    offenders.append(f"{name}: {marker}")

        self.assertEqual(
            offenders, [], f"Repo chua duong dan may ca nhan: {offenders}"
        )

    def test_config_luu_ngoai_repo(self):
        from gifpet.core.config import config_dir

        self.assertFalse(
            os.path.abspath(config_dir()).startswith(os.path.abspath(BASE_DIR)),
            "Cau hinh phai nam ngoai repo",
        )

    def test_khong_con_data_json_trong_repo(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE_DIR, "data.json")),
            "data.json cu da duoc thay bang cau hinh ngoai repo",
        )


class TestStateMachine(unittest.TestCase):
    """Quy tac uu tien hanh vi (Giai doan 3)."""

    def setUp(self):
        self.machine = state_module.StateMachine()

    def test_trang_thai_ban_dau_la_idle(self):
        self.assertEqual(self.machine.state, state_module.IDLE)

    def test_dang_bi_keo_thi_khong_duoc_ngu(self):
        """Yeu cau ro nhat cua spec: dang keo thi khong duoc bat di ngu."""
        self.machine.on_drag_start()
        self.assertEqual(self.machine.state, state_module.DRAG)
        self.assertFalse(self.machine.can_sleep())
        self.assertFalse(
            self.machine.request(state_module.SLEEP, reason="thử cho ngủ"),
            "Dang bi keo ma van cho ngu -> sai",
        )
        self.assertEqual(self.machine.state, state_module.DRAG)

    def test_dang_bi_keo_thi_khong_tu_di(self):
        self.machine.on_drag_start()
        self.assertFalse(self.machine.can_walk())
        self.assertFalse(self.machine.request(state_module.WALK))

    def test_dang_roi_thi_phai_tiep_dat_truoc(self):
        """Dang roi thi hoan tat tiep dat roi moi lam viec khac."""
        self.machine.on_drag_start()
        self.machine.on_drag_release(near_ground=False)
        self.assertEqual(self.machine.state, state_module.FALL)

        for blocked in (state_module.SLEEP, state_module.WALK, state_module.TALK):
            self.assertFalse(
                self.machine.request(blocked),
                f"Dang roi ma chuyen duoc sang {blocked} -> sai",
            )
        self.assertEqual(self.machine.state, state_module.FALL)

        self.assertTrue(self.machine.on_landed())
        self.assertEqual(self.machine.state, state_module.IDLE)

    def test_tha_gan_mat_dat_thi_ve_idle(self):
        self.machine.on_drag_start()
        self.machine.on_drag_release(near_ground=True)
        self.assertEqual(self.machine.state, state_module.IDLE)

    def test_click_thi_phan_ung(self):
        self.assertTrue(self.machine.on_click())
        self.assertEqual(self.machine.state, state_module.REACT)

    def test_dang_roi_thi_click_khong_phan_ung(self):
        self.machine.on_drag_start()
        self.machine.on_drag_release(near_ground=False)
        self.assertFalse(self.machine.on_click())
        self.assertEqual(self.machine.state, state_module.FALL)

    def test_khong_tuong_tac_thi_ngu(self):
        self.assertTrue(self.machine.can_sleep())
        self.assertTrue(self.machine.on_idle_timeout())
        self.assertEqual(self.machine.state, state_module.SLEEP)

    def test_co_tuong_tac_thi_thuc_day(self):
        self.machine.on_idle_timeout()
        self.assertEqual(self.machine.state, state_module.SLEEP)
        self.assertTrue(self.machine.on_interaction())
        self.assertEqual(self.machine.state, state_module.IDLE)

    def test_che_do_tap_trung_thi_dung_yen(self):
        """Bat che do tap trung: pet dung yen hoac ngu, khong tu di."""
        self.machine.set_focus_mode(True)
        self.assertFalse(self.machine.can_walk())
        self.assertFalse(self.machine.request(state_module.WALK))

    def test_bat_tap_trung_khi_dang_di_thi_dung_lai(self):
        self.machine.request(state_module.WALK)
        self.assertEqual(self.machine.state, state_module.WALK)
        self.machine.set_focus_mode(True)
        self.assertEqual(
            self.machine.state,
            state_module.IDLE,
            "Bat tap trung khi dang di -> phai dung yen",
        )

    def test_trang_thai_khong_hop_le_bi_tu_choi(self):
        self.assertFalse(self.machine.request("khong-ton-tai"))
        self.assertIn("không hợp lệ", self.machine.last_rejection)

    def test_listener_duoc_goi_khi_chuyen_trang_thai(self):
        seen = []
        self.machine.listeners.append(lambda old, new: seen.append((old, new)))
        self.machine.on_click()
        self.assertEqual(seen, [(state_module.IDLE, state_module.REACT)])


class TestPetPack(unittest.TestCase):
    """Thu vien nhan vat: thieu trang thai thi dung idle.gif."""

    def setUp(self):
        self.pack = pet_pack.load_pack(DEFAULT_PACK_DIR)

    def test_doc_duoc_nhan_vat_mac_dinh(self):
        self.assertIsNotNone(self.pack)
        self.assertEqual(self.pack.name, "default")

    def test_co_animation_idle(self):
        path = self.pack.animation_path(state_module.IDLE)
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("idle.gif"))

    def test_trang_thai_co_gif_rieng(self):
        self.assertTrue(self.pack.has_state("walk"))
        self.assertTrue(self.pack.has_state("drag"))
        self.assertTrue(self.pack.has_state("sleep"))

    def test_trang_thai_thieu_thi_dung_fallback(self):
        """Bo pet thieu trang thai van import duoc."""
        for missing in ("fall", "react", "talk"):
            self.assertFalse(
                self.pack.has_state(missing),
                f"{missing} khong nen co GIF rieng trong bo mau",
            )
            path = self.pack.animation_path(missing)
            self.assertIsNotNone(path, f"{missing} phai fallback chu khong tra ve None")
            self.assertTrue(
                path.endswith(self.pack.fallback_animation),
                f"{missing} phai dung {self.pack.fallback_animation}",
            )

    def test_missing_states_liet_ke_dung(self):
        missing = self.pack.missing_states()
        self.assertIn("fall", missing)
        self.assertNotIn("idle", missing)

    def test_doc_kich_thuoc_va_toc_do_tu_pet_json(self):
        self.assertGreater(self.pack.movement["speed_px_per_step"], 0)
        self.assertGreater(self.pack.behavior["idle_to_sleep_ms"], 0)

    def test_thu_muc_khong_co_gif_thi_bo_qua(self):
        empty_dir = tempfile.mkdtemp()
        pack = pet_pack.load_pack(empty_dir)
        self.assertIsNone(pack.animation_path(state_module.IDLE))

    def test_discover_tim_duoc_nhan_vat(self):
        packs = pet_pack.discover_packs(PETS_DIR)
        self.assertGreaterEqual(len(packs), 1)
        self.assertEqual(packs[0].name, "default", "default phai dung dau")

    def test_pet_json_hong_khong_lam_crash(self):
        temp_dir = tempfile.mkdtemp()
        shutil.copy(VALID_GIF, os.path.join(temp_dir, "idle.gif"))
        with open(os.path.join(temp_dir, "pet.json"), "w", encoding="utf-8") as handle:
            handle.write("{ json hong ")
        pack = pet_pack.load_pack(temp_dir)
        self.assertIsNotNone(pack.animation_path(state_module.IDLE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
