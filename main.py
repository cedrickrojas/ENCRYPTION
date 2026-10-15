import sys

from ironvault.ui.main_window import MainWindow, build_app


if __name__ == "__main__":
    app = build_app()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
