"""Cac dialog cai dat: kich thuoc giu ti le, va cai dat chung."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from gif_library import scaled_size


class ResizeDialog(QDialog):
    """Chinh kich thuoc GIF nhung giu nguyen ti le khung hinh."""

    def __init__(self, original_width, original_height, current_width, lock_width, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉnh kích thước")
        self.original_width = max(1, int(original_width or 1))
        self.original_height = max(1, int(original_height or 1))

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.orientation = QComboBox(self)
        self.orientation.addItem("Theo chiều rộng", True)
        self.orientation.addItem("Theo chiều cao", False)
        self.orientation.setCurrentIndex(0 if lock_width else 1)
        self.orientation.currentIndexChanged.connect(self._refresh_preview)

        self.spin = QSpinBox(self)
        self.spin.setRange(10, 2000)
        self.spin.setValue(max(10, int(current_width or self.original_width)))
        self.spin.setSuffix(" px")
        self.spin.valueChanged.connect(self._refresh_preview)

        form.addRow("Căn theo:", self.orientation)
        form.addRow("Kích thước:", self.spin)
        layout.addLayout(form)

        self.keep_ratio = QCheckBox("Giữ tỉ lệ khung hình", self)
        self.keep_ratio.setChecked(True)
        self.keep_ratio.stateChanged.connect(self._refresh_preview)
        layout.addWidget(self.keep_ratio)

        self.preview = QLabel("", self)
        layout.addWidget(self.preview)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._refresh_preview()

    def _refresh_preview(self):
        width, height = self.target_size()
        text = f"Kết quả: {width} × {height} px   (gốc {self.original_width} × {self.original_height})"
        if self.keep_ratio.isChecked():
            ratio = self.original_height / self.original_width
            text += f"\nTỉ lệ gốc {ratio:.3f} được giữ nguyên."
        else:
            text += "\nCảnh báo: bỏ giữ tỉ lệ sẽ làm GIF bị méo."
        self.preview.setText(text)

    def target_size(self):
        """Kich thuoc (width, height) theo lua chon hien tai."""
        target = self.spin.value()
        lock_width = bool(self.orientation.currentData())
        if self.keep_ratio.isChecked():
            return scaled_size(self.original_width, self.original_height, target, lock_width)
        if lock_width:
            return max(1, target), self.original_height
        return self.original_width, max(1, target)

    def values(self):
        width, height = self.target_size()
        return width, height, bool(self.orientation.currentData())


class SettingsDialog(QDialog):
    """Dialog cai dat hanh vi cua pet."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.auto_switch = QCheckBox("Tự động đổi GIF", self)
        self.auto_switch.setChecked(bool(config.get("auto_switch_enabled")))
        form.addRow(self.auto_switch)

        self.interval = QSpinBox(self)
        self.interval.setRange(2, 600)
        self.interval.setSuffix(" giây")
        self.interval.setValue(int(config.get("auto_switch_seconds", 10)))
        form.addRow("Đổi GIF mỗi:", self.interval)

        self.auto_walk = QCheckBox("Pet tự đi", self)
        self.auto_walk.setChecked(bool(config.get("auto_walk")))
        form.addRow(self.auto_walk)

        self.click_through = QCheckBox("Click xuyên qua pet", self)
        self.click_through.setChecked(bool(config.get("click_through")))
        form.addRow(self.click_through)

        self.hide_fullscreen = QCheckBox("Ẩn khi có ứng dụng toàn màn hình", self)
        self.hide_fullscreen.setChecked(bool(config.get("hide_on_fullscreen")))
        form.addRow(self.hide_fullscreen)

        self.pin = QCheckBox("Luôn nổi trên cùng", self)
        self.pin.setChecked(bool(config.get("pin_to_top")))
        form.addRow(self.pin)

        layout.addLayout(form)

        note = QLabel(
            "Khi bật “Click xuyên qua pet”, chuột sẽ không bấm được vào pet. "
            "Dùng khay hệ thống hoặc phím tắt để tắt lại.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def values(self):
        return {
            "auto_switch_enabled": self.auto_switch.isChecked(),
            "auto_switch_seconds": self.interval.value(),
            "auto_walk": self.auto_walk.isChecked(),
            "click_through": self.click_through.isChecked(),
            "hide_on_fullscreen": self.hide_fullscreen.isChecked(),
            "pin_to_top": self.pin.isChecked(),
        }
