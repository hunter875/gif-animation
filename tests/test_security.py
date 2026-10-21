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
    """Khong goi mang ngoai ``gifpet/ai/provider.py``.

    Giai doan 1-3 khong co network. Giai doan 4 them dung mot cho goi mang:
    provider.py. Test nay khoa lai dieu do - bat ky file nao khac them network
    la phai sua test co chu dich.
    """

    # File duoc phep cham toi thu vien mang.
    NETWORK_ALLOWED = (
        os.path.join("gifpet", "ai", "provider.py"),
        # actions.py chi PHAN TICH url (urlsplit), khong ket noi mang.
        os.path.join("gifpet", "ai", "actions.py"),
    )

    # Module mang thuc su mo ket noi. urllib.parse chi xu ly chuoi.
    NETWORK_MODULES = (
        "requests", "urllib.request", "urllib.error", "http.client", "socket",
        "httpx", "aiohttp", "ftplib", "smtplib", "telnetlib",
    )

    def test_chi_provider_mo_ket_noi_mang(self):
        found = []
        for path in source_files():
            rel = os.path.relpath(path, ROOT)
            if rel in self.NETWORK_ALLOWED:
                continue
            text = read(path)
            for module in self.NETWORK_MODULES:
                pattern = rf"^\s*(?:import|from)\s+{re.escape(module)}\b"
                if re.search(pattern, text, re.MULTILINE):
                    found.append(f"{rel}: {module}")
        self.assertEqual(found, [], f"mo ket noi mang ngoai provider.py: {found}")

    def test_provider_co_import_urllib(self):
        """Chot chan: neu provider bi doi sang thu vien khac, test bao ngay."""
        text = read(os.path.join(ROOT, self.NETWORK_ALLOWED[0]))
        self.assertIn("urllib.request", text)

    def test_url_cung_chi_nam_trong_provider(self):
        """Dia chi http(s) viet cung chi duoc o provider.py.

        Ngoai le: chuoi huong dan trong prompt (brain.py) la van ban, khong
        phai dia chi that; kiem tra theo dạng "http(s)://host/path" cu the.
        """
        found = []
        for path in source_files():
            rel = os.path.relpath(path, ROOT)
            if rel == self.NETWORK_ALLOWED[0]:
                continue
            for line_no, line in enumerate(read(path).splitlines(), 1):
                # Bo qua dong trong docstring/prompt huong dan.
                if '"""' in line or "params" in line:
                    continue
                if re.search(r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", line):
                    found.append(f"{rel}:{line_no}")
        self.assertEqual(found, [], f"URL cung ngoai provider.py: {found}")

    def test_ta_tat_ai_thi_khong_co_request_nao(self):
        """Duong chay mac dinh (ai_enabled=False) khong cham provider."""
        from gifpet.ai.brain import Brain
        from gifpet.core.config import Config

        config = Config()
        config.data["ai_enabled"] = False
        brain = Brain(config)
        # Neu provider() bi goi, no se tra ve None vi khong co key.
        self.assertFalse(brain.enabled())
        self.assertEqual(brain.ask("chat", "x").error, "disabled")


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

    # File duy nhat duoc phep goi subprocess: doc trang thai fullscreen.
    SUBPROCESS_ALLOWED = os.path.join("gifpet", "ui", "window_skin.py")

    def test_chi_window_skin_goi_subprocess(self):
        """Chi duoc dung subprocess o dung mot cho: doc trang thai fullscreen."""
        hits = []
        for path in source_files():
            for line_no, line in enumerate(read(path).splitlines(), 1):
                for pattern in self.DANGEROUS:
                    if re.search(pattern, line):
                        hits.append((os.path.relpath(path, ROOT), line_no, line.strip()))
        unexpected = [h for h in hits if h[0] != self.SUBPROCESS_ALLOWED]
        self.assertEqual(unexpected, [], f"goi lenh ngoai du kien: {unexpected}")

    def test_chi_mot_loi_goi_subprocess_trong_window_skin(self):
        """Trong window_skin chi co dung mot loi goi subprocess.run."""
        text = read(os.path.join(ROOT, self.SUBPROCESS_ALLOWED))
        self.assertEqual(
            text.count("subprocess.run("), 1,
            "window_skin chi duoc co mot loi goi subprocess.run",
        )

    def test_xprop_dung_danh_sach_tham_so_co_dinh(self):
        """xprop phai nhan list, khong nhan chuoi qua shell."""
        text = read(os.path.join(ROOT, self.SUBPROCESS_ALLOWED))
        self.assertIn('["xprop"] + args', text,
                      "xprop phai goi bang list, khong qua shell=True")

    def test_khong_co_shell_true_o_bat_ky_dau(self):
        """shell=True cho phep chen lenh - khong duoc xuat hien trong ca package."""
        offenders = []
        for path in source_files():
            text = read(path)
            if "shell=True" in text:
                offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [], f"co shell=True: {offenders}")


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
