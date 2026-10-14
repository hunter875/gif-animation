"""Logic roi khi tha pet giua khong trung (Giai doan 3).

Thuan tuy tinh toan: nhan vi tri va vung man hinh, tra ve vi tri moi va trang
thai tiep theo. Khong phu thuoc Qt nen test duoc de dang.
"""


class FallSimulator:
    """Mo phong pet roi xuong mpet duoi man hinh.

    Chuyen dong nhanh dan de trong tu nhien, nhung co gioi han toc do toi da
    de khong vuot qua mat.
    """

    def __init__(self, gravity=2.2, max_speed=28.0, start_speed=2.0):
        self.gravity = float(gravity)
        self.max_speed = float(max_speed)
        self.start_speed = float(start_speed)
        self.speed = self.start_speed

    def reset(self):
        self.speed = self.start_speed

    def next_y(self, current_y, pet_height, ground_y):
        """Vi tri y ke tiep.

        Tra ve ``(y_moi, da_tiep_dat)``. ``ground_y`` la mpet duoi cung ma pet
        duoc phep cham (thuong la day vung lam viec cua man hinh).
        """
        self.speed = min(self.max_speed, self.speed + self.gravity)
        new_y = current_y + self.speed
        landing_y = ground_y - pet_height
        if new_y >= landing_y:
            return landing_y, True
        return new_y, False


def near_ground(y, pet_height, ground_y, tolerance=60):
    """True neu pet dang o gan mat dat, tha ra thi khong can roi."""
    return (y + pet_height) >= (ground_y - tolerance)


def ground_y_for_screen(app):
    """mpet duoi cua vung lam viec tren man hinh chinh."""
    screen = app.primaryScreen()
    if screen is None:
        return 0
    return screen.availableGeometry().bottom()
