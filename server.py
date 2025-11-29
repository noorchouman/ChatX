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
        # {username: {"ip": str, "tcp_port": int, "udp_port": int, "last_seen": datetime}}
        self.peers = {}
        self.running = False
        self.server_socket: socket.socket | None = None

    def start_server(self) -> None:
        """Start the discovery server (blocking call) - localhost only."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            # Bind to localhost only (127.0.0.1) for same-machine communication
            self.server_socket.bind(('127.0.0.1', self.port))
            self.server_socket.listen(5)
            self.running = True
            print(f"ChatX Server started on 127.0.0.1:{self.port} (localhost only)")
            self._log_event("Server started (localhost only)")

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
        
        # Update last_seen for any peer making a request
        if username and username in self.peers:
            self.peers[username]["last_seen"] = datetime.now()

        if msg_type == PEER_REGISTER:
            tcp_port = message.get("tcp_port")
            udp_port = message.get("udp_port")

            if not username or tcp_port is None or udp_port is None:
                return {"status": "error", "message": "Missing registration fields"}

            # If peer already exists with same username, remove old entry (new registration = old one is stale)
            if username in self.peers:
                old_info = self.peers[username]
                # Check if it's the same IP/port (same client reconnecting) or different (new client with same username)
                if old_info["ip"] != address[0] or old_info["tcp_port"] != tcp_port:
                    self._log_event(f"Replacing peer: {username} (old: {old_info['ip']}:{old_info['tcp_port']}, new: {address[0]}:{tcp_port})")
                else:
                    self._log_event(f"Peer re-registered: {username} from {address}")

            # Force localhost IP for same-machine communication
            self.peers[username] = {
                "ip": "127.0.0.1",
                "tcp_port": tcp_port,
                "udp_port": udp_port,
                "last_seen": datetime.now(),
            }
            self._log_event(f"Peer registered: {username} from {address}")
            return {"status": "success", "message": "Registered successfully"}

        elif msg_type == PEER_UNREGISTER:
            if username in self.peers:
                del self.peers[username]
                self._log_event(f"Peer unregistered: {username}")
            return {"status": "success", "message": "Unregistered successfully"}

        elif msg_type == PEER_LIST_REQUEST:
            # Clean up stale peers and return only active ones (excluding requester)
            # Only clean up if we have peers to check (avoid unnecessary work)
            if len(self.peers) > 1:
                self._cleanup_stale_peers()
            
            peer_list = {}
            for user, info in self.peers.items():
                if user != username:
                    # Only include peer info (not last_seen timestamp)
                    peer_list[user] = {
                        "ip": info["ip"],
                        "tcp_port": info["tcp_port"],
                        "udp_port": info["udp_port"],
                    }
            self._log_event(f"Peer list requested by: {username} ({len(peer_list)} active peers)")
            return {"status": "success", "peers": peer_list}

        return {"status": "error", "message": "Unknown message type"}

    def _verify_peer_reachable(self, ip: str, tcp_port: int, timeout: float = 1.0) -> bool:
        """Verify if a peer is still reachable by attempting to connect to its TCP port."""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(timeout)
            result = test_socket.connect_ex((ip, tcp_port))
            test_socket.close()
            return result == 0  # 0 means connection successful
        except Exception:
            return False
    
    def _cleanup_stale_peers(self) -> None:
        """Remove peers that are no longer reachable (with timeout to avoid blocking)."""
        stale_peers = []
        current_time = datetime.now()
        
        for username, info in self.peers.items():
            # Check if peer hasn't been seen in a while (more than 30 seconds)
            last_seen = info.get("last_seen")
            if last_seen:
                time_diff = (current_time - last_seen).total_seconds()
                # Only verify peers that haven't been seen recently
                if time_diff > 30:
                    if not self._verify_peer_reachable(info["ip"], info["tcp_port"], timeout=0.5):
                        stale_peers.append(username)
        
        for username in stale_peers:
            del self.peers[username]
            self._log_event(f"Removed stale peer: {username} (unreachable)")

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
