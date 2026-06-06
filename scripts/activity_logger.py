#!/usr/bin/env python3
"""Local activity logger — lets Krish "see" what you're working on.

Every 15 seconds this samples the focused X11 window (title + app class) and
your idle time, then aggregates contiguous stretches of using the *same* app.
A row is written to the SQLite `logs` table only when the focus changes or you
go idle — never on every tick — so each row is one finished stretch of work.

Runs 100% locally. Needs an X11 session and the command-line tools xdotool,
xprop and xprintidle. Stop it with Ctrl-C; the in-progress stretch is flushed
on exit so nothing is lost.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

# Make the `backend` package importable when run as `python scripts/...`.
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import db  # noqa: E402

# Sampling cadence and the threshold past which we count you as idle.
TICK_SECONDS = 15
IDLE_THRESHOLD_MS = 60_000

# The CLI tools we depend on, mapped to the apt package that provides each.
REQUIRED_TOOLS = {
    "xdotool": "xdotool",
    "xprop": "x11-utils",
    "xprintidle": "xprintidle",
}


def _run(cmd: list[str]) -> str | None:
    """Run a command, returning its stripped stdout, or None on failure."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.strip()


def check_dependencies() -> None:
    """Exit cleanly with an apt hint if any required tool is missing."""
    missing = [t for t in REQUIRED_TOOLS if shutil.which(t) is None]
    if missing:
        packages = sorted({REQUIRED_TOOLS[t] for t in missing})
        print(f"Missing required tool(s): {', '.join(missing)}")
        print("Install them with:")
        print(f"    sudo apt install {' '.join(packages)}")
        sys.exit(1)


def idle_ms() -> int:
    """Milliseconds since the last input event (0 if unavailable)."""
    out = _run(["xprintidle"])
    try:
        return int(out) if out is not None else 0
    except ValueError:
        return 0


def active_window() -> tuple[str, str] | None:
    """Return (title, app_class) for the focused window, or None if there isn't
    one (e.g. focus is on the bare desktop)."""
    win_id = _run(["xdotool", "getactivewindow"])
    if not win_id:
        return None

    title = _run(["xdotool", "getwindowname", win_id]) or "(untitled)"
    app = _parse_wm_class(_run(["xprop", "-id", win_id, "WM_CLASS"]))
    return title, app


def _parse_wm_class(raw: str | None) -> str:
    """Pull the class name out of an xprop WM_CLASS line.

    e.g. `WM_CLASS(STRING) = "navigator", "firefox"` -> "firefox". The second
    quoted value is the class; we fall back to whatever we can find.
    """
    if not raw or "=" not in raw:
        return "(unknown)"
    values = [part.strip().strip('"') for part in raw.split("=", 1)[1].split(",")]
    values = [v for v in values if v]
    return values[-1] if values else "(unknown)"


def main() -> None:
    check_dependencies()
    print(
        f"activity logger running — sampling every {TICK_SECONDS}s, "
        f"idle after {IDLE_THRESHOLD_MS // 1000}s. Ctrl-C to stop.\n"
    )

    # The stretch currently being accumulated.
    cur_app: str | None = None
    cur_title: str | None = None
    accumulated = 0.0

    def flush() -> None:
        """Write the current stretch as a single row, if there is one."""
        nonlocal cur_app, cur_title, accumulated
        secs = int(round(accumulated))
        if cur_app is not None and secs > 0:
            db.save_log(activity=cur_title, app=cur_app, seconds=secs)
            print(f"  ↳ saved: {cur_app} · {secs}s · {cur_title}")
        cur_app, cur_title, accumulated = None, None, 0.0

    last_t = time.monotonic()
    try:
        while True:
            time.sleep(TICK_SECONDS)
            now = time.monotonic()
            delta = now - last_t
            last_t = now

            win = active_window()
            if idle_ms() > IDLE_THRESHOLD_MS or win is None:
                flush()
                print(f"{'—':<24} ·   0s · idle")
                continue

            title, app = win
            if app == cur_app:
                accumulated += delta
                cur_title = title  # keep the freshest title for this stretch
            else:
                flush()
                cur_app, cur_title, accumulated = app, title, delta

            print(f"{app:<24} · {int(accumulated):>3d}s · active")
    except KeyboardInterrupt:
        print("\nstopping — flushing current stretch…")
        flush()


if __name__ == "__main__":
    main()
