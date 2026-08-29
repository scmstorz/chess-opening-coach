#!/usr/bin/env python3
"""Start the local API and browser UI on operating-system-selected free ports."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(url: str, timeout: float = 25) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Lokaler Dienst wurde nicht rechtzeitig erreichbar: {url}")


def main() -> int:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])

    backend_port = free_port()
    frontend_port = free_port()
    environment = os.environ.copy()
    environment["CHESS_COACH_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "chess_coach.api:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
    )
    frontend = subprocess.Popen(
        [
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "localhost",
            "--port",
            str(frontend_port),
            "--strictPort",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
    )
    processes = [backend, frontend]

    def stop(*_: object) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        wait_for(f"http://127.0.0.1:{backend_port}/api/health")
        wait_for(f"http://localhost:{frontend_port}/")
        print("\nChess Opening Coach ist bereit:")
        print(f"  http://localhost:{frontend_port}/")
        print("\nMit Ctrl+C beenden.\n")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next((process.returncode or 1 for process in processes if process.poll()), 1)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())

