"""Diem khoi dong cua GIF Pet."""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from config import Config
from transparent_window import TransparentWindow


def main():
    # setQuitOnLastWindowClosed(False): pet co the bi an nhung app van chay
    # trong khay he thong.
    app = QApplication(sys.argv)
    app.setApplicationName("GifAnimation")
    app.setQuitOnLastWindowClosed(False)

    config = Config()
    window = TransparentWindow(app, config)
    if config.get("visible"):
        window.show()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "Lưu ý: hệ thống không có khay. Dùng chuột phải trên pet, "
            "hoặc phím tắt Ctrl+Alt+H / Ctrl+Alt+Q."
        )

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
