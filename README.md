# Claude C2 Lab

An intentionally simple command-and-control stack that pairs a Python HTTP server with a VBScript agent for university red-team labs. The project is designed for offline environments so students can explore beaconing, tasking, and file exfiltration workflows without touching production systems.

> ⚠️ **Educational use only.** Keep both the server and the Windows agent inside an isolated lab or sandboxed network segment.

## Components

| File | Description |
| --- | --- |
| `server.py` | Python3 HTTP server plus an operator console. Handles task queueing, report ingestion, and base64 loot extraction. |
| `agent.vbs` | Windows Script Host beacon that polls `/task`, executes instructions, and posts results or files back to `/report`. |
| `task_queue.json` | On-disk persistence for queued tasks so work survives restarts. |
| `agent_reports.txt` | Rolling log of everything the agent reports (shell output, heartbeat messages, errors). |
| `loot/` | Binary exfiltration drop folder. Files are automatically typed (png, docx, exe, etc.) and named after the source IP and timestamp. |

## Quick Start

### Requirements
- Python 3.8+ on the Linux/macOS host running the C2 server.
- A Windows lab VM (or sandbox) with Windows Script Host enabled for running `agent.vbs`.
- Network connectivity between the agent host and the server (default `8080/tcp`). Keep it on a closed lab switch or host-only network.

### 1. Launch the server
```bash
python3 server.py
```
The server prints a safety banner, loads any queued work from `task_queue.json`, seeds a couple of demo tasks if empty, and starts:
- an HTTP listener on `0.0.0.0:8080`
- an interactive operator console in your terminal

### 2. Queue tasks
Use the operator console (`C2>` prompt) or `curl` against `/enqueue` to add instructions. Examples:
```
C2> add SHELL:whoami
C2> add GET_FILE:C:\\ctf\\flag.txt
```
Tasks are FIFO and removed once an agent retrieves them. The queue is persisted automatically.

### 3. Run the Windows agent
1. Copy `agent.vbs` to the Windows lab host.
2. Edit the `C2_URL` and `REPORT_URL` constants if your server IP differs.
3. Double-click the script or run `wscript.exe agent.vbs`.

The agent:
- Beacons every 10 seconds (adjust `BEACON_INTERVAL_MS`).
- Sends an initial system inventory plus heartbeat updates every 10 loops.
- Executes supported task types and returns output.
- Stops when it receives `KILL`/`EXIT` or when `C:\Windows\Temp\agent_kill.txt` exists.

## Operator Console Reference

| Command | Behavior |
| --- | --- |
| `queue` | Dump the pending task list. |
| `add <TASK>` | Append a new task string to the queue. |
| `clear` | Remove all pending work. |
| `loot` | List exfiltrated files and sizes in `loot/`. |
| `reports` | Show the last 20 lines from `agent_reports.txt`. |
| `exit` | Terminate the HTTP server and console. |

The same functionality is exposed via HTTP endpoints, enabling scripted control:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/task` | Agent retrieves the next task (JSON). Returns `{"task": "sleep"}` when idle. |
| `POST` | `/report` | Agent pushes shell output or base64 file data. Server logs everything and attempts to decode loot. |
| `POST` | `/enqueue` | Operator adds a task by POSTing the raw string body. |
| `GET` | `/queue` | View queue contents in JSON (useful for dashboards). |

## Task Format

Every queued entry is a single string stored as `{ "task": "<INSTRUCTION>" }`. The agent splits on the first colon and supports the following verbs:

- `SHELL:<cmd>` – Run a command via `cmd.exe /c` and return stdout/stderr.
- `GET_FILE:<path>` / `UPLOAD:<path>` – Read the file, base64-encode it, and POST the blob. The server auto-detects file type and saves it under `loot/`.
- `SYSINFO` – Return hostname, user, OS, and domain details via WMI.
- `KILL` / `EXIT` / `QUIT` – Send a final message and terminate the agent.
- `SLEEP` – No-op (used by the server when the queue is empty).

You can seed tasks manually by editing `task_queue.json` before startup or via the helper `add_task()` inside `server.py`.

## Loot & Reporting Pipeline

1. Agent POSTs base64 data or plaintext output to `/report`.
2. `server.py` appends the raw message to `agent_reports.txt` for auditing.
3. `try_save_base64()` attempts to decode the payload and infer its type using magic bytes (images, Office docs, archives, executables, JSON, text). Successful decodes are dropped into `loot/` with the pattern `<ip>_<timestamp>.<ext>`.
4. Console output mirrors each step so you can watch uploads in real time.

## Suggested Lab Exercises 

1. **Beacon analysis** – Capture the HTTP traffic with Wireshark to understand periodic polling and OPSEC considerations.
2. **Task extensions** – Implement new verbs (e.g., `PERSIST`, `SCREENSHOT`) in both the Python server and VBScript agent.
3. **Multiple agents** – Run several `agent.vbs` instances with unique `AGENT_ID`s and observe how the shared queue behaves.
4. **Detection engineering** – Write Snort/Suricata signatures for the `/task` and `/report` flows, or build Sigma rules for the process activity on Windows.

Keep iterating within the confines of your isolated environment and treat the project as a safe place to experiment with C2 tradecraft fundamentals.
