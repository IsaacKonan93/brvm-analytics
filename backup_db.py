"""Backup of brvm.db: consistent copy (SQLite online backup API), integrity check, zip, rotation.

Usage:
    python backup_db.py                 # backup now to the default folder, keep the last 4
    python backup_db.py --if-older 7    # only if the newest backup is older than 7 days (used by daily_update.py)
    python backup_db.py --dest D:\\backups --keep 8
    python backup_db.py --list

Default folder: C:\\Users\\<you>\\Documents\\BRVM_backups (outside the project folder).
Restore: unzip the latest brvm_YYYY-MM-DD.zip and put brvm.db back in the project folder (see UPDATE.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "brvm.db"
DEFAULT_DEST = ROOT.parent / "BRVM_backups"


def backups(dest: Path) -> list[Path]:
    return sorted(dest.glob("brvm_*.zip"))


def newest_age_days(dest: Path) -> float | None:
    b = backups(dest)
    if not b:
        return None
    return (dt.datetime.now().timestamp() - b[-1].stat().st_mtime) / 86400


def make_backup(dest: Path, keep: int) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    target = dest / f"brvm_{stamp}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "brvm.db"
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(copy)
        with dst:
            src.backup(dst)  # consistent snapshot, safe while other programs read the database
        src.close()
        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        last = dst.execute("SELECT MAX(date), COUNT(*) FROM documents").fetchone()
        dst.close()
        if check != "ok":
            raise RuntimeError(f"integrity check of the copy failed: {check}")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(copy, "brvm.db")
            z.writestr("BACKUP_INFO.txt", f"brvm.db backup {stamp}\nlast bulletin: {last[0]}\nbulletins: {last[1]}\n"
                                          f"integrity_check: {check}\n")
    for old in backups(dest)[:-keep]:
        old.unlink()
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup brvm.db")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=f"backup folder (default: {DEFAULT_DEST})")
    ap.add_argument("--keep", type=int, default=4, help="number of backups to keep (default: 4)")
    ap.add_argument("--if-older", type=float, metavar="DAYS", help="only back up if the newest backup is older")
    ap.add_argument("--list", action="store_true", help="list existing backups")
    args = ap.parse_args(argv)

    if args.list:
        for b in backups(args.dest):
            print(f"{b.name}  {b.stat().st_size / 1e6:,.0f} MB")
        return 0
    if not DB.exists():
        print(f"{DB} not found")
        return 1
    age = newest_age_days(args.dest)
    if args.if_older is not None and age is not None and age < args.if_older:
        print(f"backup skipped: newest backup is {age:.1f} days old (< {args.if_older})")
        return 0
    target = make_backup(args.dest, args.keep)
    print(f"backup written: {target} ({target.stat().st_size / 1e6:,.0f} MB), {len(backups(args.dest))} kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
