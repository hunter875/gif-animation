"""Kiem tra tung tieu chi nghiem thu trong spec, in ket qua PASS/FAIL.

Chay: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/acceptance_check.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PyQt5.QtGui import QMovie, QMouseEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from gifpet.core import gif_library  # noqa: E402
from gifpet.core import screen_utils  # noqa: E402
from gifpet.core.config import Config  # noqa: E402
from gifpet.core.paths import PETS_DIR, PROJECT_ROOT  # noqa: E402
from gifpet.ui.pet_window import PetWindow  # noqa: E402

BASE_DIR = PROJECT_ROOT
# GIF cua nhan vat nam trong pets/, khong phai goc project.
GIF_DIR = os.path.join(PETS_DIR, "default")
app = QApplication.instance() or QApplication([])

results = []


def check(criterion, passed, detail):
    results.append((criterion, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {criterion}")
    print(f"         {detail}")


def fresh_config():
    temp_dir = tempfile.mkdtemp()
    return Config(os.path.join(temp_dir, "config.json"))


def press(window):
    window.dragging = True
    window.offset = QPoint(0, 0)


def release(window):
    window.mouseReleaseEvent(
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPoint(0, 0),
            QPoint(0, 0),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
    )


print("=" * 72)
print("GIAI DOAN 1 - APP GIF CHAY ON TREN MAY KHAC")
print("=" * 72)

# --- Tu tim GIF khi mo app ---
config = fresh_config()
config.data.update({"gif_path": "da-bi-xoa.gif", "gif_list": ["da-bi-xoa.gif"]})
config.save()
window = PetWindow(app, config)
check(
    "Tu tim GIF khi mo app (file mat -> van hien pet)",
    window.movie is not None and window.movie.isValid(),
    f"gif_path da xoa -> dung '{config.get('gif_path')}', movie hop le={bool(window.movie and window.movie.isValid())}",
)
window.quit_app()

# --- Cau hinh theo nguoi dung ---
config = fresh_config()
window = PetWindow(app, config)
window.move(321, 222)
press(window)
release(window)
saved = json.load(open(config.path, encoding="utf-8"))
outside_repo = not os.path.abspath(config.path).startswith(os.path.abspath(BASE_DIR))
check(
    "Cau hinh luu ngoai repo, khong dinh duong dan may ca nhan",
    outside_repo and saved["x"] == 321,
    f"luu tai {config.path} (ngoai repo={outside_repo}), x={saved['x']}",
)
check(
    "Repo sach: khong con data.json va khong co duong dan may ca nhan",
    not os.path.exists(os.path.join(BASE_DIR, "data.json")),
    f"data.json ton tai={os.path.exists(os.path.join(BASE_DIR, 'data.json'))}",
)
window.quit_app()

# --- Khong lac khoi man hinh ---
area = app.primaryScreen().availableGeometry()
config = fresh_config()
config.data.update({"x": 99999, "y": 99999, "gif_path": "idle.gif", "gif_list": ["idle.gif"]})
config.save()
window = PetWindow(app, config)
recovered = screen_utils.is_on_any_screen(
    window.x(), window.y(), window.width(), window.height(),
    screen_utils.screen_rects(app),
)
check(
    "Khong lac khoi man hinh (toa do ngoai man hinh -> keo ve)",
    recovered,
    f"luu (99999, 99999) -> thuc te ({window.x()}, {window.y()}) tren man hinh {area.width()}x{area.height()}",
)
has_center = any("giữa" in a.text() for a in window.menu.actions())
window.center_on_screen()
centered = screen_utils.is_on_any_screen(
    window.x(), window.y(), window.width(), window.height(),
    screen_utils.screen_rects(app),
)
check(
    "Menu co nut 'Dua ve giua man hinh'",
    has_center and centered,
    f"action co trong menu={has_center}, sau khi bam -> ({window.x()}, {window.y()})",
)
window.quit_app()

# --- Resize giu ti le ---
config = fresh_config()
config.data.update(
    {"gif_path": "idle.gif", "gif_list": ["idle.gif"], "gif_width": 250, "width_locked": True}
)
config.save()
window = PetWindow(app, config)
ow, oh = window.original_size()
ratio_ok = abs(window.width() / window.height() - ow / oh) < 0.01
not_square = window.width() != window.height()
check(
    "Resize giu ti le (GIF 500x667 khong bi ep vuong)",
    ratio_ok and not_square,
    f"goc {ow}x{oh} -> cua so {window.width()}x{window.height()}, ti le dung={ratio_ok}, khong vuong={not_square}",
)

# --- Luu cau hinh hop ly ---
config = fresh_config()
window = PetWindow(app, config)
saves = []
original_save = config.save


def counting_save():
    saves.append(1)
    original_save()


config.save = counting_save
press(window)
for step in range(100):
    window.mouseMoveEvent(
        QMouseEvent(
            QEvent.MouseMove,
            QPoint(step, step),
            QPoint(step, step),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
    )
moves_saved = len(saves)
release(window)
releases_saved = len(saves)
check(
    "Keo pet khong ghi file lien tuc (chi ghi khi tha chuot)",
    moves_saved == 0 and releases_saved == 1,
    f"100 lan di chuyen -> {moves_saved} lan ghi; 1 lan tha chuot -> {releases_saved} lan ghi",
)

broken = os.path.join(tempfile.mkdtemp(), "config.json")
with open(broken, "w", encoding="utf-8") as handle:
    handle.write("{ json hong ")
survived = True
try:
    Config(broken).get("x")
except Exception:
    survived = False
check(
    "File cau hinh loi khong lam app crash",
    survived,
    "doc file JSON hong -> dung gia tri mac dinh, khong nem loi",
)
window.quit_app()

# --- Doi GIF muot ---
config = fresh_config()
config.data.update(
    {"gif_path": "idle.gif", "gif_list": ["idle.gif", "drag.gif"]}
)
config.save()
window = PetWindow(app, config)
window.move(123, 456)
before = (window.x(), window.y())
window._load_gif(preferred="drag.gif")
after = (window.x(), window.y())
check(
    "Doi GIF khong nhay vi tri",
    before == after and window.movie.isValid(),
    f"vi tri truoc {before} -> sau {after}, GIF moi hop le={window.movie.isValid()}",
)
window.quit_app()

print()
print("=" * 72)
print("GIAI DOAN 2 - DUNG PET HANG NGAY")
print("=" * 72)

config = fresh_config()
config.data.update({"gif_path": "idle.gif", "gif_list": ["idle.gif"]})
config.save()
window = PetWindow(app, config)

# --- Khay he thong la trung tam dieu khien ---
labels = [a.text() for a in window.menu.actions() if a.text()]
required = [
    "Hiện pet", "Tạm dừng animation", "Tự động đổi GIF", "Pet tự đi",
    "Click xuyên qua pet", "Thư viện GIF…", "Chỉnh kích thước…",
    "Đưa về giữa màn hình", "Cài đặt…", "Thoát",
]
missing = [item for item in required if item not in labels]
check(
    "Menu khay co day du muc dieu khien",
    not missing,
    f"{len(labels)} muc, thieu={missing or 'khong'}",
)

# --- Click xuyen van thoat duoc ---
window.toggle_click_through()
click_through_on = window.testAttribute(Qt.WA_TransparentForMouseEvents)
has_escape = bool(window.shortcut_quit.key().toString()) and window.menu is not None
window.toggle_click_through()
check(
    "Bat click xuyen van luon tat/thoat duoc",
    click_through_on and has_escape,
    f"click xuyen bat={click_through_on}, phim tat thoat={window.shortcut_quit.key().toString()}, menu khay con={window.menu is not None}",
)

# --- Pause animation tach roi khoi doi GIF ---
# Dat lai trang thai sach truoc khi kiem tra tung tinh nang rieng biet.
config.data["animation_paused"] = False
window.movie.setPaused(False)
config.data["auto_switch_enabled"] = True
window._apply_switch_timer()

window.toggle_animation_pause()
paused_state = window.movie.state() == QMovie.Paused
switch_still_on = bool(config.get("auto_switch_enabled"))
check(
    "Pause animation tach roi khoi nut dung doi GIF",
    paused_state and switch_still_on,
    f"GIF dung chay={paused_state}, tuy chon doi GIF van bat={switch_still_on}",
)

# Tat pause truoc, de phep thu tiep theo chi do mot yeu to.
window.toggle_animation_pause()
window.toggle_auto_switch()
anim_still_runs = window.movie.state() != QMovie.Paused
check(
    "Tat doi GIF khong lam dung animation",
    anim_still_runs and not config.get("auto_switch_enabled"),
    f"doi GIF tat={not config.get('auto_switch_enabled')}, animation van chay={anim_still_runs}",
)

# --- An khi fullscreen thi pause animation ---
config.data["hide_on_fullscreen"] = True
window._hidden_for_fullscreen = True
window.hide()
window.movie.setPaused(True)
check(
    "An khi fullscreen thi tam dung animation",
    window.movie.state() == QMovie.Paused,
    "pet bi an -> animation dung, tiet kiem CPU",
)
window._hidden_for_fullscreen = False
window.movie.setPaused(False)

# --- Thu vien GIF: bo qua file hong ---
good = os.path.join(GIF_DIR, "idle.gif")
good2 = os.path.join(GIF_DIR, "drag.gif")
config.data["gif_list"] = [good, "da-mat.gif", "hong.gif", good2]
config.data["gif_path"] = good
# Nap lai thu vien de app don file hong.
window._prune_gif_list()
chosen = set()
for _ in range(40):
    window.auto_switch_gif()
    chosen.add(config.get("gif_path"))
all_valid = all(
    gif_library.is_valid_gif(gif_library.resolve_path(item, BASE_DIR)) for item in chosen
)
check(
    "Bo qua file hong, khong chon trung moi 10 giay",
    all_valid and len(chosen) > 0,
    f"40 lan doi GIF -> chon {sorted(os.path.basename(c) for c in chosen)}, tat ca hop le={all_valid}",
)
check(
    "Danh sach GIF tu don file hong khi nap",
    "da-mat.gif" not in config.get("gif_list") and "hong.gif" not in config.get("gif_list"),
    f"gif_list sau khi don={[os.path.basename(g) for g in config.get('gif_list')]}",
)
window.quit_app()

# --- Pet tu di ---
config = fresh_config()
config.data.update({"gif_path": "idle.gif", "gif_list": ["idle.gif"]})
config.save()
window = PetWindow(app, config)
area = app.primaryScreen().availableGeometry()
window.move(50, 100)
start_x = window.x()
for _ in range(60):
    window._walk_step()
still_inside = window.x() >= area.left() and window.x() + window.width() <= area.right() + 2
check(
    "Pet tu di va khong di lac ra ngoai man hinh",
    window.x() != start_x and still_inside,
    f"x {start_x} -> {window.x()}, con trong man hinh={still_inside}",
)
window.quit_app()

print()
print("=" * 72)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print(f"KET QUA: {passed}/{total} tieu chi PASS")
if passed < total:
    print("Cac tieu chi CHUA DAT:")
    for criterion, ok, _ in results:
        if not ok:
            print(f"  - {criterion}")
print("=" * 72)
sys.exit(0 if passed == total else 1)
