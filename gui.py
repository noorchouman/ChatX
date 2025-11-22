# gui.py
import os
import html
from typing import Optional, Dict
from datetime import datetime

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
    QDialog,
    QDialogButtonBox,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtGui import QIcon

from config import SERVER_HOST
from network import NetworkManager


class NetworkEventBridge(QtCore.QObject):
    """Qt bridge object to safely receive events from NetworkManager threads."""
    event_received = QtCore.pyqtSignal(dict)


# ----------------------------------------------------------------------
# Username Dialog
# ----------------------------------------------------------------------
class UsernameDialog(QDialog):
    """Dialog to get username when application starts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to ChatX")
        self.setModal(True)
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Enter Your Username")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        # Generate a more readable unique default username
        import random
        import string
        random_suffix = ''.join(random.choices(string.digits, k=4))
        default_username = f"User{random_suffix}"
        self.username_input.setText(default_username)
        self.username_input.selectAll()
        layout.addWidget(self.username_input)
        
        # Server input
        server_label = QLabel("Server IP:")
        layout.addWidget(server_label)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("Server IP (e.g., localhost)")
        from config import SERVER_HOST
        self.server_input.setText(SERVER_HOST)
        layout.addWidget(self.server_input)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Set focus to username input
        self.username_input.setFocus()
        
        # Apply dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#dialogTitle {
                font-size: 18px;
                font-weight: 600;
                color: #1d1d1f;
                padding-bottom: 8px;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #111111;
                border-radius: 8px;
                padding: 8px 12px;
                border: 1px solid #d1d1d6;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #0b93f6;
                background-color: #fafafa;
            }
            QPushButton {
                background-color: #e5e5ea;
                color: #111111;
                border-radius: 8px;
                padding: 8px 16px;
                border: 1px solid #d1d1d6;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #d8d8dd;
            }
            QPushButton[text="OK"] {
                background-color: #0b93f6;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton[text="OK"]:hover {
                background-color: #007aff;
            }
        """)
        
    def get_username(self) -> str:
        """Get the entered username."""
        return self.username_input.text().strip() or "User"
    
    def get_server_ip(self) -> str:
        """Get the entered server IP."""
        return self.server_input.text().strip() or "localhost"


