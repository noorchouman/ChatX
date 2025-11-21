# gui.py
import os
import html
from typing import Optional, Dict

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import (
    QMainWindow,
    QListWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QStatusBar,
    QProgressBar,
    QMessageBox,
)

from config import SERVER_HOST
from network import NetworkManager


class NetworkEventBridge(QtCore.QObject):
    """Qt bridge object to safely receive events from NetworkManager threads."""
    event_received = QtCore.pyqtSignal(dict)


# ----------------------------------------------------------------------
# Chat bubble widgets
# ----------------------------------------------------------------------
class ChatBubble(QWidget):
    def __init__(self, text: str, outgoing: bool, sender: Optional[str] = None):
        super().__init__()

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(4, 0, 4, 0)
        outer_layout.setSpacing(4)

        bubble = QLabel()
        bubble.setWordWrap(True)
        bubble.setTextFormat(QtCore.Qt.TextFormat.RichText)
        bubble.setAutoFillBackground(True)

        escaped_text = html.escape(text)
        if sender and not outgoing:
            escaped_sender = html.escape(sender)
            bubble.setText(f"<b>{escaped_sender}</b><br>{escaped_text}")
        else:
            bubble.setText(escaped_text)

        if outgoing:
            # STYLE FOR YOUR OWN (SENDER) MESSAGES
            bubble.setStyleSheet(
                """
                background-color: #0b93f6;
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 18px;
                """
            )
            outer_layout.addStretch()
            outer_layout.addWidget(bubble)
        else:
            # STYLE FOR INCOMING MESSAGES
            bubble.setStyleSheet(
                """
                background-color: #e5e5ea;
                color: #111111;
                padding: 6px 12px;
                border-radius: 18px;
                """
            )
            outer_layout.addWidget(bubble)
            outer_layout.addStretch()


