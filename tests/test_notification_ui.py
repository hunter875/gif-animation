"""Test giao dien thong bao: bong bong chu thuong, lich su, timer, hop thu.

Tat ca chay o che do offscreen cua Qt va dung thu muc cau hinh tam. Bien moi
truong duoc dat TRUOC khi import PyQt/gifpet de khong bao gio doc hay ghi cau
hinh that cua nguoi dung.

Khong goi ``exec_()``: hop thoai duoc tao truc tiep va cac phuong thuc duoc goi
bang tay, nen test khong bao gio bi treo.
"""

import json
import os
import tempfile
import time
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_SANDBOX = tempfile.mkdtemp(prefix="gifpet-notif-ui-")
os.environ["APPDATA"] = os.path.join(_SANDBOX, "appdata")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SANDBOX, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "data")
os.environ["HOME"] = os.path.join(_SANDBOX, "home")
for _directory in (
    os.environ["APPDATA"],
    os.environ["XDG_CONFIG_HOME"],
    os.environ["XDG_DATA_HOME"],
    os.environ["HOME"],
):
    os.makedirs(_directory, exist_ok=True)

import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core.config import Config  # noqa: E402
from gifpet.notifications.controller import NotificationController  # noqa: E402
from gifpet.notifications.models import PetNotification  # noqa: E402
from gifpet.notifications.state import NotificationState  # noqa: E402
from gifpet.ui import notification_panel  # noqa: E402
from gifpet.ui.pet_window import PetWindow  # noqa: E402

NOW = 1_700_000_000

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def pump(times=3):
    for _ in range(times):
        app().processEvents()


