# Deploy: Baogee Textile (HR & Payroll + Biometric Sync)

Server `169.58.20.21`, user `maqmalak`, bench `/home/maqmalak/frappe-bench` (shared with the other sites already there).

One Frappe site serves everything. Desk and the React apps share the login, the data and the domain:

| URL | What |
|---|---|
| `https://<site>/app` | ERPNext desk |
| `https://<site>/baogee/home` | HR & Payroll (React, `frontend/`) |
| `https://<site>/biometric` | Biometric Sync console (React, in biometric_sync) |
| `https://<site>/checkin-display?kiosk=1` | gate display for the wall TV |

| File | Where it runs | What it does |
|---|---|---|
| `export-data.sh` | development machine | Backs up the `baogee` site with files into `~/baogee-data-<date>` and prints the copy command. |
| `install-production.sh` | production server (Ubuntu 24.04) | Installs everything, builds the React apps, restores the data, and sets up nginx, supervisor, SSL, the firewall and the nightly backup. |
| `set-passwords.sh` | production server | Gives every user one password (asked when run, never stored). |
| `backup.sh` | production server (cron) | Nightly backup with files, kept 14 days; copies off the server when `REMOTE` is set. |
| `patches/biometric_sync-local.patch` | used by the installer | The local changes to biometric_sync (upstream commit `78deacc`): the Biometric Sync console, its API, the Check-in Display and the extra settings. |

## Steps

1. **Commit and push the app** so the server can fetch it: `git -C apps/baogee_textile push origin main`.
   If the repository is private, give the server read access (a deploy key, or `APP_REPO=https://<token>@github.com/...`).
2. **Refresh the biometric_sync patch** if biometric_sync changed since (run from the bench):
   ```bash
   cd apps/biometric_sync && IDX=$(mktemp) && cp .git/index $IDX && \
   GIT_INDEX_FILE=$IDX git add -A -- . ':!frontend/node_modules' ':!biometric_sync/public/console' ':!**/__pycache__' && \
   GIT_INDEX_FILE=$IDX git diff --cached --binary 78deacc > ../baogee_textile/deploy/patches/biometric_sync-local.patch; rm -f $IDX
   ```
3. **DNS:** `<site>` → `169.58.20.21` (Cloudflare proxy is fine; set it to *DNS only* if the SSL step fails).
4. **Export the data** (development machine): `bash apps/baogee_textile/deploy/export-data.sh`
5. **Copy to the server** with the `rsync` command it prints, and copy this `deploy` folder too (or clone the repo).
6. **Install** (on the server, as the bench user with sudo, not root):
   ```bash
   RESTORE_DIR=~/baogee-data-<date> SITE=<domain> LETSENCRYPT_EMAIL=you@yourdomain.com bash install-production.sh
   ```
7. **Switch the machine reading over.** Only one place may read the gate machines (a ZKTeco machine takes one
   connection at a time). Turn automatic sync off on the development site once production reads them
   (Biometric Sync → Settings → Sync & schedule → Automatic sync), and check that the production server can reach
   the machines (the installer tests each one; open the factory router's port forwarding to the server's IP if not).
8. **Delete the data folder** from both machines; it holds the site's encryption key and stored secrets.

Options (environment variables): `SITE`, `EXTRA_DOMAINS`, `APT_UPGRADE=0` (server already in use), `SSL=0`, `BENCH_NAME`,
`ENABLE_UFW=0`, and the pinned versions (`FRAPPE_BRANCH`, `ERPNEXT_BRANCH`, `HRMS_BRANCH`/`HRMS_REF`, `BIOMETRIC_REF`).
The script can be re-run; it pulls the latest pushed baogee_textile and rebuilds the React apps every time.

Passwords (MariaDB root, and this site's BAOGEE_ADMIN_PASSWORD) are generated on the server into `~/.frappe-install-secrets`.

## Updating later

```bash
cd ~/frappe-bench/apps/baogee_textile/deploy && APT_UPGRADE=0 SITE=<domain> LETSENCRYPT_EMAIL=… bash install-production.sh
```

or by hand: `git -C apps/baogee_textile pull`, `cd apps/baogee_textile/frontend && npm ci && npm run build`,
`bench --site <domain> migrate`, `bench build --app baogee_textile`, `sudo supervisorctl restart all`.

## Help centre videos

The manuals and the PDF guides are in git. The videos are not: copy them to the server once, and again after they
are re-recorded:

```bash
rsync -av --mkpath apps/baogee_textile/baogee_textile/public/downloads/videos/ \
  maqmalak@169.58.20.21:~/frappe-bench/apps/baogee_textile/baogee_textile/public/downloads/videos/
```
