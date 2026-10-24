"""Hop dong cho nguon thong bao.

Mot nguon la mot lop Python **duoc dang ky bang code trusted** (xem
``registry``), khong phai plugin tai dong. Nguon khong duoc doc payload roi
import module, khong duoc chay lenh, khong duoc mo URL.

Hop dong toi thieu:

    source_id   : str            - id duy nhat, chu thuong
    display_name: str            - ten hien thi cho nguoi dung
    poll(limit) -> list          - tra ve ``PetNotification`` (toi da ``limit``)

Neu nguon loi thi dispatcher chi bo qua nguon do, khong lam chet nguon khac.
"""

from gifpet.notifications.models import valid_source_id


class NotificationSource:
    """Lop co so cho nguon thong bao. Chi de hien thi, khong thuc thi."""

    source_id = "unnamed"
    display_name = "Nguồn không tên"

    def poll(self, limit):
        """Tra ve toi da ``limit`` thong bao moi. Mac dinh: khong co gi."""
        return []

    def id_problem(self):
        """Ly do id khong hop le, hoac None neu hop le."""
        if not valid_source_id(self.source_id):
            return f"id nguon khong hop le: {self.source_id!r}"
        return None


def describe(source):
    """Thong tin ngan de hien trong danh sach nguon cua UI."""
    name = getattr(source, "display_name", "") or source.source_id
    return f"{name} ({source.source_id})"
