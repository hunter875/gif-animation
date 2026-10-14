"""Che do nhic tap trung / nghi (Pomodoro) - Giai doan 5 mo rong.

Vong lap:

    FOCUS  --(het gio)--> BREAK  --(het gio)--> FOCUS ...

Trong gio FOCUS pet dung yen (khong tu di) de khong lam phan tan.
Khi chuyen sang BREAK thi nhic: uong nuoc, thu gian mat, dung day.

Module nay thuan tuy logic, khong phu thuoc Qt. UI truyen ``now_ms`` vao nen
test co the gia lap thoi gian ma khong can ``sleep``.
"""

import random

# --- Pha ---
IDLE = "idle"        # chua bat
FOCUS = "focus"      # dang trong gio tap trung
BREAK = "break"      # dang trong gio nghi
PAUSED = "paused"    # nguoi dung tam dung dong ho

PHASES = (IDLE, FOCUS, BREAK, PAUSED)

# Cac loi nhic khi bat dau gio nghi.
BREAK_REMINDERS = (
    "Uống một cốc nước đi.",
    "Đứng dậy vươn vai vài giây.",
    "Nhìn ra xa 20 giây cho mắt nghỉ.",
    "Thư giãn cổ và vai.",
    "Hít thở sâu vài nhịp.",
    "Đi lại một vòng cho đỡ mỏi lưng.",
)

# Loi nhic khi quay lai tap trung.
FOCUS_REMINDERS = (
    "Quay lại tập trung nào.",
    "Hết giờ nghỉ, mình tiếp tục nhé.",
    "Sẵn sàng chưa? Tiếp tục thôi.",
)

# Loi nhic giua gio tap trung (nhic nhe, khong bat nghi).
FOCUS_CHECKINS = (
    "Vẫn ổn chứ? Ngồi thẳng lưng chút nhé.",
    "Đừng quên chớp mắt nhiều hơn.",
    "Sắp hết hiệp rồi, cố lên.",
)


class Pomodoro:
    """Dong ho tap trung / nghi.

    ``now_ms`` la dong ho don dieu tinh bang mili giay, giong ``Behavior``.
    """

    def __init__(self, config=None, rng=None):
        self.config = config
        self.rng = rng or random.Random()
        self.phase = IDLE
        self.phase_end_ms = 0
        self.remaining_when_paused_ms = 0
        self.completed_focus = 0
        self.last_reminder = ""
        # Lich su tin nhan de UI hien thi.
        self.history = []

    # ------------------------------------------------------------------
    # Cau hinh
    # ------------------------------------------------------------------
    def _get(self, key, default):
        if self.config is None:
            return default
        return self.config.get(key, default)

    @property
    def focus_ms(self):
        minutes = self._get("pomodoro_focus_minutes", 25)
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = 25
        return minutes * 60 * 1000

    @property
    def break_ms(self):
        minutes = self._get("pomodoro_break_minutes", 5)
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = 5
        return minutes * 60 * 1000

    @property
    def enabled(self):
        return bool(self._get("pomodoro_enabled", False))

    # ------------------------------------------------------------------
    # Dieu khien
    # ------------------------------------------------------------------
    def start(self, now_ms):
        """Bat dau hiep tap trung."""
        self.phase = FOCUS
        self.phase_end_ms = now_ms + self.focus_ms
        self.remaining_when_paused_ms = 0
        return self._emit("Bắt đầu tập trung. Mình canh giờ cho bạn nhé.")

    def stop(self):
        """Tat han che do."""
        self.phase = IDLE
        self.phase_end_ms = 0
        self.remaining_when_paused_ms = 0
        return self._emit("Đã tắt chế độ tập trung.")

    def pause(self, now_ms):
        """Tam dung dong ho, giu lai thoi gian con lai."""
        if self.phase not in (FOCUS, BREAK):
            return False
        self.remaining_when_paused_ms = max(0, self.phase_end_ms - now_ms)
        # Nho pha dang do de chay tiep ve dung cho.
        self._phase_before_pause = self.phase
        self.phase = PAUSED
        return True

    def resume(self, now_ms):
        """Chay tiep tu cho da tam dung, quay ve dung pha truoc do."""
        if self.phase != PAUSED:
            return False
        previous = getattr(self, "_phase_before_pause", FOCUS)
        if previous not in (FOCUS, BREAK):
            previous = FOCUS
        self.phase = previous
        self.phase_end_ms = now_ms + self.remaining_when_paused_ms
        return True

    def skip(self, now_ms):
        """Bo qua pha hien tai, chuyen ngay sang pha ke tiep."""
        if self.phase == FOCUS:
            return self._enter_break(now_ms)
        if self.phase in (BREAK, PAUSED):
            return self._enter_focus(now_ms)
        return False

    # ------------------------------------------------------------------
    # Vong lap
    # ------------------------------------------------------------------
    def tick(self, now_ms):
        """Goi dinh ky. Tra ve tin nhan moi, hoac None.

        Chi tra ve khi thuc su chuyen pha, de UI khong hien lai lien tuc.
        """
        if self.phase not in (FOCUS, BREAK):
            return None
        if now_ms < self.phase_end_ms:
            return None

        if self.phase == FOCUS:
            return self._enter_break(now_ms)
        return self._enter_focus(now_ms)

    def _enter_break(self, now_ms):
        self.phase = BREAK
        self.phase_end_ms = now_ms + self.break_ms
        self.completed_focus += 1
        message = self.rng.choice(BREAK_REMINDERS)
        return self._emit(message, prefix=f"Nghỉ {self.break_ms // 60000} phút: ")

    def _enter_focus(self, now_ms):
        self.phase = FOCUS
        self.phase_end_ms = now_ms + self.focus_ms
        message = self.rng.choice(FOCUS_REMINDERS)
        return self._emit(message, prefix=f"Tập trung {self.focus_ms // 60000} phút: ")

    def _emit(self, message, prefix=""):
        full = f"{prefix}{message}" if prefix else message
        self.last_reminder = full
        self.history.append(full)
        # Giu lich su gon.
        if len(self.history) > 50:
            self.history = self.history[-50:]
        return full

    # ------------------------------------------------------------------
    # Truy van
    # ------------------------------------------------------------------
    def remaining_ms(self, now_ms):
        """Thoi gian con lai cua pha hien tai."""
        if self.phase == PAUSED:
            return self.remaining_when_paused_ms
        if self.phase not in (FOCUS, BREAK):
            return 0
        return max(0, self.phase_end_ms - now_ms)

    def remaining_text(self, now_ms):
        """Chuoi mm:ss de hien thi."""
        total_seconds = self.remaining_ms(now_ms) // 1000
        return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"

    def is_focusing(self):
        return self.phase == FOCUS

    def is_active(self):
        return self.phase in (FOCUS, BREAK, PAUSED)

    def status_text(self, now_ms):
        """Mo ta ngan gon trang thai hien tai."""
        if self.phase == IDLE:
            return "Chế độ tập trung: tắt"
        if self.phase == PAUSED:
            return f"Tạm dừng — còn {self.remaining_text(now_ms)}"
        label = "Tập trung" if self.phase == FOCUS else "Nghỉ"
        return f"{label} — còn {self.remaining_text(now_ms)}"

    def checkin_message(self):
        """Loi nhic nhe giua gio tap trung."""
        return self.rng.choice(FOCUS_CHECKINS)

    def random_break_reminder(self):
        """Mot loi nhic nghi ngau nhien, co luu vao lich su."""
        return self._emit(self.rng.choice(BREAK_REMINDERS))
