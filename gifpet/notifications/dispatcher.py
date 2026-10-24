"""Hang doi thong bao bounded: loc han dung, dedup, rate limit.

Module thuan Python (khong Qt) de test duoc khong can man hinh. Tang UI chi
goi ``Dispatcher.pump`` theo nhip timer.

Ba lop bao ve:

1. **Bounded queue**: toi da ``max_queue`` thong bao cho; phan du bi bo kem
   chan doan. Khong bao gio giu mang khong gioi han trong RAM.
2. **Dedup** theo id (ke ca khi producer gui lai nhieu lan trong mot phien),
   va ``seen`` ben vung do ``state`` quan ly.
3. **Rate limit**: toi da ``max_per_window`` thong bao trong ``window`` giay.
   Khi vuot, thong bao van o trong queue (khong mat) va duoc phat sau.

Tat ca ham nhan ``now`` (epoch giay) de test tat dinh.

Diem quan trong: **khong** tu goi AI, khong mo mang, khong chay lenh, khong
doc file. ``Dispatcher`` chi nhan du lieu da duoc ``Inbox``/nguon da validate.
"""

import time

from gifpet.notifications.models import PetNotification
from gifpet.notifications.protocol import NotificationSource

DEFAULT_MAX_QUEUE = 32
DEFAULT_MAX_PER_WINDOW = 3
DEFAULT_WINDOW_SECONDS = 10.0
DEFAULT_DISPLAY_SECONDS = 8.0

# Chan doan: chi giu vai mau gan nhat, khong phai bang log.
MAX_DIAGNOSTICS = 10


