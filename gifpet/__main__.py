"""Diem khoi dong cua GIF Pet.

Chay bang mot trong hai cach:

    python -m gifpet
    ./run.sh
"""

import sys

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

from gifpet.core.config import Config
from gifpet.ui.pet_window import PetWindow


def main(argv=None):
    # setQuitOnLastWindowClosed(False): pet co the bi an nhung app van chay
    # trong khay he thong.
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("GifAnimation")
    app.setQuitOnLastWindowClosed(False)

    config = Config()
    window = PetWindow(app, config)
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
