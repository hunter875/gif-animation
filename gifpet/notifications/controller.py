"""Ghep dispatcher voi gioi han thoi gian va viec don inbox (khong Qt).

Tang UI (``gifpet/ui/notification_panel.py``) chi can:

    controller = NotificationController(state, registry, inbox_source)
    controller.tick()                  # trong timer Qt
    item = controller.take_next()      # lay thong bao de hien thi
    controller.acknowledge()           # xoa tep da xu ly (sau khi hien thi)

Vi sao tach ``acknowledge``: tep chi bi xoa khi pet **da hien thi** thong
bao. Neu xoa ngay khi doc, va lat sau nguoi dung am/tat tinh nang, thong bao
se mat ma khong ai thay. Nguoc lai, tep da qua han hoac hong thi don ngay de
inbox khong bi ket.

Module nay khong import Qt, khong goi mang, khong chay lenh.
"""

import time

from gifpet.notifications.dispatcher import Dispatcher
from gifpet.notifications.inbox import InboxProblem, InboxSource
from gifpet.notifications.registry import NotificationRegistry, default_registry
from gifpet.notifications.state import NotificationState

# Nhip poll mac dinh: 2 giay la du tuoi cho thong bao van ban, va re hon
# nhieu so voi timer GIF 40ms cua pet.
DEFAULT_POLL_MS = 2000
MIN_POLL_MS = 500
MAX_POLL_MS = 60000

# Kiem tra thu muc inbox theo nhip thua hon poll de khong stat lien tuc.
INBOX_CHECK_EVERY = 5


class NotificationController:
    """Bo dieu phoi: doc nguon theo nhip, giu queue, tra thong bao ra UI."""

    def __init__(self, state, registry=None, inbox_source=None, clock=None,
                 max_queue=32, max_per_window=3, window=10.0):
        if not isinstance(state, NotificationState):
            raise TypeError("controller cần NotificationState")
        self.state = state
        self.clock = clock or time.time
        self.dispatcher = Dispatcher(
            state,
            max_queue=max_queue,
            max_per_window=max_per_window,
            window=window,
            clock=self.clock,
        )
        self.inbox_source = inbox_source
        if registry is None:
            registry = default_registry(inbox_source)
        elif not isinstance(registry, NotificationRegistry):
            registry = default_registry()
        self.registry = registry
        self.last_poll = 0.0
        self.last_error = ""
        self.poll_count = 0

    # ------------------------------------------------------------------
    # Cau hinh
    # ------------------------------------------------------------------
    def set_enabled(self, enabled):
        """Bat/tat tinh nang thong bao. Tat thi bo queue, khong phat lai."""
        self.state.set_setting("enabled", bool(enabled))
        if not enabled:
            self.dispatcher.clear("tắt thông báo")

    def set_muted(self, muted):
        """Am (mute): im lang hoan toan, khong hien bong bong hay khay."""
        self.state.set_setting("muted", bool(muted))
        if muted:
            self.dispatcher.clear("âm thông báo")

    def set_inbox(self, directory):
        """Doi thu muc inbox luc dang chay (nguoi dung chon o Cai dat)."""
        directory = (directory or "").strip()
        self.state.set_setting("inbox_path", directory)
        if not directory:
            self.inbox_source = None
        else:
            self.inbox_source = InboxSource(directory, now=self.clock)
        self.registry = default_registry(self.inbox_source)
        self.dispatcher.clear("đổi hộp thư")
        self.last_error = ""
        return self.inbox_source

    def inbox_available(self):
        """True neu inbox ton tai, doc duoc va khong phai symlink/thu muc la."""
        if self.inbox_source is None:
            return False
        try:
            self.inbox_source.inbox.check()
        except InboxProblem as exc:
            self.last_error = f"{exc.reason}: {exc.detail}".strip(": ")
            return False
        self.last_error = ""
        return True

    def source_names(self):
        return [
            (source.source_id, getattr(source, "display_name", source.source_id))
            for source in self.registry.sources()
        ]

    # ------------------------------------------------------------------
    # Nhip
    # ------------------------------------------------------------------
    def tick(self, now=None):
        """Mot luot: poll nguon va don tep. Tra so thong bao nhan them.

        Goi tu timer Qt; ham nay **khong** chan lau: moi nguon chi doc vai
        tep nho, khong co ket noi mang, khong cho model.
        """
        now = self.clock() if now is None else float(now)
        self.last_poll = now
        self.poll_count += 1
        if not self.state.active():
            self.dispatcher.clear("tắt/âm thông báo")
            self._acknowledge_handled()
            return 0
        if (
            self.inbox_source is not None
            and self.poll_count % INBOX_CHECK_EVERY == 1
            and not self.inbox_available()
        ):
            return 0
        accepted = self.dispatcher.collect(self.registry, now=now)
        self._acknowledge_handled()
        return accepted

    def take_next(self, now=None):
        """Thong bao tiep theo de hien thi, hoac None."""
        notification = self.dispatcher.next_display(now=now)
        if notification is not None:
            self._acknowledge_handled()
        return notification

    # ------------------------------------------------------------------
    # Don inbox
    # ------------------------------------------------------------------
    def _acknowledge_handled(self):
        if self.inbox_source is None:
            return 0
        names = self.inbox_source.take_ack()
        if not names:
            return 0
        return self.inbox_source.inbox.acknowledge(names)

    def acknowledge(self):
        """Xoa cac tep da xu ly (sau khi UI hien thi hoac tu choi hien thi)."""
        return self._acknowledge_handled()

    # ------------------------------------------------------------------
    # Tien ich cho UI
    # ------------------------------------------------------------------
    def history(self, limit=50):
        return self.state.recent(limit)

    def clear_history(self):
        count = self.state.clear_history()
        self.dispatcher.clear("xóa lịch sử")
        return count

    def stats(self):
        """So lieu ngan gon cho cua so lich su (khong lo noi dung thong bao)."""
        counts = self.dispatcher.total_counts()
        return {
            "enabled": bool(self.state.enabled()),
            "muted": bool(self.state.get_setting("muted", False)),
            "pending": len(self.dispatcher.pending()),
            "history": len(self.state.history),
            "inbox_available": bool(self.inbox_available()),
            "last_error": self.last_error,
            "sources": [name for _sid, name in self.source_names()],
            "poll_count": self.poll_count,
            "dropped": counts.get("dropped", 0),
            "duplicate": counts.get("duplicate", 0),
            "expired": counts.get("expired", 0),
            "source_errors": counts.get("source_errors", 0),
        }


def poll_interval_from_config(value):
    """Doi gia tri config sang ms an toan (500ms - 60s)."""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return DEFAULT_POLL_MS
    return max(MIN_POLL_MS, min(MAX_POLL_MS, interval))
