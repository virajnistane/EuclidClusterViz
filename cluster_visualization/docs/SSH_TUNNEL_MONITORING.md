# SSH Tunnel Connection Monitoring

## Overview

The Cluster Visualization Dash App now includes automatic connection monitoring to help users set up SSH tunneling correctly when accessing the app from remote servers.

## Features

### 🔗 SSH Tunnel Detection
- Automatically detects when users connect via SSH tunnel
- Provides clear setup instructions with actual hostname
- Monitors connection status in real-time

### ⚠️ Automated Warnings
- Warns users if no connections are detected within 2 minutes
- Provides step-by-step SSH tunnel setup instructions
- Shows the exact command with the correct hostname

### ✓ Connection Confirmation
- Confirms when users successfully connect
- Validates that SSH tunnel is working correctly
- Shows connection details (browser, IP)

## How It Works

### Startup Messages
When the app starts, users see:
```
=== Cluster Visualization Dash App ===
Server starting on: http://localhost:8050

🔗 SSH TUNNEL REQUIRED:
   This app runs on a remote server. To access it:
   1. Open a NEW terminal on your LOCAL machine
   2. Run: ssh -L 8050:localhost:8050 username@cca012
   3. Keep that SSH connection alive
   4. Open browser to: http://localhost:8050
   (Replace 'username' with your actual username)

Connection monitoring started - will warn if no users connect within 2 minutes
```

### Successful Connection
When a user properly connects via SSH tunnel:
```
✓ User successfully connected at 09:02:31
  ✓ SSH tunnel appears to be working correctly
  Browser: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0
  Connection from: 127.0.0.1
```

### Warning Messages
If no connections are detected after 2 minutes:
```
======================================================================
⚠️  WARNING: No users have connected yet!
   App has been running for 2.0 minutes

🔗 REQUIRED: SSH Tunnel Setup
   This app runs on a remote server and requires SSH tunneling.
   
   1. Open a NEW terminal on your LOCAL machine
   2. Run this command:
      ssh -L 8050:localhost:8050 username@cca012
   3. Keep that SSH connection alive
   4. Open your browser to: http://localhost:8050

   Replace 'username' with your actual username
======================================================================
```

## Technical Implementation

### Connection Detection
- Uses Flask middleware to track HTTP requests
- Filters for actual browser connections (ignores internal Dash requests)
- Records User-Agent and IP address information

### Background Monitoring
- Runs monitoring thread in background (daemon thread)
- Checks connection status every 10 seconds
- Automatically stops when app shuts down

### Hostname Detection
- Automatically detects the server hostname (`socket.gethostname()`)
- Provides exact SSH command with correct hostname
- Falls back to "remotehost" if hostname detection fails

### Architecture
- Integrated into both modular core and fallback implementations
- Works with existing launch scripts and deployment methods
- Non-intrusive monitoring that doesn't affect app performance

## Usage

### For Users
1. Start the app using `./launch.sh`
2. Follow the SSH tunnel instructions displayed
3. Open `http://localhost:8050` in your local browser
4. The app will confirm successful connection

### For Administrators
- No additional configuration required
- Monitoring starts automatically
- All messages are displayed in the server console
- Compatible with existing deployment workflows

## Benefits

1. **Reduces Support Requests**: Clear instructions prevent common SSH tunnel setup errors
2. **Faster Troubleshooting**: Immediate feedback if connection setup is incorrect
3. **Better User Experience**: Step-by-step guidance for remote access
4. **Automatic Detection**: No manual intervention required

## Future Enhancements

Potential improvements:
- Detect multiple users and show connection count
- Monitor for disconnections and warn about SSH tunnel drops
- Integration with web-based connection status dashboard
- Customizable warning timing and messages
