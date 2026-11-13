# Help centre: guides and videos

The React app's **Help & Guides** page (`/help`, `/help/guides`) shows:

| What | Where | In git |
|---|---|---|
| User manuals per role | `baogee_textile/manuals/*.md` (front matter: title, roles, order) | yes |
| A4 PDF guides with screenshots | `baogee_textile/public/help/<slug>.pdf` | yes |
| Demo videos (MP4) | `baogee_textile/public/downloads/videos/` | no — copy to each server by hand |

The list of guides and videos, their stage, roles and the manuals they appear in is `GUIDES` in `baogee_textile/help.py`.
A guide or video is listed only when its file exists on the server.

## Rebuild

Both scripts use the demo data (`bench --site baogee execute baogee_textile.demo.loans_demo.run`), the React dev
server (`BASE`, default http://baogee.localhost:5182), the light theme, and never save anything.

```bash
cd apps/baogee_textile
# PDF guides (all, or by slug)
DEMO_PWD=… NODE_PATH=../crm/node_modules node scripts/help/build_guides.js [organisation …]
# videos (all, or by number); the MP4 step needs a Python with imageio-ffmpeg
DEMO_PWD=… NODE_PATH=../crm/node_modules node scripts/help/record_videos.js [01 07 …]
```

`NODE_PATH` points at any app's `node_modules` that has `playwright-core`; Chrome is `/usr/bin/google-chrome`.
The sync-tool screens need the Biometric Sync tool on http://127.0.0.1:8766 (`SYNC` to change).
