# server.py
import socket
import threading
import json
from datetime import datetime
from config import (
    SERVER_HOST,
    SERVER_PORT,
    PEER_REGISTER,
    PEER_UNREGISTER,
    PEER_LIST_REQUEST,
)


class ChatXServer:
    """
    Console-based discovery server.

    Responsibilities:
    - Accept TCP connections from clients
    - Register / unregister peers
    - Return list of active peers
    """

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        # {username: {"ip": str, "tcp_port": int, "udp_port": int}}
        self.peers = {}
        self.running = False
        self.server_socket: socket.socket | None = None

    def start_server(self) -> None:
        """Start the discovery server (blocking call)."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            print(f"ChatX Server started on {self.host}:{self.port}")
            self._log_event("Server started")

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                except OSError:
                    # Socket was closed while waiting on accept
                    break

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                client_thread.start()

        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.stop_server()

    def _handle_client(self, client_socket: socket.socket, address) -> None:
        """Handle a single client request."""
        try:
            data = client_socket.recv(4096).decode("utf-8")
            if not data:
                return

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                client_socket.send(
                    json.dumps({"status": "error", "message": "Invalid JSON"}).encode(
                        "utf-8"
                    )
                )
                return

            response = self._process_message(message, address)
            client_socket.send(json.dumps(response).encode("utf-8"))

        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()

    def _process_message(self, message: dict, address):
        """Process different types of client messages."""
        msg_type = message.get("type")
        username = message.get("username")

        if msg_type == PEER_REGISTER:
            tcp_port = message.get("tcp_port")
            udp_port = message.get("udp_port")

            if not username or tcp_port is None or udp_port is None:
                return {"status": "error", "message": "Missing registration fields"}

            self.peers[username] = {
                "ip": address[0],
                "tcp_port": tcp_port,
                "udp_port": udp_port,
            }
            self._log_event(f"Peer registered: {username} from {address}")
            return {"status": "success", "message": "Registered successfully"}

        elif msg_type == PEER_UNREGISTER:
            if username in self.peers:
                del self.peers[username]
                self._log_event(f"Peer unregistered: {username}")
            return {"status": "success", "message": "Unregistered successfully"}

        elif msg_type == PEER_LIST_REQUEST:
            # Return list of peers (excluding requester)
            peer_list = {
                user: info for user, info in self.peers.items() if user != username
            }
            self._log_event(f"Peer list requested by: {username}")
            return {"status": "success", "peers": peer_list}

        return {"status": "error", "message": "Unknown message type"}

    @staticmethod
    def _log_event(event: str) -> None:
        """Log server events with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {event}")

    def stop_server(self) -> None:
        """Stop the server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
        print("Server stopped")


if __name__ == "__main__":
    server = ChatXServer()
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, stopping server...")
        server.stop_server()
