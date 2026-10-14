"""Dieu phoi hanh vi tu phat cua pet (Giai doan 3).

Tach phan "pet tu quyet dinh lam gi" ra khoi UI. Module nay thuan tuy logic:
no nhan thoi gian troi qua va tra ve quyet dinh, khong tu goi Qt.

Vong doi hanh vi:

    idle --(het thoi gian nghi)--> walk --(di mot quang)--> idle
    idle --(khong tuong tac lau)--> sleep
    sleep --(co tuong tac)--> idle

Che do tap trung: pet dung yen hoac ngu, khong tu di.
"""

import random

from gifpet.core import state as state_module


class Behavior:
    """Quyet dinh pet tu lam gi theo thoi gian.

    ``now_ms`` la dong ho don dieu (monotonic) tinh bang mili giay, do UI truyen
    vao. Nho vay test co the gia lap thoi gian ma khong can ``sleep``.
    """

    def __init__(self, config=None, rng=None, start_ms=None):
        self.config = config
        self.rng = rng or random.Random()
        # Mac dinh None nghia la "chua biet dong ho"; lan tick dau tien se lay
        # moc hien tai. Neu dat 0, pet se tuong da bi bo quen tu epoch va ngu
        # ngay khi mo app.
        self.last_interaction_ms = start_ms
        self._walk_until_ms = 0
        self._pause_until_ms = 0

    def ensure_started(self, now_ms):
        """Chot moc tuong tac dau tien neu chua co."""
        if self.last_interaction_ms is None:
            self.last_interaction_ms = now_ms
        if self._pause_until_ms == 0:
            # Nghi ngan truoc khi bat dau di lan dau.
            self._pause_until_ms = now_ms + self._pick_pause_ms()
        return now_ms

    # ------------------------------------------------------------------
    # Cau hinh
    # ------------------------------------------------------------------
    def _get(self, key, default):
        if self.config is None:
            return default
        return self.config.get(key, default)

    @property
    def walk_speed(self):
        return max(1, int(self._get("walk_speed", 2)))

    @property
    def sleep_after_ms(self):
        seconds = max(5, int(self._get("sleep_after_seconds", 120)))
        return seconds * 1000

    @property
    def pause_chance(self):
        try:
            return min(1.0, max(0.0, float(self._get("walk_pause_chance", 0.3))))
        except (TypeError, ValueError):
            return 0.3

    @property
    def focus_mode(self):
        return bool(self._get("focus_mode", False))

    # ------------------------------------------------------------------
    # Su kien
    # ------------------------------------------------------------------
    def note_interaction(self, now_ms):
        """Ghi nhan co tuong tac moi tu nguoi dung."""
        self.last_interaction_ms = now_ms

    def time_since_interaction(self, now_ms):
        """Thoi gian tu lan tuong tac cuoi. Chua co tuong tac thi tinh tu luc khoi dong."""
        if self.last_interaction_ms is None:
            self.ensure_started(now_ms)
        return max(0, now_ms - self.last_interaction_ms)

    # ------------------------------------------------------------------
    # Quyet dinh
    # ------------------------------------------------------------------
    def idle_tick(self, machine, now_ms):
        """Goi dinh ky khi pet dang ranh. Tra ve True neu co chuyen trang thai.

        Thu tu uu tien:
        1. Che do tap trung -> chi ngu, khong tu di.
        2. Khong tuong tac lau -> ngu.
        3. Het thoi gian nghi -> di mot quang.
        """
        self.ensure_started(now_ms)
        if machine.is_busy():
            return False

        # 1. Che do tap trung: dung yen hoac ngu.
        if self.focus_mode:
            if (
                machine.state != state_module.SLEEP
                and self.time_since_interaction(now_ms) >= self.sleep_after_ms
                and machine.can_sleep()
            ):
                return machine.request(
                    state_module.SLEEP, reason="chế độ tập trung, không tương tác lâu"
                )
            return False

        # 2. Ngu khi khong tuong tac lau.
        if self.time_since_interaction(now_ms) >= self.sleep_after_ms:
            if machine.can_sleep():
                return machine.request(
                    state_module.SLEEP, reason="không tương tác một thời gian"
                )
            return False

        # 3. Di mot quang sau khi het thoi gian nghi.
        if machine.state in (state_module.IDLE, state_module.REACT, state_module.TALK):
            if not machine.can_walk():
                return False
            if now_ms < self._pause_until_ms:
                return False
            duration_ms = self._pick_walk_duration_ms()
            self._walk_until_ms = now_ms + duration_ms
            return machine.request(state_module.WALK, reason="hết thời gian nghỉ")

        return False

    def walk_tick(self, machine, now_ms):
        """Goi dinh ky khi pet dang di. Tra ve True neu nen dung lai nghi."""
        if machine.state != state_module.WALK:
            return False
        if now_ms < self._walk_until_ms:
            return False
        return self.stop_walking(machine, now_ms)

    def stop_walking(self, machine, now_ms):
        """Ket thuc luot di va dat thoi gian nghi ke tiep."""
        self._pause_until_ms = now_ms + self._pick_pause_ms()
        if machine.state == state_module.WALK:
            return machine.request(state_module.IDLE, reason="đi xong một quãng")
        return False

    def on_drag_start(self, machine, now_ms):
        """Nguoi dung bat dau keo: huy luot di dang do."""
        self.note_interaction(now_ms)
        self._walk_until_ms = 0
        self._pause_until_ms = 0
        return machine.on_drag_start()

    def on_drag_release(self, machine, now_ms, near_ground):
        self.note_interaction(now_ms)
        # Tha xong thi nghi mot chut truoc khi tu di lai.
        self._pause_until_ms = now_ms + self._pick_pause_ms()
        return machine.on_drag_release(near_ground=near_ground)

    def on_landed(self, machine, now_ms):
        self.note_interaction(now_ms)
        return machine.on_landed()

    def on_click(self, machine, now_ms):
        self.note_interaction(now_ms)
        return machine.on_click()

    # ------------------------------------------------------------------
    # Chon khoang thoi gian
    # ------------------------------------------------------------------
    def _pick_walk_duration_ms(self):
        """Mot luot di keo dai bao lau."""
        base = self._get("walk_duration_ms", 4000)
        try:
            base = max(500, int(base))
        except (TypeError, ValueError):
            base = 4000
        # Dao dong 50%-150% cho tu nhien.
        return int(base * self.rng.uniform(0.5, 1.5))

    def _pick_pause_ms(self):
        """Nghi bao lau truoc khi di tiep.

        Co ``pause_chance`` xac suat nghi dai (nhu dang ngam canh), con lai
        nghi ngan.
        """
        if self.rng.random() < self.pause_chance:
            return self.rng.randint(4000, 12000)
        return self.rng.randint(1000, 3000)