class SystemLine(QWidget):
    def __init__(self, text: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        label = QLabel(text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        label.setStyleSheet("color: #8e8e93; font-size: 11px;")

        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()


# ----------------------------------------------------------------------
# Main GUI
# ----------------------------------------------------------------------
class ChatXClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ChatX – Multi-Protocol Secure Communication Platform")
        self.resize(900, 600)

        # Networking
        self.network: Optional[NetworkManager] = None
        self.server_ip: str = SERVER_HOST
        self.username: str = "User"
        self.peers: Dict[str, dict] = {}
        self.current_peer_username: Optional[str] = None

        # Bridge for thread-safe network events
        self._event_bridge = NetworkEventBridge()
        self._event_bridge.event_received.connect(self.handle_network_event)

        self._setup_ui()
        self._apply_style()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        # Left panel: connection + peers
        left_panel = QVBoxLayout()

        # Connection controls
        conn_layout = QHBoxLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        self.username_edit.setText("user1")

        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText("Server IP")
        self.server_edit.setText(self.server_ip)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.on_connect_clicked)

        conn_layout.addWidget(QLabel("User:"))
        conn_layout.addWidget(self.username_edit)
        conn_layout.addWidget(QLabel("Server:"))
        conn_layout.addWidget(self.server_edit)
        conn_layout.addWidget(self.connect_btn)

        left_panel.addLayout(conn_layout)

        # Peer list
        left_panel.addWidget(QLabel("Online Peers:"))
        self.peer_list = QListWidget()
        self.peer_list.itemSelectionChanged.connect(self.on_peer_selected)
        left_panel.addWidget(self.peer_list)

        self.refresh_peers_btn = QPushButton("Refresh Peer List")
        self.refresh_peers_btn.clicked.connect(self.refresh_peers)
        self.refresh_peers_btn.setEnabled(False)
        left_panel.addWidget(self.refresh_peers_btn)

        main_layout.addLayout(left_panel, 2)

        # Right panel: chat + file transfer
        right_panel = QVBoxLayout()

        # Chat area: scroll area with vertical layout of bubbles
        right_panel.addWidget(QLabel("Chat:"))
        self.chat_area = QtWidgets.QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout()
        self.chat_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_layout.setSpacing(6)
        self.chat_layout.addStretch()  # spacer at bottom
        self.chat_container.setLayout(self.chat_layout)

        self.chat_area.setWidget(self.chat_container)
        right_panel.addWidget(self.chat_area, 5)

        # Message input
        msg_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a message...")
        self.msg_input.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setEnabled(False)

        msg_layout.addWidget(self.msg_input)
        msg_layout.addWidget(self.send_btn)
        right_panel.addLayout(msg_layout)

        # File transfer controls
        file_layout = QHBoxLayout()
        self.send_file_btn = QPushButton("Send File")
        self.send_file_btn.clicked.connect(self.send_file)
        self.send_file_btn.setEnabled(False)

        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.file_progress.setTextVisible(False)

        file_layout.addWidget(self.send_file_btn)
        file_layout.addWidget(self.file_progress)
        right_panel.addLayout(file_layout)

        main_layout.addLayout(right_panel, 5)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._set_status("Disconnected")

    def _apply_style(self):
        """iMessage-ish light theme + primary buttons."""
        # mark primary buttons
        self.connect_btn.setObjectName("primaryButton")
        self.send_btn.setObjectName("primaryButton")
        self.send_file_btn.setObjectName("primaryButton")

        self.setStyleSheet("""
        QWidget {
            font-family: -apple-system, system-ui, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }

        QMainWindow {
            background-color: #f2f2f7;
        }

        QLabel {
            color: #111111;
        }

        QListWidget {
            background-color: #ffffff;
            color: #111111;
            border-radius: 10px;
            padding: 6px;
            border: 1px solid #d1d1d6;
        }

        QScrollArea {
            background-color: #1c1c1e;
            border-radius: 10px;
            border: 1px solid #2c2c2e;
        }

        QLineEdit {
            background-color: #ffffff;
            color: #111111;
            border-radius: 18px;
            padding: 6px 12px;
            border: 1px solid #d1d1d6;
        }

        QLineEdit:focus {
            border: 1px solid #0b93f6;
        }

        QPushButton {
            background-color: #e5e5ea;
            color: #111111;
            border-radius: 18px;
            padding: 6px 14px;
            border: 1px solid #d1d1d6;
        }

        QPushButton:hover {
            background-color: #d8d8dd;
        }

        QPushButton#primaryButton {
            background-color: #0b93f6;
            color: #ffffff;
            border-radius: 18px;
            border: none;
            font-weight: 600;
            padding: 6px 18px;
        }

        QPushButton#primaryButton:hover {
            background-color: #007aff;
        }

        QStatusBar {
            color: #3c3c43;
            background-color: #f2f2f7;
        }

        QProgressBar {
            border: 1px solid #d1d1d6;
            border-radius: 8px;
            background-color: #ffffff;
            text-align: center;
            height: 10px;
        }

        QProgressBar::chunk {
            border-radius: 8px;
            background-color: #0b93f6;
        }
        """)

    # ------------------------------------------------------------------
    # Networking setup and actions
    # ------------------------------------------------------------------
    def on_connect_clicked(self):
        if self.network:
            # Already connected -> exit app (simple behaviour)
            self.close()
            return

        self.username = self.username_edit.text().strip() or "user"
        self.server_ip = self.server_edit.text().strip() or SERVER_HOST

        self.network = NetworkManager(
            username=self.username,
            gui_callback=self._event_bridge.event_received.emit,
        )
        if not self.network.initialize_network():
            QMessageBox.critical(self, "Error", "Failed to initialize network sockets.")
            self.network = None
            return

        self.network.start_tcp_listener()
        self.network.start_udp_listener()
        self._set_status("Connecting to server...")

        result = self.network.register_with_server(self.server_ip)
        if result.get("status") != "success":
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to register with server: {result.get('message', 'unknown error')}",
            )
            self._set_status("Registration failed")
            return

        self._set_status("Connected and registered")
        self.connect_btn.setText("Quit")
        self.refresh_peers_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.send_file_btn.setEnabled(True)
        self.refresh_peers()

    def refresh_peers(self):
        if not self.network:
            return
        self._set_status("Requesting peer list...")
        self.network.get_peer_list(self.server_ip)

    def on_peer_selected(self):
        items = self.peer_list.selectedItems()
        if not items:
            self.current_peer_username = None
            return
        item = items[0]
        username = item.text()
        self.current_peer_username = username
        self._append_chat_line(f"--- Chatting with {username} ---")

    def send_message(self):
        if not self.network:
            QMessageBox.warning(self, "Not connected", "Connect to the server first.")
            return

        if not self.current_peer_username:
            QMessageBox.warning(
                self,
                "No peer selected",
                "Select a peer from the 'Online Peers' list before sending a message.",
            )
            return

        msg = self.msg_input.text().strip()
        if not msg:
            return

        peer_info = self.peers.get(self.current_peer_username)
        if not peer_info:
            QMessageBox.warning(self, "Warning", "Selected peer info not available.")
            return

        self.network.send_chat_message(
            peer_ip=peer_info["ip"],
            peer_tcp_port=peer_info["tcp_port"],
            message=msg,
        )
        self.msg_input.clear()

    def send_file(self):
        if not self.network:
            QMessageBox.warning(self, "Not connected", "Connect to the server first.")
            return

        if not self.current_peer_username:
            QMessageBox.warning(
                self,
                "No peer selected",
                "Select a peer from the 'Online Peers' list before sending a file.",
            )
            return

        peer_info = self.peers.get(self.current_peer_username)
        if not peer_info:
            QMessageBox.warning(self, "Warning", "Selected peer info not available.")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if not file_path:
            return

        self.file_progress.setValue(0)
        self.network.send_file(
            peer_ip=peer_info["ip"],
            peer_udp_port=peer_info["udp_port"],
            file_path=file_path,
        )

    # ------------------------------------------------------------------
    # Network event handling (called on main thread via signal)
    # ------------------------------------------------------------------
    @QtCore.pyqtSlot(dict)
    def handle_network_event(self, event: dict):
        etype = event.get("type")

        if etype == "chat_message":
            direction = event.get("direction")
            sender_ip = event.get("sender_ip")
            msg = event.get("message", "")

            if direction == "incoming":
                # Map IP -> username if we know it
                name = self._username_for_ip(sender_ip)
                display_name = name or str(sender_ip)
                self._append_chat_bubble(msg, outgoing=False, sender=display_name)
            else:  # outgoing
                # Outgoing bubble has no sender label (just like iMessage: it's "me")
                self._append_chat_bubble(msg, outgoing=True)

        elif etype == "status":
            level = event.get("level", "info")
            msg = event.get("message", "")
            self._set_status(msg)
            if level == "error":
                print("Error:", msg)

        elif etype == "registration_result":
            result = event.get("result", {})
            if result.get("status") != "success":
                self._set_status("Registration failed")

        elif etype == "peer_list_result":
            result = event.get("result", {})
            if result.get("status") == "success":
                peers = result.get("peers", {})
                self.peers = peers
                self._update_peer_list()
                self._set_status(f"Peer list updated ({len(peers)} peers online)")
            else:
                self._set_status("Failed to get peer list")

        elif etype == "file_start":
            filename = event.get("filename")
            total = event.get("total", 0)
            sender = event.get("sender")
            save_name = event.get("save_name")
            self._append_chat_line(
                f"Receiving file '{filename}' from {sender} -> saving as {save_name}"
            )
            self.file_progress.setValue(0)

        elif etype == "file_progress":
            total = event.get("total", 0)
            done = event.get("bytes_sent", event.get("bytes_received", 0))
            if total > 0:
                percent = int(done / total * 100)
                self.file_progress.setValue(percent)

        elif etype == "file_complete":
            filename = event.get("filename")
            save_name = event.get("save_name")
            sender = event.get("sender")

            self._append_chat_line(
                f"File received from {sender}: {filename} (saved as {save_name})"
            )
            self.file_progress.setValue(100)

            # Ask if they want to open it
            reply = QtWidgets.QMessageBox.question(
                self,
                "File received",
                f"File from {sender}:\n{filename}\n\nOpen it now?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                full_path = os.path.abspath(save_name)
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(full_path)
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _username_for_ip(self, ip: str) -> Optional[str]:
        """Try to map an IP address to a username using the current peer list."""
        for username, info in self.peers.items():
            if info.get("ip") == ip:
                return username
        return None

    def _add_chat_widget(self, widget: QWidget):
        # Insert above the stretch at the bottom
        index = self.chat_layout.count() - 1
        self.chat_layout.insertWidget(index, widget)
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.chat_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_peer_list(self):
        self.peer_list.clear()
        for username in sorted(self.peers.keys()):
            self.peer_list.addItem(username)

        # If there is exactly one peer, auto-select it
        if self.peer_list.count() == 1:
            self.peer_list.setCurrentRow(0)

    def _append_chat_line(self, text: str):
        self._add_chat_widget(SystemLine(text))

    def _append_chat_bubble(
        self, message: str, outgoing: bool, sender: Optional[str] = None
    ):
        self._add_chat_widget(ChatBubble(message, outgoing, sender))

    def _set_status(self, text: str):
        self.status_bar.showMessage(text)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self.network:
            # Try to unregister (non-critical if it fails)
            try:
                self.network.unregister_from_server(self.server_ip)
            except Exception:
                pass
            self.network.cleanup()
        event.accept()
