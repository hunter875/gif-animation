from PyQt5.QtWidgets import QApplication, QLabel, QMenu, QAction, QDialog, QVBoxLayout, QSlider, QPushButton, QFileDialog
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import Qt, QSize, QPoint, QTimer
from file_json import FileJson
import random

class TransparentWindow(QLabel):
    def __init__(self):
        super().__init__()
        self.lock1 = False
        self.resizing = False
        self.json = FileJson("data.json")
        self.label = None
        self.init_data()
        self.setup_ui()
        self.start_gif_timer()

    def init_data(self):
        default_values = {
            "x": 0, "y": 0, "pin_to_top": True,
            "size": 30, "gif_path": "abc.gif",
            "gif_width": 200, "gif_height": 200,
            "gif_list": ["abc.gif"]
        }
        for key, value in default_values.items():
            if key not in self.json.data:
                self.json.data[key] = value
        self.json.write_json_file()

    def setup_ui(self):
        self.movie = QMovie(self.json.data["gif_path"])
        if not self.movie.isValid():
            print(f"Error: Cannot load GIF {self.json.data['gif_path']}")
            return
        if self.label is None:
            self.label = QLabel(self)
        self.label.setMovie(self.movie)
        self.scale_gif(self.json.data["gif_width"])
        self.movie.start()
        self.update_styles()
        self.setup_window()

    def update_styles(self):
        self.label.setStyleSheet(f"font-size: {self.json.data['size']}px; border: none;")

    def setup_window(self):
        self.label.resize(self.json.data["gif_width"], self.json.data["gif_height"])
        self.resize(self.json.data["gif_width"], self.json.data["gif_height"])
        self.move(self.json.data['x'], self.json.data['y'])
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.toggle_pin(self.json.data['pin_to_top'])

    def toggle_pin(self, pin):
        flags = self.windowFlags()
        if pin:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.json.data['pin_to_top'] = pin
        self.json.write_json_file()
        self.show()

    def change_gif(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn GIF", "", "GIF Files (*.gif)")
        if file_path:
            self.json.data["gif_path"] = file_path
            if file_path not in self.json.data["gif_list"]:
                self.json.data["gif_list"].append(file_path)
            self.json.write_json_file()
            self.setup_ui()

    def change_size(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Thay đổi kích thước GIF")
        layout = QVBoxLayout(dialog)
        slider_size = QSlider(Qt.Horizontal)
        slider_size.setMinimum(10)
        slider_size.setMaximum(500)
        slider_size.setValue(self.json.data["gif_width"])
        slider_size.valueChanged.connect(lambda value: label_size.setText(f"Kích thước: {value}px"))
        label_size = QLabel(f"Kích thước: {self.json.data['gif_width']}px", dialog)
        btn_ok = QPushButton("OK", dialog)
        btn_ok.clicked.connect(lambda: self.apply_size(slider_size.value(), dialog))
        layout.addWidget(label_size)
        layout.addWidget(slider_size)
        layout.addWidget(btn_ok)
        dialog.setLayout(layout)
        dialog.exec_()

    def apply_size(self, new_size, dialog):
        self.scale_gif(new_size)
        self.json.data["gif_width"] = new_size
        self.json.data["gif_height"] = new_size
        self.json.write_json_file()
        dialog.accept()

    def scale_gif(self, new_size):
        self.movie.setScaledSize(QSize(new_size, new_size))
        self.label.resize(new_size, new_size)
        self.resize(new_size, new_size)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.globalPos() - self.pos()
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.offset)
            self.json.data['x'], self.json.data['y'] = self.x(), self.y()
            self.json.write_json_file()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #333; color: white; }")
        action_toggle_timer = QAction("Stop GIF Switch" if self.timer.isActive() else "Start GIF Switch", self)
        action_toggle_timer.triggered.connect(self.toggle_gif_timer)
        action_pin = QAction("Unpin from top" if self.json.data['pin_to_top'] else "Pin to top", self)
        action_pin.triggered.connect(lambda: self.toggle_pin(not self.json.data['pin_to_top']))
        action_size = QAction("Resize GIF", self)
        action_size.triggered.connect(self.change_size)
        action_gif = QAction("Change GIF", self)
        action_gif.triggered.connect(self.change_gif)
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(QApplication.quit)
        menu.addActions([action_toggle_timer, action_pin, action_size, action_gif, action_exit])
        menu.exec_(position)

    def start_gif_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.switch_gif)
        self.timer.start(10000)

    def toggle_gif_timer(self):
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start(10000)

    def switch_gif(self):
        print("Switching GIF...")
        if len(self.json.data["gif_list"]) > 1:
            current_gif = self.json.data["gif_path"]
            available_gifs = [gif for gif in self.json.data["gif_list"] if gif != current_gif]
            if available_gifs:
                new_gif = random.choice(available_gifs)
                print(f"New GIF: {new_gif}")
                self.json.data["gif_path"] = new_gif
                self.json.write_json_file()
                self.setup_ui()

if __name__ == "__main__":
    app = QApplication([])
    window = TransparentWindow()
    window.show()
    app.exec_()