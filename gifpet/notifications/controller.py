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
        self.inbox_source = None
        self._custom_sources = {}
        if isinstance(registry, NotificationRegistry):
            if inbox_source is None:
                inbox_source = registry.get(InboxSource.source_id)
            else:
                self._absorb_custom(registry)
            self.registry = registry
        else:
            # Registry khong hop le: dung registry moi chi gom nguon inbox,
            # khong ghi de len registry goc.
            registry = default_registry()
            self.registry = registry
        if inbox_source is not None:
            self.inbox_source = inbox_source
            if InboxSource.source_id not in self.registry:
                self.registry.register(inbox_source)
        self.state.set_setting("inbox_path", self.inbox_source.inbox.directory
                               if self.inbox_source is not None else "")
        self.last_poll = 0.0
        self.last_error = ""
        self.poll_count = 0

    def _absorb_custom(self, registry):
        """Ghi nho nguon trusted khac (ngoai inbox) de giu khi doi inbox."""
        for source in registry.sources():
            if getattr(source, "source_id", None) == InboxSource.source_id:
                continue
            self._custom_sources[source.source_id] = source

    # ------------------------------------------------------------------
    # Cau hinh
    # ------------------------------------------------------------------
    def set_enabled(self, enabled):
        """Bat/tat tinh nang thong bao. Tat thi bo queue, khong phat lai."""
        self.state.set_setting("enabled", bool(enabled))
        if not enabled:
            self.dispatcher.clear("tắt thông báo")

    def set_muted(self, muted):
        """Am (mute): im lang hoan toan, khong hien bong bong hay khay.

        Thong bao da xep hang duoc giu lai (khong mat); khi bo am chung duoc
        phat, va thong bao het han trong luc am bi bo qua voi chan doan.
        """
        self.state.set_setting("muted", bool(muted))

    def set_inbox(self, directory):
        """Doi thu muc inbox luc dang chay (nguoi dung chon o Cai dat).

        Nguon khac da dang ky (``registry.register``) van duoc giu; neu tep
        xoa lich su dang giu queue thi thong bao cho phat lai van con.
        """
        directory = (directory or "").strip()
        self.state.set_setting("inbox_path", directory)
        if not directory:
            self.inbox_source = None
        else:
            self.inbox_source = InboxSource(directory, now=self.clock)
        if self.inbox_source is not None:
            self._custom_sources[InboxSource.source_id] = self.inbox_source
        else:
            self._custom_sources.pop(InboxSource.source_id, None)
        self.registry = default_registry(*self._custom_sources.values())
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
            # Tat/am: khong doc them va KHONG don queue - thong bao con han
            # duoc hien khi bat/bo am lai (expiry van kiem tra luc phat).
            return 0
        if (
            self.inbox_source is not None
            and self.poll_count % INBOX_CHECK_EVERY == 1
            and not self.inbox_available()
        ):
            # Inbox thieu/hong chi bo qua nguon inbox, nguon khac van chay.
            return self.dispatcher.collect(
                _registry_without(self.registry, InboxSource.source_id), now=now
            )
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
        """Xoa lich su hien thi; giu dedup de khong phat lai tin da xu ly."""
        count = self.state.clear_history_view()
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


def _registry_without(registry, source_id):
    """Ban sao registry bo mot nguon (khong sua registry goc)."""
    copy = NotificationRegistry()
    for source in registry.sources():
        if getattr(source, "source_id", None) == source_id:
            continue
        copy.register(source)
    return copy


def poll_interval_from_config(value):
    """Doi gia tri config sang ms an toan (500ms - 60s)."""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return DEFAULT_POLL_MS
    return max(MIN_POLL_MS, min(MAX_POLL_MS, interval))
