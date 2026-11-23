"""Visible Windows supervisor for the local BuildTrack Flask server."""
from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from config import BASE_DIR, Config

EXPECTED_PORT = 5001
APP_URL = f"http://127.0.0.1:{EXPECTED_PORT}"
HEALTH_URL = f"{APP_URL}/api/health"
ERROR_ALREADY_EXISTS = 183
RETRY_SECONDS = (2, 5, 10, 20, 30)


def _log_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BuildTrack" / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / "startup.log"


def _log(message: str) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} {message}"
    print(line, flush=True)
    try:
        with _log_path().open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    except OSError as exc:
        print(f"Could not write startup log {_log_path()}: {exc}", flush=True)


def _healthy() -> bool:
    """Probe loopback directly; proxy settings must never intercept localhost."""
    try:
        opener = build_opener(ProxyHandler({}))
        request = Request(HEALTH_URL, headers={"Cache-Control": "no-cache"})
        with opener.open(request, timeout=3) as response:
            if response.status != 200:
                return False
            import json
            data = json.loads(response.read().decode("utf-8"))
            return data.get("service") == "BuildTrack" and data.get("status") == "ok"
    except (OSError, URLError, ValueError):
        return False


def _acquire_single_instance():
    if os.name != "nt":
        raise RuntimeError("BuildTrack startup supervisor is intended for Windows.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, True, "Local\\BuildTrackStartupSupervisor")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return kernel32, handle


def _port_is_available() -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("0.0.0.0", EXPECTED_PORT))
        return True
    except OSError as exc:
        _log(f"Port {EXPECTED_PORT} is occupied or unavailable ({exc}). BuildTrack will not start a competing server.")
        _log(f"Inspect the listener with: netstat -ano -p tcp | findstr :{EXPECTED_PORT}")
        return False
    finally:
        probe.close()


def _open_installed_app() -> None:
    try:
        # Existing Chrome app shortcuts can be bound to an older origin (for
        # example, 127.0.0.1:5000). Launch the PWA shell at the canonical
        # server origin rather than reusing an origin-bound app ID.
        candidates = (
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        )
        chrome = next((candidate for candidate in candidates if candidate.is_file()), None)
        if chrome is None:
            _log(f"Chrome was not found. The healthy server remains available at {APP_URL}.")
            return
        subprocess.Popen(
            [str(chrome), "--profile-directory=Default", f"--app={APP_URL}"],
            close_fds=True,
        )
        _log(f"Opened BuildTrack at its canonical PWA origin {APP_URL} after the health check succeeded.")
    except OSError as exc:
        _log(f"Could not open the BuildTrack app: {exc}. Server remains at {APP_URL}.")


def _stream_backend_output(pipe) -> None:
    try:
        with _log_path().open("a", encoding="utf-8") as logfile:
            for line in iter(pipe.readline, ""):
                sys.stdout.write(line)
                sys.stdout.flush()
                logfile.write(line)
                logfile.flush()
    except OSError as exc:
        print(f"Could not capture Flask output in startup.log: {exc}", flush=True)
    finally:
        pipe.close()


def _start_backend() -> subprocess.Popen:
    python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        raise FileNotFoundError(f"Existing virtual environment Python was not found: {python}")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    _log(f"Starting Flask with {python}; project={BASE_DIR}; port={EXPECTED_PORT}; database={Config.DATABASE_PATH}.")
    _log(f"Python environment: FLASK_ENV={env.get('FLASK_ENV', '(default development)')}; SECRET_KEY configured={bool(env.get('SECRET_KEY'))}.")
    child = subprocess.Popen(
        [str(python), "-u", "-m", "api.app"], cwd=BASE_DIR, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    threading.Thread(target=_stream_backend_output, args=(child.stdout,), daemon=True).start()
    _log(f"Flask process started (PID {child.pid}); waiting for /api/health. Its output is streamed here and to startup.log.")
    return child


def main() -> int:
    if Config.SERVER_PORT != EXPECTED_PORT:
        _log(f"Refusing to start: config.py uses port {Config.SERVER_PORT}; BuildTrack must use {EXPECTED_PORT}.")
        return 2
    try:
        mutex = _acquire_single_instance()
    except Exception as exc:
        _log(f"Could not create the single-instance startup guard: {exc}")
        return 2
    if mutex is None:
        _log("Another BuildTrack supervisor is already running in this Windows session; this launch will not start a duplicate.")
        return 0

    kernel32, handle = mutex
    _log(f"BuildTrack supervisor active. Health URL: {HEALTH_URL}. Startup log: {_log_path()}.")
    child = None
    failures = 0
    app_opened = False
    try:
        while True:
            if _healthy():
                if not app_opened:
                    _log("An existing BuildTrack server is healthy; no second Flask process will be started.")
                    _open_installed_app()
                    app_opened = True
                time.sleep(5)
                continue

            if child is not None and child.poll() is not None:
                _log(f"Flask exited with code {child.returncode}; complete output is above and in {_log_path()}.")
                child = None
                failures += 1

            if child is None:
                if not _port_is_available():
                    _log("Waiting 10 seconds before checking port 5001 again. No other process was terminated.")
                    time.sleep(10)
                    continue
                delay = RETRY_SECONDS[min(failures, len(RETRY_SECONDS) - 1)]
                if failures:
                    _log(f"Retry {failures}; waiting {delay} seconds before starting Flask again.")
                    time.sleep(delay)
                try:
                    child = _start_backend()
                    failures = 0
                except Exception as exc:
                    failures += 1
                    _log(f"Could not launch Flask: {type(exc).__name__}: {exc}")
                    continue

            # Never kill a live Flask process just because startup is slow.
            # Keep the console visible and continue probing until it is healthy
            # or the child exits with its captured error output.
            if _healthy():
                _log("BuildTrack /api/health returned HTTP 200 with service=BuildTrack and status=ok.")
                if not app_opened:
                    _open_installed_app()
                    app_opened = True
                continue
            if child.poll() is not None:
                continue
            time.sleep(2)
    except KeyboardInterrupt:
        _log("Shutdown requested in the visible BuildTrack terminal.")
    finally:
        if child is not None and child.poll() is None:
            _log(f"Stopping the Flask child started by this supervisor (PID {child.pid}).")
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
