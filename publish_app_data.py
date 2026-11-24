"""Build the slim database used by the public web app and publish it as a GitHub release asset.

Usage:
    python publish_app_data.py --dry-run     # build brvm_app.db + brvm_app.db.zip only
    python publish_app_data.py               # build and upload (needs BRVM_GITHUB_TOKEN)

Settings (environment variables of your Windows user, never stored in the repo):
    BRVM_GITHUB_TOKEN   fine-grained token with "Contents: read and write" on the app repository
    BRVM_GITHUB_REPO    "owner/repo" (default: taken from `git remote get-url origin`)

The zip is uploaded to the release tagged `data-latest`; the app downloads
https://github.com/<owner>/<repo>/releases/download/data-latest/brvm_app.db.zip (see WEBAPP.md).
Exit code: 0 ok / skipped (no token), 1 error.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "brvm.db"
OUT_DB = ROOT / "brvm_app.db"
OUT_ZIP = ROOT / "brvm_app.db.zip"
ASSET = "brvm_app.db.zip"
TAG = "data-latest"
API = "https://api.github.com"


def build() -> dict:
    """Consistent copy of brvm.db, pruned of what the web app does not use."""
    OUT_DB.unlink(missing_ok=True)
    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(OUT_DB)
    with dst:
        src.backup(dst)
    src.close()
    with dst:
        dst.executescript("""
            DROP TABLE IF EXISTS extraction_log;
            DROP TABLE IF EXISTS table_totals;
            -- meetings: materialise the view, drop the 64k daily mentions
            CREATE TABLE gm AS SELECT * FROM general_meetings;
            DROP VIEW general_meetings;
            DROP TABLE meeting_mentions;
            ALTER TABLE gm RENAME TO general_meetings;
            -- order book: last 90 sessions only
            DELETE FROM order_book WHERE date < (
                SELECT MIN(date) FROM (SELECT DISTINCT date FROM order_book ORDER BY date DESC LIMIT 90));
            -- fund NAVs: one row per fund and NAV date
            DELETE FROM fund_navs WHERE nav IS NULL OR nav_date IS NULL;
            DELETE FROM fund_navs WHERE rowid NOT IN (SELECT MAX(rowid) FROM fund_navs GROUP BY fund_name, nav_date);
            -- documents: only what the app needs
            CREATE TABLE docs AS SELECT date, status FROM documents;
            DROP TABLE documents;
            ALTER TABLE docs RENAME TO documents;
            CREATE INDEX ix_docs_date ON documents(date);
        """)
    dst.execute("VACUUM")
    check = dst.execute("PRAGMA integrity_check").fetchone()[0]
    last, n = dst.execute("SELECT MAX(date), COUNT(*) FROM documents").fetchone()
    probe = dst.execute("SELECT COUNT(*) FROM equity_quotes_adjusted WHERE date = ?", (last,)).fetchone()[0]
    links = dst.execute("SELECT COUNT(*) FROM bulletins WHERE url IS NOT NULL").fetchone()[0]  # BOC links of the app
    dst.close()
    if check != "ok" or not probe or not links:
        raise RuntimeError(f"slim database check failed: integrity={check}, adjusted rows on {last}={probe}, "
                           f"bulletin links={links}")
    OUT_ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(OUT_DB, "brvm_app.db")
    return {"last": last, "bulletins": n, "db_mb": OUT_DB.stat().st_size / 1e6, "zip_mb": OUT_ZIP.stat().st_size / 1e6}


def repo_name() -> str:
    r = os.environ.get("BRVM_GITHUB_REPO")
    if r:
        return r
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", url)
    if not m:
        raise RuntimeError("set BRVM_GITHUB_REPO=owner/repo or add a GitHub 'origin' remote")
    return m[1]


def upload(info: dict, token: str, repo: str) -> str:
    import requests

    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28"})
    r = s.get(f"{API}/repos/{repo}/releases/tags/{TAG}", timeout=30)
    body = f"BRVM data for the web app. Last bulletin: {info['last']} ({info['bulletins']} bulletins)."
    if r.status_code == 404:
        r = s.post(f"{API}/repos/{repo}/releases", json={"tag_name": TAG, "name": "BRVM data (latest)", "body": body},
                   timeout=30)
    r.raise_for_status()
    rel = r.json()
    # upload under a temporary name, then swap: the public file is never missing for more than an instant
    tmp_name = f"{ASSET}.new"
    for a in rel.get("assets", []):
        if a["name"] == tmp_name:
            s.delete(f"{API}/repos/{repo}/releases/assets/{a['id']}", timeout=30).raise_for_status()
    with open(OUT_ZIP, "rb") as f:
        up = s.post(f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets", params={"name": tmp_name},
                    headers={"Content-Type": "application/zip"}, data=f, timeout=600)
    up.raise_for_status()
    new_id = up.json()["id"]
    for a in rel.get("assets", []):
        if a["name"] == ASSET:
            s.delete(f"{API}/repos/{repo}/releases/assets/{a['id']}", timeout=30).raise_for_status()
    s.patch(f"{API}/repos/{repo}/releases/assets/{new_id}", json={"name": ASSET}, timeout=30).raise_for_status()
    s.patch(f"{API}/repos/{repo}/releases/{rel['id']}", json={"body": body}, timeout=30).raise_for_status()
    return f"https://github.com/{repo}/releases/download/{TAG}/{ASSET}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build and publish the web app database")
    ap.add_argument("--dry-run", action="store_true", help="build only, do not upload")
    args = ap.parse_args(argv)
    token = os.environ.get("BRVM_GITHUB_TOKEN")
    if not args.dry_run and not token:
        print("publish skipped: BRVM_GITHUB_TOKEN is not set (see WEBAPP.md, deployment)")
        return 0
    info = build()
    print(f"built {OUT_ZIP.name}: last bulletin {info['last']}, {info['db_mb']:.0f} MB -> {info['zip_mb']:.0f} MB zipped")
    if args.dry_run:
        return 0
    try:
        url = upload(info, token, repo_name())
    except Exception as e:
        print(f"upload failed: {e}")
        return 1
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs" / "web_published.txt").write_text(info["last"])  # read by daily_update.py
    print(f"published: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
