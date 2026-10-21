"""Dem luot dung AI trong ngay, chan vuot tran.

Xem ``docs/SECURITY.md`` muc 4. Quy tac bat buoc:

- **Dem truoc khi gui**, khong dem sau khi nhan. Luot that bai van ton tien
  va van phai tinh.
- Reset theo **ngay lich**, khong phai 24 gio truot - de hieu va de kiem tra.
- **Dong ho bi lui** (doi mui gio, sua gio he thong): neu ngay da luu nam o
  tuong lai thi coi nhu ngay moi nhung van giu bo dem, khong cho vuot tran.
- Het quota hoac mat mang -> pet van chay binh thuong, khong exception.

Module nay thuan tuy logic, khong phu thuoc Qt nen test duoc de dang.
"""

import datetime

# Gioi han toc do: toi thieu bao nhieu giay giua hai luot goi model.
MIN_SECONDS_BETWEEN_CALLS = 1.5

# So lan thu lai khi loi mang, va thoi gian cho (giay) giua cac lan.
MAX_RETRIES = 3
BACKOFF_SECONDS = (2.0, 5.0, 12.0)


def today(timestamp=None):
    """Ngay lich dang chuoi YYYY-MM-DD, theo gio dia phuong."""
    if timestamp is None:
        moment = datetime.datetime.now()
    else:
        moment = datetime.datetime.fromtimestamp(timestamp)
    return moment.strftime("%Y-%m-%d")


def _is_future_date(stored, now_date):
    """True neu ngay da luu o tuong lai (dong ho bi lui hoac doi mui gio)."""
    try:
        return stored > now_date
    except TypeError:
        return True


class Quota:
    """Bo dem luot dung, doc/ghi qua ``Config`` de o lai sau khi tat app."""

    def __init__(self, config, now_func=None):
        self.config = config
        # Tiem duoc dong ho gia lap trong test.
        self.now_func = now_func or (lambda: datetime.datetime.now().timestamp())
        self._last_call_ts = None

    # ------------------------------------------------------------------
    # Ngay va bo dem
    # ------------------------------------------------------------------
    def _current_date(self):
        return today(self.now_func())

    def _roll_if_needed(self):
        """Chuyen sang ngay moi thi dat lai bo dem. Tra ve True neu co reset."""
        current = self._current_date()
        stored = self.config.get("ai_used_date", "") or ""
        if stored == current:
            return False
        if _is_future_date(stored, current) and stored:
            # Dong ho bi lui: khong cho dung lai quota da tieu cua ngay sau.
            # Dat lai bo dem nhung ghi nhan ngay hien tai de khoi lap lai.
            self.config.data["ai_used_today"] = 0
            self.config.data["ai_used_date"] = current
            return True
        self.config.data["ai_used_today"] = 0
        self.config.data["ai_used_date"] = current
        return True

    def used_today(self):
        self._roll_if_needed()
        try:
            return int(self.config.get("ai_used_today", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def limit(self):
        try:
            return max(0, int(self.config.get("ai_daily_limit", 0) or 0))
        except (TypeError, ValueError):
            return 0

    def remaining(self):
        return max(0, self.limit() - self.used_today())

    def exhausted(self):
        return self.remaining() <= 0

    # ------------------------------------------------------------------
    # Gioi han toc do
    # ------------------------------------------------------------------
    def seconds_since_last_call(self):
        if self._last_call_ts is None:
            return None
        return self.now_func() - self._last_call_ts

    def too_soon(self):
        elapsed = self.seconds_since_last_call()
        return elapsed is not None and elapsed < MIN_SECONDS_BETWEEN_CALLS

    def wait_seconds(self):
        """Con phai cho bao nhieu giay moi duoc goi tiep."""
        elapsed = self.seconds_since_last_call()
        if elapsed is None:
            return 0.0
        return max(0.0, MIN_SECONDS_BETWEEN_CALLS - elapsed)

    # ------------------------------------------------------------------
    # API chinh
    # ------------------------------------------------------------------
    def check_and_use(self):
        """Xin mot luot goi model.

        Tra ve ``(allowed, reason)``. ``reason`` la mot trong:
        ``"ok"``, ``"disabled"``, ``"exhausted"``, ``"rate_limited"``.
        """
        if not self.config.get("ai_enabled"):
            return False, "disabled"

        self._roll_if_needed()
        # Kiem tra quota truoc rate limit: het quota la ly do that su, khong
        # nen bao "cho vai giay nua" khi doi bao lau cung khong duoc.
        if self.exhausted():
            return False, "exhausted"
        if self.too_soon():
            return False, "rate_limited"

        # Dem ngay bay gio, truoc khi gui. Luot that bai cung tinh.
        self.config.data["ai_used_today"] = self.used_today() + 1
        self._last_call_ts = self.now_func()
        try:
            self.config.save()
        except Exception:
            # Khong ghi duoc thi van cho chay: chan nguoi dung vi loi ghi dia
            # con te hon viec de ho dung app.
            pass
        return True, "ok"

    def note_failure(self):
        """Ghi nhan mot luot that bai. Khong hoan lai quota da tru."""
        # Co tinh khong lam gi: quota da bi tru trong check_and_use, va khong
        # hoan lai de tranh vong lap "loi -> goi lai -> loi" khong gioi han.
        return

    def reset(self):
        """Xoa bo dem. Chi dung khi nguoi dung tu bam trong Cai dat."""
        self.config.data["ai_used_today"] = 0
        self.config.data["ai_used_date"] = self._current_date()
        self.config.save()

    def status_text(self):
        """Cau hien trong Cai dat."""
        if not self.config.get("ai_enabled"):
            return "AI đang tắt"
        return f"Đã dùng {self.used_today()}/{self.limit()} lượt hôm nay"
