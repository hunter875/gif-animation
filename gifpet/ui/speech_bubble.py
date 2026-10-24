"""Bong bong thoai hien loi nhic cua pet.

Cua so nho, trong suot, khong vien, tu dong an sau vai giay. Dung cho loi nhic
Pomodoro va (sau nay) cau tra loi cua AI.

Cua so nay khong nhan chuot (WA_TransparentForMouseEvents) de khong chan pet.
"""

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

# Kich thuoc bong bong.
MAX_WIDTH = 340   # rong toi da truoc khi xuong dong
MIN_WIDTH = 120   # rong toi thieu, tranh bong bong qua hep
PADDING_X = 14    # phai khop padding ngang trong STYLE

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
        # Chieu rong duoc dat trong _resize_for_text().

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def say(self, text, duration_ms=6000, anchor=None, plain=False):
        """Hien loi noi, tu dong an sau ``duration_ms``.

        ``anchor`` la QRect cua pet; bong bong se nam phia tren, canh giua.

        ``plain=True`` ep hien thi van ban thuan: noi dung tu nguon ngoai
        (thong bao tu chuong trinh khac) khong duoc dien giai nhu HTML, nen
        the ``<b>`` chi hien ra nguyen van. Mac dinh giu nhu cu de loi nhac
        Pomodoro/AI khong doi hanh vi.
        """
        if not text:
            return
        self.label.setTextFormat(Qt.PlainText if plain else Qt.RichText)
        self.label.setText(text)
        self._resize_for_text()

        if anchor is not None:
            self._place_above(anchor)

        self.show()
        self.raise_()
        self.hide_timer.start(max(1000, int(duration_ms)))

    def _resize_for_text(self):
        """Chon kich thuoc vua du, nhung uu tien dung chieu rong cho phep.

        ``adjustSize()`` mot minh se chon chieu rong nho nhat co the, lam bong
        bong cao va hep bat tien. Thay vao do: do chieu rong chuoi tren mot
        dong, roi kep vao khoang [MIN_WIDTH, MAX_WIDTH].
        """
        metrics = self.label.fontMetrics()
        single_line = metrics.boundingRect(self.label.text()).width()

        # Cong them padding cua stylesheet (14px moi ben) va vien.
        wanted = single_line + 2 * PADDING_X + 2
        width = max(MIN_WIDTH, min(MAX_WIDTH, wanted))

        self.label.setFixedWidth(width)
        self.label.adjustSize()
        self.adjustSize()

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

    def say_above(self, text, pet_rect, duration_ms=6000, plain=False):
        self.say(text, duration_ms=duration_ms, anchor=pet_rect, plain=plain)
