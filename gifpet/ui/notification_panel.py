"""Lop Qt mong cho thong bao: timer, bong bong thoai, khay va cua so lich su.

Module nay chi lo phan giao dien. Toan bo logic (kiem tra du lieu, gioi han
hang doi, khu trung, het han) nam trong ``gifpet/notifications`` va khong
import Qt.

Nguyen tac:
- Noi dung thong bao la chu thuong. Luon hien thi bang ``setPlainText`` de
  HTML/tag trong payload khong duoc dien giai.
- Khong bam duoc lien ket, khong mo duong dan, khong chay lenh, khong goi AI.
- Moi vong tick deu di qua ``PetWindow._guarded`` de loi khong lam treo UI.
- Polling dien ra tren luong Qt chinh, trong mot lan doc co gioi han moi lan.

Xem docs/MODULAR-ASSISTANT.md (pham vi) va docs/SECURITY.md (rang buoc).
"""

import os
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from gifpet.core.config import config_path, default_inbox_dir
from gifpet.notifications.controller import (
    NotificationController,
    poll_interval_from_config,
)
from gifpet.notifications.dispatcher import Dispatcher
from gifpet.notifications.inbox import Inbox, InboxSource
from gifpet.notifications.registry import default_registry
from gifpet.notifications.state import NotificationState, state_path

# Hien bong bong lau hon loi nhac thuong: noi dung thong bao dai hon.
BUBBLE_MS = 9000
# Gioi han so dong trong danh sach lich su (giao dien, khong phai luu tru).
HISTORY_VIEW_LIMIT = 50

SEVERITY_ICONS = {
    "info": "ℹ️",
    "success": "✅",
    "warning": "⚠️",
    "error": "⛔",
}
SEVERITY_LABELS = {
    "info": "Thông tin",
    "success": "Xong",
    "warning": "Cảnh báo",
    "error": "Lỗi",
}


def inline_text(value, limit=400):
    """Chuoi mot dong de hien trong nhan/khay: bo xuong dong, cat bot.

    Chi thay ky tu dieu khien, khong dien giai markup.
    """
    text = str(value or "")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def notification_summary(notification, show_source=True):
    """Dong tom tat cho khay he thong."""
    icon = SEVERITY_ICONS.get(notification.severity, SEVERITY_ICONS["info"])
    title = inline_text(notification.title, 80)
    message = inline_text(notification.message, 160)
    head = f"{icon} {title}" if title else icon
    if show_source and notification.source:
        head = f"[{inline_text(notification.source, 24)}] {head}"
    if not message:
        return head
    return f"{head}\n{message}"


