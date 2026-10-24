"""Test cong cu dong lenh ``tools/notify_pet.py``.

Test chay tien trinh that (subprocess) voi ``APPDATA``/``XDG_CONFIG_HOME`` tam
nen khong bao gio doc hay ghi cau hinh that. Khong co mang, khong co PyQt: cong
cu phai dung duoc tren may khong cai PyQt va khong duoc nap PyQt khi chay.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO_ROOT, "tools", "notify_pet.py")

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_WRITE_FAILED = 3


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gifpet-notif-cli-")
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.inbox_dir = os.path.join(self.root, "inbox")
        os.makedirs(self.inbox_dir)
        self.config_dir = os.path.join(self.root, "config")
        os.makedirs(self.config_dir)
        self.env = dict(os.environ)
        # Co lap cau hinh: khong dung file that cua nguoi dung.
        self.env["APPDATA"] = self.config_dir
        self.env["XDG_CONFIG_HOME"] = self.config_dir
        self.env["XDG_DATA_HOME"] = os.path.join(self.root, "data")
        self.env["HOME"] = os.path.join(self.root, "home")
        self.env.pop("PYTHONPATH", None)
        # Khong cho PyQt lot vao tien trinh con qua sitecustomize la.
        self.env["QT_QPA_PLATFORM"] = "offscreen"

    def run_tool(self, *args, expect=None):
        command = [sys.executable, TOOL] + [str(a) for a in args]
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if expect is not None:
            self.assertEqual(
                proc.returncode,
                expect,
                "ma thoat khac ky vong\nstdout: %s\nstderr: %s"
                % (proc.stdout, proc.stderr),
            )
        return proc

    def inbox_files(self):
        return sorted(os.listdir(self.inbox_dir))

    def only_notification(self):
        files = [n for n in self.inbox_files() if not n.startswith(".")]
        self.assertEqual(len(files), 1, files)
        with open(os.path.join(self.inbox_dir, files[0]), encoding="utf-8") as handle:
            return files[0], json.load(handle)


class SuccessTests(CliCase):
    def test_writes_one_json_file_and_returns_zero(self):
        proc = self.run_tool(
            "--inbox",
            self.inbox_dir,
            "--source",
            "hermes",
            "--title",
            "Việc chạy nền",
            "--message",
            "Tác vụ đã xong",
            "--severity",
            "success",
            expect=EXIT_OK,
        )
        name, data = self.only_notification()
        self.assertTrue(name.endswith(".json"), name)
        self.assertEqual(data["source"], "hermes")
        self.assertEqual(data["severity"], "success")
        self.assertEqual(data["title"], "Việc chạy nền")
        self.assertEqual(data["message"], "Tác vụ đã xong")
        self.assertEqual(data["version"], 1)
        self.assertGreater(data["expires_at"], data["created_at"])
        self.assertIn(name, proc.stdout)
        # Khong de lai tep tam.
        leftovers = [n for n in self.inbox_files() if n.startswith(".notify-")]
        self.assertEqual(leftovers, [])

    def test_message_only_is_allowed(self):
        self.run_tool(
            "--inbox", self.inbox_dir, "--source", "build", "--message", "chi co noi dung",
            expect=EXIT_OK,
        )
        _name, data = self.only_notification()
        self.assertEqual(data["message"], "chi co noi dung")

    def test_ttl_option_sets_expiry(self):
        self.run_tool(
            "--inbox", self.inbox_dir, "--source", "build", "--title", "t", "--ttl", 5,
            expect=EXIT_OK,
        )
        _name, data = self.only_notification()
        self.assertEqual(data["expires_at"] - data["created_at"], 5)

    def test_creates_missing_inbox_directory(self):
        target = os.path.join(self.root, "moi", "inbox")
        self.run_tool(
            "--inbox", target, "--source", "build", "--title", "tao thu muc",
            expect=EXIT_OK,
        )
        self.assertTrue(os.path.isdir(target))
        self.assertEqual(len(os.listdir(target)), 1)

    def test_payload_is_readable_by_pet_pipeline(self):
        self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes", "--title", "doc lai",
            expect=EXIT_OK,
        )
        _name, data = self.only_notification()
        # Doc lai bang parser thuan Python (khong nap PyQt trong test nay).
        script = (
            "import json, sys;"
            "sys.path.insert(0, %r);"
            "from gifpet.notifications.models import PetNotification;"
            "raw = json.loads(open(%r, encoding='utf-8').read());"
            "note = PetNotification.parse(raw);"
            "print('NOTE=' + note.source + '|' + note.title)"
        ) % (REPO_ROOT, os.path.join(self.inbox_dir, _name))
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOTE=hermes|doc lai", proc.stdout)

    def test_output_has_no_action_capable_content(self):
        proc = self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes",
            "--title", "https://example.com", "--message", "rm -rf /",
            expect=EXIT_OK,
        )
        _name, data = self.only_notification()
        # Noi dung nguy hiem van chi la chu duoc pet hien thi nguyen van.
        self.assertEqual(data["title"], "https://example.com")
        self.assertEqual(data["message"], "rm -rf /")
        # Ghi ra stdout la thu muc hop thu nguoi dung chi dinh, khong phai
        # duong dan noi bo cua repo.
        self.assertNotIn(REPO_ROOT, proc.stdout)


class DefaultInboxTests(CliCase):
    """Khong truyen --inbox: producer phai ghi vao inbox da cau hinh."""

    def write_config(self, inbox_path):
        config_dir = os.path.join(self.config_dir, "GifAnimation")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {"notifications_inbox": inbox_path, "notifications_enabled": True},
                handle,
            )
        return path

    def test_default_inbox_uses_configured_inbox(self):
        configured = os.path.join(self.root, "hop-thu-da-cau-hinh")
        os.makedirs(configured)
        self.write_config(configured)
        proc = self.run_tool(
            "--source", "hermes", "--title", "dinh tuyen", "--message", "noi dung"
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        written = sorted(os.listdir(configured))
        self.assertEqual(len(written), 1, written)
        self.assertTrue(written[0].endswith(".json"), written)
        with open(os.path.join(configured, written[0]), encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["title"], "dinh tuyen")
        self.assertEqual(data["source"], "hermes")
        self.assertIn(written[0], proc.stdout)
        # Khong roi vao inbox mac dinh khac.
        fallback = os.path.join(self.config_dir, "GifAnimation", "notifications-inbox")
        self.assertFalse(
            os.path.isdir(fallback) and os.listdir(fallback),
            "producer bo qua notifications_inbox da cau hinh",
        )

    def test_default_inbox_falls_back_to_config_dir(self):
        proc = self.run_tool(
            "--source", "hermes", "--title", "mac dinh", "--message", "noi dung"
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        fallback = os.path.join(self.config_dir, "GifAnimation", "notifications-inbox")
        self.assertTrue(os.path.isdir(fallback), proc.stdout)
        self.assertEqual(len(os.listdir(fallback)), 1)


class BadInputTests(CliCase):
    def assert_no_file_written(self):
        self.assertEqual(
            [n for n in self.inbox_files() if n.endswith(".json")], []
        )

    def test_missing_source_is_bad_input(self):
        proc = self.run_tool("--inbox", self.inbox_dir, "--title", "t")
        self.assertEqual(proc.returncode, EXIT_BAD_INPUT)
        self.assert_no_file_written()

    def test_empty_title_and_message_is_bad_input(self):
        for args in (
            ("--title", "   "),
            ("--message", "   "),
            ("--title", "", "--message", "\t"),
        ):
            proc = self.run_tool("--inbox", self.inbox_dir, "--source", "hermes", *args)
            self.assertEqual(proc.returncode, EXIT_BAD_INPUT, args)
            self.assertTrue(proc.stderr.strip(), args)
        self.assert_no_file_written()

    def test_bad_source_is_bad_input(self):
        for value in ("Hermes", "../x", "a b", "nguon" * 20):
            proc = self.run_tool(
                "--inbox", self.inbox_dir, "--source", value, "--title", "t"
            )
            self.assertEqual(proc.returncode, EXIT_BAD_INPUT, value)
        self.assert_no_file_written()

    def test_bad_severity_is_bad_input(self):
        proc = self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes", "--title", "t",
            "--severity", "critical",
        )
        self.assertEqual(proc.returncode, EXIT_BAD_INPUT)
        self.assert_no_file_written()

    def test_non_numeric_ttl_is_bad_input(self):
        proc = self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes", "--title", "t",
            "--ttl", "abc",
        )
        self.assertEqual(proc.returncode, EXIT_BAD_INPUT)
        self.assert_no_file_written()

    def test_absurd_ttl_is_rejected(self):
        proc = self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes", "--title", "t",
            "--ttl", 10 ** 9,
        )
        self.assertEqual(proc.returncode, EXIT_BAD_INPUT)
        self.assert_no_file_written()

    def test_inbox_pointing_at_file_is_write_failure(self):
        path = os.path.join(self.root, "tep.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        proc = self.run_tool(
            "--inbox", path, "--source", "hermes", "--title", "t",
            expect=EXIT_WRITE_FAILED,
        )
        self.assertIn("Lỗi", proc.stderr)
        self.assertEqual([n for n in os.listdir(self.root) if n.endswith(".json")], [])

    def test_error_message_does_not_leak_traceback(self):
        proc = self.run_tool("--inbox", self.inbox_dir, "--source", "Hermes", "--title", "t")
        self.assertNotIn("Traceback", proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertNotIn("File \"", combined)


class IsolationTests(CliCase):
    def test_tool_does_not_import_pyqt(self):
        """Cong cu phai chay duoc khi may khong co PyQt."""
        script = (
            "import runpy, sys;"
            "sys.argv = ['notify_pet.py', '--inbox', %r, '--source', 'hermes',"
            " '--title', 't'];"
            "\ntry:\n"
            "    runpy.run_path(%r, run_name='__main__')\n"
            "except SystemExit as exc:\n"
            "    code = exc.code\n"
            "else:\n"
            "    code = 0\n"
            "loaded = sorted(n for n in sys.modules if n.startswith('PyQt'))\n"
            "print('QT_MODULES=' + ','.join(loaded))\n"
            "print('EXIT=' + str(code))\n"
        ) % (self.inbox_dir, TOOL)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EXIT=0", proc.stdout)
        self.assertEqual(len(self.inbox_files()), 1)

    def test_default_inbox_uses_isolated_config_not_real_one(self):
        """Khong truyen --inbox: thu muc mac dinh phai nam trong vung tam."""
        proc = self.run_tool("--source", "hermes", "--title", "mac dinh", expect=EXIT_OK)
        self.assertIn("hộp thư", proc.stdout)
        # Khong duoc ghi vao thu muc cau hinh that cua nguoi dung.
        real_home = os.path.expanduser("~")
        outside = [
            line.strip()
            for line in proc.stdout.splitlines()
            if line.strip().startswith(real_home) and self.config_dir not in line
        ]
        self.assertEqual(outside, [], outside)

    def test_does_not_touch_config_json(self):
        self.run_tool(
            "--inbox", self.inbox_dir, "--source", "hermes", "--title", "t", expect=EXIT_OK
        )
        config_json = os.path.join(self.config_dir, "GifAnimation", "config.json")
        self.assertFalse(os.path.exists(config_json))

    def test_no_network_modules_imported(self):
        script = (
            "import sys, subprocess;"
            "proc = subprocess.run([sys.executable, %r, '--inbox', %r,"
            " '--source', 'hermes', '--title', 't'], capture_output=True);\n"
            "code = proc.returncode\n"
            "bad = [n for n in ('socket', 'ssl', 'http.client', 'urllib.request',"
            " 'ftplib', 'smtplib') if n in sys.modules]\n"
            "print('NET_MODULES=' + ','.join(bad))\n"
            "print('EXIT=' + str(code))\n"
        ) % (TOOL, self.inbox_dir)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NET_MODULES=\n", proc.stdout + "\n", proc.stdout)
        self.assertIn("EXIT=0", proc.stdout)


if __name__ == "__main__":
    unittest.main()
