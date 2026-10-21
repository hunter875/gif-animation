"""Phan UI cho loi nhac hen gio va "pet tu noi".

Tach ra khoi ``pet_window`` vi day la logic nghiep vu (quet hang doi, quyet
dinh khi nao pet duoc len tieng), khong phai ve cua so. Nho vay test duoc ma
khong can mo cua so that.

Cach dung: moi ham nhan ``window`` (PetWindow) lam tham so dau tien.

Logic thuan tuy nam o ``core/reminders.py`` va ``core/proactive.py``; file nay
chi noi chung voi giao dien.
"""


# ----------------------------------------------------------------------
# Loi nhac hen gio
# ----------------------------------------------------------------------
def drop_stale(window):
    """Bo loi nhac qua han qua lau, goi mot lan luc khoi dong."""
    dropped = window.reminders.drop_stale()
    if dropped:
        print(f"Đã bỏ {dropped} lời nhắc quá hạn từ lâu.")


def check_due(window):
    """Quet hang doi: loi nhac nao den gio thi noi ra."""
    for text in window.reminders.pop_due():
        window.announce(text, duration_ms=8000)


def remind_later(window, text, seconds):
    """Hen nhac. Tra ve True neu da luu duoc ra dia."""
    return window.reminders.add(text, seconds)


def pending_count(window):
    return window.reminders.count()


# ----------------------------------------------------------------------
# Pet tu noi (ai_proactive)
# ----------------------------------------------------------------------
# Bao lau khong tuong tac thi coi la "ranh qua lau".
LONG_IDLE_SECONDS = 30 * 60


def collect(window):
    """Ghi nhan su kien dang gom, va goi model khi du dieu kien.

    Ham nay chay moi 100ms (tu ``pet_window._behavior_tick``), nen phai:

    - chi ghi nhan ``long_idle`` **mot lan** cho moi giai doan ranh, khong
      phai moi tick (neu khong se day tran trong vai giay);
    - ton trong ``should_fire`` cua batcher (cua so 60 giay + tran rieng);
    - khong lam gi khi ``ai_proactive`` tat.

    Su kien pet tu di / roi / ngu khong bao gio vao batcher.
    """
    if not window.proactive.enabled():
        return

    idle_seconds = window.behavior.time_since_interaction(window.now_ms()) / 1000.0
    if idle_seconds > LONG_IDLE_SECONDS and not window._long_idle_noted:
        window._long_idle_noted = True
        window.proactive.add(
            "long_idle", f"{int(idle_seconds // 60)} phút không tương tác"
        )
    elif idle_seconds <= LONG_IDLE_SECONDS:
        # Co tuong tac lai: lan sau ranh lai duoc ghi nhan.
        window._long_idle_noted = False

    focusing = bool(window.config.get("focus_mode")) or window.pomodoro.is_focusing()
    should, _reason = window.proactive.should_fire(focusing=focusing)
    if not should:
        return

    events = window.proactive.take()
    content = window.proactive.build_content(events)
    result = window.brain.ask("chat", content)
    if result.ok and result.text:
        window.announce(result.text, duration_ms=6000)
    # Du model loi hay khong, khong thu lai ngay: batcher da danh dau
    # _last_call trong take().
