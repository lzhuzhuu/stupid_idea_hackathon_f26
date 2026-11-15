#!/usr/bin/env python3
"""Starts the face servers the Chrome extension (ui/) talks to.

    python3 run.py              # both: Everyone Is You on 8765, Potato on 8766
    python3 run.py everyone     # just Everyone Is You
    python3 run.py potato       # just Potato

Each server runs with its own Python environment (see SERVERS). Their output is shown here,
each line tagged with the server's name. Ctrl+C stops them all.
"""
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# name -> (folder, port, Python environments to try, first that exists wins)
SERVERS = {
    "everyone": ("everyone_is_you", 8765, [".venv", "everyone_is_you/.venv"]),
    "potato": ("potato", 8766, ["potato/.venv", ".venv"]),
}
SETUP = {
    "everyone": "python3.12 -m venv .venv && .venv/bin/pip install -r everyone_is_you/requirements.txt",
    "potato": "python3.12 -m venv potato/.venv && potato/.venv/bin/pip install -r potato/requirements.txt",
}


def python_for(name):
    for env in SERVERS[name][2]:
        python = ROOT / env / "bin" / "python"
        if python.exists():
            return python
    return None


def port_taken(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def show_output(name, process):
    for line in process.stdout:
        print(f"[{name}] {line}", end="", flush=True)
    print(f"[{name}] stopped (exit code {process.wait()})", flush=True)


def stop(*_):
    raise KeyboardInterrupt


def main():
    # However this is stopped (Ctrl+C, kill, closing the window), take the servers down with it.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    names = sys.argv[1:] or list(SERVERS)
    unknown = [n for n in names if n not in SERVERS]
    if unknown:
        sys.exit(f"Unknown server {', '.join(unknown)}. Choose from: {', '.join(SERVERS)}")

    running = []
    for name in names:
        folder, port, _ = SERVERS[name]
        python = python_for(name)
        if python is None:
            print(f"[{name}] skipped: no Python environment yet. Set it up with:\n    {SETUP[name]}")
            continue
        if port_taken(port):
            print(f"[{name}] skipped: port {port} is already in use (running in another Terminal?)")
            continue
        print(f"[{name}] starting on http://127.0.0.1:{port} (test page: /test)")
        process = subprocess.Popen(
            [str(python), "-u", str(ROOT / folder / "app.py")],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        threading.Thread(target=show_output, args=(name, process), daemon=True).start()
        running.append(process)

    if not running:
        sys.exit("Nothing started.")
    try:
        for process in running:
            process.wait()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        for process in running:
            if process.poll() is None:
                process.terminate()
        for process in running:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
