#!/usr/bin/env python3
"""Start the local API and browser UI on stable, configurable ports."""

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
DEFAULT_BACKEND_PORT = 53686
DEFAULT_FRONTEND_PORT = 53687


def configured_port(variable: str, default: int) -> int:
    raw_value = os.environ.get(variable, str(default))
    try:
        port = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{variable} muss eine Portnummer sein, nicht {raw_value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{variable} muss zwischen 1 und 65535 liegen")
    return port


def ensure_port_available(port: int, label: str, variable: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"{label}-Port {port} ist bereits belegt. "
                f"Beende den anderen Dienst oder setze {variable} bewusst auf einen anderen Port."
            ) from exc


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

    try:
        backend_port = configured_port("CHESS_COACH_BACKEND_PORT", DEFAULT_BACKEND_PORT)
        frontend_port = configured_port("CHESS_COACH_FRONTEND_PORT", DEFAULT_FRONTEND_PORT)
        ensure_port_available(backend_port, "Backend", "CHESS_COACH_BACKEND_PORT")
        ensure_port_available(frontend_port, "Browser", "CHESS_COACH_FRONTEND_PORT")
    except (RuntimeError, ValueError) as exc:
        print(f"\nChess Opening Coach konnte nicht starten:\n  {exc}\n", file=sys.stderr)
        return 2
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
