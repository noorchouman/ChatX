# encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os


class MessageEncryption:
    """Handles encryption and decryption for chat messages and files."""

    def __init__(self, password: str = None):
        """
        Initialize encryption with a password.

        Args:
            password: Password for encryption (if None, uses default)
        """
        # Use default password or provided one
        if password is None:
            password = "ChatX_Default_Key_2025"  # Default password

        # Derive a key from the password
        self.key = self._derive_key(password)
        self.cipher = Fernet(self.key)

    def _derive_key(self, password: str) -> bytes:
        """
        Derive a Fernet key from a password using PBKDF2.

        Args:
            password: Password string

        Returns:
            Base64-encoded Fernet key
        """
        # Fixed salt for consistency (in production, should be random and shared)
        salt = b'ChatX_Salt_2025_'

        # Derive key using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_message(self, message: str) -> str:
        """
        Encrypt a text message.

        Args:
            message: Plain text message

        Returns:
            Encrypted message as base64 string
        """
        try:
            encrypted = self.cipher.encrypt(message.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            raise Exception(f"Encryption failed: {e}")

    def decrypt_message(self, encrypted_message: str) -> str:
        """
        Decrypt a text message.

        Args:
            encrypted_message: Encrypted message as base64 string

        Returns:
            Decrypted plain text message
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_message.encode('utf-8'))
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise Exception(f"Decryption failed: {e}")

    def encrypt_file_chunk(self, chunk: bytes) -> bytes:
        """
        Encrypt a file chunk.

        Args:
            chunk: Raw file data chunk

        Returns:
            Encrypted chunk
        """
        try:
            return self.cipher.encrypt(chunk)
        except Exception as e:
            raise Exception(f"File chunk encryption failed: {e}")

    def decrypt_file_chunk(self, encrypted_chunk: bytes) -> bytes:
        """
        Decrypt a file chunk.

        Args:
            encrypted_chunk: Encrypted file data chunk

        Returns:
            Decrypted chunk
        """
        try:
            return self.cipher.decrypt(encrypted_chunk)
        except Exception as e:
            raise Exception(f"File chunk decryption failed: {e}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new random Fernet key.

        Returns:
            Base64-encoded key as string
        """
        return Fernet.generate_key().decode('utf-8')

    @staticmethod
    def is_encrypted(message: str) -> bool:
        """
        Check if a message appears to be encrypted.

        Args:
            message: Message to check

        Returns:
            True if message looks encrypted
        """
        try:
            # Encrypted messages are base64 and have specific format
            base64.urlsafe_b64decode(message.encode('utf-8'))
            return len(message) > 50 and message.replace('_', '').replace('-', '').isalnum()
        except:
            return False


# Example usage and testing
if __name__ == "__main__":
    # Test encryption
    enc = MessageEncryption("my_secure_password")

    # Test message encryption
    original = "Hello, this is a secret message!"
    encrypted = enc.encrypt_message(original)
    decrypted = enc.decrypt_message(encrypted)

    print(f"Original: {original}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {original == decrypted}")

    # Test file chunk encryption
    file_data = b"This is file content that needs to be encrypted."
    encrypted_chunk = enc.encrypt_file_chunk(file_data)
    decrypted_chunk = enc.decrypt_file_chunk(encrypted_chunk)

    print(f"\nFile chunk match: {file_data == decrypted_chunk}")
