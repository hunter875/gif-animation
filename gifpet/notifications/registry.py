"""Dang ky nguon thong bao trusted, bang code.

Vi sao khong dung plugin tu dong:

- Nap module tu duong dan hay tu payload la duong tan cong co dien (code
  injection). Pet chi can mot tep nguon nho, viet tay, duoc import trong
  package.
- Nguoi viet nguon khac chi can viet mot lop va goi
  ``registry.register(MySource())`` mot lan (xem ``default_registry``).

Quy tac:

- id trung nhau bi tu choi (ke ca khac lop), de mot nguon khong gia danh
  nguon khac trong history.
- Loi khi ``poll`` khong lam hong cac nguon khac; dispatcher bat rieng.
- Chi chap nhan the hien cua ``NotificationSource``: khong nhan chuoi, dict,
  duong dan, hay bat ky doi tuong "goi duoc" nao.
"""

from gifpet.notifications.protocol import NotificationSource


class RegistryError(ValueError):
    """Nguon khong hop le hoac trung id."""


class NotificationRegistry:
    """Tap hop nguon theo thu tu dang ky (thu tu uu tien poll)."""

    def __init__(self):
        self._sources = {}

    def register(self, source):
        """Dang ky mot nguon. Tra ve chinh ``source`` de tien cho test."""
        if not isinstance(source, NotificationSource):
            raise RegistryError(
                "nguon phai ke thua NotificationSource, khong nhan "
                f"{type(source).__name__}"
            )
        problem = source.id_problem()
        if problem:
            raise RegistryError(problem)
        if not callable(getattr(source, "poll", None)):
            raise RegistryError(f"nguon {source.source_id!r} thieu poll(limit)")
        if source.source_id in self._sources:
            raise RegistryError(f"id nguon trung: {source.source_id}")
        self._sources[source.source_id] = source
        return source

    def unregister(self, source_id):
        return self._sources.pop(source_id, None) is not None

    def get(self, source_id):
        return self._sources.get(source_id)

    def sources(self):
        return list(self._sources.values())

    def ids(self):
        return list(self._sources)

    def __len__(self):
        return len(self._sources)

    def __contains__(self, source_id):
        return source_id in self._sources


def default_registry(*sources):
    """Registry san sang dung: nguon inbox JSON (va sau nay nguon khac).

    Nguon moi chi can them mot dong o day; ``PetWindow`` khong phai sua vi
    controller lap qua danh sach nguon trong registry.
    """
    registry = NotificationRegistry()
    for source in sources:
        if source is not None:
            registry.register(source)
    return registry
