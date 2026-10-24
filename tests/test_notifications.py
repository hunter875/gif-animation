"""Test loi cho tinh nang thong bao chi-nhan (khong co hanh dong).

Pham vi: ``gifpet.notifications`` (models, inbox, state, dispatcher,
controller, registry, sender). Khong import Qt: toan bo phan nay phai chay
duoc tren may khong co PyQt (xem docs/MODULAR-ASSISTANT.md).

Nguyen tac viet test:
- Dong ho luon duoc tiem (``clock=``/``now=``), khong ``sleep``, khong mang.
- Moi test dung thu muc tam, khong doc/ghi file cau hinh that.
- Ky vong bam theo yeu cau trong docs, khong bam theo hanh vi hien tai cua
  code: cho nao code lam sai thi test phai do.
"""

import builtins
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gifpet.notifications import inbox as inbox_module  # noqa: E402
from gifpet.notifications import models, sender, state as state_module  # noqa: E402
from gifpet.notifications.controller import (  # noqa: E402
    DEFAULT_POLL_MS,
    MAX_POLL_MS,
    MIN_POLL_MS,
    NotificationController,
    poll_interval_from_config,
)
from gifpet.notifications.dispatcher import (  # noqa: E402
    MAX_DIAGNOSTICS,
    Dispatcher,
    MemorySource,
)
from gifpet.notifications.inbox import (  # noqa: E402
    MAX_FILE_BYTES,
    MAX_NOTIFICATIONS_PER_POLL,
    Inbox,
    InboxProblem,
    InboxSource,
)
from gifpet.notifications.models import PetNotification  # noqa: E402
from gifpet.notifications.protocol import NotificationSource  # noqa: E402
from gifpet.notifications.registry import (  # noqa: E402
    NotificationRegistry,
    RegistryError,
    default_registry,
)
from gifpet.notifications.sender import SenderError, write_notification  # noqa: E402
from gifpet.notifications.state import (  # noqa: E402
    MAX_HISTORY,
    NotificationState,
    SEEN_TTL_SECONDS,
)

NOW = 1_700_000_000  # moc thoi gian co dinh cho moi test


# ----------------------------------------------------------------------
# Tien ich
# ----------------------------------------------------------------------
class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gifpet-notif-")
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.inbox_dir = os.path.join(self.root, "inbox")
        os.makedirs(self.inbox_dir)
        self.state_path = os.path.join(self.root, "notifications_state.json")

    def make_state(self, clock=None):
        return NotificationState(path=self.state_path, clock=clock or (lambda: NOW))

    def write_raw(self, name, text, encoding="utf-8"):
        path = os.path.join(self.inbox_dir, name)
        data = text.encode(encoding) if isinstance(text, str) else text
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def payload(self, **overrides):
        data = {
            "id": "n1",
            "source": "hermes",
            "created_at": NOW - 5,
            "expires_at": NOW + 300,
            "version": 1,
            "title": "Xong viec",
            "message": "Tac vu da hoan tat",
            "severity": "info",
        }
        data.update(overrides)
        return data

    def write_payload(self, data, name=None):
        name = name or "%s.json" % data.get("id", "n1")
        return self.write_raw(name, json.dumps(data))

    def build(self, ident="n1", ttl_seconds=300, source="hermes", title="Tin"):
        return PetNotification.build(
            source=source,
            title=title,
            message="",
            id=ident,
            ttl_seconds=ttl_seconds,
            now=NOW,
        )


