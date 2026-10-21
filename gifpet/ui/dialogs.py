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
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from gifpet.ai import secrets
from gifpet.ai.memory import Memory
from gifpet.core.gif_library import scaled_size


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

        self.focus_mode = QCheckBox("Chế độ tập trung (đứng yên hoặc ngủ)", self)
        self.focus_mode.setChecked(bool(config.get("focus_mode")))
        form.addRow(self.focus_mode)

        self.walk_speed = QSpinBox(self)
        self.walk_speed.setRange(1, 20)
        self.walk_speed.setSuffix(" px/bước")
        self.walk_speed.setValue(max(1, int(config.get("walk_speed", 2))))
        form.addRow("Tốc độ tự đi:", self.walk_speed)

        self.walk_pause = QSpinBox(self)
        self.walk_pause.setRange(0, 100)
        self.walk_pause.setSuffix(" %")
        self.walk_pause.setValue(
            int(round(float(config.get("walk_pause_chance", 0.3)) * 100))
        )
        form.addRow("Tần suất nghỉ dài:", self.walk_pause)

        self.sleep_after = QSpinBox(self)
        self.sleep_after.setRange(5, 3600)
        self.sleep_after.setSuffix(" giây")
        self.sleep_after.setValue(max(5, int(config.get("sleep_after_seconds", 120))))
        form.addRow("Ngủ sau khi rảnh:", self.sleep_after)

        # --- Nhac tap trung / nghi ---
        self.pomodoro = QCheckBox("Nhắc tập trung / nghỉ", self)
        self.pomodoro.setChecked(bool(config.get("pomodoro_enabled")))
        form.addRow(self.pomodoro)

        self.pomodoro_focus = QSpinBox(self)
        self.pomodoro_focus.setRange(1, 180)
        self.pomodoro_focus.setSuffix(" phút")
        self.pomodoro_focus.setValue(max(1, int(config.get("pomodoro_focus_minutes", 25))))
        form.addRow("Thời gian tập trung:", self.pomodoro_focus)

        self.pomodoro_break = QSpinBox(self)
        self.pomodoro_break.setRange(1, 60)
        self.pomodoro_break.setSuffix(" phút")
        self.pomodoro_break.setValue(max(1, int(config.get("pomodoro_break_minutes", 5))))
        form.addRow("Thời gian nghỉ:", self.pomodoro_break)

        self.pomodoro_bubble = QCheckBox("Hiện lời nhắc trong bong bóng thoại", self)
        self.pomodoro_bubble.setChecked(bool(config.get("pomodoro_bubble", True)))
        form.addRow(self.pomodoro_bubble)

        self.pomodoro_notify = QCheckBox("Hiện thông báo khay hệ thống", self)
        self.pomodoro_notify.setChecked(bool(config.get("pomodoro_notify", True)))
        form.addRow(self.pomodoro_notify)

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

        # --- AI (Giai doan 4) ---
        layout.addWidget(QLabel("<b>Trợ lý AI</b>", self))

        ai_form = QFormLayout()

        self.ai_enabled = QCheckBox("Bật trợ lý AI", self)
        self.ai_enabled.setChecked(bool(config.get("ai_enabled")))
        ai_form.addRow(self.ai_enabled)

        self.ai_provider = QComboBox(self)
        self.ai_provider.addItem("Groq", "groq")
        self.ai_provider.addItem("Google Gemini", "gemini")
        index = self.ai_provider.findData(config.get("ai_provider", "groq"))
        self.ai_provider.setCurrentIndex(max(0, index))
        ai_form.addRow("Nhà cung cấp:", self.ai_provider)

        self.ai_model = QLineEdit(self)
        self.ai_model.setPlaceholderText("để trống = model mặc định")
        self.ai_model.setText(str(config.get("ai_model", "") or ""))
        ai_form.addRow("Model:", self.ai_model)

        # API key: o nhap moi, khong dien lai key da luu.
        key_row = QHBoxLayout()
        self.ai_key = QLineEdit(self)
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("dán API key vào đây")
        key_row.addWidget(self.ai_key, 1)
        self.ai_key_clear = QPushButton("Xoá key", self)
        key_row.addWidget(self.ai_key_clear)
        ai_form.addRow("API key:", key_row)

        current_key = secrets.get_api_key()
        if secrets.env_override_active():
            key_note = (
                "Đang dùng key từ biến môi trường GIFPET_API_KEY "
                "(ô trên bị bỏ qua)."
            )
        elif current_key:
            key_note = f"Đã lưu key: {secrets.masked(current_key)}"
        else:
            key_note = "Chưa có key. Key lưu ở file riêng, quyền 0600, không nằm trong config.json."
        self.ai_key_status = QLabel(key_note, self)
        self.ai_key_status.setWordWrap(True)
        ai_form.addRow(self.ai_key_status)

        self.ai_limit = QSpinBox(self)
        self.ai_limit.setRange(0, 5000)
        self.ai_limit.setSuffix(" lượt/ngày")
        self.ai_limit.setValue(max(0, int(config.get("ai_daily_limit", 50))))
        ai_form.addRow("Giới hạn:", self.ai_limit)

        self.ai_proactive = QCheckBox("Pet tự nói (tự gọi model)", self)
        self.ai_proactive.setChecked(bool(config.get("ai_proactive", False)))
        ai_form.addRow(self.ai_proactive)

        layout.addLayout(ai_form)

        # Bo nho: xem va xoa duoc, chi chua ghi chu nguoi dung go tay.
        layout.addWidget(QLabel("<b>Điều pet đã ghi nhớ</b> (bạn tự gõ)", self))
        self.memory = Memory()
        self.memory_view = QPlainTextEdit(self)
        self.memory_view.setReadOnly(True)
        self.memory_view.setMaximumHeight(90)
        self._refresh_memory()
        layout.addWidget(self.memory_view)

        memory_row = QHBoxLayout()
        self.memory_add = QLineEdit(self)
        self.memory_add.setPlaceholderText("ví dụ: tôi thích trà sữa")
        memory_row.addWidget(self.memory_add, 1)
        self.memory_add_button = QPushButton("Thêm", self)
        memory_row.addWidget(self.memory_add_button)
        self.memory_clear = QPushButton("Xoá hết", self)
        memory_row.addWidget(self.memory_clear)
        layout.addLayout(memory_row)

        self.memory_add_button.clicked.connect(self._add_memory)
        self.memory_clear.clicked.connect(self._clear_memory)
        self.ai_key_clear.clicked.connect(self._clear_key)
        self._pending_key = None

        note = QLabel(
            "Khi bật “Click xuyên qua pet”, chuột sẽ không bấm được vào pet. "
            "Dùng khay hệ thống hoặc phím tắt để tắt lại.\n\n"
            "“Chế độ tập trung” giữ pet đứng yên hoặc ngủ, không tự đi lại.\n\n"
            "“Nhắc tập trung / nghỉ” là Pomodoro: hết giờ tập trung pet sẽ nhắc "
            "uống nước, thư giãn mắt. Trong giờ tập trung pet đứng yên.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    # ------------------------------------------------------------------
    # Bo nho va API key
    # ------------------------------------------------------------------
    def _refresh_memory(self):
        entries = self.memory.entries()
        if not entries:
            self.memory_view.setPlainText("(chưa có gì)")
            return
        lines = [f"• {item['text']}" for item in entries]
        self.memory_view.setPlainText("\n".join(lines))

    def _add_memory(self):
        text = self.memory_add.text().strip()
        if not text:
            return
        if self.memory.add(text):
            self.memory_add.clear()
            self._refresh_memory()

    def _clear_memory(self):
        self.memory.clear()
        self._refresh_memory()

    def _clear_key(self):
        self._pending_key = ""
        self.ai_key.clear()
        self.ai_key_status.setText("Key sẽ bị xoá khi bấm OK.")

    def pending_key(self):
        """Gia tri key can ghi, hoac None neu nguoi dung khong doi.

        Tra ve chuoi rong nghia la xoa key.
        """
        if self._pending_key is not None:
            return self._pending_key
        typed = self.ai_key.text().strip()
        return typed if typed else None

    def values(self):
        return {
            "auto_switch_enabled": self.auto_switch.isChecked(),
            "auto_switch_seconds": self.interval.value(),
            "auto_walk": self.auto_walk.isChecked(),
            "focus_mode": self.focus_mode.isChecked(),
            "walk_speed": self.walk_speed.value(),
            "walk_pause_chance": self.walk_pause.value() / 100.0,
            "sleep_after_seconds": self.sleep_after.value(),
            "pomodoro_enabled": self.pomodoro.isChecked(),
            "pomodoro_focus_minutes": self.pomodoro_focus.value(),
            "pomodoro_break_minutes": self.pomodoro_break.value(),
            "pomodoro_bubble": self.pomodoro_bubble.isChecked(),
            "pomodoro_notify": self.pomodoro_notify.isChecked(),
            "ai_enabled": self.ai_enabled.isChecked(),
            "ai_provider": self.ai_provider.currentData(),
            "ai_model": self.ai_model.text().strip(),
            "ai_daily_limit": self.ai_limit.value(),
            "ai_proactive": self.ai_proactive.isChecked(),
            "click_through": self.click_through.isChecked(),
            "hide_on_fullscreen": self.hide_fullscreen.isChecked(),
            "pin_to_top": self.pin.isChecked(),
        }
