# ChatX - P2P Secure Chat Application

ChatX is a peer-to-peer secure messaging application with end-to-end encryption, file transfer capabilities, and a modern GUI interface.

## Features

- **Secure Messaging**: End-to-end encryption for all messages
- **File Transfer**: Send and receive files with progress tracking
- **P2P Architecture**: Direct peer-to-peer communication
- **Discovery Server**: Central server for peer discovery
- **Modern GUI**: Built with PyQt6 for a sleek user interface
- **Logging**: Comprehensive logging system for debugging and monitoring

## Requirements

- Python 3.7 or higher
- Windows, Linux, or macOS

## Installation

1. **Clone or download the repository**

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

The required packages are:
- `cryptography` - For encryption
- `PyQt6` - For the GUI interface

## Running the Application

### 1. Start the Discovery Server

The server helps peers discover each other on the network.

```bash
python server.py
```

The server will start on port 5000 by default.

### 2. Start Client Instances

Open new terminal windows for each client you want to run:

```bash
python client.py
```


## Usage

### First Time Setup

1. When you start the application, you'll be prompted to enter a username
2. Click "OK" to proceed

### Connecting to the Server

1. Enter the server IP address in the "Server IP" field (use `localhost` or `127.0.0.1` for local testing)
2. Click "Connect to Server"
3. Wait for the peer list to populate

### Sending Messages

1. Select a peer from the list on the left
2. Type your message in the input field at the bottom
3. Press Enter or click "Send"

### Sending Files

1. Select a peer from the list
2. Click "Send File" button
3. Choose a file from your system
4. The file will be transferred with progress tracking
5. Received files are saved to `~/Downloads/ChatX_Received/`

### Receiving Files

1. When someone sends you a file, you'll see a progress indicator
2. After the transfer completes, a popup will ask if you want to open the file
3. Click "Yes" to open it immediately, or "No" to open it later from the Downloads folder

## Configuration

Default ports can be modified in `config.py`:
- Server port: 5000
- TCP port range: 6000-6999
- UDP port range: 7000-7999

## Network Setup

### Local Testing
Use `127.0.0.1` or `localhost` as the server IP.

### LAN Testing
1. Find your server's local IP address (e.g., `192.168.1.100`)
2. Ensure firewall allows connections on the required ports
3. Clients should use the server's LAN IP address

### Internet/Remote Testing
1. Port forward the server port (5000) and peer ports (6000-7999) on your router
2. Use your public IP address as the server IP
3. Ensure proper firewall configuration

## Security Features

- **End-to-End Encryption**: All messages are encrypted using Fernet symmetric encryption
- **Secure Key Exchange**: Keys are exchanged securely between peers
- **No Message Storage**: Messages are not stored on the server
- **Peer Verification**: Username-based peer identification

## Logging

Logs are stored in the `logs/` directory:
- `chatx_client_YYYYMMDD_HHMMSS.log` - Client logs
- `chatx_server_YYYYMMDD_HHMMSS.log` - Server logs

Log files include timestamps, severity levels, and detailed information for debugging.

## Troubleshooting

### Cannot connect to server
- Verify the server is running
- Check the server IP address is correct
- Ensure firewall allows connections on port 5000

### Cannot see other peers
- Make sure all clients are connected to the same server
- Click "Refresh" to update the peer list
- Check server logs for connection issues

### File transfer fails
- Ensure sufficient disk space in Downloads folder
- Check file permissions
- Verify network connection is stable

### Port already in use
- Close other instances of the application
- Change port configuration in `config.py`
- Check for other applications using the same ports

## Development

### Project Structure

```
ChatX/
├── client.py           # Client entry point (CLI)
├── gui.py             # GUI application
├── server.py          # Discovery server
├── network.py         # Network communication layer
├── encryption.py      # Encryption utilities
├── logger.py          # Logging configuration
├── config.py          # Configuration constants
├── threading_utils.py # Threading utilities
└── requirements.txt   # Python dependencies
```


