"""Daily update of the BRVM database: download new bulletins, extract them, refresh the QC report.

Usage:
    python daily_update.py               # download + extract + QC report
    python daily_update.py --notebook    # ... and re-run the showcase notebook
    python daily_update.py --no-download # only extract PDFs already in boc/

Designed to run unattended (Windows Task Scheduler, see UPDATE.md):
* idempotent and incremental: only new or changed bulletins are downloaded and extracted;
* catches up automatically after days without a run (PC off, holidays);
* re-checks the last 5 days, so a bulletin published late is picked up the next evening;
* one run at a time (lock file), full log in logs/daily_update_YYYY-MM-DD.log and one summary
  line per run in logs/daily_update.log;
* exit code 0 = success, 1 = a step failed, 2 = another run is in progress.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# the steps run with python.exe (they print to stdout), even when this script runs under pythonw.exe
PY = str(Path(sys.executable).with_name("python.exe"))
LOGS = ROOT / "logs"
LOCK = ROOT / "logs" / "daily_update.lock"
DB = ROOT / "brvm.db"


def db_state() -> dict:
    if not DB.exists():
        return {"bulletins": 0, "last": None}
    with sqlite3.connect(DB) as con:
        n, last = con.execute("SELECT COUNT(*), MAX(date) FROM documents").fetchone()
    return {"bulletins": n, "last": last}


def run(step: str, args: list[str], log) -> bool:
    """Run one step as a subprocess, streaming its output to the log."""
    log(f"--- {step}: {' '.join(args)}")
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    # no console window for the steps: the scheduled task runs windowless (pythonw.exe), and a visible
    # console can be closed by mistake, which kills the run (exit code 0xC000013A)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, creationflags=flags)
    for line in (proc.stdout + proc.stderr).splitlines():
        if "MuPDF error" not in line and line.strip():
            log("    " + line)
    ok = proc.returncode in (0, 2) if step == "download" else proc.returncode == 0
    # download_all.py returns 2 when some dates failed (site unreachable): they are retried next run
    log(f"--- {step}: {'ok' if ok else 'FAILED'} (exit {proc.returncode}, {time.time() - t0:.0f}s)")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Daily update of brvm.db")
    ap.add_argument("--no-download", action="store_true", help="skip the download step")
    ap.add_argument("--notebook", action="store_true", help="also re-run brvm_database_showcase.ipynb")
    args = ap.parse_args(argv)

    LOGS.mkdir(exist_ok=True)
    start = dt.datetime.now()
    logfile = LOGS / f"daily_update_{start:%Y-%m-%d}.log"

    def log(msg: str) -> None:
        line = f"{dt.datetime.now():%H:%M:%S} {msg}"
        if sys.stdout is not None:  # None under pythonw.exe (scheduled task)
            print(line, flush=True)
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # one run at a time; a lock older than 3 hours is considered stale (crashed run)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 3 * 3600:
        log("another update is running (logs/daily_update.lock) - exiting")
        return 2
    LOCK.write_text(str(os.getpid()))
    try:
        before = db_state()
        log(f"=== daily update started - database: {before['bulletins']} bulletins, last {before['last']}")
        ok = True
        if not args.no_download:
            ok &= run("download", ["download_all.py"], log)
        ok &= run("extract", ["extract_boc.py"], log)
        ok &= run("qc report", ["extract_boc.py", "--qc"], log)
        if args.notebook and ok:
            ok &= run("notebook", ["-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
                                   "--ExecutePreprocessor.timeout=900", "brvm_database_showcase.ipynb"], log)
        after = db_state()
        new = after["bulletins"] - before["bulletins"]
        with sqlite3.connect(DB) as con:
            bad = con.execute("SELECT date, status FROM documents WHERE status != 'ok' AND date > ?",
                              (before["last"] or "",)).fetchall()
        summary = (f"{start:%Y-%m-%d %H:%M} {'OK  ' if ok else 'FAIL'} new bulletins: {new:+d}, "
                   f"last: {after['last']}, total: {after['bulletins']}"
                   + (f", not fully extracted: {bad}" if bad else "")
                   + f", {(dt.datetime.now() - start).seconds}s")
        log("=== " + summary)
        with open(LOGS / "daily_update.log", "a", encoding="utf-8") as f:
            f.write(summary + "\n")
        return 0 if ok else 1
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
