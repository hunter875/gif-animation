"""Nhan va hien thi thong bao tu cac nguon mo rong.

Pham vi chot ngay 24/10/2026: pet chi **nhan va hien thi** thong bao.
Khong co giao viec, khong chay task, khong goi model, khong mo URL, khong
doc file ngoai thu muc inbox.

Cac module cua goi nay deu thuan Python (khong import Qt):

- ``models``     : ``PetNotification`` - du lieu da validate, plain text.
- ``protocol``   : ``NotificationSource`` - hop dong cho moi nguon.
- ``registry``   : dang ky nguon trusted bang code, tu choi id trung.
- ``inbox``      : doc file JSON trong thu muc chuyen dung (gioi han chat).
- ``sender``     : ghi mot thong bao ra inbox theo kieu atomic.
- ``state``      : dedup/history ben vung, co gioi han.
- ``dispatcher`` : hang doi bounded, rate limit, han dung, dedup.
- ``controller`` : noi dispatcher voi timer/UI (chi module nay biet chut it
  ve ham hien thi; van khong import Qt).

Muc dich cua thong bao la **hien thi**. Ten nguon va noi dung la du lieu
khong dang tin: khong bao gio duoc dien giai thanh hanh dong.
"""

from gifpet.notifications.models import PetNotification, SEVERITIES
from gifpet.notifications.protocol import NotificationSource
from gifpet.notifications.registry import NotificationRegistry

__all__ = [
    "PetNotification",
    "SEVERITIES",
    "NotificationSource",
    "NotificationRegistry",
]
