"""Tinh toan vi tri pet tren cac man hinh.

Xu ly truong hop toa do da luu nam ngoai moi man hinh (vi du: rut man hinh
phu, hoac copy cau hinh tu may co do phan giai khac) thi keo pet ve man hinh
chinh.
"""

from PyQt5.QtCore import QPoint, QRect


def screen_rects(app):
    """Danh sach vung hien thi cua tat ca man hinh."""
    rects = []
    for screen in app.screens():
        rects.append(QRect(screen.availableGeometry()))
    return rects


def is_on_any_screen(x, y, width, height, rects, min_visible=40):
    """True neu con mot phan du lon cua pet nam trong man hinh nao do.

    Nguong ``min_visible`` tu dong giam voi pet nho, neu khong mot pet 5x5
    hop le se bi coi la lac va bi keo ve giua man hinh moi lan mo app.
    """
    if not rects:
        return True
    width = max(1, int(width))
    height = max(1, int(height))
    # Voi pet nho hon nguong, yeu cau thay toan bo pet la du.
    required_width = min(min_visible, width)
    required_height = min(min_visible, height)
    pet = QRect(int(x), int(y), width, height)
    for rect in rects:
        overlap = rect.intersected(pet)
        if overlap.width() >= required_width and overlap.height() >= required_height:
            return True
    return False


def clamp_to_primary(app, x, y, width, height):
    """Dua pet ve giua man hinh chinh, dam bao nam gon trong vung hien thi."""
    screen = app.primaryScreen()
    if screen is None:
        return int(x), int(y)
    area = QRect(screen.availableGeometry())
    return center_in(area, width, height)


def center_in(area, width, height):
    """Toa do de pet nam giua vung ``area``."""
    width = max(1, int(width))
    height = max(1, int(height))
    x = area.x() + (area.width() - width) // 2
    y = area.y() + (area.height() - height) // 2
    return x, y


def ensure_visible(app, x, y, width, height):
    """Tra ve toa do an toan: giu nguyen neu con thay duoc, nguoc lai ve giua."""
    rects = screen_rects(app)
    if is_on_any_screen(x, y, width, height, rects):
        return int(x), int(y)
    return clamp_to_primary(app, x, y, width, height)


def center_on_primary(app, width, height):
    """Toa do giua man hinh chinh."""
    screen = app.primaryScreen()
    if screen is None:
        return 0, 0
    return center_in(QRect(screen.availableGeometry()), width, height)


def default_position(app, width, height, margin=40):
    """Cho ngoi ban dau cho pet: goc duoi-trai man hinh chinh.

    Chon goc duoi-trai vi do la cho desktop pet thuong dung, va quan trong hon:
    con du cho phia tren de hien bong bong thoai.
    """
    screen = app.primaryScreen()
    if screen is None:
        return 0, 0
    area = QRect(screen.availableGeometry())
    width = max(1, int(width))
    height = max(1, int(height))

    x = area.left() + margin
    y = area.bottom() - height - margin

    # Man hinh qua nho: kep lai cho vua.
    x = max(area.left(), min(x, area.right() - width))
    y = max(area.top(), min(y, area.bottom() - height))
    return x, y
