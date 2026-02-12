from PySide6.QtWidgets import QApplication
from .window import MainWindow


def main():
    app = QApplication([])
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
