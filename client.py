# client.py
import sys

from PyQt6.QtWidgets import QApplication

from gui import ChatXClientGUI


def main():
    app = QApplication(sys.argv)
    window = ChatXClientGUI()
    # Window will be shown after username dialog in __init__
    window.show()
    sys.exit(app.exec())



if __name__ == "__main__":
    main()
