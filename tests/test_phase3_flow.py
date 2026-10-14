"""Kich ban end-to-end cua Giai doan 3.

Mo phong day du vong doi: tu di -> nghi -> bi keo -> tha -> roi -> tiep dat ->
click -> phan ung. Chay khong can man hinh.

Chay: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_phase3_flow.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PyQt5.QtGui import QMouseEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core import falling  # noqa: E402
from gifpet.core import state as state_module  # noqa: E402
from gifpet.core.config import Config  # noqa: E402
from gifpet.ui.pet_window import PetWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
results = []


def check(label, passed, detail=""):
    results.append((label, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def fresh_window(**overrides):
    temp_dir = tempfile.mkdtemp()
    config = Config(os.path.join(temp_dir, "config.json"))
    config.data.update({"auto_walk": True, "walk_speed": 4})
    config.data.update(overrides)
    config.save()
    return config, PetWindow(app, config)


def press(window, pos=None):
    point = pos or window.pos()
    window.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(0, 0),
            point,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
    )


def move(window, pos):
    window.mouseMoveEvent(
        QMouseEvent(
            QEvent.MouseMove,
            QPoint(0, 0),
            pos,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
    )


def release(window, pos=None):
    point = pos or window.pos()
    window.mouseReleaseEvent(
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPoint(0, 0),
            point,
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
    )


print("=" * 70)
print("GIAI DOAN 3 - VONG DOI DESKTOP PET")
print("=" * 70)

# --- 1. Mac dinh la idle ---
config, window = fresh_window()
check(
    "Mo app: pet o trang thai idle",
    window.state == state_module.IDLE,
    f"state={window.state}, animation={os.path.basename(window._current_resolved_path or '')}",
)

# --- 2. Tu di roi nghi ---
start_x = window.x()
now = window.now_ms()
window.behavior.note_interaction(now)
# Chot moc khoi dong, roi cho qua thoi gian nghi ngan.
window.behavior.ensure_started(now)
window.behavior._pause_until_ms = now
window.behavior.idle_tick(window.machine, now + 100)
walking = window.state == state_module.WALK
moved_before = window.x()
for _ in range(40):
    window._walk_step()
moved_after = window.x()
check(
    "Pet tu di",
    walking and moved_after != moved_before,
    f"state={window.state}, x {moved_before} -> {moved_after}",
)

window.behavior.walk_tick(window.machine, window.now_ms() + 999_999)
check(
    "Di xong thi dung lai nghi",
    window.state == state_module.IDLE,
    f"state={window.state}",
)

# --- 3. Di cham bien thi quay dau ---
area = app.primaryScreen().availableGeometry()
window.machine.request(state_module.WALK, force=True)
window.walk_direction = -1
window.move(area.left(), window.y())
window._walk_step()
turned = window.walk_direction == 1
check(
    "Cham bien trai thi quay dau, khong di mat",
    turned and window.x() >= area.left(),
    f"huong moi={window.walk_direction}, x={window.x()} (bien trai={area.left()})",
)

# --- 4. Keo: vung vay, khong cho ngu ---
# Bam roi nha khong keo la click; phai di chuyen moi tinh la keo.
press(window)
check(
    "Bam giu ma chua keo: chua vao drag (con la click)",
    window.state != state_module.DRAG,
    f"state={window.state}",
)

drag_from = window.pos()
move(window, QPoint(drag_from.x() + 60, drag_from.y() + 40))
check(
    "Keo chuot: pet vao trang thai drag (vung vay)",
    window.state == state_module.DRAG,
    f"state={window.state}, animation={os.path.basename(window._current_resolved_path or '')}",
)
blocked = not window.machine.can_sleep()
sleep_refused = not window.machine.request(state_module.SLEEP)
check(
    "Dang bi keo: khong the bat di ngu",
    blocked and sleep_refused,
    f"can_sleep={not blocked}, yeu cau ngu bi tu choi={sleep_refused}",
)

# --- 5. Tha giua khong trung: roi ---
window.move(300, 50)
move(window, QPoint(340, 90))
release(window, QPoint(340, 90))
check(
    "Tha giua khong trung: pet roi",
    window.state == state_module.FALL,
    f"state={window.state}, animation={os.path.basename(window._current_resolved_path or '')}",
)

# --- 6. Roi xuong tiep dat ---
landed = False
for _ in range(2000):
    if window.state != state_module.FALL:
        landed = True
        break
    window._fall_step()
ground = falling.ground_y_for_screen(app)
check(
    "Roi xuong va tiep dat",
    landed and window.state == state_module.IDLE,
    f"state={window.state}, y={window.y()}, day pet={window.y() + window.height()}, mat dat={ground}",
)

# --- 7. Dang roi thi khong lam gi khac ---
window.machine.force(state_module.FALL)
refused = []
for other in (state_module.SLEEP, state_module.WALK, state_module.TALK):
    if not window.machine.request(other):
        refused.append(other)
check(
    "Dang roi: moi hanh vi khac deu bi tu choi",
    len(refused) == 3,
    f"bi tu choi: {refused}",
)
window.machine.force(state_module.IDLE)

# --- 8. Click: phan ung ---
before = window.state
press(window)
release(window)
check(
    "Click vao pet: phan ung",
    window.state == state_module.REACT,
    f"state {before} -> {window.state}, animation={os.path.basename(window._current_resolved_path or '')}",
)
window.quit_app()

# --- 9. Che do tap trung ---
config, window = fresh_window()
window.toggle_focus_mode()
check(
    "Bat che do tap trung",
    config.get("focus_mode") and not window.machine.can_walk(),
    f"focus_mode={config.get('focus_mode')}, can_walk={window.machine.can_walk()}",
)

window.machine.force(state_module.WALK)
window.toggle_focus_mode()
check(
    "Tat che do tap trung: pet di lai duoc",
    not config.get("focus_mode") and window.machine.can_walk(),
    f"focus_mode={config.get('focus_mode')}, can_walk={window.machine.can_walk()}",
)
window.quit_app()

# --- 10. Ngu va thuc ---
config, window = fresh_window()
ok = window.send_to_sleep()
check(
    "Cho pet ngu ngay",
    ok and window.state == state_module.SLEEP,
    f"state={window.state}, animation={os.path.basename(window._current_resolved_path or '')}",
)

window.wake_up()
check(
    "Co tuong tac thi thuc day",
    window.state == state_module.IDLE,
    f"state={window.state}",
)

# --- 11. Ngu khi khong tuong tac lau ---
config.data["sleep_after_seconds"] = 5
window.behavior.note_interaction(0)
window.behavior.idle_tick(window.machine, 10_000)
check(
    "Khong tuong tac lau: tu ngu",
    window.state == state_module.SLEEP,
    f"state={window.state}",
)
window.quit_app()

print()
total = len(results)
passed = sum(1 for _, ok in results if ok)
print("=" * 70)
print(f"KET QUA GIAI DOAN 3: {passed}/{total} PASS")
for label, ok in results:
    if not ok:
        print(f"  CHUA DAT: {label}")
print("=" * 70)
sys.exit(0 if passed == total else 1)
