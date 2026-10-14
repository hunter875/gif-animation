"""GIF Pet - desktop pet hien thi GIF trong suot.

Cau truc package:

    gifpet/
        core/       logic thuan tuy, khong phu thuoc UI
            config.py        cau hinh nguoi dung, luu ngoai repo
            gif_library.py   chon GIF hop le, tinh kich thuoc giu ti le
            screen_utils.py  giu pet trong pham vi man hinh
        ui/         giao dien PyQt5
            pet_window.py        cua so pet, menu khay, phim tat
            dialogs.py           dialog resize va cai dat
            gif_library_dialog.py dialog thu vien GIF
    pets/       thu vien nhan vat, moi nhan vat mot thu muc
    tests/      test tu dong

Cac giai doan tiep theo se bo sung:

    gifpet/core/state.py     may trang thai (idle, walk, drag, fall, sleep, react, talk)
    gifpet/core/behavior.py  quy tac chuyen trang thai va uu tien hanh vi
    gifpet/ai/               ket noi model, gioi han hanh dong, bo nho
    gifpet/voice/            speech-to-text va text-to-speech

Xem docs/ARCHITECTURE.md de biet chi tiet.
"""

__version__ = "0.2.0"