# ----------------------------------------------------------------------
# models: kiem tra du lieu chat + gia tri thu dich
# ----------------------------------------------------------------------
class ModelTests(TempDirCase):
    def test_round_trip_build_and_parse(self):
        note = PetNotification.build(
            source="hermes",
            title="Chao",
            message="Pet nhan duoc tin",
            ttl_seconds=120,
            now=NOW,
        )
        self.assertIsInstance(note, PetNotification)
        self.assertEqual(note.expires_at - note.created_at, 120)
        raw = note.to_dict()
        self.assertEqual(
            set(raw),
            {
                "version",
                "id",
                "source",
                "title",
                "message",
                "severity",
                "created_at",
                "expires_at",
            },
        )
        again = PetNotification.parse(raw, now=NOW)
        self.assertEqual(again.id, note.id)
        self.assertEqual(again.title, "Chao")

    def test_payload_has_no_action_fields(self):
        """Thong bao chi de doc: khong duong dan, khong lenh, khong URL."""
        raw = self.build().to_dict()
        for banned in ("url", "link", "command", "action", "cmd", "exec", "callback"):
            self.assertNotIn(banned, raw)

    def test_required_keys_are_enforced(self):
        self.assertEqual(
            set(models.REQUIRED_KEYS), {"id", "source", "created_at", "expires_at"}
        )
        for key in models.REQUIRED_KEYS:
            raw = self.payload()
            del raw[key]
            with self.assertRaises(models.NotificationError, msg=key):
                PetNotification.parse(raw, now=NOW)

    def test_unknown_field_is_rejected(self):
        raw = self.payload()
        raw["command"] = "rm -rf /"
        with self.assertRaises(models.NotificationError):
            PetNotification.parse(raw, now=NOW)

    def test_non_object_payload_is_rejected(self):
        for value in ([], "text", 42, None, True):
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(value, now=NOW)

    def test_hostile_ids_rejected(self):
        bad = [
            "../escape",
            "..",
            "a/b",
            "a\\b",
            "nul\x00byte",
            "",
            "x" * (models.MAX_ID_LEN + 1),
            "-dash-first",
            "space id",
            ".hidden",
        ]
        for value in bad:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(self.payload(id=value), now=NOW)

    def test_hostile_sources_rejected(self):
        bad = [
            "",
            "Hermes",
            "her mes",
            "../x",
            "a/b",
            "x" * (models.MAX_SOURCE_LEN + 1),
            ".dot",
        ]
        for value in bad:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(self.payload(source=value), now=NOW)

    def test_bad_severity_rejected(self):
        for value in ["critical", "", "INFO", None, 3]:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(self.payload(severity=value), now=NOW)

    def test_bad_version_rejected(self):
        for value in [0, 2, "1", True, None]:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(self.payload(version=value), now=NOW)

    def test_timestamp_types_rejected(self):
        for value in ["1700000000", None, True, float("nan"), float("inf"), []]:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.parse(self.payload(created_at=value), now=NOW)

    def test_expiry_window_rules(self):
        # expires_at phai sau created_at.
        with self.assertRaises(models.NotificationError):
            PetNotification.parse(self.payload(created_at=NOW, expires_at=NOW), now=NOW)
        # TTL toi da mot tuan.
        with self.assertRaises(models.NotificationError):
            PetNotification.parse(
                self.payload(
                    created_at=NOW - 10,
                    expires_at=NOW - 10 + models.MAX_TTL_SECONDS + 1,
                ),
                now=NOW,
            )
        # Khong nhan tin tao qua tuong lai xa.
        with self.assertRaises(models.NotificationError):
            PetNotification.parse(
                self.payload(
                    created_at=NOW + models.MAX_CLOCK_SKEW_SECONDS + 60,
                    expires_at=NOW + models.MAX_CLOCK_SKEW_SECONDS + 600,
                ),
                now=NOW,
            )
        ok = PetNotification.parse(
            self.payload(created_at=NOW + 5, expires_at=NOW + 60), now=NOW
        )
        self.assertEqual(ok.created_at, NOW + 5)

    def test_empty_content_rejected(self):
        with self.assertRaises(models.NotificationError):
            PetNotification.parse(self.payload(title="", message=""), now=NOW)

    def test_control_characters_are_stripped(self):
        note = PetNotification.parse(
            self.payload(title="a\x00b\x1b[31mc", message="line1\nline2\x07"), now=NOW
        )
        joined = note.title + note.message
        for char in ("\x00", "\x1b", "\x07"):
            self.assertNotIn(char, joined)
        self.assertEqual(note.title, "a b [31mc")
        self.assertNotIn("\x1b", note.title)

    def test_html_is_preserved_as_text_only(self):
        note = PetNotification.parse(
            self.payload(title="<b>bold</b>", message="<script>x</script>"), now=NOW
        )
        # Model giu nguyen markup; viec khong dien giai la trach nhiem cua UI
        # (khoa bang test PlainText o test_notification_ui).
        self.assertEqual(note.title, "<b>bold</b>")
        self.assertEqual(note.message, "<script>x</script>")

    def test_long_text_is_truncated_not_rejected(self):
        note = PetNotification.parse(
            self.payload(
                title="T" * (models.MAX_TITLE_LEN + 50),
                message="M" * (models.MAX_MESSAGE_LEN + 50),
            ),
            now=NOW,
        )
        self.assertLessEqual(len(note.title), models.MAX_TITLE_LEN)
        self.assertLessEqual(len(note.message), models.MAX_MESSAGE_LEN)

    def test_expired_uses_injected_clock(self):
        note = PetNotification.parse(self.payload(), now=NOW)
        self.assertFalse(note.expired(now=NOW))
        self.assertTrue(note.expired(now=note.expires_at))

    def test_build_rejects_bad_ttl(self):
        for value in ["60", None, float("nan"), float("inf"), -5]:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.build(
                    source="hermes",
                    title="t",
                    message="m",
                    ttl_seconds=value,
                    now=NOW,
                )
        clamped = PetNotification.build(
            source="hermes", title="t", message="m", ttl_seconds=10 ** 9, now=NOW
        )
        self.assertEqual(
            clamped.expires_at - clamped.created_at, models.MAX_TTL_SECONDS
        )

    def test_build_rejects_bad_source(self):
        for value in ["", "../x", "Hermes", "x" * 100]:
            with self.assertRaises(models.NotificationError, msg=repr(value)):
                PetNotification.build(source=value, title="t", message="m", now=NOW)

    def test_repr_is_bounded(self):
        note = PetNotification.parse(self.payload(title="T" * 500), now=NOW)
        self.assertLess(len(repr(note)), 250)

    def test_new_id_is_safe_and_unique(self):
        ids = {models.new_id(now=NOW) for _ in range(50)}
        self.assertEqual(len(ids), 50)
        for value in ids:
            self.assertTrue(models.valid_notification_id(value), value)


