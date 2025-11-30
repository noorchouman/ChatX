# client.py
import sys

from PyQt6.QtWidgets import QApplication

from gui import ChatXClientGUI


def main(): #initializes and run GUI app.
    app = QApplication(sys.argv) #QApplication is required for any PyQt6 application
    #sys.argv is command line arguments (passed to Qt)
    
    window = ChatXClientGUI() #LOADS THE WHOLE CHATXINTERFACE.
    #The username dialog appears,The GUI connects to the server,The networking threads start (TCP listener, UDP listener)
    window.show()
    #Makes window visible (if not already shown)
    sys.exit(app.exec())
# Start the Qt event loop (keeps the GUI running and responsive)
# Handles all GUI events (clicks, typing, redraws)
# Processes signals coming from network threads (messages, file chunks)
# Keeps the application alive until the user closes the window
# When the window closes, app.exec() returns an exit code
# sys.exit() passes that exit code to the OS and shuts down cleanly


if __name__ == "__main__":
    main()