def notification_body(notification, show_source=True):
    """Noi dung bong bong thoai: nhieu dong, van la chu thuong."""
    lines = []
    title = inline_text(notification.title, 120)
    if title:
        lines.append(title)
    message = inline_text(notification.message, 500)
    if message:
        lines.append(message)
    if show_source and notification.source:
        lines.append(f"— {inline_text(notification.source, 24)}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Lien ket voi PetWindow
# ----------------------------------------------------------------------
def resolve_inbox_dir(config):
    """Thu muc inbox dang cau hinh, hoac thu muc mac dinh neu de trong."""
    value = config.get("notifications_inbox")
    text = str(value or "").strip()
    return text or default_inbox_dir()


def _max_queue(config):
    """Gioi han hang doi tu config, luon trong khoang an toan."""
    try:
        value = int(config.get("notifications_max_queue", 32) or 32)
    except (TypeError, ValueError):
        value = 32
    return max(1, min(200, value))


def build_state(config):
    """Trang thai thong bao (lich su, cai dat, dedup) luu canh config.json."""
    return NotificationState(state_path(os.path.dirname(config_path())))


def setup(window):
    """Tao trang thai, bo dieu phoi, controller va timer cho pet.

    Goi mot lan tu ``PetWindow._setup_timers``. Khong tao cua so nao.
    """
    config = window.config
    state = build_state(config)
    state.load()

    # Dong bo co bat/tat tu config.json sang trang thai cua module.
    state.update_settings(
        {
            "enabled": bool(config.get("notifications_enabled", True)),
            "bubble": bool(config.get("notifications_bubble", True)),
            "tray": bool(config.get("notifications_tray", True)),
            "inbox_path": str(config.get("notifications_inbox", "") or ""),
        }
    )

    inbox_source = InboxSource(Inbox(resolve_inbox_dir(config)))
    registry = default_registry(inbox_source)
    controller = NotificationController(
        state,
        registry,
        inbox_source,
        max_queue=_max_queue(config),
    )
    dispatcher = controller.dispatcher

    window.notifications_state = state
    window.notifications = controller
    window.notification_inbox = inbox_source

    interval = poll_interval_from_config(config.get("notifications_poll_ms"))
    timer = QTimer(window)
    timer.timeout.connect(
        lambda: window._guarded("_notification_tick", notification_tick, window)
    )
    if state.enabled():
        timer.start(interval)
    window.notification_timer = timer
    return controller


def notification_tick(window):
    """Mot vong: doc nguon co gioi han, roi hien toi da mot thong bao."""
    controller = getattr(window, "notifications", None)
    if controller is None:
        return
    now = time.time()
    controller.tick(now)
    notification = controller.take_next(now)
    if notification is None:
        return
    show_notification(window, notification)


def show_notification(window, notification):
    """Hien thi mot thong bao da duoc chap nhan (chu thuong, khong hanh dong)."""
    state = getattr(window, "notifications_state", None)
    show_source = True
    if state is not None:
        show_source = bool(state.get_setting("show_source", True))

    if _bubble_on(window):
        body = notification_body(notification, show_source)
        window.announce(body, duration_ms=BUBBLE_MS, plain=True)

    if _tray_on(window):
        notify_tray(window, notification_summary(notification, show_source))


def _bubble_on(window):
    state = getattr(window, "notifications_state", None)
    if state is not None and not bool(state.get_setting("bubble", True)):
        return False
    return True


def _tray_on(window):
    state = getattr(window, "notifications_state", None)
    if state is not None and not bool(state.get_setting("tray", True)):
        return False
    return True


def notify_tray(window, message):
    """Gui thong bao khay qua ``tray_menu.notify`` san co."""
    from gifpet.ui import tray_menu

    if not message:
        return
    tray_menu.notify(window, message)


def set_enabled(window, enabled, persist=True):
    """Bat/tat nhan thong bao; khi tat thi xoa hang doi (khong phat lai sau)."""
    controller = getattr(window, "notifications", None)
    if controller is not None:
        controller.set_enabled(bool(enabled))
    timer = getattr(window, "notification_timer", None)
    if timer is not None:
        if enabled:
            timer.start(poll_interval_from_config(window.config.get(
                "notifications_poll_ms")))
        else:
            timer.stop()
    _sync_state(window, {"enabled": bool(enabled)})
    if persist:
        window.config.data["notifications_enabled"] = bool(enabled)
        window.config.save()


def set_muted(window, muted):
    """Tam im: don hang doi va danh dau da thay, khong hien gi."""
    controller = getattr(window, "notifications", None)
    if controller is not None:
        controller.set_muted(bool(muted))
    _sync_state(window, {"muted": bool(muted)})


def is_muted(window):
    state = getattr(window, "notifications_state", None)
    return bool(state.get_setting("muted", False)) if state is not None else False


def is_enabled(window):
    state = getattr(window, "notifications_state", None)
    if state is None:
        return bool(window.config.get("notifications_enabled", True))
    return bool(state.enabled())


def _sync_state(window, values):
    state = getattr(window, "notifications_state", None)
    if state is not None:
        state.update_settings(values)


def apply_config(window):
    """Ap dung lai cai dat thong bao sau khi nguoi dung bam OK trong Cai dat."""
    config = window.config
    enabled = bool(config.get("notifications_enabled", True))
    inbox_dir = resolve_inbox_dir(config)
    controller = getattr(window, "notifications", None)
    if controller is not None:
        controller.set_inbox(inbox_dir)
    _sync_state(
        window,
        {
            "enabled": enabled,
            "bubble": bool(config.get("notifications_bubble", True)),
            "tray": bool(config.get("notifications_tray", True)),
            "inbox_path": str(config.get("notifications_inbox", "") or ""),
        },
    )
    timer = getattr(window, "notification_timer", None)
    if timer is not None:
        if enabled:
            timer.start(poll_interval_from_config(config.get(
                "notifications_poll_ms")))
        else:
            timer.stop()


# ----------------------------------------------------------------------
# Cua so lich su / trang thai
# ----------------------------------------------------------------------
class NotificationHistoryDialog(QDialog):
    """Xem lich su thong bao, phat lai noi dung cu (chi de doc)."""

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.window = window
        self.setWindowTitle("Thông báo đã nhận")
        self.setMinimumSize(460, 400)

        layout = QVBoxLayout(self)

        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.list = QListWidget(self)
        layout.addWidget(self.list, 1)

        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(130)
        layout.addWidget(self.detail)

        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Xoá lịch sử", self)
        self.close_button = QPushButton("Đóng", self)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.list.currentItemChanged.connect(self._show_current)
        self.clear_button.clicked.connect(self._clear_history)
        self.close_button.clicked.connect(self.reject)

        self._refresh()

    def _entries(self):
        state = getattr(self.window, "notifications_state", None)
        if state is None:
            return []
        return state.recent(HISTORY_VIEW_LIMIT)

    def _refresh(self):
        self.list.clear()
        for entry in self._entries():
            source = inline_text(entry.get("source", ""), 24)
            title = inline_text(entry.get("title", ""), 80)
            message = inline_text(entry.get("message", ""), 60)
            icon = SEVERITY_ICONS.get(entry.get("severity"), SEVERITY_ICONS["info"])
            label = f"{icon} [{source}] {title}".strip()
            if message:
                label = f"{label} — {message}"
            item = QListWidgetItem(label)
            # Giu entry goc trong data de hien thi chi tiet dang chu thuong.
            item.setData(Qt.UserRole, entry)
            self.list.addItem(item)

        self.status.setText(self._status_text())
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.detail.setPlainText("(chưa có thông báo nào)")

    def _status_text(self):
        controller = getattr(self.window, "notifications", None)
        lines = []
        inbox = getattr(self.window, "notification_inbox", None)
        if inbox is not None:
            directory = inbox.inbox.directory
            available = inbox.inbox.check()
            lines.append(f"Hộp thư: {directory}")
            if not available:
                lines.append("Hộp thư chưa sẵn sàng (chưa có thư mục).")
        if controller is not None:
            stats = controller.stats()
            lines.append(
                "Đang bật" if stats.get("enabled") else "Đang tắt nhận thông báo"
            )
            if stats.get("muted"):
                lines.append("Đang tạm im.")
            lines.append(f"Đang chờ hiện: {stats.get('pending', 0)}")
            names = stats.get("sources") or []
            if names:
                lines.append("Nguồn: " + ", ".join(names))
        lines.append(
            "Chỉ lưu chữ của thông báo, tối đa 200 mục. "
            "Xoá lịch sử cũng xoá danh sách chống trùng."
        )
        return "\n".join(lines)

    def _show_current(self, current, _previous=None):
        if current is None:
            return
        entry = current.data(Qt.UserRole) or {}
        lines = []
        title = str(entry.get("title", "") or "")
        message = str(entry.get("message", "") or "")
        label = SEVERITY_LABELS.get(entry.get("severity"), "Thông tin")
        lines.append(f"[{label}] {title}".strip())
        if message:
            lines.append(message)
        source = str(entry.get("source", "") or "")
        if source:
            lines.append(f"— {source}")
        self.detail.setPlainText("\n".join(lines))

    def _clear_history(self):
        state = getattr(self.window, "notifications_state", None)
        if state is not None:
            state.clear_history()
        self._refresh()


def open_history(window):
    """Mo cua so lich su thong bao."""
    dialog = NotificationHistoryDialog(window)
    dialog.exec_()
    return dialog


# ----------------------------------------------------------------------
# Cai dat nhanh cho thong bao
# ----------------------------------------------------------------------
class NotificationSettingsDialog(QDialog):
    """Cai dat rieng cho thong bao: bat/tat, tam im, hien thi, hop thu."""

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.window = window
        state = getattr(window, "notifications_state", None)
        self.setWindowTitle("Cài đặt thông báo")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.enabled = QCheckBox("Bật nhận thông báo", self)
        self.enabled.setChecked(is_enabled(window))
        form.addRow(self.enabled)

        self.muted = QCheckBox("Tạm im (vẫn nhận, không hiện)", self)
        self.muted.setChecked(is_muted(window))
        form.addRow(self.muted)

        self.bubble = QCheckBox("Hiện bong bóng thoại", self)
        self.tray = QCheckBox("Hiện thông báo khay hệ thống", self)
        self.show_source = QCheckBox("Ghi tên nguồn trong nội dung", self)
        show_source = True
        if state is not None:
            self.bubble.setChecked(bool(state.get_setting("bubble", True)))
            self.tray.setChecked(bool(state.get_setting("tray", True)))
            show_source = bool(state.get_setting("show_source", True))
        else:
            self.bubble.setChecked(bool(window.config.get("notifications_bubble", True)))
            self.tray.setChecked(bool(window.config.get("notifications_tray", True)))
        self.show_source.setChecked(show_source)
        form.addRow(self.bubble)
        form.addRow(self.tray)
        form.addRow(self.show_source)

        self.inbox = QLineEdit(self)
        self.inbox.setPlaceholderText("để trống = thư mục mặc định")
        self.inbox.setText(str(window.config.get("notifications_inbox", "") or ""))
        form.addRow("Thư mục hộp thư:", self.inbox)

        self.poll = QSpinBox(self)
        self.poll.setRange(1, 60)
        self.poll.setSuffix(" giây")
        seconds = max(1, int(round(poll_interval_from_config(
            window.config.get("notifications_poll_ms")) / 1000.0)))
        self.poll.setValue(min(60, seconds))
        form.addRow("Khoảng kiểm tra:", self.poll)

        layout.addLayout(form)

        note = QLabel(
            "Thông báo là chữ do nguồn gửi vào hộp thư. Pet không chạy lệnh, "
            "không mở đường dẫn, không gọi model và không ghi vào bộ nhớ "
            "người dùng. Chỉ đọc đúng thư mục hộp thư ở trên.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def values(self):
        return {
            "enabled": self.enabled.isChecked(),
            "muted": self.muted.isChecked(),
            "bubble": self.bubble.isChecked(),
            "tray": self.tray.isChecked(),
            "show_source": self.show_source.isChecked(),
            "inbox_path": self.inbox.text().strip(),
            "poll_ms": self.poll.value() * 1000,
        }

    def apply(self):
        """Ghi cai dat vao trang thai va config (khong dung API AI)."""
        values = self.values()
        state = getattr(self.window, "notifications_state", None)
        if state is not None:
            state.update_settings(
                {
                    "bubble": values["bubble"],
                    "tray": values["tray"],
                    "show_source": values["show_source"],
                }
            )
        self.window.config.data["notifications_inbox"] = values["inbox_path"]
        self.window.config.data["notifications_poll_ms"] = values["poll_ms"]
        self.window.config.data["notifications_bubble"] = values["bubble"]
        self.window.config.data["notifications_tray"] = values["tray"]
        self.window.config.save()
        set_muted(self.window, values["muted"])
        set_enabled(self.window, values["enabled"], persist=True)
        apply_config(self.window)


def open_settings(window):
    """Mo cai dat thong bao; tra ve dialog de test co the doc gia tri."""
    dialog = NotificationSettingsDialog(window)
    if dialog.exec_() == QDialog.Accepted:
        dialog.apply()
    return dialog
