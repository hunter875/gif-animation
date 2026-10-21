"""Khoa cac rang buoc bao mat da chot trong docs/SECURITY.md.

Muc dich: neu sau nay ai do them mot lenh shell, mot lenh goi mang, hay nhet
API key vao config, test nay phai do. Khong kiem tra "AI co an toan khong"
(vi chua co AI), ma kiem tra nhung dieu kien nen phai giu.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "gifpet")


def source_files():
    """Tat ca file .py trong package, tru __pycache__."""
    for base, _dirs, files in os.walk(PACKAGE):
        if "__pycache__" in base:
            continue
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestNoNetwork(unittest.TestCase):
    """App chua co AI thi khong duoc co bat ky lenh goi mang nao."""

    # Thu vien mang pho bien. Them vao la phai sua test nay co chu dich.
    NETWORK_MODULES = (
        "requests", "urllib", "http.client", "socket", "httpx",
        "aiohttp", "ftplib", "smtplib", "telnetlib",
    )

    def test_khong_import_thu_vien_mang(self):
        found = []
        for path in source_files():
            text = read(path)
            for module in self.NETWORK_MODULES:
                # Bat ca "import X" va "from X import ..."
                pattern = rf"^\s*(?:import|from)\s+{re.escape(module)}\b"
                if re.search(pattern, text, re.MULTILINE):
                    found.append(f"{os.path.relpath(path, ROOT)}: {module}")
        self.assertEqual(found, [], f"phat hien goi mang: {found}")

    def test_khong_co_url_cung_trong_code(self):
        """Khong co dia chi http(s) viet cung trong code."""
        found = []
        for path in source_files():
            for line_no, line in enumerate(read(path).splitlines(), 1):
                if re.search(r"https?://[a-zA-Z0-9.-]+", line):
                    found.append(f"{os.path.relpath(path, ROOT)}:{line_no}")
        self.assertEqual(found, [], f"co URL cung trong code: {found}")


class TestNoArbitraryExecution(unittest.TestCase):
    """Khong chay lenh tuy y tu ket qua model hay tu du lieu ngoai."""

    DANGEROUS = (
        r"\bos\.system\s*\(",
        r"\bos\.popen\s*\(",
        r"\bos\.exec[lv]",
        r"\bsubprocess\.(?:call|run|Popen|check_output|check_call)\s*\(",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\b__import__\s*\(",
    )

    def test_chi_co_mot_cho_goi_subprocess(self):
        """Chi duoc dung subprocess o dung mot cho: doc trang thai fullscreen."""
        hits = []
        for path in source_files():
            for line_no, line in enumerate(read(path).splitlines(), 1):
                for pattern in self.DANGEROUS:
                    if re.search(pattern, line):
                        hits.append((os.path.relpath(path, ROOT), line_no, line.strip()))
        # Cho phep duy nhat: xprop trong pet_window.
        unexpected = [
            h for h in hits
            if not (h[0].endswith("pet_window.py") and "subprocess" in h[2])
        ]
        self.assertEqual(unexpected, [], f"goi lenh ngoai du kien: {unexpected}")

    def test_xprop_dung_danh_sach_tham_so_co_dinh(self):
        """xprop phai nhan list, khong nhan chuoi qua shell."""
        text = read(os.path.join(PACKAGE, "ui", "pet_window.py"))
        self.assertIn('["xprop"] + args', text,
                      "xprop phai goi bang list, khong qua shell=True")
        self.assertNotIn("shell=True", text, "khong duoc dung shell=True")


class TestSecretsIsolation(unittest.TestCase):
    """API key khong duoc nam trong config.json."""

    def test_config_khong_co_truong_chua_key(self):
        sys.path.insert(0, ROOT)
        from gifpet.core.config import DEFAULTS

        # Ten truong nao chua "key"/"token"/"secret" deu dang ngo.
        offenders = [
            name for name in DEFAULTS
            if re.search(r"api_?key|token|secret|password", name, re.IGNORECASE)
        ]
        self.assertEqual(
            offenders, [],
            f"config.json khong duoc chua bi mat, thay: {offenders}",
        )

    def test_config_ghi_ra_ngoai_repo(self):
        """Cau hinh phai o thu muc he dieu hanh, khong nam trong repo."""
        from gifpet.core.config import config_dir

        path = os.path.abspath(config_dir())
        repo = os.path.abspath(ROOT)
        self.assertFalse(
            path.startswith(repo + os.sep),
            f"cau hinh nam trong repo: {path}",
        )

    def test_config_file_quyen_chan_nguoi_khac_doc(self):
        """File cau hinh phai la 0600 sau khi ghi."""
        if os.name == "nt":
            self.skipTest("Windows dung ACL, khong co bit quyen POSIX")

        from gifpet.core.config import Config

        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="gifpet-sec-")
        try:
            config = Config()
            config.save()
            mode = os.stat(config.path).st_mode & 0o777
            self.assertEqual(
                mode, 0o600,
                f"cau hinh phai 0600 (chi chu doc), dang {oct(mode)}",
            )
        finally:
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old


class TestAIDefaultsOff(unittest.TestCase):
    """AI tat mac dinh: nguoi dung phai tu bat."""

    def test_ai_tat_mac_dinh(self):
        from gifpet.core.config import DEFAULTS

        self.assertFalse(DEFAULTS["ai_enabled"])
        self.assertFalse(DEFAULTS["ai_proactive"])

    def test_co_bien_quota(self):
        """Duoc goi model phai co tran luot/ngay."""
        from gifpet.core.config import DEFAULTS

        for name in ("ai_daily_limit", "ai_used_today", "ai_used_date"):
            self.assertIn(name, DEFAULTS)
        self.assertGreater(DEFAULTS["ai_daily_limit"], 0)

    def test_voice_da_bo(self):
        """Giai doan 5 da bo khoi pham vi: khong con goi voice."""
        self.assertFalse(
            os.path.isdir(os.path.join(PACKAGE, "voice")),
            "thu muc voice le ra da bi xoa",
        )


class TestSecurityDoc(unittest.TestCase):
    """Tai lieu phai ton tai va de cap du bon chu de."""

    def setUp(self):
        self.doc = read(os.path.join(ROOT, "docs", "SECURITY.md")).lower()

    def test_co_tai_lieu(self):
        self.assertTrue(len(self.doc) > 2000, "SECURITY.md qua ngan")

    def test_de_cap_prompt_injection(self):
        self.assertIn("prompt injection", self.doc)

    def test_de_cap_api_key(self):
        self.assertIn("api key", self.doc)
        self.assertIn("secrets.json", self.doc)

    def test_de_cap_quota_va_chi_phi(self):
        for topic in ("quota", "chi ph", "rate limit"):
            self.assertIn(topic, self.doc)

    def test_co_checklist(self):
        self.assertIn("checklist", self.doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
