"""Diem khoi dong cua GIF Pet.

Chay bang mot trong hai cach:

    python -m gifpet
    ./run.sh
"""

import os
import signal
import sys

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

from gifpet.core.config import Config
from gifpet.ui.pet_window import PetWindow


def _install_error_guard():
    """Loi khong bat duoc: in ro rang thay vi chet im lang.

    Mot app Qt dang o trang thai loi co the khong thoat duoc qua ``app.quit()``,
    nen sau khi in thong bao ta de he thong don. Khong coi day la loi he thong.
    """

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        import traceback

        traceback.print_exception(exc_type, exc_value, exc_tb)
        print(
            "\n[GIF Pet] Gặp lỗi không mong đợi và đã dừng.\n"
            "Đây không phải lỗi hệ thống; khởi động lại app là được.",
            file=sys.stderr,
        )

    sys.excepthook = hook


def main(argv=None):
    _install_error_guard()

    # setQuitOnLastWindowClosed(False): pet co the bi an nhung app van chay
    # trong khay he thong.
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("GifAnimation")
    app.setQuitOnLastWindowClosed(False)

    # app.exec_() chay vong lap C, khong nha GIL cho signal Python -> Ctrl+C
    # trong terminal khong lam tat app. Timer rong de Python co dip chay handler.
    def _allow_sigint(*_args):
        signal.signal(signal.SIGINT, lambda *_: os._exit(0))

    signal.signal(signal.SIGINT, _allow_sigint)
    from PyQt5.QtCore import QTimer

    _sigint_timer = QTimer()
    _sigint_timer.timeout.connect(lambda: None)
    _sigint_timer.start(300)

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
