"""Bong bong thoai hien loi nhic cua pet.

Cua so nho, trong suot, khong vien, tu dong an sau vai giay. Dung cho loi nhic
Pomodoro va (sau nay) cau tra loi cua AI.

Cua so nay khong nhan chuot (WA_TransparentForMouseEvents) de khong chan pet.
"""

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

# Kich thuoc toi da cua bong bong truoc khi xuong dong.
MAX_WIDTH = 340

STYLE = """
QLabel {
    background-color: rgba(30, 30, 30, 235);
    color: #f0f0f0;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
}
"""


class SpeechBubble(QWidget):
    """Bong bong thoai noi tren dau pet."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Khong chan chuot: nguoi dung van keo duoc pet nam duoi bong bong.
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.label = QLabel("", self)
        self.label.setStyleSheet(STYLE)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def say(self, text, duration_ms=6000, anchor=None):
        """Hien loi noi, tu dong an sau ``duration_ms``.

        ``anchor`` la QRect cua pet; bong bong se nam phia tren, canh giua.
        """
        if not text:
            return
        self.label.setText(text)
        self.adjustSize()

        if anchor is not None:
            self._place_above(anchor)

        self.show()
        self.raise_()
        self.hide_timer.start(max(1000, int(duration_ms)))

    def _place_above(self, anchor):
        """Dat bong bong ngay tren pet, keo vao trong man hinh neu tran."""
        screen = self.screen()
        area = screen.availableGeometry() if screen else None

        x = anchor.x() + (anchor.width() - self.width()) // 2
        y = anchor.y() - self.height() - 8

        if area is not None:
            # Tran tren: dat xuong duoi pet.
            if y < area.top():
                y = anchor.y() + anchor.height() + 8
            # Tran ngang: kep lai trong man hinh.
            x = max(area.left() + 4, min(x, area.right() - self.width() - 4))
            y = max(area.top() + 4, min(y, area.bottom() - self.height() - 4))

        self.move(QPoint(int(x), int(y)))

    def say_above(self, text, pet_rect, duration_ms=6000):
        self.say(text, duration_ms=duration_ms, anchor=pet_rect)
