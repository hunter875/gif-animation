from PyQt5.QtWidgets import QApplication
from transparent_window import TransparentWindow

app = QApplication([])
window = TransparentWindow()
window.show()
app.exec_()