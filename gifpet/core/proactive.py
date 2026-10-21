"""Gom su kien de pet tu noi, co gioi han tan suat.

Xem ``docs/SECURITY.md`` muc 4.3. Co ``ai_proactive`` trong config nhung truoc
day khong co gi doc no - bat len cung khong lam gi. File nay lam cho no co tac
dung, dung theo thiet ke:

- Gom su kien trong cua so thoi gian (mac dinh 60 giay) thay vi goi model cho
  tung su kien. Nguoi dung di chuot qua pet 20 lan khong phai 20 luot goi.
- Tran rieng thap hon nhieu so voi tran chung (mac dinh 10 luot/ngay).
- Khong chay khi dang trong gio tap trung (Pomodoro focus).
- Su kien pet tu di / roi / ngu khong bao gio vao hang doi.

Module nay thuan tuy logic, khong phu thuoc Qt, nen test duoc de dang.
"""

import time

# Su kien duoc phep gom de pet tu noi. Di lai/roi/ngu/click KHONG co o day.
PROACTIVE_KINDS = ("long_idle", "returned", "pomodoro_break")

# Cua so gom: chi goi model toi da mot lan trong khoang nay.
BATCH_WINDOW_SECONDS = 60.0

# Tran rieng cho pet tu noi, thap hon ai_daily_limit.
DEFAULT_PROACTIVE_LIMIT = 10


class ProactiveBatcher:
    """Gom su kien va quyet dinh khi nao duoc goi model.

    Trach nhiem cua lop nay chi la "co nen goi bay gio khong"; viec goi model
    va kiem quota chung van do ``Brain`` lo.
    """

    def __init__(self, config, now_func=None):
        self.config = config
        self.now_func = now_func or time.time
        self._pending = []          # su kien dang cho trong cua so
        self._window_start = None   # moc bat dau cua so hien tai
        self._last_call = None      # lan cuoi thuc su goi model
        self._used_today = 0
        self._used_date = ""

    # ------------------------------------------------------------------
    def enabled(self):
        return bool(self.config.get("ai_enabled")) and bool(
            self.config.get("ai_proactive")
        )

    def limit(self):
        try:
            return max(0, int(self.config.get(
                "ai_proactive_limit", DEFAULT_PROACTIVE_LIMIT
            )))
        except (TypeError, ValueError):
            return DEFAULT_PROACTIVE_LIMIT

    def remaining(self):
        return max(0, self.limit() - self._used_today)

    # ------------------------------------------------------------------
    def add(self, kind, detail=""):
        """Ghi nhan mot su kien. Tra ve True neu su kien duoc chap nhan.

        Chi nhap su kien thuoc ``PROACTIVE_KINDS``. Pet tu di, roi, ngu khong
        bao gio vao day.
        """
        if not self.enabled():
            return False
        if kind not in PROACTIVE_KINDS:
            return False

        now = self.now_func()
        day = time.strftime("%Y-%m-%d", time.localtime(now))
        if day != self._used_date:
            self._used_date = day
            self._used_today = 0

        if self._window_start is None:
            self._window_start = now
        self._pending.append({"kind": kind, "detail": detail, "at": now})
        return True

    def should_fire(self, focusing=False):
        """Kiem tra co nen goi model ngay bay gio khong.

        Tra ve ``(co_nen, ly_do)``. Ly do: ``"ok"``, ``"disabled"``,
        ``"focus"``, ``"empty"``, ``"too_soon"``, ``"exhausted"``.
        """
        if not self.enabled():
            return False, "disabled"
        if focusing:
            # Dang trong gio tap trung: khong lam phien.
            return False, "focus"
        if not self._pending:
            return False, "empty"

        now = self.now_func()
        # Chua du mot cua so: tiep tuc gom.
        if now - (self._window_start or now) < BATCH_WINDOW_SECONDS:
            return False, "too_soon"
        if self._last_call is not None and now - self._last_call < BATCH_WINDOW_SECONDS:
            return False, "too_soon"
        if self.remaining() <= 0:
            return False, "exhausted"
        return True, "ok"

    def take(self):
        """Lay su kien da gom va danh dau da goi model.

        Goi sau khi ``should_fire`` tra ve True.
        """
        events = list(self._pending)
        self._pending.clear()
        self._window_start = None
        self._last_call = self.now_func()
        self._used_today += 1
        return events

    def pending_count(self):
        return len(self._pending)

    def reset(self):
        """Xoa trang thai trong bo nho. Dung trong test."""
        self._pending.clear()
        self._window_start = None
        self._last_call = None
        self._used_today = 0
        self._used_date = ""

    # ------------------------------------------------------------------
    def build_content(self, events):
        """Dong goi cac su kien thanh du lieu cho model.

        Van la DU LIEU, khong phai menh lenh: ``brain.build_user_content`` se
        dat no vao truong ``content`` cua JSON.
        """
        if not events:
            return ""
        parts = []
        for event in events:
            detail = event.get("detail")
            parts.append(f"{event['kind']}: {detail}" if detail else event["kind"])
        return "; ".join(parts)
