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


GuiCallbackType = Optional[Callable[[dict], None]]


class NetworkManager:
    """
    Handles all networking:
    - TCP socket for chat (listening + sending)
    - UDP socket for file transfer (listening + sending)
    - Communication with discovery server
    """

    
    def __init__(self, username: str, gui_callback: GuiCallbackType = None):
        self.username = username
        self.gui_callback = gui_callback

        self.tcp_socket: Optional[socket.socket] = None
        self.udp_socket: Optional[socket.socket] = None

        self.tcp_port: Optional[int] = None
        self.udp_port: Optional[int] = None

        self.running = False
        self._incoming_files = {}

    # ------------------------------------------------------------------
    # Socket setup and threads
    # ------------------------------------------------------------------
    def initialize_network(self) -> bool:
        """Initialize TCP and UDP sockets."""
        try:
            # TCP socket for chat
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 0 = pick any free port
            self.tcp_socket.bind(("", 0))
            self.tcp_port = self.tcp_socket.getsockname()[1]

            # UDP socket for file transfer
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(("", 0))
            self.udp_port = self.udp_socket.getsockname()[1]

            self.running = True
            return True
        except Exception as e:
            print(f"Network initialization error: {e}")
            return False

    def start_tcp_listener(self) -> None:
        """Start TCP listener thread for incoming chat connections."""

        def tcp_listener():
            assert self.tcp_socket is not None
            self.tcp_socket.listen(5)
            while self.running:
                try:
                    client_socket, address = self.tcp_socket.accept()
                except OSError:
                    break
                threading.Thread(
                    target=self._handle_tcp_connection,
                    args=(client_socket, address),
                    daemon=True,
                ).start()

        threading.Thread(target=tcp_listener, daemon=True).start()

    def _handle_tcp_connection(self, client_socket: socket.socket, address) -> None:
        """Handle incoming TCP chat connections."""
        try:
            while self.running:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                message = data.decode("utf-8")
                self._emit_gui_event(
                    {
                        "type": "chat_message",
                        "sender_ip": address[0],
                        "message": message,
                        "direction": "incoming",
                    }
                )
        except Exception as e:
            print(f"TCP connection handling error: {e}")
        finally:
            client_socket.close()

    def start_udp_listener(self) -> None:
        """Start UDP listener thread for file transfers."""

        def udp_listener():
            assert self.udp_socket is not None
            while self.running:
                try:
                    data, address = self.udp_socket.recvfrom(BUFFER_SIZE * 2)
                except OSError:
                    break
                self._handle_udp_data(data, address)

        threading.Thread(target=udp_listener, daemon=True).start()

    # ------------------------------------------------------------------
    # TCP chat
    # ------------------------------------------------------------------
    def send_chat_message(self, peer_ip: str, peer_tcp_port: int, message: str) -> bool:
        """Send chat message to peer via TCP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((peer_ip, peer_tcp_port))
                sock.send(message.encode("utf-8"))

            # Notify GUI about outgoing message
            self._emit_gui_event(
                {
                    "type": "chat_message",
                    "sender_ip": "me",
                    "message": message,
                    "direction": "outgoing",
                }
            )
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
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
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break

                    # Encode chunk into base64 for JSON transport
                    b64_chunk = base64.b64encode(chunk).decode("ascii")
                    chunk_packet = {
                        "type": FILE_TRANSFER_CHUNK,
                        "filename": filename,
                        "data": b64_chunk,
                    }
                    self.udp_socket.sendto(
                        json.dumps(chunk_packet).encode("utf-8"),
                        (peer_ip, peer_udp_port),
                    )

                    bytes_sent += len(chunk)
                    self._emit_gui_event(
                        {
                            "type": "file_progress",
                            "filename": filename,
                            "bytes_sent": bytes_sent,
                            "total": file_size,
                        }
                    )

            # Send FILE_END control packet
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
            text = data.decode("utf-8")
            packet = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("Received non-JSON UDP packet, ignoring.")
            return

        p_type = packet.get("type")

        if p_type == FILE_TRANSFER_START:
            filename = packet.get("filename")
            total_size = packet.get("size", 0)
            sender = packet.get("from", address[0])

            if not filename:
                return

            save_name = f"received_{filename}"
            try:
                f = open(save_name, "wb")
            except OSError as e:
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
            info["bytes_received"] += len(chunk)

            self._emit_gui_event(
                {
                    "type": "file_progress",
                    "filename": filename,
                    "bytes_received": info["bytes_received"],
                    "total": info["total"],
                }
            )

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
    def register_with_server(self, server_ip: str) -> dict:
        """Register peer with central server."""
        try:
            registration_data = {
                 "type": PEER_REGISTER,
                "username": self.username,
                "tcp_port": self.tcp_port,
                "udp_port": self.udp_port,
}

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((server_ip, SERVER_PORT))
                sock.send(json.dumps(registration_data).encode("utf-8"))
                response = sock.recv(4096).decode("utf-8")
                result = json.loads(response)
        except Exception as e:
            print(f"Registration error: {e}")
            result = {"status": "error", "message": str(e)}

        self._emit_gui_event(
            {"type": "registration_result", "result": result, "server_ip": server_ip}
        )
        return result

    def unregister_from_server(self, server_ip: str) -> None:
        """Optional clean unregister."""
        try:
            data = {"type": PEER_UNREGISTER, "username": self.username}
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((server_ip, SERVER_PORT))
                sock.send(json.dumps(data).encode("utf-8"))
        except Exception as e:
            print(f"Unregister error: {e}")

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
        return result

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
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