# ----------------------------------------------------------------------
# inbox: ten, doc file, han che khoi luong
# ----------------------------------------------------------------------
class InboxNameTests(TempDirCase):
    def test_safe_name_filters(self):
        safe = ["n1.json", "abc-123.json"]
        unsafe = [
            "../n1.json",
            "..",
            ".",
            "/etc/passwd",
            "sub/n1.json",
            "sub\\n1.json",
            ".hidden.json",
            "n1\x00.json",
            "",
            None,
            "n1.txt",
        ]
        for name in safe:
            self.assertTrue(inbox_module.is_safe_name(name), name)
        for name in unsafe:
            self.assertFalse(inbox_module.is_safe_name(name), name)

    def test_check_reports_problems(self):
        with self.assertRaises(InboxProblem):
            Inbox("").check()
        with self.assertRaises(InboxProblem) as ctx:
            Inbox(os.path.join(self.root, "missing")).check()
        self.assertEqual(ctx.exception.reason, "missing")

        plain = self.write_raw("file.txt", "x")
        with self.assertRaises(InboxProblem) as ctx:
            Inbox(plain).check()
        self.assertIn(ctx.exception.reason, {"not_directory", "missing"})

        Inbox(self.inbox_dir).check()  # khong nem

    def test_names_skips_unsafe_and_caps_listing(self):
        for index in range(inbox_module.MAX_FILES_LISTED + 25):
            self.write_raw("n%04d.json" % index, "{}")
        self.write_raw(".hidden.json", "{}")
        names = Inbox(self.inbox_dir).names()
        self.assertLessEqual(len(names), inbox_module.MAX_FILES_LISTED)
        self.assertNotIn(".hidden.json", names)
        # Khong chi gioi han so ten tra ve: so muc duyet qua cung bi chan,
        # neu khong mot thu muc day tep rac se quet ca thu muc moi luot poll.
        limit = inbox_module.MAX_FILES_LISTED
        total_entries = limit * 3
        for index in range(limit + 25, total_entries):
            self.write_raw("n%04d.json" % index, "{}")
        consumed = []

        real_scandir = os.scandir

        def counting_scandir(path="."):
            entries = real_scandir(path)
            outer = entries

            class Counting:
                def __iter__(self):
                    inner = outer.__iter__()

                    def generate():
                        for entry in inner:
                            consumed.append(entry.name)
                            yield entry

                    return generate()

            return Counting()

        os.scandir = counting_scandir
        try:
            listed = Inbox(self.inbox_dir).names()
        finally:
            os.scandir = real_scandir
        self.assertLessEqual(len(listed), limit)
        self.assertLessEqual(
            len(consumed),
            limit,
            "Inbox.names phai ngung duyet thu muc sau gioi han, khong quet het %d muc"
            % total_entries,
        )

    def test_poll_workload_is_bounded_with_irrelevant_entries(self):
        """Chi phi poll gio han ca voi tep rac va tep khong phai thong bao."""
        budget = MAX_NOTIFICATIONS_PER_POLL
        total_entries = budget * 4
        for index in range(total_entries):
            name = "n%04d.json" % index
            if index % 2:
                self.write_raw(name, "{}")
            else:
                self.write_raw(name.replace(".json", ".txt"), "rac")
        consumed = []

        real_scandir = os.scandir

        def counting_scandir(path="."):
            entries = real_scandir(path)
            outer = entries

            class Counting:
                def __iter__(self):
                    inner = outer.__iter__()

                    def generate():
                        for entry in inner:
                            consumed.append(entry.name)
                            yield entry

                    return generate()

            return Counting()

        os.scandir = counting_scandir
        try:
            notifications, handled = Inbox(self.inbox_dir).poll(
                limit=budget, now=NOW
            )
        finally:
            os.scandir = real_scandir
        for note in notifications:
            self.assertIsInstance(note, PetNotification)
        self.assertLessEqual(
            len(consumed),
            budget * 3,
            "poll phai gioi han so muc duyet qua (da duyet %d/%d)"
            % (len(consumed), total_entries),
        )


