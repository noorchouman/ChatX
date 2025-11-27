# logger.py
import logging
import os
from datetime import datetime
from typing import Optional


class ChatLogger:
    """Logger for chat messages and file transfers."""

    def __init__(self, username: str, log_dir: Optional[str] = None):
        """
        Initialize logger for a specific user.

        Args:
            username: Username of the current user
            log_dir: Directory to store log files (defaults to ./logs)
        """
        self.username = username

        # Set up log directory
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{username}_{timestamp}.log"
        self.log_path = os.path.join(self.log_dir, log_filename)

        # Configure logger
        self.logger = logging.getLogger(f"ChatX_{username}")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # File handler
        file_handler = logging.FileHandler(self.log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        # Log session start
        self.logger.info("=" * 60)
        self.logger.info(f"ChatX Session Started - User: {username}")
        self.logger.info("ENCRYPTION: ENABLED (All messages are encrypted)")
        self.logger.info("=" * 60)

    def log_connection(self, server_ip: str, status: str):
        """Log connection to server."""
        self.logger.info(f"SERVER | Connection to {server_ip} - Status: {status}")

    def log_disconnection(self, server_ip: str):
        """Log disconnection from server."""
        self.logger.info(f"SERVER | Disconnected from {server_ip}")

    def log_peer_discovery(self, peer_count: int, peers: list):
        """Log peer discovery."""
        self.logger.info(f"PEER DISCOVERY | Found {peer_count} peer(s): {', '.join(peers)}")

    def log_message_sent(self, recipient: str, message: str, encrypted: str = None):
        """Log outgoing chat message."""
        if encrypted:
            # Show both encrypted and plaintext versions
            self.logger.info(f"CHAT OUT | To: {recipient}")
            self.logger.info(f"         | Encrypted: {encrypted[:80]}...")
            self.logger.info(f"         | Plaintext: {message}")
        else:
            self.logger.info(f"CHAT OUT | To: {recipient} | Message: {message}")

    def log_message_received(self, sender: str, message: str, encrypted: str = None):
        """Log incoming chat message."""
        if encrypted:
            # Show both encrypted and plaintext versions
            self.logger.info(f"CHAT IN  | From: {sender}")
            self.logger.info(f"         | Encrypted: {encrypted[:80]}...")
            self.logger.info(f"         | Decrypted: {message}")
        else:
            self.logger.info(f"CHAT IN  | From: {sender} | Message: {message}")

    def log_file_send_start(self, recipient: str, filename: str, filesize: int, encrypted: bool = False):
        """Log start of file send."""
        size_mb = filesize / (1024 * 1024)
        encryption_status = "[ENCRYPTED]" if encrypted else "[UNENCRYPTED]"
        self.logger.info(
            f"FILE OUT {encryption_status} | To: {recipient} | File: {filename} | "
            f"Size: {filesize} bytes ({size_mb:.2f} MB)"
        )

    def log_file_send_complete(self, recipient: str, filename: str):
        """Log completion of file send."""
        self.logger.info(f"FILE OUT | To: {recipient} | File: {filename} | Status: COMPLETE")

    def log_file_send_error(self, recipient: str, filename: str, error: str):
        """Log file send error."""
        self.logger.error(
            f"FILE OUT | To: {recipient} | File: {filename} | "
            f"Status: ERROR | Details: {error}"
        )

    def log_file_receive_start(self, sender: str, filename: str, filesize: int, encrypted: bool = False):
        """Log start of file receive."""
        size_mb = filesize / (1024 * 1024)
        encryption_status = "[ENCRYPTED]" if encrypted else "[UNENCRYPTED]"
        self.logger.info(
            f"FILE IN  {encryption_status} | From: {sender} | File: {filename} | "
            f"Size: {filesize} bytes ({size_mb:.2f} MB)"
        )

    def log_file_receive_complete(self, sender: str, filename: str, save_path: str):
        """Log completion of file receive."""
        self.logger.info(
            f"FILE IN  | From: {sender} | File: {filename} | "
            f"Saved to: {save_path} | Status: COMPLETE"
        )

    def log_file_receive_error(self, sender: str, filename: str, error: str):
        """Log file receive error."""
        self.logger.error(
            f"FILE IN  | From: {sender} | File: {filename} | "
            f"Status: ERROR | Details: {error}"
        )

    def log_error(self, component: str, error: str):
        """Log general error."""
        self.logger.error(f"{component} | Error: {error}")

    def log_info(self, component: str, message: str):
        """Log general info."""
        self.logger.info(f"{component} | {message}")

    def close(self):
        """Close the logger and log session end."""
        self.logger.info("=" * 60)
        self.logger.info(f"ChatX Session Ended - User: {self.username}")
        self.logger.info("=" * 60)

        # Close all handlers
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)
