# SSH Tunnel Connection Monitoring

## Overview

The app includes automatic connection monitoring to detect SSH tunneling issues and guide users through setup.

**For full setup instructions, see [README.md — Quick Remote Access Setup](https://github.com/virajnistane/EuclidClusterViz/blob/main/README.md#quick-remote-access-setup).**

## Per-User Port Assignment

Each user is assigned a deterministic remote port:

```
remote_port = 8050 + (uid % 1000)
```

- UID is stable across all cluster nodes (set at account creation, synced via LDAP/NIS)
- Different users → different ports → no collision on shared interactive nodes
- Port is printed at startup with the exact `ssh -L` command to use

The SSH tunnel always maps **fixed local port 8050** → your personal remote port:
```bash
ssh -L 8050:localhost:<YOUR_PORT> user@host
```
So `http://localhost:8050` works as a permanent bookmark regardless of remote port.

## Connection Status Messages

### Startup (port bound)
```
┌─────────────────────────────────────────────────────────────┐
│  🖥️  REMOTE ACCESS — run this on your LOCAL machine:        │
│                                                             │
│ 1) ssh -L 8050:localhost:8134 alice@node001.cluster.fr      │
│ 2) cd /path/to/ClusterViz                                   │
│ 3) ./launch.sh                                              │
│ 4) Then open in browser:  http://localhost:8050             │
│                                                             │
│  Run step 1 in a NEW terminal — keep the connection open.   │
└─────────────────────────────────────────────────────────────┘
```

### Successful browser connection
```
✓ User successfully connected at 09:02:31
  ✓ SSH tunnel appears to be working correctly
  Browser: Mozilla/5.0 (...)
  Connection from: 127.0.0.1
```

### Warning (no connection after 1 minute)
```
⚠️  WARNING: No users have connected yet!
   App has been running for 1.0 minutes

🔗 REQUIRED: SSH Tunnel Setup
   1. Open a NEW terminal on your LOCAL machine
   2. Run this command:
      ssh -L 8050:localhost:8134 alice@node001.cluster.fr
   3. Keep that SSH connection alive
   4. Open your browser to: http://localhost:8050
```

## Technical Implementation

- Flask `before_request` middleware records browser connections (filters Mozilla/Chrome/Safari/Firefox)
- `ConnectionMonitor` daemon thread checks every 10 seconds
- `bound_port` passed from `try_multiple_ports()` → `run()` → `start_monitoring()` so warning always shows the correct port
- Monitoring stops cleanly when the server shuts down

## Already Logged In Without `-L`?

If you connected to the remote node in an existing session (without port forwarding):
1. Look at the app startup output for the tunnel command
2. Open a **new terminal** on your local machine
3. Run: `ssh -L 8050:localhost:<YOUR_PORT> user@host`
4. Open `http://localhost:8050` — no disconnect needed
