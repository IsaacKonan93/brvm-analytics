# Updating the database every day

BRVM publishes the Bulletin Officiel de la Cote (BOC) on the evening of each trading day, around **18:15 GMT**. Abidjan time is GMT, the same as this PC. One command brings `brvm.db` up to date:

```powershell
& "$env:USERPROFILE\Documents\BRVM\daily_update.cmd"
```

## What it does

[daily_update.py](daily_update.py) runs these steps with the project's `.env` Python. It is launched by the scheduled task (windowless), or by [daily_update.cmd](daily_update.cmd) when you run it by hand.

| Step | Command | What happens |
|---|---|---|
| 1. Download | `download_all.py` | Fetches the PDFs of all weekdays not yet in `boc/`. Dates already confirmed as "no bulletin" are skipped, except the last 5 days, which are always re-checked in case a bulletin is published late. It also looks up again the brvm.org address of any bulletin recorded without one; the web app links to it. |
| 2. Share counts | `fetch_shares.py` | Once a day, reads the number of shares of every listed stock on brvm.org's *Capitalisations* page and adds the day's snapshot to `boc/shares_outstanding.csv`. The web app's *Market structure* page uses it. **Not blocking:** if brvm.org is unreachable, the run goes on and the next run tries again. |
| 3. Extract | `extract_boc.py` | Loads every new or changed PDF into `brvm.db`, then refreshes the derived tables: `bulletins` (the brvm.org links), `shares_outstanding` (the share counts), `securities`, the split adjustments (`corporate_actions`, `equity_quotes_adjusted`…). Nothing is redone for bulletins already extracted. |
| 4. QC report | `extract_boc.py --qc` | Rewrites [qc_report.md](qc_report.md). |
| 5. Backup | `backup_db.py --if-older 7` | Once a week, a verified compressed copy of `brvm.db` (see [Backup](#backup)). |
| 6. Publish web data | `publish_app_data.py` | When there is a new bulletin, rebuilds the slim database of the web app and uploads it to GitHub, where the online app picks it up (see [WEBAPP.md](WEBAPP.md#daily-data-updates-online)). Skipped until `BRVM_GITHUB_TOKEN` is set. |
| 7. *(optional)* Notebook | `--notebook` | Re-runs [brvm_database_showcase.ipynb](brvm_database_showcase.ipynb) so its charts include the new day. |

Properties:
* **Incremental and safe to repeat.** Running it twice, or on a holiday, does nothing harmful. A normal day takes about 10 seconds.
* **Catches up by itself.** If the PC was off for a week, the next run downloads and extracts all the missing days.
* **One run at a time.** A lock file, `logs/daily_update.lock`, prevents overlapping runs. A lock older than 3 hours is ignored.
* **Logs:**
  * `logs/daily_update_YYYY-MM-DD.log` has the full output of the day's run;
  * `logs/daily_update.log` has one summary line per run, e.g. `2026-11-18 20:00 OK   new bulletins: +1, last: 2026-11-18, total: 2526, 11s`.
* **Exit code:** `0` success, `1` a step failed, `2` another run is in progress.

Options:

```powershell
.\.env\Scripts\python.exe daily_update.py --notebook      # also refresh the notebook's charts
.\.env\Scripts\python.exe daily_update.py --no-download   # only extract PDFs already in boc/
```

## Automatic run with Windows Task Scheduler

The task **"BRVM daily update"** is registered on this PC (since 2026-11-18, triggers added on 2026-11-23). It runs at three moments:

| Trigger | Why |
|---|---|
| Monday–Friday **20:00** | Picks up the evening bulletin (published around 18:15). |
| Monday–Friday **09:00** | Catches up if the PC was off or asleep at 20:00. |
| **At logon** (+5 min) | Catches up as soon as you start the PC after days away. |

Since the update only fetches what is missing, extra runs cost a few seconds and do nothing else. Two more settings matter:
* `-StartWhenAvailable`: if the PC was off or asleep at a trigger time, the task runs as soon as it is back on.
* **No window:** the task runs `pythonw.exe daily_update.py` and each step starts without a console. A visible console window can be closed by mistake, which kills the run. This happened on 2026-11-20 and 2026-11-23, with exit code `0xC000013A`.

The task only runs while your Windows session is open. To recreate it (e.g. on another PC), run this once in PowerShell, as your user, with no admin rights needed:

```powershell
$dir      = "$env:USERPROFILE\Documents\BRVM"
$action   = New-ScheduledTaskAction -Execute "$dir\.env\Scripts\pythonw.exe" -Argument "daily_update.py" -WorkingDirectory $dir
$days     = "Monday","Tuesday","Wednesday","Thursday","Friday"
$logon    = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"; $logon.Delay = "PT5M"
$triggers = @((New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At 20:00),
              (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At 09:00), $logon)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "BRVM daily update" -Action $action -Trigger $triggers -Settings $settings `
            -Description "Download the new BRVM bulletins and load them into brvm.db (see UPDATE.md)"
```

Useful commands:

```powershell
Start-ScheduledTask -TaskName "BRVM daily update"                     # run it now
Get-ScheduledTaskInfo -TaskName "BRVM daily update"                   # last run time and result (0 = OK)
Get-Content "$env:USERPROFILE\Documents\BRVM\logs\daily_update.log" -Tail 10   # recent runs
Disable-ScheduledTask -TaskName "BRVM daily update"                   # pause
Unregister-ScheduledTask -TaskName "BRVM daily update" -Confirm:$false  # remove
```

You can also manage it in the *Task Scheduler* app (Win + R → `taskschd.msc`).

Why 20:00: the bulletin is usually online by about 18:30. If it is late, the next day's run picks it up anyway, since the last 5 days are always re-checked.

## Checking that it works

* `logs/daily_update.log`: one `OK` line per weekday, with `last:` equal to the previous trading day or today.
* [qc_report.md](qc_report.md): new bulletins should be `ok`. A `partial` or `error` bulletin is listed under *Documents not fully extracted*, with the reason.
* From Python: `SELECT MAX(date) FROM documents` gives the latest bulletin in the database.

## Backup

The daily update runs [backup_db.py](backup_db.py) and makes a backup once a week, when the newest one is more than 7 days old.
* **Where:** `Documents\BRVM_backups\`, next to the project folder and outside it. This protects against a corrupted database or a mistake, not against losing the PC.
* **What:** `brvm_YYYY-MM-DD_HHMM.zip`, about 60 MB each, containing `brvm.db` and a `BACKUP_INFO.txt` that gives the last bulletin included.
* **How:** the copy is taken with SQLite's online backup API, so it is consistent even if the app or the notebook is reading the database. It is then checked (`PRAGMA integrity_check`) before being compressed.
* **Rotation:** the last 4 backups are kept, about 1 month.

```powershell
.\.env\Scripts\python.exe backup_db.py            # backup now
.\.env\Scripts\python.exe backup_db.py --list     # list backups
.\.env\Scripts\python.exe backup_db.py --dest X:\BRVM --keep 8   # other folder, keep 8
```

**To restore:**
1. Make sure no update is running (`logs\daily_update.lock` absent).
2. Rename the damaged `brvm.db`.
3. Unzip `brvm.db` from the latest backup into the project folder.
4. Run `.\daily_update.cmd`. It re-extracts the bulletins published since the backup, so nothing is lost.

If all backups are lost, `brvm.db` can be rebuilt entirely from the PDFs in `boc/` with `python extract_boc.py --reprocess` (about 4 minutes). The PDFs themselves can be downloaded again with `python download_all.py`.

The **code** is versioned with git in the project folder (`git log` shows the history). The data (`boc/`, `brvm.db`) is excluded from git, see [.gitignore](.gitignore).

## When something goes wrong

| Symptom | Cause / action |
|---|---|
| `FAIL` in `daily_update.log` | Open `logs/daily_update_<date>.log` to see which step failed. |
| `download failed` for recent dates | brvm.org was unreachable. These dates are retried at the next run, so there is nothing to do. |
| `download failed` for 2018-12-06 and 2018-12-07 | Broken links on BRVM's side (see [SITE_NOTES.md](SITE_NOTES.md#broken-links)). They are retried every run, which costs a few seconds. |
| `no BOC found` for today | Not published yet (run before ~18:30), or a market holiday. It is re-checked for 5 days. |
| New bulletins `partial`, or `header anchors not found` in the QC report | BRVM changed its layout. Follow [EXTRACTION.md → Maintenance](EXTRACTION.md#maintenance-when-brvm-changes-its-layout), then run `python extract_boc.py` (after bumping `PARSER_VERSION`, all PDFs are re-extracted). |
| `another update is running` | A run is in progress, or one crashed less than 3 hours ago. Delete `logs/daily_update.lock` if no run is active. |
| `LastTaskResult` = `3221225786` (`0xC000013A`), day log ends in the middle of a step | The run was killed, e.g. its console window was closed. The task now runs windowless (`pythonw.exe`). If it happens again, delete `logs/daily_update.lock` and start the task again; the next run completes the work anyway. |
| Task never runs | Check `Get-ScheduledTaskInfo` (LastTaskResult). The task only runs while your Windows session is open. |
| `database is locked` | `brvm.db` was open for writing in another program (e.g. a DB browser with uncommitted changes). Close it and re-run. Reading the database from the notebook or Excel while it updates is fine. |
