# network.py
import os
import json
import base64
import socket
import threading
from typing import Callable, Optional, Dict, Tuple

from config import (
    TCP_CHAT_PORT,
    UDP_FILE_PORT,
    BUFFER_SIZE,
    FILE_CHUNK_SIZE,
    PEER_REGISTER,
    PEER_LIST_REQUEST,
    PEER_UNREGISTER,
    FILE_TRANSFER_START,
    FILE_TRANSFER_CHUNK,
    FILE_TRANSFER_END,
    SERVER_PORT,
)

# Import logging and encryption
from logger import ChatLogger
from encryption import MessageEncryption


GuiCallbackType = Optional[Callable[[dict], None]]


class NetworkManager:
    """
    Handles all networking:
    - TCP socket for chat (listening + sending)
    - UDP socket for file transfer (listening + sending)
    - Communication with discovery server
    """


    def __init__(self, username: str, gui_callback: GuiCallbackType = None):
        # Initializes network manager
        self.username = username  # Client's username
        self.gui_callback = gui_callback

        self.tcp_socket: Optional[socket.socket] = None  # TCP socket for chat - none initially
        self.udp_socket: Optional[socket.socket] = None

        self.tcp_port: Optional[int] = None  # TCP port number - none initially
        self.udp_port: Optional[int] = None

        self.running = False
        self._incoming_files = {}

        # Initialize logger and encryption
        self.logger = ChatLogger(username=username)
        self.encryption = MessageEncryption()

    # ------------------------------------------------------------------
    # Socket setup and threads
    # ------------------------------------------------------------------
    def initialize_network(self) -> bool:
        """Initialize TCP and UDP sockets - localhost only."""
        try:
            # Creating TCP socket that binds to localhost only
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Binds to localhost; port number 0: OS picks any free port
            self.tcp_socket.bind(("127.0.0.1", 0))
            self.tcp_port = self.tcp_socket.getsockname()[1]  # Gets the port number OS assigned

            # UDP socket for file transfer (bind to localhost only)
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(("127.0.0.1", 0))
            self.udp_port = self.udp_socket.getsockname()[1]

            self.running = True
            print(f"Network initialized: TCP port {self.tcp_port}, UDP port {self.udp_port} (localhost only)")
            return True
        except Exception as e:
            print(f"Network initialization error: {e}")
            return False

    # Start thread that listens for incoming TCP connections
    def start_tcp_listener(self) -> None:
        """Start TCP listener thread for incoming chat connections."""

        def tcp_listener():
            assert self.tcp_socket is not None
            self.tcp_socket.listen(5)  # Start listening, max 5 queued connections
            while self.running:
                try:
                    client_socket, address = self.tcp_socket.accept()
                except OSError:
                    break
                # Each connection gets its own thread
                # Handler processes messages from that connection
                # Daemon: dies when main program exits
                threading.Thread(
                    target=self._handle_tcp_connection,
                    args=(client_socket, address),
                    daemon=True,
                ).start()

        threading.Thread(target=tcp_listener, daemon=True).start()

    # Receiving loop - Handle messages from a single TCP connection (runs in handler thread)
    def _handle_tcp_connection(self, client_socket: socket.socket, address) -> None:
        """Handle incoming TCP chat connections with JSON message format."""
        try:
            while self.running:
                data = client_socket.recv(BUFFER_SIZE)  # Receive up to 4096 bytes
                if not data:  # If no data, break the loop
                    break

                try:
                    # Convert bytes to string, then parse JSON
                    text = data.decode("utf-8")
                    message_packet = json.loads(text)

                    # Check if it's a chat message packet
                    if message_packet.get("type") == "chat":
                        # Extract sender, target, encrypted text
                        sender_username = message_packet.get("from", "unknown")
                        target_username = message_packet.get("to", "unknown")
                        encrypted_text = message_packet.get("text", "")

                        # DECRYPT the message
                        try:
                            decrypted_text = self.encryption.decrypt_message(encrypted_text)
                        except Exception as decrypt_error:
                            # If decryption fails, use original (backwards compatibility)
                            decrypted_text = encrypted_text
                            self.logger.log_error("DECRYPTION", str(decrypt_error))

                        # LOG the decrypted message with encrypted version for visibility
                        self.logger.log_message_received(sender_username, decrypted_text, encrypted=encrypted_text)

                        # Notify GUI about incoming message
                        self._emit_gui_event(
                            {
                                "type": "chat_message",
                                "sender_username": sender_username,
                                "target_username": target_username,
                                "message": decrypted_text,  # Show decrypted message
                                "direction": "incoming",
                            }
                        )
                    else:
                        # Handle non-chat messages (plain text fallback)
                        self._emit_gui_event(
                            {
                                "type": "chat_message",
                                "sender_username": "unknown",
                                "target_username": self.username,
                                "message": text,
                                "direction": "incoming",
                            }
                        )
                except (json.JSONDecodeError, KeyError):
                    # Fallback: treat as plain text message
                    message = data.decode("utf-8", errors="ignore")
                    self._emit_gui_event(
                        {
                            "type": "chat_message",
                            "sender_username": "unknown",
                            "target_username": self.username,
                            "message": message,
                            "direction": "incoming",
                        }
                    )
        except Exception as e:
            print(f"TCP connection handling error: {e}")
            self.logger.log_error("TCP_HANDLER", str(e))
        finally:
            client_socket.close()

    # Start thread that listens for incoming UDP packets
    # Continuously receive UDP packets and process them
    def start_udp_listener(self) -> None:
        """Start UDP listener thread for file transfers."""

        def udp_listener():
            assert self.udp_socket is not None
            while self.running:
                try:
                    # recvfrom(): Receives UDP packet
                    # Returns: (data_bytes, (ip, port))
                    # BUFFER_SIZE * 2: 8192 bytes max
                    data, address = self.udp_socket.recvfrom(BUFFER_SIZE * 2)
                except OSError:
                    break
                # Process packet immediately (no separate thread)
                # UDP is stateless, so no connection to maintain
                self._handle_udp_data(data, address)

        threading.Thread(target=udp_listener, daemon=True).start()

    # ------------------------------------------------------------------
    # TCP CHAT MESSAGE SENDING
    # ------------------------------------------------------------------
    def send_chat_message(self, peer_ip: str, peer_tcp_port: int, message: str, target_username: str = None) -> bool:
        """Send chat message to peer via TCP using JSON format with usernames."""
        try:
            # ENCRYPT the message before sending
            encrypted_message = self.encryption.encrypt_message(message)

            # Create JSON message packet with ENCRYPTED text
            message_packet = {
                "type": "chat",
                "from": self.username,
                "to": target_username or "unknown",
                "text": encrypted_message  # Send encrypted version
            }

            # Create new socket, connect to peer
            # with statement: auto-closes socket when done
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((peer_ip, peer_tcp_port))
                sock.send(json.dumps(message_packet).encode("utf-8"))

            # LOG the original message with encrypted version for visibility
            self.logger.log_message_sent(target_username or "unknown", message, encrypted=encrypted_message)

            # Notify GUI about outgoing message (original text for display)
            self._emit_gui_event(
                {
                    "type": "chat_message",
                    "sender_username": self.username,
                    "target_username": target_username,
                    "message": message,  # Display original message
                    "direction": "outgoing",
                }
            )
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            self.logger.log_error("SEND_MESSAGE", str(e))
            self._emit_gui_event(
                {
                    "type": "status",
                    "level": "error",
                    "message": f"Error sending message: {e}",
                }
            )
            return False

    # ------------------------------------------------------------------
    # UDP file transfer
    # ------------------------------------------------------------------
    def send_file(self, peer_ip: str, peer_udp_port: int, file_path: str) -> None:
        """Send a file to a peer over UDP using a simple JSON+base64 protocol."""
        # Validate file exists
        if not os.path.isfile(file_path):
            self._emit_gui_event(
                {
                    "type": "status",
                    "level": "error",
                    "message": f"File not found: {file_path}",
                }
            )
            return

        assert self.udp_socket is not None

        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Send FILE_START control packet
        # Signals start of file transfer
        start_packet = {
            "type": FILE_TRANSFER_START,
            "filename": filename,
            "size": file_size,
            "from": self.username,
        }
        self.udp_socket.sendto(
            json.dumps(start_packet).encode("utf-8"), (peer_ip, peer_udp_port)
        )

        bytes_sent = 0
        try:
            # Send file in chunks: read 1024 bytes at a time
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break

                    # Encode binary data as base64 (JSON-safe)
                    b64_chunk = base64.b64encode(chunk).decode("ascii")
                    chunk_packet = {
                        "type": FILE_TRANSFER_CHUNK,
                        "filename": filename,
                        "data": b64_chunk,
                    }
                    # Send chunk packet
                    self.udp_socket.sendto(
                        json.dumps(chunk_packet).encode("utf-8"),
                        (peer_ip, peer_udp_port),
                    )

                    # Track bytes sent
                    bytes_sent += len(chunk)
                    # Update GUI with progress
                    self._emit_gui_event(
                        {
                            "type": "file_progress",
                            "filename": filename,
                            "bytes_sent": bytes_sent,
                            "total": file_size,
                        }
                    )

            # Send FILE_END control packet
            # Signals end of transfer
            end_packet = {"type": FILE_TRANSFER_END, "filename": filename}
            self.udp_socket.sendto(
                json.dumps(end_packet).encode("utf-8"), (peer_ip, peer_udp_port)
            )

            self._emit_gui_event(
                {
                    "type": "status",
                    "level": "info",
                    "message": f"File sent: {filename}",
                }
            )
        except Exception as e:
            self._emit_gui_event(
                {
                    "type": "status",
                    "level": "error",
                    "message": f"Error sending file: {e}",
                }
            )

    def _handle_udp_data(self, data: bytes, address) -> None:
        """Handle incoming UDP file data.

        Protocol is JSON-based:
        - FILE_START: {type, filename, size, from}
        - FILE_CHUNK: {type, filename, data(base64)}
        - FILE_END:   {type, filename}
        """
        try:
            text = data.decode("utf-8")  # Convert bytes to string
            packet = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("Received non-JSON UDP packet, ignoring.")
            return

        p_type = packet.get("type")

        if p_type == FILE_TRANSFER_START:
            # Extract filename, size, sender
            filename = packet.get("filename")
            total_size = packet.get("size", 0)
            sender = packet.get("from", address[0])

            if not filename:
                return

            # Save to proper directory (Downloads/ChatX_Received)
            import os
            if os.name == 'nt':  # Windows
                downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            else:  # Linux/Mac
                downloads = os.path.join(os.path.expanduser('~'), 'Downloads')

            chatx_dir = os.path.join(downloads, 'ChatX_Received')
            os.makedirs(chatx_dir, exist_ok=True)

            # Save name as named received_{filename}
            save_name = os.path.join(chatx_dir, f"received_{filename}")
            try:
                f = open(save_name, "wb")
            except OSError as e:
                # Notify GUI about error
                self._emit_gui_event(
                    {
                        "type": "status",
                        "level": "error",
                        "message": f"Could not open file for writing: {e}",
                    }
                )
                return

            key = (address[0], filename)
            self._incoming_files[key] = {
                "file": f,
                "bytes_received": 0,
                "total": total_size,
                "save_name": save_name,
                "sender": sender,
            }
            self._emit_gui_event(
                {
                    "type": "file_start",
                    "filename": filename,
                    "total": total_size,
                    "sender": sender,
                    "save_name": save_name,
                }
            )

        # Process incoming file chunk
        elif p_type == FILE_TRANSFER_CHUNK:
            filename = packet.get("filename")
            if not filename:
                return

            key = (address[0], filename)
            info = self._incoming_files.get(key)
            if not info:
                # No FILE_START received
                return

            data_b64 = packet.get("data")
            if not data_b64:
                return

            try:
                chunk = base64.b64decode(data_b64)
            except Exception:
                return

            f = info["file"]
            f.write(chunk)
            # Update bytes_received counter
            info["bytes_received"] += len(chunk)

            # Notify GUI with progress update
            self._emit_gui_event(
                {
                    "type": "file_progress",
                    "filename": filename,
                    "bytes_received": info["bytes_received"],
                    "total": info["total"],
                }
            )

        # Signals end of transfer
        elif p_type == FILE_TRANSFER_END:
            filename = packet.get("filename")
            if not filename:
                return

            key = (address[0], filename)
            info = self._incoming_files.pop(key, None)
            if not info:
                return

            f = info["file"]
            f.close()

            # Notify GUI with completion message
            self._emit_gui_event(
                {
                    "type": "file_complete",
                    "filename": filename,
                    "save_name": info["save_name"],
                    "sender": info["sender"],
                }
            )

    # ------------------------------------------------------------------
    # Discovery server interaction
    # ------------------------------------------------------------------
    # Register this client with discovery server
    def register_with_server(self, server_ip: str) -> dict:
        """Register peer with central server."""
        try:
            # Create registration data
            registration_data = {
                 "type": PEER_REGISTER,
                "username": self.username,
                "tcp_port": self.tcp_port,
                "udp_port": self.udp_port,
}

            # Send to server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((server_ip, SERVER_PORT))
                sock.send(json.dumps(registration_data).encode("utf-8"))
                response = sock.recv(4096).decode("utf-8")
                result = json.loads(response)

            # Log successful connection
            if result.get("status") == "success":
                self.logger.log_connection(server_ip, "SUCCESS")
            else:
                self.logger.log_connection(server_ip, f"FAILED: {result.get('message', 'Unknown error')}")

        except Exception as e:
            # Notify GUI about error
            print(f"Registration error: {e}")
            self.logger.log_error("REGISTRATION", str(e))
            result = {"status": "error", "message": str(e)}

        self._emit_gui_event(
            {"type": "registration_result", "result": result, "server_ip": server_ip}
        )
        return result

    # Unregister from server (clean disconnect)
    def unregister_from_server(self, server_ip: str) -> None:
        """Optional clean unregister."""
        try:
            data = {"type": PEER_UNREGISTER, "username": self.username}
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((server_ip, SERVER_PORT))
                sock.send(json.dumps(data).encode("utf-8"))
            self.logger.log_disconnection(server_ip)
        except Exception as e:
            print(f"Unregister error: {e}")
            self.logger.log_error("UNREGISTER", str(e))

    # Get list of active peers from server
    def get_peer_list(self, server_ip: str) -> dict:
        """Get list of active peers from server."""
        try:
            request_data = {"type": PEER_LIST_REQUEST, "username": self.username}
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((server_ip, SERVER_PORT))
                sock.send(json.dumps(request_data).encode("utf-8"))
                response = sock.recv(4096).decode("utf-8")
                result = json.loads(response)
        except Exception as e:
            print(f"Peer list request error: {e}")
            result = {"status": "error", "message": str(e)}

        self._emit_gui_event({"type": "peer_list_result", "result": result})
        return result  # Return list of active peers

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    # Clean up network resources on shutdown
    # Stop listener loops
    # Close sockets
    # Close logger
    # Notify GUI about cleanup
    def cleanup(self) -> None:
        """Clean up network resources."""
        self.running = False
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except OSError:
                pass
            self.tcp_socket = None
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except OSError:
                pass
            self.udp_socket = None

        # Close logger
        if hasattr(self, 'logger'):
            self.logger.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _emit_gui_event(self, event: dict) -> None:
        """Send event to GUI if callback is registered."""
        if self.gui_callback:
            try:
                self.gui_callback(event)
            except Exception as e:
                print(f"GUI callback error: {e}")