class UiCase(unittest.TestCase):
    """Moi test co mot PetWindow that nhung cau hinh va hop thu rieng."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gifpet-notif-ui-case-")
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.inbox_dir = os.path.join(self.root, "inbox")
        os.makedirs(self.inbox_dir)

        self.config = Config(os.path.join(self.root, "config.json"))
        self.config.data["notifications_inbox"] = self.inbox_dir
        self.config.data["notifications_enabled"] = True

        self.window = PetWindow(app(), self.config)
        pump()
        # Trang thai rieng: khong doc/ghi file cua nguoi dung that.
        self.state = NotificationState(
            os.path.join(self.root, "notifications_state.json"),
            clock=lambda: NOW,
        )
        self.controller = NotificationController(self.state, clock=lambda: NOW)
        self.controller.set_inbox(self.inbox_dir)
        self.window.notifications_state = self.state
        self.window.notifications = self.controller
        self.window.notification_inbox = self.controller.inbox_source

    def tearDown(self):
        try:
            self.window.close()
            self.window.deleteLater()
        except RuntimeError:
            pass
        pump()

    def note(self, ident="n1", title="Xong viec", message="Tac vu da xong",
             severity="info", source="hermes"):
        return PetNotification.build(
            source=source,
            title=title,
            message=message,
            severity=severity,
            id=ident,
            ttl_seconds=300,
            now=NOW,
        )

    def populate(self, count=2):
        notes = []
        for index in range(count):
            note = self.note(
                ident="hist%d" % index,
                title="Tieu de %d" % index,
                message="Noi dung %d" % index,
            )
            self.state.add_history(note, save=False)
            notes.append(note)
        return notes


# ----------------------------------------------------------------------
# Bong bong thoai: chu thuong, khong dien giai HTML
# ----------------------------------------------------------------------
class BubbleTests(UiCase):
    def bubble_label(self):
        bubble = self.window.bubble
        self.assertIsNotNone(bubble, "PetWindow phai co bong bong thoai")
        return bubble.label

    def test_announce_plain_uses_plain_text_format(self):
        self.window.announce("<b>dam</b> & <script>x</script>", plain=True)
        pump()
        label = self.bubble_label()
        self.assertEqual(label.textFormat(), Qt.PlainText)
        self.assertEqual(label.text(), "<b>dam</b> & <script>x</script>")

    def test_notification_bubble_is_plain_text(self):
        note = self.note(title="<img src=x onerror=1>", message="<a href='#'>bam</a>")
        notification_panel.show_notification(self.window, note)
        pump()
        label = self.bubble_label()
        self.assertEqual(label.textFormat(), Qt.PlainText)
        self.assertIn("<img src=x onerror=1>", label.text())
        self.assertNotIn("rich", label.textFormat().__class__.__name__.lower())

    def test_bubble_text_contains_title_message_and_source(self):
        note = self.note(title="Tieu de", message="Noi dung", source="hermes")
        notification_panel.show_notification(self.window, note)
        pump()
        text = self.bubble_label().text()
        self.assertIn("Tieu de", text)
        self.assertIn("Noi dung", text)
        self.assertIn("hermes", text)

    def test_hide_source_setting_is_respected(self):
        self.state.set_setting("show_source", False, save=False)
        notification_panel.show_notification(self.window, self.note(source="hermes"))
        pump()
        self.assertNotIn("hermes", self.bubble_label().text())

    def test_bubble_disabled_setting_suppresses_bubble(self):
        # Tao bong bong truoc khi kiem tra -> bong bong phai dang hien.
        self.window.announce("tin truoc do", plain=True)
        pump()
        bubble = self.window.bubble
        self.assertIsNotNone(bubble, "PetWindow phai co bong bong thoai")
        self.assertTrue(bubble.isVisible(), "bong bong phai hien sau khi announce")
        self.state.set_setting("bubble", False, save=False)
        notification_panel.show_notification(self.window, self.note())
        pump()
        self.assertFalse(bubble.isVisible())

    def test_bubble_hide_timer_is_single_shot_and_long_enough(self):
        self.window.announce("tin", duration_ms=notification_panel.BUBBLE_MS, plain=True)
        pump()
        timer = self.window.bubble.hide_timer
        self.assertTrue(timer.isSingleShot())
        self.assertTrue(timer.isActive())
        self.assertGreaterEqual(timer.interval(), 1000)

    def test_long_notification_does_not_break_layout(self):
        note = self.note(title="T" * 5000, message="M" * 9000)
        notification_panel.show_notification(self.window, note)
        pump()
        label = self.bubble_label()
        self.assertLessEqual(len(label.text()), 5000 + 9000 + 200)
        self.assertLessEqual(label.width(), 340 + 40)


# ----------------------------------------------------------------------
# Cua so lich su
# ----------------------------------------------------------------------
class HistoryDialogTests(UiCase):
    def dialog(self):
        return notification_panel.NotificationHistoryDialog(self.window)

    def _name(self, widget):
        for attribute in dir(widget):
            if attribute.startswith("_"):
                continue
            try:
                value = getattr(widget, attribute)
            except Exception:
                continue
            if value is name:
                return attribute
        return None

    def _list(self, dialog):
        name = self._name(dialog, "list")
        self.assertIsNotNone(name, "cua so lich su phai co danh sach")
        return getattr(dialog, name)

    def _detail(self, dialog):
        name = self._name(dialog, "detail")
        self.assertIsNotNone(name, "cua so lich su phai co vung chi tiet")
        return getattr(dialog, name)

    def _status(self, dialog):
        name = self._name(dialog, "status")
        self.assertIsNotNone(name, "cua so lich su phai co dong trang thai")
        return getattr(dialog, name)

    def test_empty_history_shows_placeholder(self):
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        self.assertEqual(self._list(dialog).count(), 0)
        self.assertEqual(self._detail(dialog).textFormat(), Qt.PlainText)
        self.assertTrue(self._detail(dialog).toPlainText())

    def test_history_rows_show_saved_entries(self):
        self.populate(3)
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        rows = self._list(dialog)
        self.assertEqual(rows.count(), 3)
        self.assertIn("Tieu de 2", rows.item(0).text())

    def test_detail_is_plain_text_and_not_html(self):
        note = self.note(title="<b>a</b>", message="<script>b</script>")
        self.state.add_history(note, save=False)
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        rows = self._list(dialog)
        rows.setCurrentRow(0)
        dialog._show_current(rows.currentItem())
        detail = self._detail(dialog)
        self.assertEqual(detail.textFormat(), Qt.PlainText)
        text = detail.toPlainText()
        self.assertIn("<b>a</b>", text)
        self.assertIn("<script>b</script>", text)

    def test_clear_history_empties_list_and_state(self):
        self.populate(2)
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        self.assertEqual(self._list(dialog).count(), 2)
        dialog._clear_history()
        self.assertEqual(self._list(dialog).count(), 0)
        self.assertEqual(self.state.recent(), [])

    def test_status_text_reports_inbox_and_state(self):
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        text = self._status(dialog).text()
        self.assertIn(self.inbox_dir, text)

    def test_missing_inbox_does_not_crash_dialog(self):
        """Hop thu bien mat: cua so lich su van phai mo duoc."""
        empty = os.path.join(self.root, "bi-xoa")
        self.controller.set_inbox(empty)
        if os.path.isdir(empty):
            os.rmdir(empty)
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        self.assertEqual(self._list(dialog).count(), 0)

    def test_history_view_limit(self):
        self.populate(notification_panel.HISTORY_VIEW_LIMIT + 10)
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        self.assertLessEqual(self._list(dialog).count(), notification_panel.HISTORY_VIEW_LIMIT)


# ----------------------------------------------------------------------
# Timer va vong doc hop thu
# ----------------------------------------------------------------------
class TimerTests(UiCase):
    def test_setup_creates_timer_and_controller(self):
        window = PetWindow(app(), self.config)
        self.addCleanup(window.close)
        self.addCleanup(window.deleteLater)
        timer = getattr(window, "notification_timer", None)
        if timer is None:
            self.fail("thiếu notification_timer: tính năng thông báo không bật được")
        self.assertIsNotNone(getattr(window, "notifications", None))
        self.assertIsNotNone(getattr(window, "notification_inbox", None))
        self.assertIsNotNone(getattr(window, "notifications_state", None))

    def test_disable_stops_timer_and_enable_restarts(self):
        timer = self.window.notification_timer
        self.assertIsNotNone(timer)
        notification_panel.set_enabled(self.window, False, persist=False)
        pump()
        self.assertFalse(timer.isActive())
        notification_panel.set_enabled(self.window, True, persist=False)
        pump()
        self.assertTrue(timer.isActive())

    def test_close_stops_notification_timer(self):
        timer = self.window.notification_timer
        self.assertTrue(timer.isActive())
        self.window.close()
        pump()
        self.assertFalse(timer.isActive())

    def test_shutdown_closes_open_dialogs(self):
        dialog = notification_panel.NotificationHistoryDialog(self.window)
        self.window._notification_history_dialog = dialog
        dialog.show()
        pump()
        self.window._shutdown_notifications()
        pump()
        self.assertFalse(dialog.isVisible())
        self.assertIsNone(self.window._notification_history_dialog)
        dialog.deleteLater()

    def test_toggle_notifications_does_not_touch_real_config(self):
        self.window.toggle_notifications(False)
        pump()
        self.assertFalse(self.window.notification_timer.isActive())
        self.window.toggle_notifications(True)
        pump()
        self.assertTrue(self.window.notification_timer.isActive())

    def test_mute_is_reflected_in_state(self):
        notification_panel.set_muted(self.window, True)
        self.assertTrue(notification_panel.is_muted(self.window))
        notification_panel.set_muted(self.window, False)
        self.assertFalse(notification_panel.is_muted(self.window))


# ----------------------------------------------------------------------
# Producer -> presenter: tep trong hop thu thanh bong bong
# ----------------------------------------------------------------------
class InboxPresenterTests(UiCase):
    def write(self, name, data):
        path = os.path.join(self.inbox_dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def payload(self, **overrides):
        now = int(time.time())
        data = {
            "id": "ui1",
            "source": "hermes",
            "created_at": now - 2,
            "expires_at": now + 300,
            "version": 1,
            "title": "Build xong",
            "message": "Tac vu nen da hoan tat",
            "severity": "success",
        }
        data.update(overrides)
        return data

    def drain(self, rounds=3):
        presented = []
        for _step in range(rounds):
            self.controller.tick()
            note = self.controller.take_next()
            if note is not None:
                presented.append(note)
                notification_panel.show_notification(self.window, note)
        pump()
        return presented

    def test_inbox_file_becomes_bubble_and_history(self):
        path = self.write("ui1.json", self.payload())
        presented = self.drain()
        self.assertEqual([n.id for n in presented], ["ui1"])
        self.assertIn("Build xong", self.window.bubble.label.text())
        self.assertEqual(self.window.bubble.label.textFormat(), Qt.PlainText)
        self.assertEqual([e["id"] for e in self.state.recent()], ["ui1"])
        self.assertFalse(os.path.exists(path))

    def test_disabled_notifications_show_nothing(self):
        self.write("ui3.json", self.payload(id="ui3"))
        notification_panel.set_enabled(self.window, False, persist=False)
        self.assertEqual(self.drain(), [])
        notification_panel.set_enabled(self.window, True, persist=False)
        presented = self.drain()
        self.assertEqual([n.id for n in presented], ["ui3"])

    def test_two_files_are_spaced_by_rate_limit(self):
        self.write("a.json", self.payload(id="a"))
        self.write("b.json", self.payload(id="b"))
        presented = self.drain(rounds=4)
        self.assertLessEqual(len(presented), 2)

    def test_history_dialog_shows_presented_notification(self):
        self.write("ui4.json", self.payload(id="ui4", title="Lich su"))
        self.drain()
        dialog = notification_panel.NotificationHistoryDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        dialog._refresh()
        rows = UiCase._list(self, dialog)
        self.assertEqual(rows.count(), 1)
        self.assertIn("Lich su", rows.item(0).text())


# ----------------------------------------------------------------------
# Hop thoai cai dat
# ----------------------------------------------------------------------
class SettingsDialogTests(UiCase):
    def dialog(self):
        return notification_panel.NotificationSettingsDialog(self.window)

    def checkbox(self, dialog, key):
        widget = getattr(dialog, key, None)
        if widget is None:
            self.fail("hộp thoại cài đặt thiếu ô chọn %r" % key)
        return widget

    def test_values_keys_and_round_trip(self):
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        values = dialog.values()
        self.assertEqual(
            set(values),
            {"enabled", "muted", "bubble", "tray", "show_source", "inbox_path", "poll_ms"},
        )
        self.assertEqual(values["inbox_path"], self.inbox_dir)
        self.assertGreaterEqual(values["poll_ms"], 1000)

    def test_apply_returns_state_to_settings(self):
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        self.checkbox(dialog, "bubble").setChecked(False)
        self.checkbox(dialog, "show_source").setChecked(False)
        dialog.apply()
        pump()
        self.assertFalse(self.state.get_setting("bubble"))
        self.assertFalse(self.state.get_setting("show_source"))

    def test_values_reflect_checkboxes(self):
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        box = self.checkbox(dialog, "muted")
        box.setChecked(not box.isChecked())
        self.assertEqual(dialog.values()["muted"], box.isChecked())

    def test_apply_survives_missing_controller(self):
        self.window.notifications = None
        dialog = self.dialog()
        self.addCleanup(dialog.deleteLater)
        dialog.apply()
        pump()


if __name__ == "__main__":
    unittest.main()
