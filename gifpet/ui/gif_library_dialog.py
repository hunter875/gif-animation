"""Dialog quan ly thu vien GIF: xem thumbnail, them, xoa, chon GIF."""

import os

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QMovie, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from gifpet.core.gif_library import is_valid_gif, normalize_path, resolve_path

THUMB = 96


def gif_thumbnail(path, size=THUMB):
    """Lay khung dau tien cua GIF lam thumbnail, tra ve QPixmap hoac None."""
    if not is_valid_gif(path):
        return None
    movie = QMovie(path)
    movie.jumpToFrame(0)
    pixmap = movie.currentPixmap()
    if pixmap.isNull():
        return None
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class GifLibraryDialog(QDialog):
    """Cho phep nguoi dung quan ly va chon GIF cu the."""

    def __init__(self, entries, current, base_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thư viện GIF")
        self.setMinimumSize(460, 420)
        self.base_dir = base_dir
        self.selected = None
        self.entries = list(entries or [])

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget(self)
        self.list_widget.setIconSize(QSize(THUMB, THUMB))
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.list_widget)

        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Thêm GIF…", self)
        self.btn_add.clicked.connect(self.add_gifs)
        self.btn_remove = QPushButton("Xóa khỏi danh sách", self)
        self.btn_remove.clicked.connect(self.remove_selected)
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self._accept_selection)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._reload(current)

    def _reload(self, current=None):
        self.list_widget.clear()
        missing = 0
        for entry in self.entries:
            resolved = resolve_path(entry, self.base_dir)
            valid = is_valid_gif(resolved)
            if not valid:
                missing += 1
            label = os.path.basename(resolved) or entry
            if not valid:
                label += "   (không tìm thấy / file hỏng)"
            item = QListWidgetItem(label)
            thumb = gif_thumbnail(resolved)
            if thumb is not None:
                item.setIcon(QIcon(thumb))
            item.setData(Qt.UserRole, entry)
            item.setToolTip(resolved)
            self.list_widget.addItem(item)
            if current is not None and entry == current:
                self.list_widget.setCurrentItem(item)

        if self.list_widget.currentRow() < 0 and self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

        if missing:
            self.status.setText(
                f"{missing} mục không dùng được (file đã mất hoặc hỏng). "
                "Chọn một mục rồi bấm “Xóa khỏi danh sách” để dọn."
            )
        else:
            self.status.setText(f"{self.list_widget.count()} GIF trong thư viện.")

    def _on_selection_changed(self, current, _previous):
        if current is None:
            return
        entry = current.data(Qt.UserRole)
        resolved = resolve_path(entry, self.base_dir)
        if not is_valid_gif(resolved):
            self.status.setText(f"Không dùng được: {resolved}")
        else:
            size = gif_thumbnail(resolved, 512)
            if size is not None:
                self.status.setText(
                    f"{os.path.basename(resolved)} — {size.width()}×{size.height()} px"
                )
            else:
                self.status.setText(os.path.basename(resolved))

    def add_gifs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn GIF để thêm", self.base_dir, "GIF Files (*.gif)"
        )
        added = 0
        for path in files:
            if not is_valid_gif(path):
                continue
            stored = normalize_path(path, self.base_dir)
            if stored not in self.entries:
                self.entries.append(stored)
                added += 1
        if added:
            self._reload(self.list_widget.currentItem().data(Qt.UserRole)
                         if self.list_widget.currentItem() else None)

    def remove_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        entry = item.data(Qt.UserRole)
        if entry in self.entries:
            self.entries.remove(entry)
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        self._reload(None)

    def _accept_selection(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self.selected = item.data(Qt.UserRole)
        self.accept()

    def result_entries(self):
        return self.entries
