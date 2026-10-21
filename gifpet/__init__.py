"""GIF Pet - desktop pet hien thi GIF trong suot.

Cau truc package:

    gifpet/
        core/       logic thuan tuy, khong phu thuoc UI
            config.py        cau hinh nguoi dung, luu ngoai repo
            gif_library.py   chon GIF hop le, tinh kich thuoc giu ti le
            screen_utils.py  giu pet trong pham vi man hinh
            pet_pack.py      thu vien nhan vat, thieu trang thai thi fallback
            state.py         may trang thai 7 trang thai + quy tac uu tien
            behavior.py      vong lap tu di / nghi / ngu
            falling.py       mo phong roi khi tha pet
            pomodoro.py      nhac tap trung / nghi
        ui/         giao dien PyQt5
            pet_window.py        cua so pet, menu khay, phim tat
            speech_bubble.py     bong bong thoai
            dialogs.py           dialog resize va cai dat
            gif_library_dialog.py dialog thu vien GIF
    pets/       thu vien nhan vat, moi nhan vat mot thu muc
    tests/      test tu dong

Giai doan 4 (chua trien khai):

    gifpet/ai/  ket noi model, gioi han hanh dong, bo nho, quota

Giai doan 5 (giong noi) da bo khoi pham vi.

Xem docs/ARCHITECTURE.md de biet chi tiet.
Rang buoc bao mat cua Giai doan 4: docs/SECURITY.md.
"""

__version__ = "0.3.0"