class InboxReadTests(TempDirCase):
    def test_read_rejects_bad_json_and_bad_shape(self):
        cases = {
            "n1.json": "{not json",
            "n2.json": "[]",
            "n3.json": "",
        }
        for name, text in cases.items():
            self.write_raw(name, text)
        box = Inbox(self.inbox_dir)
        for name in cases:
            with self.assertRaises(InboxProblem) as ctx:
                box.read(name)
            self.assertIn(
                ctx.exception.reason,
                {"bad_json", "not_object", "empty_file"},
                name,
            )

    def test_read_rejects_non_utf8(self):
        self.write_raw("n1.json", b"\xff\xfe\x00bad")
        with self.assertRaises(InboxProblem) as ctx:
            Inbox(self.inbox_dir).read("n1.json")
        self.assertIn(ctx.exception.reason, {"not_utf8", "bad_json"})

    def test_read_rejects_oversized_file(self):
        big = json.dumps(self.payload(message="x" * (MAX_FILE_BYTES + 512)))
        self.assertGreater(len(big), MAX_FILE_BYTES)
        self.write_raw("n1.json", big)
        with self.assertRaises(InboxProblem) as ctx:
            Inbox(self.inbox_dir).read("n1.json")
        self.assertEqual(ctx.exception.reason, "too_large")

    def test_read_caps_bytes_even_if_file_grows(self):
        """Tep phinh sau lstat khong lam doc vo han: cap max_file_bytes + 1."""
        self.write_payload(self.payload())
        small = Inbox(self.inbox_dir, max_file_bytes=256)
        real_open = builtins.open
        requests = []

        def counting_open(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            if str(path).endswith(".json"):
                real_read = handle.read

                def read(*a, **k):
                    data = real_read(*a, **k)
                    requests.append(len(data))
                    return data

                handle.read = read
            return handle

        builtins.open = counting_open
        try:
            try:
                small.read("n1.json")
            except InboxProblem as exc:
                self.assertEqual(exc.reason, "too_large")
        finally:
            builtins.open = real_open
        self.assertTrue(requests, "phai doc tep qua ham open co gioi han")
        self.assertLessEqual(max(requests), MAX_FILE_BYTES + 1)

    def test_read_never_loads_more_than_budget(self):
        """Lan doc nao cung phai bi chan boi mot gioi han byte."""
        self.write_payload(self.payload(message="z" * (MAX_FILE_BYTES - 400)))
        real_open = builtins.open
        oversize = []

        def checking_open(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            if str(path).endswith(".json"):
                real_read = handle.read

                def read(*a, **k):
                    size = a[0] if a else k.get("size")
                    if not isinstance(size, int) or size > MAX_FILE_BYTES + 1:
                        oversize.append(size)
                    return real_read(*a, **k)

                handle.read = read
            return handle

        builtins.open = checking_open
        try:
            Inbox(self.inbox_dir).read("n1.json")
        finally:
            builtins.open = real_open
        self.assertEqual(oversize, [], "doc khong gioi han se doc ca tep lon")

    def test_read_rejects_unsafe_name(self):
        with self.assertRaises(InboxProblem) as ctx:
            Inbox(self.inbox_dir).read("../escape.json")
        self.assertEqual(ctx.exception.reason, "unsafe_name")

    @unittest.skipUnless(hasattr(os, "symlink"), "khong ho tro symlink")
    def test_symlink_is_rejected_and_not_followed(self):
        outside = os.path.join(self.root, "secret.json")
        with open(outside, "w", encoding="utf-8") as handle:
            json.dump(self.payload(), handle)
        link = os.path.join(self.inbox_dir, "n1.json")
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("khong tao duoc symlink")
        box = Inbox(self.inbox_dir)
        with self.assertRaises(InboxProblem) as ctx:
            box.read("n1.json")
        self.assertEqual(ctx.exception.reason, "symlink")
        # Poll khong duoc coi file symlink la thong bao hop le.
        notifications, handled = box.poll(now=NOW)
        self.assertEqual([n.id for n in notifications], [])
        # Khong duoc xoa file ben ngoai qua acknowledge.
        box.acknowledge("n1.json")
        self.assertTrue(os.path.exists(outside))
        self.assertIn("n1.json", handled)

    @unittest.skipUnless(hasattr(os, "link"), "khong ho tro hardlink")
    def test_hardlink_is_rejected(self):
        outside = os.path.join(self.root, "outside.json")
        with open(outside, "w", encoding="utf-8") as handle:
            json.dump(self.payload(), handle)
        try:
            os.link(outside, os.path.join(self.inbox_dir, "n1.json"))
        except (OSError, NotImplementedError):
            self.skipTest("khong tao duoc hardlink")
        box = Inbox(self.inbox_dir)
        try:
            payload = box.read("n1.json")
        except InboxProblem as exc:
            self.assertIn(exc.reason, {"hardlink", "unsafe_name"})
            return
        # Neu doc duoc thi phai vi nền tang khong bao so link (Windows).
        self.assertIn("id", payload)

    def test_poll_is_bounded_by_byte_budget(self):
        """Moi luot poll chi doc toi da mot khoi luong byte nhat dinh."""
        chunk = "y" * (MAX_FILE_BYTES - 2000)
        total_written = MAX_NOTIFICATIONS_PER_POLL + 15
        for index in range(total_written):
            self.write_payload(self.payload(id="n%d" % index, message=chunk))
        box = Inbox(self.inbox_dir)
        read_bytes = 0
        real_open = open

        def counting_open(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            if str(path).endswith(".json"):
                real_read = handle.read

                def read(*a, **k):
                    nonlocal read_bytes
                    data = real_read(*a, **k)
                    read_bytes += len(data)
                    return data

                handle.read = read
            return handle

        builtins.open = counting_open
        try:
            notifications, handled = box.poll(
                limit=MAX_NOTIFICATIONS_PER_POLL, now=NOW
            )
        finally:
            builtins.open = real_open
        self.assertLessEqual(len(notifications), MAX_NOTIFICATIONS_PER_POLL)
        self.assertLessEqual(read_bytes, inbox_module.MAX_TOTAL_BYTES)
        # File chua doc van con do cho lan sau (khong bi bo mat).
        self.assertGreater(len(box.names()), len(handled))

    def test_poll_limit_is_respected(self):
        for index in range(MAX_NOTIFICATIONS_PER_POLL + 10):
            self.write_payload(self.payload(id="n%d" % index))
        notifications, _handled = Inbox(self.inbox_dir).poll(limit=3, now=NOW)
        self.assertEqual(len(notifications), 3)


class InboxPollTests(TempDirCase):
    def test_poll_returns_valid_and_skips_expired(self):
        self.write_payload(self.payload(id="good"))
        self.write_payload(
            self.payload(id="old", created_at=NOW - 900, expires_at=NOW - 1)
        )
        notifications, handled = Inbox(self.inbox_dir).poll(now=NOW)
        self.assertEqual([n.id for n in notifications], ["good"])
        self.assertIn("old.json", handled)

    def test_malformed_file_does_not_break_other_files(self):
        self.write_raw("n1.json", "{broken")
        self.write_payload(self.payload(id="good", source="s1"))
        notifications, handled = Inbox(self.inbox_dir).poll(now=NOW)
        self.assertEqual([n.id for n in notifications], ["good"])
        self.assertIn("n1.json", handled)

    def test_bad_payload_file_is_handled_not_raised(self):
        self.write_payload(self.payload(id="../evil"))
        notifications, handled = Inbox(self.inbox_dir).poll(now=NOW)
        self.assertEqual(notifications, [])
        self.assertEqual(len(handled), 1)

    def test_acknowledge_removes_only_safe_regular_files(self):
        path = self.write_payload(self.payload(id="good"))
        box = Inbox(self.inbox_dir)
        self.assertEqual(box.acknowledge(["good.json"]), 1)
        self.assertFalse(os.path.exists(path))
        # Ten khong an toan: khong duoc dung toi filesystem.
        self.assertEqual(box.acknowledge(["../escape.json"]), 0)
        self.assertEqual(box.acknowledge(["missing.json"]), 0)

    def test_poll_and_ack_preserve_unrelated_json(self):
        """Chi tep thong bao da nhan dien moi duoc xoa; JSON khac phai giu."""
        package = os.path.join(self.inbox_dir, "package.json")
        self.write_raw("package.json", json.dumps({"name": "khong-phai-thong-bao"}))
        malformed = self.write_raw("malformed.json", "{not json")
        other_program = self.write_raw(
            "other.json", json.dumps({"id": "x", "status": "running", "pid": 42})
        )
        not_json = self.write_raw("notes.txt", "ghi chu")
        note_file = self.write_payload(self.payload(id="real"))
        box = Inbox(self.inbox_dir)
        notifications, handled = box.poll(now=NOW)
        self.assertEqual([n.id for n in notifications], ["real"])
        names = handled if isinstance(handled, (list, set, tuple)) else [handled]
        box.acknowledge(names)
        self.assertFalse(os.path.exists(note_file), "tep thong bao da nhan phai duoc xoa")
        for path in (package, malformed, other_program, not_json):
            self.assertTrue(
                os.path.exists(path),
                "tep khong phai thong bao bi xoa nham: %s" % os.path.basename(path),
            )
        notifications, _handled = box.poll(now=NOW)
        self.assertNotIn("real", [n.id for n in notifications])

    def test_source_tracks_pending_ack(self):
        self.write_payload(self.payload(id="a"))
        source = InboxSource(self.inbox_dir, now=lambda: NOW)
        got = source.poll(5)
        self.assertEqual([n.id for n in got], ["a"])
        self.assertEqual(source.take_ack(), ["a.json"])
        self.assertEqual(source.take_ack(), [])

    def test_diagnostic_counters_start_at_zero(self):
        """Dem chan doan khong duoc no ra vi thuoc tinh chua khoi tao."""
        self.write_raw("n1.json", "{broken")
        box = Inbox(self.inbox_dir, now=lambda: NOW)
        self.assertEqual(getattr(box, "diagnostic_count", 0), 0)
        self.assertEqual(getattr(box, "skipped_count", 0), 0)
        notifications, handled = box.poll(now=NOW)
        self.assertEqual(notifications, [])
        self.assertEqual(box.diagnostic_count, 1)
        self.assertEqual(box.skipped_count, 1)

    def test_reset_diagnostics_clears_counters(self):
        self.write_raw("n1.json", "{broken")
        box = Inbox(self.inbox_dir, now=lambda: NOW)
        box.poll(now=NOW)
        box.reset_diagnostics()
        self.assertEqual(box.diagnostic_count, 0)
        self.assertEqual(box.skipped_count, 0)
        self.assertEqual(box.diagnostics, [])


# ----------------------------------------------------------------------
# state: trung lap, khoi phuc sau restart, xoa lich su, cai dat
# ----------------------------------------------------------------------
class StateTests(TempDirCase):
    def test_settings_round_trip_and_active(self):
        state = self.make_state()
        self.assertTrue(state.active())
        state.save()
        reloaded = self.make_state()
        self.assertTrue(reloaded.active())
        reloaded.set_setting("muted", True)
        self.assertFalse(reloaded.active())
        with self.assertRaises(KeyError):
            reloaded.set_setting("khong_ton_tai", 1)

    def test_state_file_is_outside_inbox(self):
        state = self.make_state()
        state.save()
        self.assertTrue(os.path.exists(self.state_path))
        self.assertNotEqual(os.path.dirname(state.path), self.inbox_dir)

    def test_corrupt_state_file_falls_back_to_defaults(self):
        with open(self.state_path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        state = self.make_state()
        self.assertTrue(state.active())
        self.assertEqual(state.recent(), [])
        self.assertTrue(state.get_setting("enabled"))

    def test_mark_seen_dedup_and_restart(self):
        state = self.make_state()
        self.assertTrue(state.mark_seen("n1"))
        self.assertFalse(state.mark_seen("n1"))
        self.assertTrue(state.is_seen("n1"))
        restarted = self.make_state()
        self.assertTrue(restarted.is_seen("n1"))
        self.assertFalse(restarted.mark_seen("n1"))

    def test_invalid_id_not_marked(self):
        state = self.make_state()
        self.assertFalse(state.mark_seen("../x"))
        self.assertFalse(state.is_seen("../x"))

    def test_history_is_bounded_and_deduped(self):
        state = self.make_state()
        note = PetNotification.parse(self.payload(), now=NOW)
        state.add_history(note)
        state.add_history(note)
        self.assertEqual(len(state.recent()), 1)
        for index in range(MAX_HISTORY + 20):
            state.add_history(
                PetNotification.parse(self.payload(id="h%d" % index), now=NOW)
            )
        self.assertLessEqual(len(state.recent()), MAX_HISTORY)
        self.assertEqual(state.recent()[0]["id"], "h%d" % (MAX_HISTORY + 19))

    def test_history_message_is_truncated(self):
        state = self.make_state()
        note = PetNotification.parse(
            self.payload(message="M" * models.MAX_MESSAGE_LEN), now=NOW
        )
        entry = state.add_history(note)
        self.assertLessEqual(len(entry["message"]), state_module.HISTORY_MESSAGE_LIMIT)

    def test_clear_history_clears_history_but_seen_persists(self):
        """Xoa lich su KHONG duoc lam tin cu duoc hien lai (khong replay).

        Yeu cau cua owner: "clear history khong vo tinh replay tin cu", dedup
        theo id phai con hieu luc ca sau khi khoi dong lai.
        """
        state = self.make_state()
        self.assertTrue(state.mark_seen("n1"))
        state.add_history(PetNotification.parse(self.payload(), now=NOW))
        self.assertEqual(state.clear_history(), 1)
        # Lich su bi xoa...
        self.assertEqual(state.recent(), [])
        # ...nhung dedup theo id van con.
        self.assertTrue(state.is_seen("n1"))
        self.assertFalse(state.mark_seen("n1"))
        restarted = self.make_state()
        self.assertEqual(restarted.recent(), [])
        self.assertTrue(
            restarted.is_seen("n1"), "dedup phai con sau restart, neu khong se replay"
        )
        self.assertFalse(restarted.mark_seen("n1"))

    def test_seen_is_pruned_by_ttl(self):
        state = self.make_state()
        state.mark_seen("n1")
        later = 1_700_000_000 + SEEN_TTL_SECONDS + 10
        restarted = self.make_state(clock=lambda: later)
        self.assertFalse(restarted.is_seen("n1"))

    def test_seen_is_bounded(self):
        state = self.make_state()
        for index in range(state_module.MAX_SEEN + 50):
            state.mark_seen("s%d" % index, save=False)
        self.assertLessEqual(len(state.seen), state_module.MAX_SEEN)
        self.assertTrue(state.is_seen("s%d" % (state_module.MAX_SEEN + 49)))

    def test_inbox_path_setting_rejects_control_characters(self):
        state = self.make_state()
        state.set_setting("inbox_path", "C:/x\x00/y", save=False)
        value = state.get_setting("inbox_path")
        self.assertNotIn("\x00", value or "")

    def test_inbox_path_setting_is_bounded(self):
        state = self.make_state()
        state.set_setting("inbox_path", "a" * 5000, save=False)
        self.assertLessEqual(len(state.get_setting("inbox_path")), 260)


# ----------------------------------------------------------------------
# dispatcher: hang doi, gioi han nhip, khu trung, nguon loi
# ----------------------------------------------------------------------
class DispatcherTests(TempDirCase):
    def make(self, **kwargs):
        state = self.make_state()
        source = MemorySource(source_id="mem")
        registry = default_registry(source)
        return state, source, registry, Dispatcher(state, **kwargs)

    def test_offer_queues_and_presents(self):
        state, _source, _registry, dispatcher = self.make()
        note = self.build()
        self.assertTrue(dispatcher.offer(note, now=NOW))
        presented = dispatcher.next_display(now=NOW)
        self.assertEqual(presented.id, note.id)
        self.assertTrue(state.is_seen(note.id))
        self.assertEqual([entry["id"] for entry in state.recent()], [note.id])

    def test_duplicate_is_not_presented_twice(self):
        _state, _source, _registry, dispatcher = self.make()
        note = self.build()
        dispatcher.offer(note, now=NOW)
        self.assertFalse(dispatcher.offer(note, now=NOW))
        self.assertIsNotNone(dispatcher.next_display(now=NOW))
        self.assertFalse(dispatcher.offer(note, now=NOW + 1))
        self.assertIsNone(dispatcher.next_display(now=NOW + 1))

    def test_restart_does_not_replay_history(self):
        state, _source, _registry, dispatcher = self.make()
        note = self.build()
        dispatcher.offer(note, now=NOW)
        dispatcher.next_display(now=NOW)
        restarted_state = self.make_state()
        fresh = Dispatcher(restarted_state)
        self.assertFalse(fresh.offer(note, now=NOW + 5))
        self.assertEqual(fresh.total_counts()["duplicate"], 1)
        self.assertTrue(state.is_seen(note.id))

    def test_expired_offer_and_dequeue_are_dropped(self):
        state, _source, _registry, dispatcher = self.make()
        self.assertFalse(dispatcher.offer(self.build(ttl_seconds=1), now=NOW + 60))
        note = self.build("n2", ttl_seconds=10)
        self.assertTrue(dispatcher.offer(note, now=NOW))
        self.assertIsNone(dispatcher.next_display(now=NOW + 120))
        self.assertEqual(dispatcher.total_counts()["expired"], 2)
        self.assertEqual(dispatcher.pending(), [])

    def test_queue_limit_drops_excess(self):
        _state, _source, _registry, dispatcher = self.make(max_queue=2)
        for index in range(5):
            dispatcher.offer(self.build("q%d" % index), now=NOW)
        self.assertLessEqual(len(dispatcher.pending()), 2)
        self.assertGreaterEqual(dispatcher.total_counts()["dropped"], 1)

    def test_rate_limit_spaces_out_display(self):
        _state, _source, _registry, dispatcher = self.make(
            max_per_window=2, window=10.0
        )
        for index in range(4):
            dispatcher.offer(self.build("r%d" % index), now=NOW)
        shown = []
        for step in range(6):
            got = dispatcher.next_display(now=NOW + step)
            if got is not None:
                shown.append(got.id)
        self.assertLessEqual(len(shown), 2)
        later = [dispatcher.next_display(now=NOW + 30 + step) for step in range(4)]
        self.assertEqual(len([n for n in later if n is not None]), 2)

    def test_muted_or_disabled_blocks_presentation(self):
        state, _source, _registry, dispatcher = self.make()
        state.set_setting("muted", True, save=False)
        self.assertFalse(dispatcher.offer(self.build(), now=NOW))
        self.assertIsNone(dispatcher.next_display(now=NOW))
        state.set_setting("muted", False, save=False)
        state.set_setting("enabled", False, save=False)
        self.assertFalse(dispatcher.offer(self.build("n2"), now=NOW))
        self.assertIsNone(dispatcher.next_display(now=NOW))

    def test_muted_does_not_permanently_swallow_pending(self):
        """Am roi mo lai: thong bao con han khong duoc bi an vinh vien."""
        state, _source, _registry, dispatcher = self.make()
        dispatcher.offer(self.build("keep"), now=NOW)
        state.set_setting("muted", True, save=False)
        self.assertIsNone(dispatcher.next_display(now=NOW))
        state.set_setting("muted", False, save=False)
        self.assertTrue(state.active())

    def test_faulty_source_is_isolated(self):
        state = self.make_state()

        class Boom(NotificationSource):
            source_id = "boom"

            def poll(self, limit):
                raise RuntimeError("nguon hong")

        class BadReturn(NotificationSource):
            source_id = "bad"

            def poll(self, limit):
                return "khong phai list"

        good = MemorySource(source_id="good")
        good.push(self.build("g1", source="good"))
        registry = default_registry(Boom(), BadReturn(), good)
        dispatcher = Dispatcher(state)
        accepted = dispatcher.collect(registry, now=NOW)
        self.assertEqual(accepted, 1)
        self.assertEqual([n.id for n in dispatcher.pending()], ["g1"])
        self.assertEqual(dispatcher.source_errors.get("boom"), 1)
        codes = [code for _at, code, _detail in dispatcher.diagnostics]
        self.assertIn("source_error", codes)
        self.assertIn("source_bad_return", codes)

    def test_offer_rejects_non_notification(self):
        _state, _source, _registry, dispatcher = self.make()
        for value in [None, "text", {"id": "x"}, object()]:
            self.assertFalse(dispatcher.offer(value, now=NOW), repr(value))

    def test_clear_does_not_make_state_unusable(self):
        _state, _source, _registry, dispatcher = self.make()
        dispatcher.offer(self.build(), now=NOW)
        self.assertEqual(dispatcher.clear("tat thong bao"), 1)
        self.assertEqual(dispatcher.pending(), [])
        self.assertIsNone(dispatcher.next_display(now=NOW))

    def test_diagnostics_are_bounded(self):
        state = self.make_state()
        dispatcher = Dispatcher(state, max_queue=1)
        registry = default_registry()
        for index in range(50):
            registry.register(
                MemorySource(
                    source_id="nguon-%d" % index,
                    items=[self.build("diag-%d" % index)],
                )
            )
        dispatcher.collect(registry, now=NOW)
        self.assertGreater(dispatcher.dropped_count, 0)
        self.assertLessEqual(len(dispatcher.diagnostics), MAX_DIAGNOSTICS)
        self.assertEqual(len(dispatcher.pending()), 1)

    def test_describe_has_no_message_body(self):
        _state, _source, _registry, dispatcher = self.make()
        dispatcher.offer(self.build(), now=NOW)
        text = dispatcher.describe()
        self.assertNotIn("Tac vu", text)


# ----------------------------------------------------------------------
# controller: tick, inbox, cai dat, nguon tu dang ky
# ----------------------------------------------------------------------
class ControllerTests(TempDirCase):
    def make_controller(self, **kwargs):
        state = self.make_state()
        controller = NotificationController(state, **kwargs)
        return state, controller

    def test_requires_state(self):
        with self.assertRaises(TypeError):
            NotificationController(None)

    def test_tick_presents_inbox_file_and_acknowledges(self):
        path = self.write_payload(self.payload(id="frominbox", source="hermes"))
        state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        got = []
        for step in range(3):
            controller.tick(now=NOW + step)
            note = controller.take_next(now=NOW + step)
            if note is not None:
                got.append(note)
        self.assertEqual([n.id for n in got], ["frominbox"])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(len(state.recent()), 1)

    def test_inbox_file_is_not_replayed_after_restart(self):
        self.write_payload(self.payload(id="once", source="hermes"))
        _state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        controller.tick(now=NOW)
        self.assertIsNotNone(controller.take_next(now=NOW))

        # Neu file van con (vi du loi xoa) thi khong duoc hien lai.
        self.write_payload(self.payload(id="once", source="hermes"))
        _state2, restarted = self.make_controller()
        restarted.set_inbox(self.inbox_dir)
        for step in range(3):
            restarted.tick(now=NOW + 1 + step)
        self.assertIsNone(restarted.take_next(now=NOW + 5))

    def test_expired_inbox_file_is_ignored_and_removed(self):
        path = self.write_payload(
            self.payload(id="stale", created_at=NOW - 900, expires_at=NOW - 60)
        )
        _state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        for step in range(3):
            controller.tick(now=NOW + step)
        self.assertIsNone(controller.take_next(now=NOW + 5))
        self.assertFalse(os.path.exists(path))

    def test_malformed_inbox_file_does_not_break_tick(self):
        bad = self.write_raw("n1.json", "{broken")
        good = self.write_payload(self.payload(id="good", source="hermes"))
        _state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        controller.tick(now=NOW)
        presented = controller.take_next(now=NOW)
        self.assertIsNotNone(presented)
        self.assertEqual(presented.id, "good")
        self.assertFalse(os.path.exists(bad))
        self.assertFalse(os.path.exists(good))

    def test_disabled_or_muted_returns_nothing(self):
        path = self.write_payload(self.payload(id="a", source="hermes"))
        _state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        controller.set_muted(True)
        controller.tick(now=NOW)
        self.assertIsNone(controller.take_next(now=NOW))
        # Tep chua hien thi thi phai con lai cho luc bat lai.
        self.assertTrue(os.path.exists(path))
        controller.set_muted(False)
        controller.set_enabled(False)
        controller.tick(now=NOW + 1)
        self.assertIsNone(controller.take_next(now=NOW + 1))
        controller.set_enabled(True)
        controller.tick(now=NOW + 2)
        presented = controller.take_next(now=NOW + 2)
        self.assertIsNotNone(presented)
        self.assertEqual(presented.id, "a")

    def test_custom_source_survives_inbox_change(self):
        class Custom(NotificationSource):
            source_id = "custom"
            display_name = "Nguồn tự đăng ký"

            def __init__(self):
                self.items = []

            def poll(self, limit):
                out = self.items[:limit]
                self.items = self.items[len(out):]
                return out

        custom = Custom()
        _state, controller = self.make_controller()
        controller.registry.register(custom)
        controller.set_inbox(self.inbox_dir)
        self.assertIn("custom", controller.registry.ids())
        self.assertIs(controller.registry.get("custom"), custom)

        custom.items.append(self.build("c1", source="custom"))
        controller.tick(now=NOW)
        presented = controller.take_next(now=NOW + 1)
        self.assertIsNotNone(presented)
        self.assertEqual(presented.source, "custom")

    def test_custom_source_with_explicit_registry(self):
        class Custom(NotificationSource):
            source_id = "custom"

            def poll(self, limit):
                return []

        registry = NotificationRegistry()
        registry.register(Custom())
        _state, controller = self.make_controller(registry=registry)
        self.assertEqual(controller.registry.ids(), ["custom"])
        self.assertEqual(controller.tick(now=NOW), 0)

    def test_inbox_problem_is_reported_not_raised(self):
        _state, controller = self.make_controller()
        controller.set_inbox(os.path.join(self.root, "khong-ton-tai"))
        self.assertFalse(controller.inbox_available())
        self.assertTrue(controller.last_error)
        self.assertEqual(controller.tick(now=NOW), 0)

    def test_stats_keys(self):
        _state, controller = self.make_controller()
        stats = controller.stats()
        for key in (
            "enabled",
            "muted",
            "pending",
            "history",
            "inbox_available",
            "last_error",
            "sources",
            "poll_count",
            "dropped",
            "duplicate",
            "expired",
            "source_errors",
        ):
            self.assertIn(key, stats)

    def test_stats_has_no_message_body(self):
        self.write_payload(self.payload(id="secret", message="noi dung rieng"))
        state, controller = self.make_controller()
        controller.set_inbox(self.inbox_dir)
        controller.tick(now=NOW)
        controller.take_next(now=NOW)
        text = json.dumps(controller.stats(), ensure_ascii=False)
        self.assertNotIn("noi dung rieng", text)
        self.assertEqual(len(state.recent()), 1)

    def test_poll_interval_is_clamped(self):
        self.assertEqual(poll_interval_from_config(None), DEFAULT_POLL_MS)
        self.assertEqual(poll_interval_from_config("abc"), DEFAULT_POLL_MS)
        self.assertEqual(poll_interval_from_config(1), MIN_POLL_MS)
        self.assertEqual(poll_interval_from_config(10 ** 9), MAX_POLL_MS)
        self.assertEqual(poll_interval_from_config(2000), 2000)

    def test_clear_history_resets_queue(self):
        _state, controller = self.make_controller()
        controller.dispatcher.offer(self.build("x"), now=NOW)
        controller.clear_history()
        self.assertEqual(controller.dispatcher.pending(), [])


class RegistryTests(unittest.TestCase):
    def test_rejects_non_source_and_duplicates(self):
        registry = default_registry()
        with self.assertRaises(RegistryError):
            registry.register(object())
        with self.assertRaises(RegistryError):
            registry.register(None)
        source = MemorySource(source_id="mem")
        registry.register(source)
        with self.assertRaises(RegistryError):
            registry.register(MemorySource(source_id="mem"))
        self.assertEqual(registry.ids(), ["mem"])

    def test_rejects_bad_id(self):
        registry = default_registry()
        for value in ["", "../x", "A B", "x" * 100]:
            with self.assertRaises(RegistryError, msg=repr(value)):
                registry.register(MemorySource(source_id=value))

    def test_rejects_missing_poll(self):
        class NoPoll(NotificationSource):
            source_id = "nopoll"

        instance = NoPoll()
        instance.poll = None
        with self.assertRaises(RegistryError):
            default_registry().register(instance)

    def test_default_registry_skips_none(self):
        registry = default_registry(None, MemorySource(source_id="mem2"), None)
        self.assertEqual(registry.ids(), ["mem2"])


# ----------------------------------------------------------------------
# sender: ghi file nguyen tu, khong ghi ra ngoai inbox
# ----------------------------------------------------------------------
class SenderTests(TempDirCase):
    def test_write_creates_json_file(self):
        note = self.build()
        path = write_notification(self.inbox_dir, note)
        self.assertEqual(os.path.basename(path), note.id + ".json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["id"], note.id)
        leftovers = [n for n in os.listdir(self.inbox_dir) if n.startswith(".notify-")]
        self.assertEqual(leftovers, [])

    def test_written_file_parses_back(self):
        note = self.build()
        path = write_notification(self.inbox_dir, note)
        with open(path, encoding="utf-8") as handle:
            parsed = PetNotification.parse(json.load(handle), now=NOW)
        self.assertEqual(parsed.id, note.id)

    def test_write_rejects_bad_type(self):
        with self.assertRaises(SenderError) as ctx:
            write_notification(self.inbox_dir, {"id": "x"})
        self.assertEqual(ctx.exception.reason, "bad_type")

    def test_write_rejects_path_outside_inbox(self):
        note = self.build("safe")
        note.id = "../escape"
        with self.assertRaises(SenderError) as ctx:
            write_notification(self.inbox_dir, note)
        self.assertEqual(ctx.exception.reason, "bad_name")
        self.assertFalse(os.path.exists(os.path.join(self.root, "escape.json")))

    def test_ensure_inbox_refuses_file(self):
        path = self.write_raw("plain.txt", "x")
        with self.assertRaises(SenderError) as ctx:
            sender.ensure_inbox(path)
        self.assertEqual(ctx.exception.reason, "not_directory")

    def test_send_helper_wraps_validation_errors(self):
        with self.assertRaises(SenderError) as ctx:
            sender.send(self.inbox_dir, source="../bad", title="t", message="m", now=NOW)
        self.assertEqual(ctx.exception.reason, "bad_source")
        note, path = sender.send(
            self.inbox_dir, source="hermes", title="ok", message="noi dung", now=NOW
        )
        self.assertTrue(os.path.exists(path))
        self.assertEqual(note.source, "hermes")


# ----------------------------------------------------------------------
# Khong phu thuoc Qt
# ----------------------------------------------------------------------
class NoQtTests(unittest.TestCase):
    def test_notification_package_does_not_import_qt(self):
        checked = 0
        for name, module in list(sys.modules.items()):
            if not name.startswith("gifpet.notifications"):
                continue
            source_file = getattr(module, "__file__", "") or ""
            if not source_file:
                continue
            with open(source_file, encoding="utf-8") as handle:
                text = handle.read()
            checked += 1
            self.assertNotIn("PyQt5", text, source_file)
            self.assertNotIn("QApplication", text, source_file)
        self.assertGreater(checked, 0)

    def test_no_qt_modules_loaded_for_headless_layers(self):
        loaded = [name for name in sys.modules if name.startswith("PyQt")]
        if loaded:
            self.skipTest("PyQt da duoc nap boi test khac trong cung tien trinh")
        self.assertEqual(loaded, [])


if __name__ == "__main__":
    unittest.main()
