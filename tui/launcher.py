"""Open BitCraft in its own, large terminal window.

Engine behind the `bitcraft` command (tui/cli.py). It finds a terminal
(Windows Terminal, then a classic console on Windows; the usual emulators
on Linux; Terminal.app on macOS), opens a new window sized for the full
layout, and runs a session there.

A session runs the TUI. Inside a source checkout that has a loaded
database it also starts the API in the background (when nothing is serving
yet) and stops it again on exit; a pip-installed copy just connects to
--api-url or falls back to demo data.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from tui.api_client import DEFAULT_BASE_URL

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PACKAGE_ROOT / "backend"
# Only a source checkout carries the backend next to the tui package.
IN_CHECKOUT = (BACKEND / "app" / "main.py").is_file()
DEFAULT_SIZE = (190, 52)


@dataclass
class Options:
    """What to run and where."""

    source: str = "auto"  # auto | demo | api
    api_url: str = DEFAULT_BASE_URL
    size: tuple[int, int] = DEFAULT_SIZE


def workdir() -> Path:
    """Checkout root in development, otherwise wherever the user ran bitcraft."""
    return PACKAGE_ROOT if IN_CHECKOUT else Path.cwd()


# --- New window -------------------------------------------------------------


def session_command(opts: Options) -> list[str]:
    """Command line the new window runs."""
    cmd = [sys.executable, "-m", "tui.cli", "here"]
    if opts.source == "demo":
        cmd.append("--demo")
    elif opts.source == "api":
        cmd.append("--api")
    if opts.api_url != DEFAULT_BASE_URL:
        cmd += ["--api-url", opts.api_url]
    return cmd


def _open_windows(cmd: list[str], cols: int, rows: int, cwd: Path) -> str:
    wt = shutil.which("wt.exe") or shutil.which("wt")
    if wt:
        subprocess.Popen(
            [wt, "--size", f"{cols},{rows}", "--title", "BitCraft", "-d", str(cwd), *cmd],
            cwd=cwd,
        )
        return "Windows Terminal"
    line = subprocess.list2cmdline(cmd)
    subprocess.Popen(
        ["cmd.exe", "/c", f"title BitCraft & mode con: cols={cols} lines={rows} & {line}"],
        cwd=cwd,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    return "Command Prompt"


def _open_linux(cmd: list[str], cols: int, rows: int, cwd: Path) -> str:
    geometry = f"{cols}x{rows}"
    candidates = [
        ("gnome-terminal", [f"--geometry={geometry}", "--title=BitCraft", "--", *cmd]),
        ("konsole", ["-p", f"TerminalColumns={cols}", "-p", f"TerminalRows={rows}", "-e", *cmd]),
        ("xfce4-terminal", [f"--geometry={geometry}", "--title=BitCraft", "-x", *cmd]),
        ("kitty", ["-o", f"initial_window_width={cols}c", "-o", f"initial_window_height={rows}c", *cmd]),
        ("alacritty", ["-o", f"window.dimensions.columns={cols}", "-o", f"window.dimensions.lines={rows}", "-e", *cmd]),
        ("xterm", ["-geometry", geometry, "-title", "BitCraft", "-e", *cmd]),
        ("x-terminal-emulator", ["-e", *cmd]),
    ]
    for name, extra in candidates:
        exe = shutil.which(name)
        if exe:
            subprocess.Popen([exe, *extra], cwd=cwd, start_new_session=True)
            return name
    raise RuntimeError("no supported terminal emulator found")


def _applescript_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _open_macos(cmd: list[str], cols: int, rows: int, cwd: Path) -> str:
    line = f"cd {shlex.quote(str(cwd))} && {shlex.join(cmd)}"
    script = (
        'tell application "Terminal"\n'
        f"  do script {_applescript_quote(line)}\n"
        f"  set number of columns of front window to {cols}\n"
        f"  set number of rows of front window to {rows}\n"
        "  activate\n"
        "end tell"
    )
    subprocess.Popen(["osascript", "-e", script])
    return "Terminal.app"


def open_window(opts: Options) -> str:
    """Spawn a session in a new terminal window; returns the terminal used."""
    cmd = session_command(opts)
    cols, rows = opts.size
    cwd = workdir()
    if sys.platform == "win32":
        return _open_windows(cmd, cols, rows, cwd)
    if sys.platform == "darwin":
        return _open_macos(cmd, cols, rows, cwd)
    return _open_linux(cmd, cols, rows, cwd)


# --- Session (runs inside the window) ---------------------------------------


def api_healthy(api_url: str = DEFAULT_BASE_URL, timeout_s: float = 0.5) -> bool:
    """True when the API answers /health with status ok."""
    try:
        import httpx

        return httpx.get(f"{api_url}/health", timeout=timeout_s).json().get("status") == "ok"
    except Exception:  # noqa: BLE001 - any failure means "not serving"
        return False


def start_local_api() -> subprocess.Popen | None:
    """Serve the checkout's loaded database in the background, if there is one."""
    if not IN_CHECKOUT:
        return None
    if not (BACKEND / "bitcraft.db").exists() and not os.environ.get("DATABASE_URL"):
        print("No loaded database (run ml.pipeline + app.loader); using demo data.")
        return None
    log_path = BACKEND / "api.log"
    print("Starting the BitCraft API ...", flush=True)
    log = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - lives as long as the API
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "warning"],
        cwd=BACKEND,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"API failed to start (see {log_path}); using demo data.")
            return None
        if api_healthy():
            return proc
        time.sleep(0.3)
    print(f"API did not answer in time (see {log_path}); using demo data.")
    proc.terminate()
    return None


def run_session(opts: Options) -> int:
    """Run the TUI in this terminal (plus a local API when available)."""
    if IN_CHECKOUT:
        os.chdir(PACKAGE_ROOT)
    api_proc = None
    try:
        local = opts.api_url == DEFAULT_BASE_URL
        if opts.source != "demo" and local and not api_healthy():
            api_proc = start_local_api()
        from tui.app import main as tui_main

        tui_args = {"demo": ["--demo"], "api": ["--api"]}.get(opts.source, [])
        tui_main([*tui_args, "--api-url", opts.api_url])
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:  # noqa: BLE001 - keep the window open long enough to read it
        traceback.print_exc()
        input("\nBitCraft stopped with an error. Press Enter to close this window.")
        return 1
    finally:
        if api_proc is not None:
            api_proc.terminate()
            try:
                api_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_proc.kill()
