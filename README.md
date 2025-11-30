# ChatX - Peer-to-Peer Chat Application

ChatX is a peer-to-peer messaging application with end-to-end encryption and file transfer capabilities.

## Requirements

- Python 3.7 or higher
- PyQt6
- cryptography

## Installation

Install required packages:

```bash
pip install PyQt6 cryptography
```

## Running ChatX

### Step 1: Start the Server

The discovery server must be running first:

```bash
python server.py
```

The server will start on `localhost:8888` and display connection logs.

### Step 2: Start Client(s)

Open a new terminal window for each client:

```bash
python gui.py
```

## How to Use

1. **Enter Username**: When the client starts, enter your username in the dialog box
2. **Connect to Server**: Click "Connect to Server" button
3. **Select a Peer**: Choose a peer from the "Online Peers" list on the left
4. **Send Messages**: Type your message and press Enter or click "Send"
5. **Send Files**: Click "Send File" button and select a file to transfer
6. **Refresh Peers**: Click "Refresh" to update the list of online peers

## File Transfers

- Sent and received files are saved to `~/Downloads/ChatX_Received/`
- Progress bars show transfer status
- You'll be prompted to open files after receiving them

## Configuration

Default settings in `config.py`:
- Server: `localhost:8888`
- TCP ports: `6000-6999`
- UDP ports: `7000-7999`

## Troubleshooting

**Cannot connect to server**
- Make sure `server.py` is running first
- Check that no other program is using port 8888

**Cannot see other peers**
- Click "Refresh" button
- Ensure all clients are connected to the same server

**File transfer fails**
- Check that the receiving client is online
- Verify you have write permissions in the Downloads folder

## Stopping the Application

- **Server**: Press `Ctrl+C` in the server terminal
- **Client**: Click the "Quit" button or close the window