# ----------------------------------------------------------------------
# Chat bubble widgets
# ----------------------------------------------------------------------
class ChatBubble(QWidget):
    def __init__(self, text: str, outgoing: bool, sender: Optional[str] = None, timestamp: Optional[str] = None):
        super().__init__()

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(4, 0, 4, 0)
        outer_layout.setSpacing(4)

        bubble = QLabel()
        bubble.setWordWrap(True)
        bubble.setTextFormat(QtCore.Qt.TextFormat.RichText)
        bubble.setAutoFillBackground(True)

        escaped_text = html.escape(text)
        
        # Format timestamp (show time only, e.g., "2:30 PM")
        time_str = ""
        if timestamp:
            try:
                # Parse timestamp if it's a string
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp)
                else:
                    dt = timestamp
                time_str = dt.strftime("%I:%M %p")  # e.g., "02:30 PM"
            except:
                time_str = ""
        
        # Build message text with timestamp
        if sender and not outgoing:
            escaped_sender = html.escape(sender)
            if time_str:
                bubble.setText(f"<b>{escaped_sender}</b><br>{escaped_text}<br><small style='color: #666; font-size: 10px;'>{time_str}</small>")
            else:
                bubble.setText(f"<b>{escaped_sender}</b><br>{escaped_text}")
        else:
            if time_str:
                bubble.setText(f"{escaped_text}<br><small style='color: rgba(255,255,255,0.8); font-size: 10px;'>{time_str}</small>")
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
        
        # Per-peer conversation storage: {username: [{"direction": "incoming/outgoing", "sender": str, "text": str, "is_system": bool}, ...]}
        self.conversations: Dict[str, list] = {}

        # Bridge for thread-safe network events
        self._event_bridge = NetworkEventBridge()
        self._event_bridge.event_received.connect(self.handle_network_event)

        # Notification system
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._setup_notifications()

        # Show username dialog first (before UI setup)
        self._show_username_dialog()
        
        self._setup_ui()
        self._apply_style()
        
        # Update username display after UI is created
        if hasattr(self, 'username_display'):
            self.username_display.setText(self.username)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)
        central.setLayout(main_layout)

        # Left panel: connection + peers
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        # Connection controls
        conn_widget = QWidget()
        conn_widget.setObjectName("connectionPanel")
        conn_layout = QVBoxLayout()
        conn_layout.setSpacing(8)
        conn_widget.setLayout(conn_layout)
        
        # Username display (read-only, set from dialog)
        username_row = QHBoxLayout()
        username_row.setSpacing(8)
        username_label = QLabel("Username:")
        username_label.setMinimumWidth(70)
        self.username_display = QLabel(self.username)
        self.username_display.setObjectName("usernameDisplay")
        self.username_display.setStyleSheet("""
            QLabel {
                background-color: #f2f2f7;
                color: #111111;
                border-radius: 6px;
                padding: 8px 12px;
                border: 1px solid #d1d1d6;
                font-weight: 500;
            }
        """)
        username_row.addWidget(username_label)
        username_row.addWidget(self.username_display)
        
        # Server row
        server_row = QHBoxLayout()
        server_row.setSpacing(8)
        server_label = QLabel("Server:")
        server_label.setMinimumWidth(70)
        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText("Server IP (e.g., localhost)")
        self.server_edit.setText(self.server_ip)
        server_row.addWidget(server_label)
        server_row.addWidget(self.server_edit)
        
        # Connect button
        self.connect_btn = QPushButton("Connect to Server")
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.connect_btn.setMinimumHeight(36)
        
        conn_layout.addLayout(username_row)
        conn_layout.addLayout(server_row)
        conn_layout.addWidget(self.connect_btn)

        left_panel.addWidget(conn_widget)

        # Peer list section
        peers_label = QLabel("Online Peers")
        peers_label.setObjectName("sectionLabel")
        left_panel.addWidget(peers_label)
        
        self.peer_list = QListWidget()
        self.peer_list.itemSelectionChanged.connect(self.on_peer_selected)
        self.peer_list.setMinimumHeight(200)
        left_panel.addWidget(self.peer_list)

        self.refresh_peers_btn = QPushButton("🔄 Refresh Peer List")
        self.refresh_peers_btn.clicked.connect(self.refresh_peers)
        self.refresh_peers_btn.setEnabled(False)
        left_panel.addWidget(self.refresh_peers_btn)

        main_layout.addLayout(left_panel, 2)

        # Right panel: chat + file transfer
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        # Chat header (shows current peer's username)
        self.chat_header = QWidget()
        self.chat_header.setObjectName("chatHeader")
        self.chat_header.setMinimumHeight(50)
        self.chat_header.setMaximumHeight(50)
        chat_header_layout = QHBoxLayout()
        chat_header_layout.setContentsMargins(16, 8, 16, 8)
        self.chat_header_label = QLabel("Select a peer to start chatting")
        self.chat_header_label.setObjectName("chatHeaderLabel")
        chat_header_layout.addWidget(self.chat_header_label)
        chat_header_layout.addStretch()
        self.chat_header.setLayout(chat_header_layout)
        right_panel.addWidget(self.chat_header)
        
        # Chat area: scroll area with vertical layout of bubbles
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
        msg_layout.setSpacing(8)
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a message...")
        self.msg_input.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setEnabled(False)
        self.send_btn.setMinimumWidth(80)

        msg_layout.addWidget(self.msg_input, 4)
        msg_layout.addWidget(self.send_btn, 1)
        right_panel.addLayout(msg_layout)

        # File transfer controls
        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)
        self.send_file_btn = QPushButton("📁 Send File")
        self.send_file_btn.clicked.connect(self.send_file)
        self.send_file_btn.setEnabled(False)

        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.file_progress.setTextVisible(False)
        self.file_progress.setMinimumHeight(24)

        file_layout.addWidget(self.send_file_btn)
        file_layout.addWidget(self.file_progress, 2)
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
        
        QLabel#sectionLabel {
            font-weight: 600;
            font-size: 14px;
            color: #1d1d1f;
            padding: 4px 0px;
        }
        
        QWidget#connectionPanel {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 12px;
            border: 1px solid #d1d1d6;
        }
        
        QLabel#dialogTitle {
            font-size: 18px;
            font-weight: 600;
            color: #1d1d1f;
            padding-bottom: 8px;
        }
        
        QWidget#chatHeader {
            background-color: #ffffff;
            border-bottom: 1px solid #d1d1d6;
            border-radius: 0px;
        }
        
        QLabel#chatHeaderLabel {
            font-size: 16px;
            font-weight: 600;
            color: #1d1d1f;
        }

        QListWidget {
            background-color: #ffffff;
            color: #111111;
            border-radius: 10px;
            padding: 8px;
            border: 1px solid #d1d1d6;
        }
        
        QListWidget::item {
            padding: 8px;
            border-radius: 6px;
        }
        
        QListWidget::item:selected {
            background-color: #0b93f6;
            color: #ffffff;
        }
        
        QListWidget::item:hover {
            background-color: #f2f2f7;
        }

        QScrollArea {
            background-color: #1c1c1e;
            border-radius: 10px;
            border: 1px solid #2c2c2e;
        }

        QLineEdit {
            background-color: #ffffff;
            color: #111111;
            border-radius: 8px;
            padding: 8px 12px;
            border: 1px solid #d1d1d6;
            min-height: 20px;
        }

        QLineEdit:focus {
            border: 2px solid #0b93f6;
            background-color: #fafafa;
        }

        QPushButton {
            background-color: #e5e5ea;
            color: #111111;
            border-radius: 8px;
            padding: 8px 16px;
            border: 1px solid #d1d1d6;
            min-height: 32px;
        }

        QPushButton:hover {
            background-color: #d8d8dd;
        }
        
        QPushButton:disabled {
            background-color: #e5e5ea;
            color: #8e8e93;
            border: 1px solid #d1d1d6;
        }

        QPushButton#primaryButton {
            background-color: #0b93f6;
            color: #ffffff;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            padding: 10px 20px;
            min-height: 36px;
        }

        QPushButton#primaryButton:hover {
            background-color: #007aff;
        }
        
        QPushButton#primaryButton:disabled {
            background-color: #8e8e93;
            color: #ffffff;
        }

        QStatusBar {
            color: #3c3c43;
            background-color: #f2f2f7;
            padding: 4px;
            border-top: 1px solid #d1d1d6;
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
    def _show_username_dialog(self):
        """Show username dialog on startup."""
        dialog = UsernameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.username = dialog.get_username()
            self.server_ip = dialog.get_server_ip()
            # Update display
            if hasattr(self, 'username_display'):
                self.username_display.setText(self.username)
        else:
            # User cancelled, use defaults
            import random
            import string
            random_suffix = ''.join(random.choices(string.digits, k=4))
            self.username = f"User{random_suffix}"
            self.server_ip = SERVER_HOST
    
    def on_connect_clicked(self):
        if self.network:
            # Already connected -> exit app (simple behaviour)
            self.close()
            return

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
            self._update_chat_header(None)
            self._clear_chat_window()
            return
        item = items[0]
        username = item.text()
        self.current_peer_username = username
        
        # Update chat header with peer's username
        self._update_chat_header(username)
        
        # Clear chat window and load this peer's conversation
        self._clear_chat_window()
        self._load_conversation(username)

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
            target_username=self.current_peer_username,
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
            sender_username = event.get("sender_username")  # Now using username directly
            target_username = event.get("target_username")  # The peer we're chatting with
            msg = event.get("message", "")

            # Determine which peer this message belongs to
            if direction == "incoming":
                peer_username = sender_username
            else:  # outgoing
                peer_username = target_username

            # Skip storing if we can't determine the peer (edge case: malformed message)
            if not peer_username or peer_username == "unknown":
                # Still try to display if it's for the current peer (fallback)
                if direction == "incoming" and self.current_peer_username:
                    self._append_chat_bubble(msg, outgoing=False, sender=sender_username or "Unknown")
                elif direction == "outgoing" and self.current_peer_username:
                    self._append_chat_bubble(msg, outgoing=True)
                return

            # Store message in conversation history with timestamp
            if peer_username not in self.conversations:
                self.conversations[peer_username] = []
            
            timestamp = datetime.now().isoformat()
            self.conversations[peer_username].append({
                "direction": direction,
                "sender": sender_username if direction == "incoming" else self.username,
                "text": msg,
                "is_system": False,
                "timestamp": timestamp
            })

            # Only display if this peer's conversation is currently open
            if peer_username == self.current_peer_username:
                if direction == "incoming":
                    self._append_chat_bubble(msg, outgoing=False, sender=sender_username, timestamp=timestamp)
                    # Show notification for incoming messages if window not focused or different peer
                    self._show_message_notification(sender_username, msg)
                else:  # outgoing
                    self._append_chat_bubble(msg, outgoing=True, timestamp=timestamp)

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
            system_msg = f"Receiving file '{filename}' from {sender} -> saving as {save_name}"
            
            # Store system message in sender's conversation
            if sender and sender in self.peers:
                if sender not in self.conversations:
                    self.conversations[sender] = []
                self.conversations[sender].append({
                    "direction": "incoming",
                    "sender": sender,
                    "text": system_msg,
                    "is_system": True
                })
            
            # Only show if this peer's conversation is open
            if sender == self.current_peer_username:
                self._append_chat_line(system_msg)
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
            system_msg = f"File received from {sender}: {filename} (saved as {save_name})"

            # Store system message in sender's conversation
            if sender and sender in self.peers:
                if sender not in self.conversations:
                    self.conversations[sender] = []
                self.conversations[sender].append({
                    "direction": "incoming",
                    "sender": sender,
                    "text": system_msg,
                    "is_system": True
                })
            
            # Only show if this peer's conversation is open
            if sender == self.current_peer_username:
                self._append_chat_line(system_msg)
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
    
    def _get_received_files_dir(self) -> str:
        """Get the directory for saving received files."""
        import os
        # Use Downloads folder if available, otherwise use current directory
        if os.name == 'nt':  # Windows
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
        else:  # Linux/Mac
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        # Create ChatX_Received folder in Downloads
        chatx_dir = os.path.join(downloads, 'ChatX_Received')
        os.makedirs(chatx_dir, exist_ok=True)
        return chatx_dir

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
        """Append a system message line (only for system notifications)."""
        self._add_chat_widget(SystemLine(text))

    def _append_chat_bubble(
        self, message: str, outgoing: bool, sender: Optional[str] = None, timestamp: Optional[str] = None
    ):
        """Append a chat bubble (for actual messages)."""
        self._add_chat_widget(ChatBubble(message, outgoing, sender, timestamp))
    
    def _clear_chat_window(self):
        """Clear the chat window except for the bottom stretch."""
        # Remove all widgets except the stretch at the bottom
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _update_chat_header(self, peer_username: Optional[str]):
        """Update the chat header to show the current peer's username."""
        if peer_username:
            self.chat_header_label.setText(f"💬 Chatting with {peer_username}")
        else:
            self.chat_header_label.setText("Select a peer to start chatting")
    
    def _load_conversation(self, peer_username: str):
        """Load and display conversation history for a peer."""
        # Don't show "Chatting with X" system message since it's in the header
        if peer_username not in self.conversations:
            # No conversation yet
            return
        
        # Load all messages from this conversation
        for msg_data in self.conversations[peer_username]:
            if msg_data.get("is_system", False):
                self._append_chat_line(msg_data["text"])
            else:
                direction = msg_data["direction"]
                sender = msg_data.get("sender")
                text = msg_data["text"]
                timestamp = msg_data.get("timestamp")
                if direction == "incoming":
                    self._append_chat_bubble(text, outgoing=False, sender=sender, timestamp=timestamp)
                else:
                    self._append_chat_bubble(text, outgoing=True, timestamp=timestamp)

    def _set_status(self, text: str):
        self.status_bar.showMessage(text)
    
    def _setup_notifications(self):
        """Setup system tray icon and notification system."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            # Use a simple icon (or create a default one)
            self.tray_icon.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon))
            self.tray_icon.setToolTip("ChatX - Multi-Protocol Communication Platform")
            self.tray_icon.show()
    
    def _show_message_notification(self, sender: str, message: str):
        """Show notification for incoming message."""
        # Only show notification if:
        # 1. Window is not active/focused, OR
        # 2. Message is from a different peer than currently viewing
        is_window_active = self.isActiveWindow()
        is_current_peer = (sender == self.current_peer_username)
        
        if not is_window_active or not is_current_peer:
            # Truncate long messages
            preview = message[:50] + "..." if len(message) > 50 else message
            
            # Show system tray notification
            if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
                self.tray_icon.showMessage(
                    f"New message from {sender}",
                    preview,
                    QSystemTrayIcon.MessageIcon.Information,
                    3000  # 3 seconds
                )
            
            # Play notification sound (system beep)
            QtWidgets.QApplication.beep()

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
