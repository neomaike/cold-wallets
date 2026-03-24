#!/usr/bin/env python3
"""
Tor Background Manager — download, start, stop tor.exe
Uses Tor Expert Bundle (standalone, no browser needed).
SOCKS5 proxy on 127.0.0.1:9050
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

TOR_DIR = Path(__file__).parent / "tor_runtime"
TOR_EXE = TOR_DIR / "tor" / "tor.exe"
TORRC = TOR_DIR / "torrc"
TOR_DATA = TOR_DIR / "data"
TOR_PID_FILE = TOR_DIR / "tor.pid"
SOCKS_PORT = 9050

# Tor Expert Bundle URL (Windows x86_64)
TOR_VERSION = "14.0.7"
TOR_URL = (
    "https://archive.torproject.org/tor-package-archive/"
    f"torbrowser/{TOR_VERSION}/"
    f"tor-expert-bundle-windows-x86_64-{TOR_VERSION}.tar.gz"
)


def _tcp_probe(port, timeout=0.5):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
        sock.close()
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def is_tor_running():
    """Check if any Tor SOCKS proxy is available"""
    return _tcp_probe(9050) or _tcp_probe(9150)


def get_tor_port():
    """Return active Tor SOCKS port or None"""
    if _tcp_probe(9150):
        return 9150
    if _tcp_probe(9050):
        return 9050
    return None


def _get_pid():
    """Get stored tor.exe PID"""
    if TOR_PID_FILE.exists():
        try:
            pid = int(TOR_PID_FILE.read_text().strip())
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}",
                     "/FI", "IMAGENAME eq tor.exe"],
                    capture_output=True, text=True,
                    creationflags=0x08000000)
                if "tor.exe" in result.stdout:
                    return pid
        except Exception:
            pass
    return None


def is_managed_tor_running():
    """Check if our managed tor.exe is running"""
    return _get_pid() is not None


def download_tor(progress_cb=None):
    """Download and extract Tor Expert Bundle"""
    if TOR_EXE.exists():
        return True, "Already downloaded"

    if requests is None:
        return False, "requests library not installed"

    TOR_DIR.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb("Downloading Tor Expert Bundle...")

    try:
        r = requests.get(TOR_URL, stream=True, timeout=120)
        r.raise_for_status()

        # Download to temp file (not RAM)
        import tarfile
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".tar.gz",
                                   dir=str(TOR_DIR)))
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

        if progress_cb:
            progress_cb("Extracting...")

        with tarfile.open(str(tmp), mode="r:gz") as tar:
            # Filter to prevent path traversal (Python 3.12+)
            try:
                tar.extractall(path=str(TOR_DIR),
                               filter="data")
            except TypeError:
                # Python < 3.12: manual safety check
                for member in tar.getmembers():
                    dest = Path(TOR_DIR / member.name).resolve()
                    if not str(dest).startswith(
                            str(TOR_DIR.resolve())):
                        continue  # Skip path traversal
                tar.extractall(path=str(TOR_DIR))

        tmp.unlink(missing_ok=True)

        if not TOR_EXE.exists():
            # Search for it
            found = list(TOR_DIR.rglob("tor.exe"))
            if found:
                return True, f"Downloaded (tor.exe at {found[0]})"
            return False, "Download succeeded but tor.exe not found"

        return True, "Downloaded and extracted"

    except Exception as e:
        return False, f"Download failed: {e}"


def _write_torrc():
    """Write minimal torrc"""
    TOR_DATA.mkdir(parents=True, exist_ok=True)
    TORRC.write_text(
        f"SocksPort {SOCKS_PORT}\n"
        f"DataDirectory {TOR_DATA.as_posix()}\n"
        "Log notice stderr\n"
    )


def start_tor():
    """Start tor.exe in background"""
    if is_tor_running():
        port = get_tor_port()
        return True, f"Tor already running on port {port}"

    # Find tor.exe
    tor_exe = None
    if TOR_EXE.exists():
        tor_exe = TOR_EXE
    else:
        # Search in extracted directory
        found = list(TOR_DIR.rglob("tor.exe"))
        if found:
            tor_exe = found[0]

    if tor_exe is None:
        # Try to find Tor Browser's tor.exe
        tor_browser_paths = [
            Path(os.environ.get("USERPROFILE", "")) /
            "Desktop" / "Tor Browser" / "Browser" /
            "TorBrowser" / "Tor" / "tor.exe",
            Path("C:/Tor Browser/Browser/TorBrowser/Tor/tor.exe"),
            Path(os.environ.get("PROGRAMFILES", "")) /
            "Tor Browser" / "Browser" /
            "TorBrowser" / "Tor" / "tor.exe",
        ]
        for p in tor_browser_paths:
            if p.exists():
                tor_exe = p
                break

    if tor_exe is None:
        return False, "tor.exe not found. Use download first."

    _write_torrc()

    try:
        proc = subprocess.Popen(
            [str(tor_exe), "-f", str(TORRC)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=(
                0x08000000 |  # CREATE_NO_WINDOW
                0x00000008    # DETACHED_PROCESS
            ),
        )
        TOR_PID_FILE.write_text(str(proc.pid))

        # Wait for SOCKS port to open (max 30s)
        for _ in range(60):
            time.sleep(0.5)
            if _tcp_probe(SOCKS_PORT):
                return True, f"Tor started (PID {proc.pid}, port {SOCKS_PORT})"

        return False, (
            f"Tor started (PID {proc.pid}) but SOCKS "
            f"port {SOCKS_PORT} not responding after 30s"
        )

    except Exception as e:
        return False, f"Failed to start tor: {e}"


def stop_tor():
    """Stop managed tor.exe"""
    pid = _get_pid()
    if pid is None:
        return True, "Tor not running (managed)"

    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            creationflags=0x08000000)
        TOR_PID_FILE.unlink(missing_ok=True)
        return True, f"Tor stopped (PID {pid})"
    except Exception as e:
        return False, f"Failed to stop: {e}"


def status():
    """Full Tor status"""
    port = get_tor_port()
    managed = is_managed_tor_running()
    downloaded = TOR_EXE.exists() or bool(list(TOR_DIR.rglob("tor.exe")))

    return {
        "running": port is not None,
        "port": port,
        "managed": managed,
        "downloaded": downloaded,
        "tor_exe": str(TOR_EXE) if TOR_EXE.exists() else None,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tor Manager")
    parser.add_argument("action",
                        choices=["status", "start", "stop", "download"])
    args = parser.parse_args()

    if args.action == "status":
        s = status()
        print(f"Running: {s['running']} (port {s['port']})")
        print(f"Managed: {s['managed']}")
        print(f"Downloaded: {s['downloaded']}")

    elif args.action == "download":
        ok, msg = download_tor(progress_cb=print)
        print(f"{'OK' if ok else 'FAIL'}: {msg}")

    elif args.action == "start":
        ok, msg = start_tor()
        print(f"{'OK' if ok else 'FAIL'}: {msg}")

    elif args.action == "stop":
        ok, msg = stop_tor()
        print(f"{'OK' if ok else 'FAIL'}: {msg}")