class Dispatcher:
    """Nhan thong bao tu nguon, giu hang doi ngan va phat theo nhip."""

    def __init__(self, state, max_queue=DEFAULT_MAX_QUEUE,
                 max_per_window=DEFAULT_MAX_PER_WINDOW,
                 window=DEFAULT_WINDOW_SECONDS, clock=None):
        self.state = state
        self.max_queue = max(1, int(max_queue))
        self.max_per_window = max(1, int(max_per_window))
        self.window = max(0.0, float(window))
        self._clock = clock or time.time

        self._queue = []              # list[PetNotification]
        self._queued_ids = set()
        self._recent_release = []     # moc phat gan day (epoch giay)
        self.diagnostics = []         # (epoch, ma loi, chi tiet ngan)
        self.dropped_count = 0
        self.duplicate_count = 0
        self.expired_count = 0
        self.source_errors = {}       # source_id -> so lan loi

    # ------------------------------------------------------------------
    # Truy van
    # ------------------------------------------------------------------
    def pending(self):
        return list(self._queue)

    def total_counts(self):
        return {
            "dropped": self.dropped_count,
            "duplicate": self.duplicate_count,
            "expired": self.expired_count,
            "source_errors": sum(self.source_errors.values()),
        }

    def clear(self, reason="reset"):
        """Bo toan bo queue (khi nguoi dung am thong bao hoac tat tinh nang).

        Khong dung ``state.seen``: thong bao da bo khong duoc phat lai tu dia
        neu producer con giu tep, va do la hanh vi co chu dich ("im lang la
        im lang that").
        """
        count = len(self._queue)
        for notification in self._queue:
            self.state.mark_seen(notification.id, save=False)
        self._queue = []
        self._queued_ids = set()
        self._recent_release = []
        if count:
            self._diagnose("cleared", f"{count} thông báo ({reason})")
        return count

    # ------------------------------------------------------------------
    # Nap thong bao
    # ------------------------------------------------------------------
    def offer(self, notification, now=None):
        """Dua mot thong bao vao queue. Tra ve True neu duoc nhan."""
        now = self._clock() if now is None else float(now)
        if not isinstance(notification, PetNotification):
            self._diagnose("bad_item", type(notification).__name__)
            return False
        if not self.state.active():
            # Tat/am: khong xep hang, khong danh dau seen de khi bat lai chi
            # thay thong bao con han (Inbox lo viec loc ``expired``).
            return False
        if notification.expired(now):
            self.expired_count += 1
            self.state.mark_seen(notification.id, save=False)
            return False
        if notification.id in self._queued_ids or self.state.is_seen(notification.id):
            self.duplicate_count += 1
            return False
        if len(self._queue) >= self.max_queue:
            self.dropped_count += 1
            self._diagnose("queue_full", notification.id)
            self.state.mark_seen(notification.id, save=False)
            return False
        self._queue.append(notification)
        self._queued_ids.add(notification.id)
        return True

    def offer_many(self, notifications, now=None):
        accepted = 0
        for notification in notifications or ():
            if self.offer(notification, now=now):
                accepted += 1
        return accepted

    def collect(self, registry, limit=None, now=None):
        """Poll moi nguon, cach ly loi tung nguon. Tra ve so thong bao nhan.

        Mot nguon loi (exception, du lieu sai) chi bi ghi chan doan va bo qua;
        cac nguon khac van chay. Nguon khong duoc tai dong tu du lieu.
        """
        now = self._clock() if now is None else float(now)
        limit = self.max_queue if limit is None else int(limit)
        accepted = 0
        for source in registry.sources():
            source_id = getattr(source, "source_id", "?")
            try:
                items = source.poll(limit)
            except Exception as exc:  # nguon hong khong duoc giet dispatcher
                self.source_errors[source_id] = self.source_errors.get(source_id, 0) + 1
                self._diagnose("source_error", f"{source_id}: {type(exc).__name__}")
                continue
            if not isinstance(items, (list, tuple)):
                self._diagnose("source_bad_return", source_id)
                continue
            for item in items[:limit]:
                if self.offer(item, now=now):
                    accepted += 1
        return accepted

    # ------------------------------------------------------------------
    # Phat
    # ------------------------------------------------------------------
    def _release_allowed(self, now):
        cutoff = now - self.window
        self._recent_release = [m for m in self._recent_release if m > cutoff]
        return len(self._recent_release) < self.max_per_window

    def next_display(self, now=None):
        """Lay thong bao tiep theo de hien thi, hoac None.

        Thong bao het han tai thoi diem phat bi bo qua va danh dau seen (de
        khong doc lai tep).

        ``rate limit`` chi anh huong viec phat; thuong thi queue ngan nen
        chenh lech vai giay la chap nhan duoc.
        """
        now = self._clock() if now is None else float(now)
        if not self.state.active():
            if self._queue:
                self.clear("tắt/âm thông báo")
            return None
        if not self._queue:
            return None
        if not self._release_allowed(now):
            return None
        while self._queue:
            notification = self._queue.pop(0)
            self._queued_ids.discard(notification.id)
            if notification.expired(now):
                self.expired_count += 1
                self.state.mark_seen(notification.id, save=False)
                continue
            self._recent_release.append(now)
            self.state.mark_seen(notification.id)
            self.state.add_history(notification)
            return notification
        return None

    # ------------------------------------------------------------------
    # Chan doan
    # ------------------------------------------------------------------
    def _diagnose(self, code, detail=""):
        self.diagnostics.append((self._clock(), code, str(detail)[:120]))
        if len(self.diagnostics) > MAX_DIAGNOSTICS:
            del self.diagnostics[: len(self.diagnostics) - MAX_DIAGNOSTICS]

    def describe(self):
        """Chuoi mot dong cho UI: hang doi/thong ke ngan."""
        counts = self.total_counts()
        return (
            f"Đang chờ: {len(self._queue)} · trùng: {counts['duplicate']} · "
            f"hết hạn: {counts['expired']} · bỏ: {counts['dropped']}"
        )


class MemorySource(NotificationSource):
    """Nguon trong RAM de test/nguon tich hop khong can file.

    Khong dung cho producer ben ngoai: chi code trusted moi tao duoc, nen day
    la duong mo rong an toan (khong co duong dan/payload).
    """

    def __init__(self, source_id="memory", display_name="Bộ nhớ tạm", items=None):
        self.source_id = source_id
        self.display_name = display_name
        self.items = list(items or [])

    def push(self, notification):
        self.items.append(notification)

    def poll(self, limit):
        taken = self.items[:limit]
        del self.items[:limit]
        return taken
