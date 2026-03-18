# ICT Trading Bot (Vercel UI + Render Backend + Render Worker)

## PWA (Add to Home Screen)
- UI now includes `manifest.json` and `service-worker.js`.
- When you open the site on mobile, use “Add to Home Screen”.
- Cached snapshot data is shown immediately on open.

### Replace Logo & Icons
Replace these files with your real logo:
- `frontend/logo.svg` (header logo)
- `frontend/icons/icon-192.png`
- `frontend/icons/icon-512.png`

If you want me to use your provided logo image, send it as a file (PNG/SVG) and I will wire it in.

## Backend API (Render Web Service)
1. Push this repo to GitHub.
2. In Render, create a **Web Service** and connect the repo.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn backend.app:app`

This service provides `/api/snapshot` and `/api/scan_all` for the UI.

## Telegram Worker 24/7 (Render Background Worker)
1. In Render, create a **Background Worker** with the same repo.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. Set environment variables:
   - `TELEGRAM_ENABLED=true`
   - `TELEGRAM_BOT_TOKEN=...`
   - `TELEGRAM_CHAT_ID=...`
   - Optional: `TELEGRAM_DEDUP_TTL_SECONDS=3600`

The worker runs continuously and sends Telegram alerts. Duplicate signals are deduplicated by key for the TTL.

## Frontend (Vercel)
1. Create a new Vercel project.
2. Set **Root Directory** to `frontend`.
3. Build Command: leave empty (static)
4. Output Directory: `.`
5. Deploy.

## Connect UI to Backend
1. Open your Vercel UI.
2. Click **API** in the top bar.
3. Enter your Render URL (e.g. `https://your-app.onrender.com`) and click **Save**.

## Local Run (optional)
Backend:
```powershell
pip install -r requirements.txt
python backend\app.py
```

Worker:
```powershell
python main.py
```

Frontend:
Open `frontend\index.html` in a browser or serve as static files.
