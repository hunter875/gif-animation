"""Test loi nhac luu ben va gom su kien "pet tu noi".

Hai viec nay truoc day chi la thiet ke tren giay:

- ``remind`` dung QTimer.singleShot nen hen 30 phut roi tat app la mat.
- ``ai_proactive`` la co trong config nhung khong co gi doc no.

Khong goi mang: provider gia.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="gifpet-remind-test-")

from gifpet.core.config import Config  # noqa: E402
from gifpet.core.proactive import ProactiveBatcher  # noqa: E402
from gifpet.core.reminders import Reminders  # noqa: E402


# ----------------------------------------------------------------------
# Loi nhac luu ben
# ----------------------------------------------------------------------
class TestReminders(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="remind-")
        self.path = os.path.join(self.dir, "reminders.json")
        self.clock = [10000.0]
        self.reminders = Reminders(self.path, now_func=lambda: self.clock[0])

    def make(self):
        """Tao object moi: gia lap tat app roi mo lai."""
        return Reminders(self.path, now_func=lambda: self.clock[0])

    def test_them_va_dem(self):
        self.assertTrue(self.reminders.add("uống nước", 1800))
        self.assertEqual(self.reminders.count(), 1)

    def test_song_qua_lan_tat_app(self):
        """Diem chinh: truoc day QTimer.singleShot lam mat loi nhac."""
        self.reminders.add("uống nước", 1800)
        # Khong truyen giu trang thai: doc hoan toan tu file.
        again = self.make()
        self.assertEqual(again.count(), 1)
        self.assertEqual(again.all()[0]["text"], "uống nước")

    def test_chua_den_gio_thi_chua_tra_ve(self):
        self.reminders.add("uống nước", 60)
        self.assertEqual(self.reminders.due(), [])
        self.clock[0] += 61
        self.assertEqual(len(self.reminders.due()), 1)

    def test_pop_due_xoa_khoi_hang_doi(self):
        self.reminders.add("a", 60)
        self.clock[0] += 61
        self.assertEqual(self.reminders.pop_due(), ["a"])
        self.assertEqual(self.reminders.count(), 0)
        # Pop lan hai khong tra ve gi.
        self.assertEqual(self.reminders.pop_due(), [])

    def test_nhieu_loi_nhac_den_gio_cung_luc(self):
        self.reminders.add("a", 10)
        self.reminders.add("b", 20)
        self.clock[0] += 30
        self.assertEqual(sorted(self.reminders.pop_due()), ["a", "b"])

    def test_bo_loi_nhac_qua_han_qua_lau(self):
        """Mo app sau vai ngay khong duoc do ra mot loat thong bao."""
        self.reminders.add("cũ", 60)
        self.clock[0] += 25 * 3600
        self.assertEqual(self.reminders.drop_stale(), 1)
        self.assertEqual(self.reminders.count(), 0)

    def test_loi_nhac_trong_han_khong_bi_bo(self):
        self.reminders.add("mới", 60)
        self.clock[0] += 23 * 3600
        self.assertEqual(self.reminders.drop_stale(), 0)
        self.assertEqual(self.reminders.count(), 1)

    def test_gioi_han_so_loi_nhac(self):
        for i in range(30):
            self.reminders.add(f"muc {i}", 60 + i)
        self.assertLessEqual(self.reminders.count(), 20)

    def test_tu_choi_text_rong_va_giay_khong_hop_le(self):
        self.assertFalse(self.reminders.add("", 60))
        self.assertFalse(self.reminders.add("   ", 60))
        self.assertFalse(self.reminders.add("x", 0))
        self.assertFalse(self.reminders.add("x", -5))
        self.assertFalse(self.reminders.add("x", "abc"))

    def test_cat_text_dai(self):
        self.reminders.add("x" * 1000, 60)
        self.assertLessEqual(len(self.reminders.all()[0]["text"]), 200)

    def test_file_hong_khong_lam_crash(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{hong json")
        self.assertEqual(self.reminders.count(), 0)
        # Van ghi duoc tiep sau khi file hong.
        self.assertTrue(self.reminders.add("mới", 60))

    def test_file_la_json_doc_duoc(self):
        self.reminders.add("test", 60)
        with open(self.path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["text"], "test")

    def test_next_wait_seconds(self):
        self.assertIsNone(self.reminders.next_wait_seconds())
        self.reminders.add("a", 100)
        self.assertAlmostEqual(self.reminders.next_wait_seconds(), 100.0, delta=1)

    def test_clear(self):
        self.reminders.add("a", 60)
        self.reminders.clear()
        self.assertEqual(self.reminders.count(), 0)


# ----------------------------------------------------------------------
# Gom su kien cho "pet tu noi"
# ----------------------------------------------------------------------
class TestProactiveBatcher(unittest.TestCase):

    def make(self, proactive=True, enabled=True, limit=10):
        config = Config()
        config.data["ai_enabled"] = enabled
        config.data["ai_proactive"] = proactive
        config.data["ai_proactive_limit"] = limit
        clock = [50000.0]
        return ProactiveBatcher(config, now_func=lambda: clock[0]), clock

    def test_tat_thi_tu_choi(self):
        for value in (
            {"proactive": False}, {"enabled": False},
        ):
            batcher, _ = self.make(**value)
            self.assertFalse(batcher.add("long_idle"), value)
            self.assertEqual(batcher.should_fire()[1], "disabled")

    def test_su_kien_pet_tu_di_roi_ngu_bi_tu_choi(self):
        """Quy tac cung: cac su kien nay khong bao gio goi model."""
        batcher, _ = self.make()
        for kind in ("walk", "fall", "sleep", "idle", "click", "drag", "react"):
            self.assertFalse(batcher.add(kind), kind)
        self.assertEqual(batcher.pending_count(), 0)

    def test_su_kien_hop_le_duoc_nhan(self):
        batcher, _ = self.make()
        for kind in ("long_idle", "returned", "pomodoro_break"):
            batcher.reset()
            self.assertTrue(batcher.add(kind), kind)

    def test_chua_du_cua_so_thi_chua_goi(self):
        batcher, clock = self.make()
        batcher.add("long_idle")
        self.assertEqual(batcher.should_fire()[1], "too_soon")
        clock[0] += 61
        self.assertEqual(batcher.should_fire(), (True, "ok"))

    def test_gom_nhieu_su_kien_thanh_mot_lan_goi(self):
        """20 su kien trong cua so = mot lan goi, khong phai 20."""
        batcher, clock = self.make()
        for _ in range(20):
            batcher.add("long_idle", "30 phút")
        clock[0] += 61
        self.assertTrue(batcher.should_fire()[0])
        events = batcher.take()
        self.assertEqual(len(events), 20)
        self.assertEqual(batcher.pending_count(), 0)

    def test_khong_goi_lai_ngay_sau_khi_goi(self):
        batcher, clock = self.make()
        batcher.add("long_idle")
        clock[0] += 61
        batcher.take()
        batcher.add("returned")
        # Vua goi xong: phai cho tiep mot cua so.
        self.assertEqual(batcher.should_fire()[1], "too_soon")

    def test_khong_chay_trong_gio_tap_trung(self):
        batcher, clock = self.make()
        batcher.add("long_idle")
        clock[0] += 61
        self.assertEqual(batcher.should_fire(focusing=True), (False, "focus"))

    def test_het_tran_rieng(self):
        batcher, clock = self.make(limit=2)
        fired = 0
        for _ in range(5):
            batcher.add("long_idle")
            clock[0] += 61
            should, reason = batcher.should_fire()
            if should:
                batcher.take()
                fired += 1
            elif reason == "exhausted":
                break
        self.assertEqual(fired, 2, "tran rieng phai chan dung so lan")

    def test_build_content_la_du_lieu(self):
        batcher, _ = self.make()
        content = batcher.build_content(
            [{"kind": "long_idle", "detail": "30 phút"}, {"kind": "returned"}]
        )
        self.assertIn("long_idle", content)
        self.assertIn("returned", content)

    def test_build_content_rong(self):
        batcher, _ = self.make()
        self.assertEqual(batcher.build_content([]), "")


# ----------------------------------------------------------------------
# Tich hop: config co bien moi
# ----------------------------------------------------------------------
class TestConfigWiring(unittest.TestCase):

    def test_co_tran_rieng_cho_pet_tu_noi(self):
        from gifpet.core.config import DEFAULTS

        self.assertIn("ai_proactive_limit", DEFAULTS)
        self.assertLess(
            DEFAULTS["ai_proactive_limit"], DEFAULTS["ai_daily_limit"],
            "tran rieng phai thap hon tran chung",
        )

    def test_reminders_khong_nam_trong_config(self):
        """Loi nhac o file rieng, khong lam phinh config.json."""
        from gifpet.core.config import DEFAULTS

        self.assertNotIn("reminders", DEFAULTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
