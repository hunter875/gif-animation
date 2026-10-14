"""May trang thai cua pet (Giai doan 3).

Trang thai va y nghia:

    idle    dung yen, thinh thoang doi tu the
    walk    tu di trong vung man hinh duoc phep
    drag    nguoi dung dang giu chuot keo; pet vung vay
    fall    vua duoc tha giua khong trung; pet roi xuong mpet duoi man hinh
    sleep   khong tuong tac mot thoi gian
    react   duoc click hoac goi ten
    talk    dang noi bang bong bong thoai hoac giong

Quy tac uu tien (quan trong nhat cua giai doan nay):

- Dang bi keo thi KHONG duoc chuyen sang sleep hay walk.
- Dang roi thi phai tiep dat xong moi lam viec khac.
- Che do tap trung (focus_mode) thi chi dung idle hoac sleep.

Module nay thuan tuy logic, khong phu thuoc Qt, nen test duoc de dang.
"""

# --- Trang thai ---
IDLE = "idle"
WALK = "walk"
DRAG = "drag"
FALL = "fall"
SLEEP = "sleep"
REACT = "react"
TALK = "talk"

ALL_STATES = (IDLE, WALK, DRAG, FALL, SLEEP, REACT, TALK)

# Trang thai khong the bi ngat boi hanh vi tu phat.
# Dang keo thi khong duoc bat di ngu; dang roi thi phai tiep dat xong.
BLOCKING_STATES = (DRAG, FALL)

# Trang thai chi duoc thoat khi chu dong (het thoi gian hoac do nguoi dung).
TIMED_STATES = (REACT, TALK)

# Trang thai chi duoc phep khi khong bat che do tap trung.
FOCUS_BLOCKED_STATES = (WALK, FALL)

# Cac chuyen trang thai hop le. Dung de phat hien loi logic som.
_ALLOWED = {
    IDLE: {WALK, DRAG, SLEEP, REACT, TALK, FALL},
    WALK: {IDLE, DRAG, SLEEP, REACT, TALK, FALL},
    DRAG: {FALL, IDLE, REACT},
    FALL: {IDLE, REACT},
    SLEEP: {IDLE, DRAG, REACT, TALK},
    REACT: {IDLE, WALK, DRAG, TALK, SLEEP},
    TALK: {IDLE, WALK, DRAG, SLEEP, REACT},
}


class StateMachine:
    """Giu trang thai hien tai va quyet dinh chuyen trang thai nao duoc phep."""

    def __init__(self, initial=IDLE, focus_mode=False):
        self.state = initial
        self.focus_mode = bool(focus_mode)
        # Ly do vao trang thai hien tai, huu ich cho debug va cho AI sau nay.
        self.reason = "khởi tạo"
        self.listeners = []

    # ------------------------------------------------------------------
    # Truy van
    # ------------------------------------------------------------------
    def is_busy(self):
        """True khi pet dang bi keo hoac dang roi (khong duoc ngat)."""
        return self.state in BLOCKING_STATES

    def can_sleep(self):
        """Chi duoc ngu khi dang ranh va khong bat che do tap trung chan."""
        if self.is_busy():
            return False
        if self.focus_mode and SLEEP in FOCUS_BLOCKED_STATES:
            return False
        return self.state != SLEEP

    def can_walk(self):
        if self.is_busy() or self.state == SLEEP:
            return False
        if self.focus_mode:
            return False
        return True

    # ------------------------------------------------------------------
    # Chuyen trang thai
    # ------------------------------------------------------------------
    def request(self, state, reason="", force=False):
        """Yeu cau chuyen sang trang thai moi.

        Tra ve ``True`` neu chuyen thanh cong, ``False`` neu bi tu choi.
        Ly do tu choi luu trong ``self.last_rejection`` de test va debug.
        """
        self.last_rejection = ""
        if state not in ALL_STATES:
            self.last_rejection = f"trạng thái không hợp lệ: {state}"
            return False
        if state == self.state:
            return False

        if not force:
            rejection = self._check(state)
            if rejection:
                self.last_rejection = rejection
                return False

        previous = self.state
        self.state = state
        self.reason = reason or f"{previous} -> {state}"
        for listener in self.listeners:
            listener(previous, state)
        return True

    def _check(self, state):
        """Tra ve ly do tu choi, hoac chuoi rong neu duoc phep."""
        # Dang keo: khong duoc bat di ngu hay tu di.
        if self.state == DRAG and state in (SLEEP, WALK):
            return f"đang bị kéo, không thể chuyển sang {state}"
        # Dang roi: phai tiep dat xong.
        if self.state == FALL and state != IDLE:
            return f"đang rơi, phải tiếp đất trước khi chuyển sang {state}"
        if self.focus_mode and state in FOCUS_BLOCKED_STATES:
            return f"chế độ tập trung: không cho phép {state}"
        allowed = _ALLOWED.get(self.state, set())
        if state not in allowed and state not in (IDLE, DRAG):
            return f"không có chuyển trạng thái {self.state} -> {state}"
        return ""

    def set_focus_mode(self, enabled):
        """Bat che do tap trung: pet dung yen hoac ngu."""
        self.focus_mode = bool(enabled)
        if self.focus_mode and self.state in FOCUS_BLOCKED_STATES:
            self.request(IDLE, reason="bật chế độ tập trung", force=True)

    def force(self, state, reason="bị buộc"):
        """Dat trang thai bo qua kiem tra, dung khi can dong bo voi UI."""
        return self.request(state, reason=reason, force=True)

    # ------------------------------------------------------------------
    # Su kien tu UI
    # ------------------------------------------------------------------
    def on_drag_start(self):
        return self.request(DRAG, reason="người dùng giữ chuột")

    def on_drag_release(self, near_ground):
        """Tha chuot: neu con tren cao thi roi, neu sat mat dat thi ve idle."""
        if near_ground:
            return self.request(IDLE, reason="thả gần mặt đất")
        return self.request(FALL, reason="thả giữa không trung")

    def on_landed(self):
        return self.request(IDLE, reason="đã tiếp đất")

    def on_click(self):
        if self.state in BLOCKING_STATES:
            return False
        return self.request(REACT, reason="người dùng click")

    def on_idle_timeout(self):
        if not self.can_sleep():
            return False
        return self.request(SLEEP, reason="không tương tác một thời gian")

    def on_interaction(self):
        """Co tuong tac moi: neu dang ngu thi thuc day."""
        if self.state == SLEEP:
            return self.request(IDLE, reason="có tương tác mới")
        return False
